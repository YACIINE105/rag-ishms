"""Bounded answer receipts and append-only, redacted feedback for a single worker."""

import json
from collections import OrderedDict
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from fastapi import HTTPException

from utils.guardrails import redact_pii
from utils.observability import get_client, trace_id

_lock = Lock()


class AnswerReceipts:
    def __init__(self):
        self.records = OrderedDict()

    def remember(self, request_id, project_id, user_id):
        key = (request_id, project_id, user_id)
        self.records.pop(key, None)
        self.records[key] = True
        while len(self.records) > 1000:
            self.records.popitem(last=False)

    def require(self, request_id, project_id, user_id):
        if (request_id, project_id, user_id) not in self.records:
            raise HTTPException(
                404, "Answer receipt not found for this identity and project"
            )


def receipts(app):
    if not hasattr(app.state, "answer_receipts"):
        app.state.answer_receipts = AnswerReceipts()
    return app.state.answer_receipts


def save_feedback(path, request_id, project_id, user_id, score, comment):
    record = {
        "request_id": request_id,
        "project_id": project_id,
        "user_id": user_id,
        "score": score,
        "comment": redact_pii(comment),
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    path = Path(path)
    with _lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(record, ensure_ascii=False) + "\n")
        path.chmod(0o600)
    client = get_client()
    if client:
        # Local receipt is authoritative even if the optional exporter is unavailable.
        try:
            client.create_score(
                trace_id=trace_id(request_id),
                name="user_feedback",
                value=score,
                comment=record["comment"],
                data_type="NUMERIC",
            )
        except Exception:
            import logging

            logging.getLogger(__name__).warning("feedback.export.failed")
    return {"status": "recorded", "request_id": request_id}
