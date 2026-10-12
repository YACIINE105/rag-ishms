"""Install locust separately; run against an indexed test project."""

import json
import os
import random
from pathlib import Path

from locust import HttpUser, between, task

CASES = json.loads(Path("eval/golden_set.json").read_text())


class RAGUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        if os.environ.get("RAG_API_KEY"):
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
