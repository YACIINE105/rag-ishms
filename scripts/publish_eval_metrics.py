"""Publish a real evaluation report to node_exporter's atomic textfile collector."""

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path

METRICS = (
    "faithfulness",
    "response_relevancy",
    "context_precision",
    "context_recall",
    "reference_accuracy",
)


def render(report):
    completed = report.get("completed_at")
    if not completed:
        raise ValueError("Report needs its actual completed_at timestamp")
    timestamp = datetime.fromisoformat(completed).timestamp()
    lines = [
        f"rag_eval_last_run_timestamp_seconds {timestamp}",
        f"rag_eval_run_success {int(report.get('passed') is True)}",
    ]
    for language, scores in report.get("by_language", {}).items():
        if language not in {"en", "ar", "unknown"}:
            raise ValueError("Unsupported evaluation language")
        for name in METRICS:
            value = scores.get(name)
            if value is None:
                continue
            if (
                type(value) not in (int, float)
                or not math.isfinite(value)
                or not 0 <= value <= 1
            ):
                raise ValueError("Invalid evaluation score")
            lines.append(f'rag_eval_score{{metric="{name}",lang="{language}"}} {value}')
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=Path("eval/reports/latest.json"))
    parser.add_argument(
        "--output", type=Path, default=Path("reports/metrics/rag_eval.prom")
    )
    args = parser.parse_args()
    report = json.loads(args.report.read_text())
    # Failed CLI reports have no scores; record failure without inventing them.
    if "completed_at" not in report and "error_type" in report:
        report["completed_at"] = datetime.fromtimestamp(
            args.report.stat().st_mtime, timezone.utc
        ).isoformat()
    text = render(report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    temporary = args.output.with_suffix(".tmp")
    temporary.write_text(text)
    temporary.replace(args.output)


if __name__ == "__main__":
    main()
