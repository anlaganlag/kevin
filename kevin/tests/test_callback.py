import hashlib
import hmac
import json
from unittest.mock import patch, MagicMock

import pytest

from kevin.callback import CallbackClient


class TestCallbackClient:
    def test_sign_body(self):
        client = CallbackClient(
            callback_url="https://example.com/callback",
            callback_secret="test-secret",
        )
        body = '{"run_id": "abc"}'
        sig = client._sign(body)
        expected = hmac.new(b"test-secret", body.encode(), hashlib.sha256).hexdigest()
        assert sig == expected

    @patch("kevin.callback.urllib.request.urlopen")
    def test_report_status_sends_hmac(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CallbackClient(
            callback_url="https://example.com/callback",
            callback_secret="test-secret",
        )
        client.report_status(run_id="abc-123", status="running")

        call_args = mock_urlopen.call_args
        req = call_args[0][0]
        assert req.get_header("X-signature") is not None
        assert req.get_header("Content-type") == "application/json"

        sent_body = json.loads(req.data.decode())
        assert sent_body["run_id"] == "abc-123"
        assert sent_body["status"] == "running"

    def test_noop_client_does_nothing(self):
        client = CallbackClient(callback_url="", callback_secret="")
        # Should not raise
        client.report_status(run_id="abc", status="running")

    @patch("kevin.callback.urllib.request.urlopen")
    def test_report_with_result(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.read.return_value = b'{"ok": true}'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        client = CallbackClient(
            callback_url="https://example.com/callback",
            callback_secret="secret",
        )
        client.report_status(
            run_id="abc",
            status="completed",
            result={"pr_url": "https://github.com/pr/1"},
        )

        req = mock_urlopen.call_args[0][0]
        sent = json.loads(req.data.decode())
        assert sent["status"] == "completed"
        assert sent["result"]["pr_url"] == "https://github.com/pr/1"
