"""Tests for Webhooks.verify_signature() — HMAC-SHA256 webhook verification."""

import hashlib
import hmac

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
