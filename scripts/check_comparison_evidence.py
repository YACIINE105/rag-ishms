"""Check the committed five-run comparison against the historical report, offline."""

import csv
import math
import re
from pathlib import Path

COMPARISON = (
    Path(__file__).resolve().parents[1] / "reports/review/mlflow-comparison.csv"
)
METRICS = (
    "faithfulness",
    "response_relevancy",
    "context_precision",
    "context_recall",
    "reference_accuracy",
    "p95_latency_seconds",
)
# docs/final-project-report.md, Five configuration comparisons. Aggregate scores
# alone do not determine the historical gate; 250-rerank failed by language.
EXPECTED = {
    "article-rerank": ("PASS", (0.949, 0.710, 0.962, 1.000, 0.935, 28.719)),
    "article-no-rerank": ("PASS", (0.946, 0.706, 0.894, 1.000, 0.887, 28.000)),
    "250-rerank": ("FAIL", (0.928, 0.769, 0.915, 0.950, 0.774, 27.308)),
    "500-rerank": ("PASS", (0.925, 0.719, 0.958, 1.000, 0.919, 36.618)),
    "article-k3": ("PASS", (0.969, 0.746, 0.957, 1.000, 0.903, 33.956)),
}


def check_comparison(path: Path) -> None:
    seen_configs = set()
    seen_runs = set()
    required = {"config", "run_id", "gate", "cases_scored", "cases_total", *METRICS}
    with path.open(encoding="utf-8", newline="") as source:
        rows = csv.DictReader(source, strict=True)
        columns = rows.fieldnames or []
        if len(columns) != len(set(columns)) or not required.issubset(columns):
            raise ValueError("comparison CSV has missing or duplicate columns")

        for row in rows:
            config = row["config"]
            if None in row or None in row.values():
                raise ValueError(f"row {rows.line_num}: wrong number of CSV fields")
            if config not in EXPECTED or config in seen_configs:
                raise ValueError(f"row {rows.line_num}: unexpected or duplicate config")
            seen_configs.add(config)
            run_id = row["run_id"]
            if not re.fullmatch(r"[0-9a-f]{32}", run_id) or run_id in seen_runs:
                raise ValueError(f"{config}: invalid or duplicate MLflow run ID")
            seen_runs.add(run_id)

            if row["cases_scored"] != "62" or row["cases_total"] != "62":
                raise ValueError(f"{config}: expected all 62 cases scored")
            gate, expected_metrics = EXPECTED[config]
            if row["gate"] != gate:
                raise ValueError(f"{config}: historical gate must be {gate}")
            for metric, expected in zip(METRICS, expected_metrics, strict=True):
                try:
                    score = float(row[metric])
                except ValueError:
                    raise ValueError(f"{config}: {metric} must be numeric") from None
                limit = math.inf if metric == "p95_latency_seconds" else 1.0
                if (
                    not math.isfinite(score)
                    or not 0 <= score <= limit
                    or round(score, 3) != expected
                ):
                    raise ValueError(
                        f"{config}: {metric} must match the historical value "
                        f"({expected:.3f})"
                    )

    if missing := EXPECTED.keys() - seen_configs:
        raise ValueError(f"missing configurations: {', '.join(sorted(missing))}")


if __name__ == "__main__":
    try:
        check_comparison(COMPARISON)
    except (OSError, ValueError, csv.Error) as exc:
        raise SystemExit(f"RAG comparison evidence check failed: {exc}") from None
    print("RAG comparison evidence check passed (four historical PASS, one FAIL).")
