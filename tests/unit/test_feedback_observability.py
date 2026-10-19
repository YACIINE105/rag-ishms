import json
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from utils import feedback, observability
from utils.feedback import AnswerReceipts


def test_receipts_prevent_cross_user_and_project_feedback():
    receipts = AnswerReceipts()
    receipts.remember("r1", 1, "alice")
    receipts.require("r1", 1, "alice")
    with pytest.raises(HTTPException):
        receipts.require("r1", 2, "alice")
    with pytest.raises(HTTPException):
        receipts.require("r1", 1, "bob")


def test_feedback_is_redacted_and_saved_even_if_export_fails(tmp_path, monkeypatch):
    client = MagicMock()
    client.create_score.side_effect = RuntimeError("offline")
    monkeypatch.setattr(feedback, "get_client", lambda: client)
    path = tmp_path / "feedback.jsonl"
    assert (
        feedback.save_feedback(path, "r1", 1, "alice", -1, "user@example.com")["status"]
        == "recorded"
    )
    record = json.loads(path.read_text())
    assert record["comment"] == "[REDACTED]"
    assert client.create_score.call_args.kwargs["trace_id"] == observability.trace_id(
        "r1"
    )


def test_span_start_failure_is_fail_open(monkeypatch):
    @contextmanager
    def failing(**kwargs):
        raise RuntimeError("unavailable")
        yield

    monkeypatch.setattr(
        observability,
        "get_client",
        lambda: SimpleNamespace(start_as_current_observation=failing),
    )
    with observability.span("test") as span:
        assert span is None
    with pytest.raises(ValueError):
        with observability.span("test"):
            raise ValueError("actual application error")


def test_recursive_export_mask():
    assert observability.mask({"input": ["user@example.com"], "count": 1}) == {
        "input": ["[REDACTED]"],
        "count": 1,
    }
