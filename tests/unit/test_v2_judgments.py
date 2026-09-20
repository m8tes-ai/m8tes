"""Wire contracts for advisory judgments; these tests never call TypeSafe."""

import json

import pytest
import responses

from m8tes import M8tes
from m8tes._exceptions import ValidationError

BASE = "https://api.test/api/v2"
RESULT = {
    "id": "judgment_test",
    "model": "jev-1.13.0",
    "answers": {"complete": {"type": "noul", "noul": 0.2}},
    "usage": {"input_tokens": 321, "output_tokens": 20},
    "latency_ms": 123,
    "cost_usd": 0.000013482,
    "rubric_version": None,
    "coverage": None,
}


@responses.activate
@pytest.mark.parametrize("state", ["Tests failed", {"tests": "failed"}, ["Tests failed"]])
def test_decide_preserves_state_questions_and_user_scope(state):
    responses.post(f"{BASE}/judgments", json=RESULT)
    questions = {"complete": {"type": "noul", "instructions": "Did the tests pass?"}}
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.judgments.create(
            mode="decide", state=state, questions=questions, user_id="customer_42"
        )
    assert json.loads(responses.calls[0].request.body) == {
        "mode": "decide",
        "state": state,
        "questions": questions,
        "user_id": "customer_42",
    }
    assert result.id == "judgment_test"
    assert result.answers == RESULT["answers"]
    assert result.usage == RESULT["usage"]
    assert result.cost_usd == RESULT["cost_usd"]
    assert result.latency_ms == 123
    assert result.coverage is None
    assert result.rubric_version is None


@responses.activate
def test_verify_preserves_claim_evidence_links_and_coverage():
    claims = [{"id": "c1", "text": "Tests passed", "evidence_ids": ["e1"]}]
    evidence = [{"id": "e1", "text": "Tests failed"}]
    answer = {
        "type": "choice",
        "choice": "contradicted",
        "confidence": 0.98,
        "probabilities": {"supported": 0.01, "contradicted": 0.98, "insufficient_evidence": 0.01},
    }
    coverage = {"claim_ids": ["c1"], "evidence_ids": ["e1"], "evidence_origin": "caller_provided"}
    responses.post(
        f"{BASE}/judgments",
        json={
            **RESULT,
            "answers": {"c1": answer},
            "coverage": coverage,
            "rubric_version": "verify-v1",
        },
    )
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.judgments.create(mode="verify", claims=claims, evidence=evidence)
    assert json.loads(responses.calls[0].request.body) == {
        "mode": "verify",
        "claims": claims,
        "evidence": evidence,
    }
    assert result.answers["c1"] == answer
    assert result.coverage == coverage
    assert result.rubric_version == "verify-v1"


@responses.activate
def test_judgment_validation_error_is_not_retried_or_treated_as_a_judgment():
    responses.post(
        f"{BASE}/judgments",
        status=422,
        json={
            "error": {
                "message": "Unknown evidence id",
                "type": "validation_error",
                "code": "invalid_request",
                "request_id": "req_test",
            }
        },
    )
    with M8tes(api_key="m8_test", base_url=BASE) as client, pytest.raises(ValidationError):
        client.judgments.create(
            mode="verify",
            claims=[{"id": "c1", "text": "Tests passed", "evidence_ids": ["missing"]}],
            evidence=[],
        )
    assert len(responses.calls) == 1


@responses.activate
def test_idempotency_key_is_header_and_run_attribution_is_body():
    responses.post(f"{BASE}/judgments", json=RESULT)
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        client.judgments.create(
            mode="verify", claims=[], evidence=[], run_id=42, idempotency_key="report-v1"
        )
    request = responses.calls[0].request
    assert request.headers["Idempotency-Key"] == "report-v1"
    assert json.loads(request.body) == {
        "mode": "verify",
        "claims": [],
        "evidence": [],
        "run_id": 42,
    }


@responses.activate
@pytest.mark.parametrize("key,expected_calls", [(None, 1), ("report-v1", 2)])
def test_provider_failure_retries_only_with_idempotency_key(key, expected_calls, monkeypatch):
    from m8tes._exceptions import APIError

    monkeypatch.setattr("m8tes._http.time.sleep", lambda _: None)
    responses.post(f"{BASE}/judgments", status=503, json={"error": {"message": "Unavailable"}})
    responses.post(f"{BASE}/judgments", json=RESULT)
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        if key:
            assert (
                client.judgments.create(
                    mode="verify", claims=[], evidence=[], idempotency_key=key
                ).id
                == RESULT["id"]
            )
        else:
            with pytest.raises(APIError):
                client.judgments.create(mode="verify", claims=[], evidence=[])
    assert len(responses.calls) == expected_calls
    if key:
        assert {call.request.headers["Idempotency-Key"] for call in responses.calls} == {key}


@responses.activate
def test_get_saved_result_preserves_original_cost_and_user_scope():
    responses.get(f"{BASE}/judgments/judgment_test?user_id=customer%2F42", json=RESULT)
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        result = client.judgments.get("judgment_test", user_id="customer/42")
    assert result.id == RESULT["id"]
    assert result.cost_usd == RESULT["cost_usd"]
    assert len(responses.calls) == 1


@responses.activate
def test_source_reference_is_not_expanded_by_sdk():
    evidence = [{"id": "e1", "source": {"type": "document", "id": 123}}]
    responses.post(f"{BASE}/judgments", json=RESULT)
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        client.judgments.create(mode="verify", claims=[], evidence=evidence)
    assert json.loads(responses.calls[0].request.body)["evidence"] == evidence


@responses.activate
def test_pending_idempotent_attempt_is_not_retried():
    from m8tes._exceptions import ConflictError

    responses.post(
        f"{BASE}/judgments",
        status=409,
        json={"error": {"message": "Attempt is pending", "code": "judgment_in_progress"}},
    )
    with M8tes(api_key="m8_test", base_url=BASE) as client, pytest.raises(ConflictError):
        client.judgments.create(
            mode="verify", claims=[], evidence=[], idempotency_key="pending-attempt"
        )
    assert len(responses.calls) == 1


@responses.activate
def test_get_preserves_source_provenance_without_authenticating_it():
    coverage = {
        "claim_ids": ["c1"],
        "evidence_ids": ["e1"],
        "evidence_origin": "stored_sources",
        "provenance": [
            {
                "evidence_id": "e1",
                "origin": "stored_document",
                "source_id": 123,
                "content_sha256": "a" * 64,
                "independently_authenticated": False,
            }
        ],
    }
    responses.get(f"{BASE}/judgments/judgment_test", json={**RESULT, "coverage": coverage})
    with M8tes(api_key="m8_test", base_url=BASE) as client:
        assert client.judgments.get("judgment_test").coverage == coverage
