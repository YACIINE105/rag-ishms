"""Install locust separately; run against an indexed test project."""

import json
import os
import random
from itertools import cycle
from pathlib import Path

from locust import HttpUser, between, task

random.seed(20261015)

CASES = [
    case
    for case in json.loads(
        Path(os.environ.get("LOADTEST_DATASET", "eval/golden_set.json")).read_text()
    )
    if not case.get("expect_no_answer", False)
]
KEYS = (
    cycle(json.loads(Path(os.environ["LOADTEST_KEYS_FILE"]).read_text()))
    if os.environ.get("LOADTEST_KEYS_FILE")
    else None
)


class RAGUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        if KEYS:
            self.client.headers["X-API-Key"] = next(KEYS)
        elif os.environ.get("RAG_API_KEY"):
            self.client.headers["X-API-Key"] = os.environ["RAG_API_KEY"]

    @task(10)
    def answer(self):
        case = random.choice(CASES)
        project = os.environ.get("LOADTEST_PROJECT_ID", str(case["project_id"]))
        with self.client.post(
            f"/api/v1/nlp/index/answer/{project}",
            json={"text": case["question"]},
            name="/index/answer/{project_id}",
            catch_response=True,
            timeout=180,
        ) as response:
            if response.status_code != 200:
                response.failure(f"HTTP {response.status_code}")
                return
            try:
                body = response.json()
                if not body.get("answer") or not body.get("sources"):
                    response.failure(
                        "Missing answer or sources for answerable benchmark question"
                    )
            except ValueError:
                response.failure("Invalid JSON")

    @task
    def health(self):
        self.client.get("/health")
