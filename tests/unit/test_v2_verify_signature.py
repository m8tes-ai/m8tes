"""Tests for Webhooks.verify_signature() — HMAC-SHA256 webhook verification."""

import hashlib
import hmac
import time

from m8tes._resources.webhooks import Webhooks


def _sign(body: str, secret: str, webhook_id: str, timestamp: str) -> str:
    """Generate a valid webhook signature for testing."""
    msg = f"{webhook_id}.{timestamp}.{body}"
    return "v1=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()


class TestVerifySignature:
    def test_valid_signature(self):
        """Valid HMAC-SHA256 signature passes verification."""
        body = '{"event":"run.completed","run_id":42}'
        secret = "whsec_test_secret_123"
        webhook_id = "msg_abc"
        timestamp = "1700000000"
        sig = _sign(body, secret, webhook_id, timestamp)

        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(body, headers, secret) is True

    def test_invalid_signature(self):
        """Wrong signature fails verification."""
        body = '{"event":"run.completed"}'
        secret = "whsec_real_secret"
        headers = {
            "Webhook-Id": "msg_1",
            "Webhook-Timestamp": "1700000000",
            "Webhook-Signature": (
                "v1=0000000000000000000000000000000000000000000000000000000000000000"
            ),
        }
        assert Webhooks.verify_signature(body, headers, secret) is False

    def test_wrong_secret(self):
        """Correct format but wrong secret fails verification."""
        body = '{"event":"run.completed"}'
        correct_secret = "whsec_correct"
        wrong_secret = "whsec_wrong"
        webhook_id = "msg_2"
        timestamp = "1700000000"
        sig = _sign(body, correct_secret, webhook_id, timestamp)

        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(body, headers, wrong_secret) is False

    def test_body_as_bytes(self):
        """Body can be provided as bytes."""
        body_str = '{"event":"run.completed"}'
        body_bytes = body_str.encode("utf-8")
        secret = "whsec_bytes_test"
        webhook_id = "msg_3"
        timestamp = "1700000000"
        sig = _sign(body_str, secret, webhook_id, timestamp)

        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(body_bytes, headers, secret) is True

    def test_tampered_body(self):
        """Signature for original body fails if body is tampered."""
        body = '{"event":"run.completed","run_id":42}'
        tampered = '{"event":"run.completed","run_id":99}'
        secret = "whsec_tamper"
        webhook_id = "msg_4"
        timestamp = "1700000000"
        sig = _sign(body, secret, webhook_id, timestamp)

        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(tampered, headers, secret) is False

    def test_missing_webhook_id(self):
        """Missing Webhook-Id header returns False (not KeyError)."""
        headers = {"Webhook-Timestamp": "1700000000", "Webhook-Signature": "v1=abc"}
        assert Webhooks.verify_signature("body", headers, "secret") is False

    def test_missing_timestamp(self):
        """Missing Webhook-Timestamp header returns False (not KeyError)."""
        headers = {"Webhook-Id": "msg_1", "Webhook-Signature": "v1=abc"}
        assert Webhooks.verify_signature("body", headers, "secret") is False

    def test_missing_signature(self):
        """Missing Webhook-Signature header returns False (not KeyError)."""
        headers = {"Webhook-Id": "msg_1", "Webhook-Timestamp": "1700000000"}
        assert Webhooks.verify_signature("body", headers, "secret") is False

    def test_empty_body(self):
        """Empty body still produces valid signature."""
        body = ""
        secret = "whsec_empty"
        webhook_id = "msg_5"
        timestamp = "1700000000"
        sig = _sign(body, secret, webhook_id, timestamp)

        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(body, headers, secret) is True

    def test_tolerance_rejects_stale_timestamp(self):
        """Payload with old timestamp rejected when tolerance set."""
        body = '{"event":"test"}'
        secret = "whsec_test_replay"
        webhook_id = "msg_replay"
        old_timestamp = str(int(time.time()) - 600)  # 10 min ago
        msg = f"{webhook_id}.{old_timestamp}.{body}"
        sig = "v1=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": old_timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(body, headers, secret, tolerance_seconds=300) is False

    def test_tolerance_accepts_fresh_timestamp(self):
        """Fresh timestamp passes when tolerance set."""
        body = '{"event":"test"}'
        secret = "whsec_test_fresh"
        webhook_id = "msg_fresh"
        timestamp = str(int(time.time()))
        msg = f"{webhook_id}.{timestamp}.{body}"
        sig = "v1=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(body, headers, secret, tolerance_seconds=300) is True

    def test_no_tolerance_accepts_old_timestamp(self):
        """Without tolerance param, old timestamps accepted (backward compat)."""
        body = '{"event":"test"}'
        secret = "whsec_compat"
        webhook_id = "msg_old"
        old_timestamp = "1000000000"  # Year 2001
        msg = f"{webhook_id}.{old_timestamp}.{body}"
        sig = "v1=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        headers = {
            "Webhook-Id": webhook_id,
            "Webhook-Timestamp": old_timestamp,
            "Webhook-Signature": sig,
        }
        assert Webhooks.verify_signature(body, headers, secret) is True

    def test_tolerance_rejects_non_numeric_timestamp(self):
        """Non-numeric timestamp rejected when tolerance set."""
        headers = {
            "Webhook-Id": "x",
            "Webhook-Timestamp": "not-a-number",
            "Webhook-Signature": "v1=abc",
        }
        assert Webhooks.verify_signature("body", headers, "secret", tolerance_seconds=300) is False

    def test_case_insensitive_headers(self):
        """Headers matched case-insensitively."""
        body = '{"event":"test"}'
        secret = "whsec_case"
        webhook_id = "msg_case"
        timestamp = str(int(time.time()))
        msg = f"{webhook_id}.{timestamp}.{body}"
        sig = "v1=" + hmac.new(secret.encode(), msg.encode(), hashlib.sha256).hexdigest()
        # Use uppercase header names
        headers = {
            "WEBHOOK-ID": webhook_id,
            "WEBHOOK-TIMESTAMP": timestamp,
            "WEBHOOK-SIGNATURE": sig,
        }
        assert Webhooks.verify_signature(body, headers, secret) is True
