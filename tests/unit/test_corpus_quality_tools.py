import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_quality_export_does_not_invent_missing_scores():
    publisher = module("publish_eval_metrics")
    text = publisher.render(
        {
            "completed_at": "2026-10-11T00:00:00+00:00",
            "passed": False,
            "by_language": {"ar": {"faithfulness": 0.5, "context_recall": None}},
        }
    )
    assert 'metric="faithfulness",lang="ar"' in text
    assert "context_recall" not in text
    assert "rag_eval_run_success 0" in text
    with pytest.raises(ValueError):
        publisher.render(
            {
                "completed_at": "2026-10-11T00:00:00+00:00",
                "by_language": {"ar": {"faithfulness": float("nan")}},
            }
        )


def test_full_corpus_validation_rejects_unexplained_gaps_and_empty_text():
    corpus = module("build_legal_corpus")
    row = {
        "article_number": 1,
        "text_ar": "نص",
        "text_en": "text",
        "is_repealed": False,
    }
    corpus.validate([row])
    with pytest.raises(ValueError, match="gaps"):
        corpus.validate([{**row, "article_number": 2}])
    with pytest.raises(ValueError, match="missing"):
        corpus.validate([{**row, "text_ar": ""}])
