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
    main_module = SimpleNamespace(app=app, lifespan=lifespan)
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
