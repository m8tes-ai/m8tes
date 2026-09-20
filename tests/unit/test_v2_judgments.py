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
