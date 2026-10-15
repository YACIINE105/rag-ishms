import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "evaluate_rag", Path(__file__).resolve().parents[2] / "scripts/evaluate_rag.py"
)
evaluation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(evaluation)


def test_dataset_validation(tmp_path):
    case = {
        "id": "case-1",
        "project_id": 1,
        "question": "Example question?",
        "expected_answer": "Example fact.",
        "reference_documents": ["example.txt"],
    }
    path = tmp_path / "cases.json"
    path.write_text(json.dumps([case, case]))
    with pytest.raises(ValueError, match="unique"):
        evaluation.load_cases(path, 1)
    case["reference_documents"] = []
    path.write_text(json.dumps([case]))
    with pytest.raises(ValueError, match="reference_documents"):
        evaluation.load_cases(path, 1)
    with pytest.raises(ValueError, match="20"):
        evaluation.load_cases(path)


@pytest.mark.parametrize("supported", ["false", 1, None])
def test_judge_claims_require_booleans(supported):
    with pytest.raises(ValueError, match="claim"):
        evaluation.score_verdict(
            {
                "claims": [{"text": "Claim", "supported": supported}],
                "answers_reference": True,
                "ragas_faithfulness": 0.75,
            }
        )


@pytest.mark.asyncio
async def test_supported_but_evasive_answers_fail():
    async def answer(case):
        return "Claim", [{"text": "Context"}]

    async def judge(*args):
        return {
            "claims": [{"text": "Claim", "supported": True}],
            "answers_reference": False,
            "ragas_faithfulness": 1.0,
        }

    report = await evaluation.evaluate(
        [{"id": "1", "question": "Question"}], answer, judge, 0.75
    )
    assert report["faithfulness"] == 1.0
    assert report["reference_accuracy"] == 0.0
    assert not report["passed"]


@pytest.mark.asyncio
async def test_zero_retrieval_fails_without_calling_judge():
    async def answer(case):
        return "No information", []

    async def judge(*args):
        pytest.fail("No-context answers must not reach the judge")

    report = await evaluation.evaluate(
        [{"id": "1", "question": "Question"}], answer, judge, 0.75
    )
    assert report["faithfulness"] == 0.0
    assert not report["passed"]


@pytest.mark.asyncio
async def test_threshold_boundary_and_malformed_judge():
    async def answer(case):
        return "Four claims", [{"text": "Context"}]

    async def judge(*args):
        return {
            "claims": [{"text": str(i), "supported": i < 3} for i in range(4)],
            "answers_reference": True,
            "ragas_faithfulness": 0.75,
        }

    cases = [{"id": "1", "question": "Question"}]
    report = await evaluation.evaluate(cases, answer, judge, 0.75)
    assert report["faithfulness"] == 0.75
    assert report["passed"]

    async def invalid_judge(*args):
        return {"claims": [], "answers_reference": True, "ragas_faithfulness": 0.75}

    with pytest.raises(ValueError):
        await evaluation.evaluate(cases, answer, invalid_judge, 0.75)
    with pytest.raises(ValueError):
        await evaluation.evaluate(cases, answer, judge, float("nan"))


@pytest.mark.asyncio
async def test_live_capture_uses_the_same_context_as_generation(monkeypatch):
    from contextlib import asynccontextmanager
    from types import SimpleNamespace

    document = SimpleNamespace(
        text="Exact context", metadata={"asset_name": "reference.txt"}
    )
    searches = []

    class Controller:
        def get_index_metadata(self):
            return {"embedding_model_id": "test-embed", "embedding_size": 2}

        def create_collection_name(self, project_id):
            return f"collection_test_embed_123_2_{project_id}"

        def __init__(self, **kwargs):
            pass

        async def search_vector_db_collection(self, **kwargs):
            searches.append(kwargs)
            return [document]

        async def answer_rag_query(self, **kwargs):
            docs = await self.search_vector_db_collection(**kwargs)
            return {"answer": docs[0].text}

    @asynccontextmanager
    async def lifespan(app):
        yield

    app = SimpleNamespace(
        **{
            name: None
            for name in (
                "generation_client",
                "embedding_client",
                "vector_db_client",
                "reranker_client",
                "template_parser",
            )
        }
    )
    main_module = SimpleNamespace(
        app=app,
        lifespan=lifespan,
        get_settings=lambda: SimpleNamespace(
            GENERATION_MODEL_ID="test-generation", GENERATION_PROVIDER="OPENAI"
        ),
    )
    original_import = evaluation.importlib.import_module

    def import_module(name):
        if name == "main":
            return main_module
        if name == "controllers.NLPController":
            return SimpleNamespace(NLPController=Controller)
        return original_import(name)

    class Client:
        closed = False

        async def close(self):
            self.closed = True

    client = Client()

    async def judge(case, answer, contexts):
        assert answer == contexts[0]["text"] == "Exact context"
        return {
            "claims": [{"text": answer, "supported": True}],
            "answers_reference": True,
            "ragas_faithfulness": 0.75,
        }

    monkeypatch.setattr(evaluation.importlib, "import_module", import_module)
    monkeypatch.setattr(evaluation, "make_judge", lambda: (client, judge))
    monkeypatch.setenv("RAG_EVAL_JUDGE_MODEL", "test-model")
    original_directory = Path.cwd()
    report = await evaluation.run_live(
        [
            {
                "id": "1",
                "project_id": 1,
                "question": "Question",
                "reference_documents": ["reference.txt"],
            }
        ],
        0.75,
    )
    assert report["passed"]
    assert report["index_metadata"]["embedding_model_id"] == "test-embed"
    assert report["collections"] == {"1": "collection_test_embed_123_2_1"}
    assert report["generation_model"] == "test-generation"
    assert report["generation_provider"] == "OPENAI"
    assert report["judge_model"] == "test-model"
    assert len(searches) == 1
    assert client.closed
    assert Path.cwd() == original_directory


def test_cli_provider_errors_do_not_expose_credentials(tmp_path, monkeypatch, capsys):
    import sys

    dataset = tmp_path / "dataset.json"
    dataset.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "project_id": 1,
                    "question": "Question",
                    "expected_answer": "Answer",
                    "reference_documents": ["reference.txt"],
                }
            ]
        )
    )
    report = tmp_path / "report.json"

    async def fail(*args):
        raise RuntimeError("https://user:private-password@example.invalid")

    monkeypatch.setattr(evaluation, "run_live", fail)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "evaluate_rag",
            "--dataset",
            str(dataset),
            "--minimum-cases",
            "1",
            "--report",
            str(report),
        ],
    )
    assert evaluation.main() == 2
    assert "private-password" not in capsys.readouterr().out
    assert json.loads(report.read_text()) == {
        "passed": False,
        "error_type": "RuntimeError",
    }


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1, True, "0.75"])
def test_invalid_ragas_scores_cannot_pass(score):
    with pytest.raises(ValueError, match="RAGAS"):
        evaluation.score_verdict(
            {
                "claims": [{"text": "Claim", "supported": True}],
                "answers_reference": True,
                "ragas_faithfulness": score,
            }
        )


@pytest.mark.asyncio
async def test_corpus_seed_preserves_article_metadata_and_never_resets():
    inserted = []

    class Controller:
        async def index_into_vector_db(self, **kwargs):
            inserted.append(kwargs)
            return True

    records = [
        {
            "article_number": 147,
            "citation": "Egyptian Civil Code, Article 147",
            "text_en": "Source text",
            "asset_name": "egyptian-civil-code.pdf",
            "source_pages": [16],
        }
    ]
    await evaluation.seed_corpus(Controller(), [{"project_id": 1}], records)
    assert len(inserted) == 1
    assert inserted[0]["do_reset"] is False
    assert inserted[0]["chunks_ids"] == [147]
    metadata = inserted[0]["chunks"][0].chunk_metadata
    assert metadata["page"] == 15
    assert metadata["article_number"] == 147


def test_committed_benchmark_is_grounded_in_the_source_snapshot():
    import hashlib

    root = Path(__file__).resolve().parents[2]
    cases = evaluation.load_cases(root / "eval/golden_set.json")
    records = json.loads((root / "eval/corpus/articles.json").read_text())
    articles = {row["article_number"]: row for row in records}
    digest = hashlib.sha256(
        (root / "eval/corpus/egyptian-civil-code.pdf").read_bytes()
    ).hexdigest()
    assert len(cases) == len(articles) == 20
    assert {case["language"] for case in cases} == {"ar", "en"}
    for case in cases:
        article = articles[case["article_number"]]
        assert case["reference_context"] == article["text_en"]
        assert case["source_sha256"] == article["source_sha256"] == digest
        assert case["source_pages"] == article["source_pages"]
    assert articles[148]["source_pages"] == [16, 17]


@pytest.mark.asyncio
async def test_per_language_failure_cannot_hide_in_pooled_score():
    cases = [
        {"id": str(i), "question": "Question", "language": "en"} for i in range(9)
    ] + [{"id": "ar", "question": "سؤال", "language": "ar"}]

    async def answer(case):
        return "answer", [{"text": "context"}]

    async def judge(case, *args):
        score = 0.0 if case["language"] == "ar" else 1.0
        return {
            "claims": [{"text": "claim", "supported": True}],
            "answers_reference": True,
            "ragas_faithfulness": score,
        }

    report = await evaluation.evaluate(cases, answer, judge, 0.75)
    assert report["faithfulness"] == 0.9
    assert report["by_language"]["ar"]["faithfulness"] == 0
    assert not report["passed"]


@pytest.mark.asyncio
async def test_out_of_corpus_requires_an_exact_refusal():
    cases = [{"id": "1", "question": "Medical dosage?", "expect_no_answer": True}]

    async def answer(case):
        return (
            "I could not find information in the indexed documents to answer your question. Take 50 mg.",
            [],
        )

    async def judge(*args):
        pytest.fail("Refusal check must not call judge")

    report = await evaluation.evaluate(cases, answer, judge, 0.75)
    assert report["reference_accuracy"] == 0
    assert report["faithfulness"] is None
    assert not report["passed"]


def test_monitoring_dataset_has_bilingual_provenance():
    root = Path(__file__).resolve().parents[2]
    cases = evaluation.load_cases(root / "eval/monitoring_set.json", 50)
    assert len(cases) == 52
    assert sum(case.get("expect_no_answer", False) for case in cases) == 2
    assert {case["language"] for case in cases} == {"ar", "en"}
    assert all(case["review_status"] == "draft" for case in cases)


@pytest.mark.asyncio
async def test_checkpoint_retains_answer_when_judge_fails(tmp_path):
    calls = []
    checkpoint = tmp_path / "checkpoint.json"
    cases = [{"id": "1", "question": "Question"}]

    async def answer(case):
        calls.append(case["id"])
        return "Answer", [{"text": "Context"}]

    async def unavailable(*args):
        raise TimeoutError("Judge unavailable")

    with pytest.raises(TimeoutError):
        await evaluation.evaluate(cases, answer, unavailable, 0.75, checkpoint)
    assert json.loads(checkpoint.read_text())["pending"]["answer"] == "Answer"

    async def judge(*args):
        return {
            "claims": [{"text": "Answer", "supported": True}],
            "answers_reference": True,
            "ragas_faithfulness": 1.0,
        }

    report = await evaluation.evaluate(cases, answer, judge, 0.75, checkpoint)
    assert report["passed"]
    assert calls == ["1"]
    with pytest.raises(ValueError, match="different dataset"):
        await evaluation.evaluate(
            [{"id": "2", "question": "Other"}], answer, judge, 0.75, checkpoint
        )


@pytest.mark.asyncio
async def test_semantic_refusal_uses_judge_without_claiming_faithfulness():
    async def answer(case):
        return "The provision does not identify any particular person.", [
            {"text": "General statute"}
        ]

    async def judge(case, answer, contexts):
        return {"answers_reference": True}

    report = await evaluation.evaluate(
        [
            {
                "id": "negative",
                "question": "Who?",
                "expect_no_answer": True,
                "semantic_refusal": True,
            }
        ],
        answer,
        judge,
        0.75,
    )
    assert report["reference_accuracy"] == 1.0
    assert report["faithfulness"] is None


@pytest.mark.asyncio
async def test_bilingual_seed_batches_have_unique_ids_and_language_metadata():
    batches = []

    class Controller:
        async def index_into_vector_db(self, **kwargs):
            batches.append(kwargs)
            return True

    records = [
        dict(
            article_number=n,
            citation=f"Article {n}",
            text_en="English",
            text_ar="عربي",
            asset_name="source.pdf",
            source_pages=[1],
        )
        for n in range(1, 28)
    ]
    await evaluation.seed_corpus(Controller(), [{"project_id": 1}], records)
    assert [len(batch["chunks"]) for batch in batches] == [50, 4]
    ids = [item for batch in batches for item in batch["chunks_ids"]]
    assert len(ids) == len(set(ids)) == 54
    assert {
        chunk.chunk_metadata["language"]
        for batch in batches
        for chunk in batch["chunks"]
    } == {"ar", "en"}
    assert all(not batch["do_reset"] for batch in batches)


@pytest.mark.asyncio
async def test_judge_obeys_rate_limit_cooldown(tmp_path, monkeypatch):
    import asyncio

    import httpx

    original_client = httpx.AsyncClient
    real_sleep = asyncio.sleep
    clock = [0.0]
    attempts = []

    async def sleep(seconds):
        clock[0] += seconds
        await real_sleep(0)

    async def respond(request):
        attempts.append(clock[0])
        if len(attempts) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "65"},
                json={"error": {"message": "Rate limited"}},
            )
        return httpx.Response(
            200,
            json={
                "id": "test",
                "object": "chat.completion",
                "created": 0,
                "model": "test",
                "choices": [
                    {
                        "finish_reason": "stop",
                        "index": 0,
                        "message": {
                            "role": "assistant",
                            "content": json.dumps(
                                {
                                    "claims": [
                                        {"text": "Unavailable", "supported": True}
                                    ],
                                    "answers_reference": True,
                                }
                            ),
                        },
                    }
                ],
            },
        )

    class MockClient(original_client):
        def __init__(self, **kwargs):
            super().__init__(transport=httpx.MockTransport(respond), **kwargs)

    monkeypatch.setattr(httpx, "AsyncClient", MockClient)
    monkeypatch.setattr(evaluation, "perf_counter", lambda: clock[0])
    monkeypatch.setattr(asyncio, "sleep", sleep)
    monkeypatch.setenv("RAG_EVAL_JUDGE_API_KEY", "test-key")
    monkeypatch.setenv("RAG_EVAL_JUDGE_MODEL", "test-model")
    monkeypatch.setenv("RAG_EVAL_JUDGE_BASE_URL", "https://judge.invalid/v1")
    monkeypatch.setenv("RAG_EVAL_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("RAG_EVAL_FULL_METRICS", "0")
    client, judge = evaluation.make_judge()
    try:
        verdict = await judge(
            {
                "question": "Name?",
                "expected_answer": "Unavailable",
                "expect_no_answer": True,
            },
            "Unavailable",
            [],
        )
        assert verdict["answers_reference"] is True
        assert len(attempts) == 2
        assert attempts[1] - attempts[0] >= 65
    finally:
        await client.close()


def test_experiment_retries_wrapped_rate_limits_but_not_auth_errors(monkeypatch):
    from types import SimpleNamespace

    scripts = Path(__file__).resolve().parents[2] / "scripts"
    monkeypatch.syspath_prepend(str(scripts))
    spec = importlib.util.spec_from_file_location(
        "run_experiments", scripts / "run_experiments.py"
    )
    experiments = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(experiments)
    rate_error = RuntimeError("Rate limited")
    rate_error.status_code = 429
    wrapped = RuntimeError("Instructor wrapper")
    wrapped.failed_attempts = [SimpleNamespace(exception=rate_error)]
    assert experiments.is_transient_provider_error(wrapped)
    auth_error = RuntimeError("Invalid credentials")
    auth_error.status_code = 401
    assert not experiments.is_transient_provider_error(auth_error)


@pytest.mark.asyncio
async def test_capture_only_can_resume_judging_without_generating_again(tmp_path):
    calls = []
    cases = [
        {"id": "1", "question": "Question", "language": "en", "article_number": 44}
    ]
    checkpoint = tmp_path / "capture.json"

    async def answer(case):
        calls.append(case["id"])
        return "Twenty-one", [{"text": "Source", "metadata": {"article_number": 44}}]

    capture = await evaluation.evaluate(cases, answer, None, 0.75, checkpoint)
    assert capture["status"] == "awaiting_judge"
    assert not capture["passed"]
    assert capture["reference_accuracy"] is None
    assert capture["metrics"]["article_hit_rate"] == 1
    assert len(json.loads(checkpoint.read_text())["answers"]) == 1

    async def judge(*args):
        return {
            "claims": [{"text": "Twenty-one", "supported": True}],
            "answers_reference": True,
            "ragas_faithfulness": 1.0,
        }

    scored = await evaluation.evaluate(cases, answer, judge, 0.75, checkpoint)
    assert scored["passed"]
    assert calls == ["1"]
