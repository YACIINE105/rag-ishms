"""Create a reproducible report and figures from completed evaluation/load evidence."""

import argparse
import csv
import hashlib
import json
import math
import shutil
from datetime import datetime, timezone
from pathlib import Path

import markdown
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

NAMES = [
    "article-rerank",
    "article-no-rerank",
    "250-rerank",
    "500-rerank",
    "article-k3",
]


def read_json(path):
    return json.loads(path.read_text())


def percentile(values, fraction):
    return sorted(values)[math.ceil(len(values) * fraction) - 1]


def number(value):
    return f"{value:.3f}" if isinstance(value, (float, int)) else "n/a"


def load_answer_statistics(directory):
    final = directory / "load-final.json"
    if final.exists():
        row = next(
            item
            for item in read_json(final)
            if item["name"] == "/index/answer/{project_id}"
        )
        histogram = sorted(
            (int(bound), count) for bound, count in row["response_times"].items()
        )

        def quantile(fraction):
            target = math.ceil(
                (row["num_requests"] - row["num_none_requests"]) * fraction
            )
            observed = 0
            for bound, count in histogram:
                observed += count
                if observed >= target:
                    return bound
            return None

        return {
            "Request Count": row["num_requests"],
            "Failure Count": row["num_failures"],
            "Median Response Time": quantile(0.5),
            "95%": quantile(0.95),
            "99%": quantile(0.99),
            "statistics_source": "Locust final JSON after request draining",
        }
    with (directory / "load_stats.csv").open() as source:
        rows = list(csv.DictReader(source))
    row = next(item for item in rows if item["Name"] == "/index/answer/{project_id}")
    row["statistics_source"] = (
        "Periodic CSV snapshot; consult final console for trailing requests"
    )
    return row


def stage_summary(path):
    import re

    stages = {}
    for line in path.read_text().splitlines():
        match = re.match(
            r'rag_stage_latency_seconds_(sum|count)\{stage="([^"]+)"\} ([0-9.eE+-]+)',
            line,
        )
        if match:
            kind, stage, value = match.groups()
            stages.setdefault(stage, {})[kind] = float(value)
        match = re.match(
            r'rag_stage_latency_seconds_bucket\{le="([^"]+)",stage="([^"]+)"\} ([0-9.eE+-]+)',
            line,
        )
        if match:
            bound, stage, value = match.groups()
            stages.setdefault(stage, {}).setdefault("buckets", {})[bound] = float(value)
    return stages


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--results", type=Path, default=Path("eval/reports/final-project")
    )
    parser.add_argument(
        "--report", type=Path, default=Path("docs/final-project-report.md")
    )
    parser.add_argument(
        "--allow-incomplete",
        action="store_true",
        help="Publish captured runs with pending judge scores explicitly marked n/a",
    )
    args = parser.parse_args()
    root = args.results
    reports = []
    for name in NAMES:
        path = root / "configurations" / f"{name}.json"
        if not path.exists() and args.allow_incomplete:
            path = root / "configurations" / f"{name}.capture.json"
        reports.append(read_json(path))
    if any(len(report.get("cases", [])) != 62 for report in reports):
        raise ValueError(
            "All five frozen 62-case comparisons must finish before reporting"
        )
    dataset = read_json(
        Path(__file__).resolve().parents[1] / "eval/civil_code_full.json"
    )
    references = {case["id"]: case["expected_answer"] for case in dataset}
    with (root / "case-review.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as output:
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "configuration",
                "id",
                "language",
                "question",
                "expected_answer",
                "answer",
                "expect_no_answer",
                "judge_correct",
                "article_hit",
                "faithfulness",
                "latency_seconds",
                "retrieved_articles",
            ],
        )
        writer.writeheader()
        for name, report in zip(NAMES, reports):
            for case in report["cases"]:
                writer.writerow(
                    dict(
                        configuration=name,
                        id=case["id"],
                        language=case["language"],
                        question=case["question"],
                        expected_answer=references[case["id"]],
                        answer=case["answer"],
                        expect_no_answer=case["expect_no_answer"],
                        judge_correct=case["answers_reference"],
                        article_hit=case["reference_article_retrieved"],
                        faithfulness=case["faithfulness"],
                        latency_seconds=case["latency_seconds"],
                        retrieved_articles=",".join(
                            str(item.get("metadata", {}).get("article_number"))
                            for item in case["contexts"]
                        ),
                    )
                )
    load = read_json(root / "load/metadata.json")
    streams = read_json(root / "load/streaming.json")
    answer_stats = load_answer_statistics(root / "load")
    images = root / "figures"
    images.mkdir(exist_ok=True)
    plt.rcParams.update({"font.size": 10, "figure.dpi": 150})
    x = np.arange(len(NAMES))
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for offset, language, color in [(-0.19, "ar", "#147d92"), (0.19, "en", "#df9c35")]:
        ax.bar(
            x + offset,
            [
                r["by_language"].get(language, {}).get("reference_accuracy", np.nan)
                for r in reports
            ],
            width=0.36,
            label={"ar": "Arabic", "en": "English"}[language],
            color=color,
        )
    ax.axhline(0.75, color="#9b3341", linestyle="--", label="Engineering gate 0.75")
    ax.set(
        xticks=x,
        xticklabels=NAMES,
        ylim=(0, 1.08),
        ylabel="Reference accuracy",
        title="Frozen Civil Code questions: 31 per language (missing bars = unscored)",
    )
    ax.tick_params(axis="x", rotation=12)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(images / "accuracy.png")
    fig.savefig(images / "accuracy.pdf")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    for offset, metric, label in [
        (-0.27, "faithfulness", "Faithfulness"),
        (-0.09, "response_relevancy", "Response relevancy"),
        (0.09, "context_precision", "Context precision"),
        (0.27, "context_recall", "Context recall"),
    ]:
        ax.bar(
            x + offset,
            [r["metrics"].get(metric, np.nan) for r in reports],
            width=0.17,
            label=label,
        )
    ax.set(
        xticks=x,
        xticklabels=NAMES,
        ylim=(0, 1.08),
        ylabel="RAGAS score",
        title="RAGAS diagnostics: answerable questions (missing bars = unscored)",
    )
    ax.tick_params(axis="x", rotation=12)
    ax.legend(loc="lower right")
    fig.tight_layout()
    fig.savefig(images / "ragas.png")
    fig.savefig(images / "ragas.pdf")
    plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    axes[0].bar(
        NAMES, [r["metrics"]["p95_latency_seconds"] for r in reports], color="#147d92"
    )
    axes[0].tick_params(axis="x", rotation=45)
    axes[0].set(ylabel="Seconds", title="Sequential RAG p95 (judge excluded)")
    axes[1].bar(
        range(1, len(streams) + 1),
        [r["first_text_seconds"] for r in streams],
        label="First delivered text",
        color="#df9c35",
    )
    axes[1].set(
        xlabel="Streaming probe",
        ylabel="Seconds",
        title="Guarded SSE: delivered first text",
    )
    fig.tight_layout()
    fig.savefig(images / "latency.png")
    fig.savefig(images / "latency.pdf")
    plt.close(fig)
    before, after = [
        stage_summary(root / "load" / f"metrics-{point}.prom")
        for point in ("before", "after")
    ]
    stages = {}
    for stage, values in after.items():
        old = before.get(stage, {})
        count = values.get("count", 0) - old.get("count", 0)
        total = values.get("sum", 0) - old.get("sum", 0)
        if count <= 0:
            continue
        bounds = sorted(
            (float(k), value - old.get("buckets", {}).get(k, 0))
            for k, value in values.get("buckets", {}).items()
        )
        bound = next((bound for bound, n in bounds if n >= 0.95 * count), float("inf"))
        stages[stage] = dict(
            count=count,
            mean_seconds=total / count,
            p95_bucket_upper_seconds=bound if math.isfinite(bound) else None,
        )
    fig, ax = plt.subplots(figsize=(8, 4.2))
    ax.bar(
        list(stages), [row["mean_seconds"] for row in stages.values()], color="#147d92"
    )
    ax.set(
        ylabel="Mean seconds including stage queue",
        title="50-user load: measured stage latency",
    )
    fig.tight_layout()
    fig.savefig(images / "load-stages.png")
    fig.savefig(images / "load-stages.pdf")
    plt.close(fig)
    summary = dict(
        created_at=datetime.now(timezone.utc).isoformat(),
        status="awaiting_judge"
        if any(r.get("status") == "awaiting_judge" for r in reports)
        else "scored",
        comparisons=[
            dict(
                name=name,
                status=r.get("status", "scored"),
                passed=r["passed"],
                metrics=r["metrics"],
                by_language=r["by_language"],
            )
            for name, r in zip(NAMES, reports)
        ],
        load=load,
        load_answer_statistics=answer_stats,
        stages=stages,
        streaming=dict(
            samples=len(streams),
            first_text_p50_seconds=percentile(
                [s["first_text_seconds"] for s in streams], 0.5
            ),
            first_text_p95_seconds=percentile(
                [s["first_text_seconds"] for s in streams], 0.95
            ),
            mean_end_to_end_output_tokens_per_second=sum(
                s["end_to_end_output_tokens_per_second"] for s in streams
            )
            / len(streams),
        ),
        limitations=[
            "Assistant source review only; no legal expert certification.",
            "LLM judge has observed Arabic misreadings; automated correctness is provisional.",
            "Evaluation uses direct NVIDIA embeddings, not the production OpenRouter free route.",
            "25 source articles have reference questions; corpus retrieval includes 1149.",
            "Single local 4-bit Qwen serving run per configuration; no new model training.",
        ],
    )
    (root / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n"
    )
    lines = [
        "# Final-project evaluation report",
        "",
        "Measured Civil Code retrieval, answer quality and local serving capacity. These results are engineering diagnostics; they do not certify legal correctness.",
        "",
        (
            "**Scoring is incomplete.** All five configurations have captured 62 answers each, but the external judge is unavailable. Missing scores are n/a; no five-way quality winner or promotion is claimed."
            if summary["status"] == "awaiting_judge"
            else "All five configurations have completed automated scoring; the judge limitations below still apply."
        ),
        "",
        "## Source and experiment",
        "",
        "- Supplied PDF: `G:\\Downloads\\1576751803.pdf`, 170 pages.",
        "- SHA-256: `2d6419fb262dab712f7bf5f6e31834bea74fbcf03b78ae081dd35d156915eebf`.",
        "- Qalam: 1,149 articles and 2,297 nonempty language chunks; known Article 1021/1022 alignment defect retained and excluded from references.",
        "- Frozen questions: 62, with 25 answerable and six unanswerable in each language, covering 25 distinct articles. Assistant source review; no independent legal expert review.",
        "- All five configurations use full-corpus retrieval, local Qwen3-4B-Instruct-2507 at the pinned revision, temperature zero, maximum 256 output tokens, and the existing BGE GPU reranker where enabled.",
        "- Generator uses 4-bit NF4 on the 6-GiB RTX 3060; context 2,048, one active generation sequence. No adapter is loaded and no training was performed.",
        "- Direct NVIDIA Nemotron VL 1B v2 embeddings (2,048 dimensions) avoid exhausting the production OpenRouter 50-request daily allowance. Existing production settings/indexes were preserved.",
        "- Independent judge: NVIDIA Nemotron 3 Super 120B, temperature zero. Twelve simple calibration items passed. Subsequent inspection found Arabic misreadings: judge correctness remains provisional, even where a score passes its engineering gate.",
        "- HTTP 429 interrupted the first scoring attempt. Saved answers and completed scores were resumed with request pacing; no answers were regenerated to improve scores.",
        "",
        "## Five configuration comparisons",
        "",
        "| Configuration | Faithfulness | Relevancy | Context precision | Context recall | Reference accuracy | p95 seconds | Gate |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for name, r in zip(NAMES, reports):
        m = r["metrics"]
        lines.append(
            "| "
            + name
            + " | "
            + " | ".join(
                number(m.get(k))
                for k in (
                    "faithfulness",
                    "response_relevancy",
                    "context_precision",
                    "context_recall",
                    "reference_accuracy",
                    "p95_latency_seconds",
                )
            )
            + (
                " | PENDING |"
                if r.get("status") == "awaiting_judge"
                else (" | PASS |" if r["passed"] else " | FAIL |")
            )
        )
    lines += [
        "",
        "| Configuration / language | Answerable accuracy | Abstention accuracy | Article hit rate |",
        "|---|---:|---:|---:|",
    ]
    for name, r in zip(NAMES, reports):
        for language, m in r["by_language"].items():
            lines.append(
                f"| {name} / {language} | "
                + " | ".join(
                    number(m.get(k))
                    for k in (
                        "answerable_accuracy",
                        "abstention_accuracy",
                        "article_hit_rate",
                    )
                )
                + " |"
            )
    lines += [
        "",
        "Faithfulness excludes expected refusals; reference accuracy includes them. Additional RAGAS scores cover answerable questions only. Generation remains sequential; remote grading is overlapped and excluded from response latency. Completed per-case answers and exact retrieved contexts are saved. MLflow records the five configurations and artifacts; interrupted attempts remain visible.",
        "",
        "## Load and streaming",
        "",
        f"Locust used 50 independent identities (observed peak {load['observed_peak_users']}), spawn rate 5/s, 180 seconds plus up to 180 seconds to drain. Exit code: {load['locust_exit_code']}. The isolated API uses the existing application code on localhost:8003, {load.get('vector_backend', 'QDRANT')}, the full Qalam-upload/process/index workflow, local GPU servers and direct NVIDIA embeddings. This measures the application directly; it is not a production nginx/OpenRouter capacity claim.",
        "",
        "The original Qdrant load run exposed worker-pool starvation: 66 answer requests, 49 failures, and all four health checks failed. An async wait gate now keeps queued model calls outside the worker pool. The later PGVector run also changes the backend and fixes the workload seed, so differences cannot be attributed solely to that fix. A preceding PGVector setup indexed all 2,297 chunks but stopped during SSE after a CUDA unknown-error crash; it is preserved separately. The measured PGVector retry reused that verified index after the host restart.",
        "",
        f"Answer requests: {answer_stats['Request Count']}; failed: {answer_stats['Failure Count']}; median: {answer_stats['Median Response Time']} ms; p95: {answer_stats['95%']} ms; p99: {answer_stats['99%']} ms. Inspect the failure CSV and provider logs alongside aggregate rates; HTTP 200 with empty answers/sources is also a load-test failure.",
        "",
        "| Stage | Samples | Mean seconds | p95 histogram upper bound seconds |",
        "|---|---:|---:|---:|",
    ]
    for stage, m in stages.items():
        lines.append(
            f"| {stage} | {m['count']:.0f} | {m['mean_seconds']:.3f} | {number(m['p95_bucket_upper_seconds'])} |"
        )
    lines += [
        "",
        "Stage timings include serialization/queue waits. Histogram p95 values are bucket bounds, not precise per-request quantiles; separate stage p95s cannot identify which stage occurred in the same p95 request.",
        "",
        f"Six bilingual SSE probes: first delivered text p50 {summary['streaming']['first_text_p50_seconds']:.3f}s, p95 {summary['streaming']['first_text_p95_seconds']:.3f}s. Mean end-to-end output rate {summary['streaming']['mean_end_to_end_output_tokens_per_second']:.3f} tokens/s, counted with the served Qwen tokenizer. Guardrails buffer text until filtering completes, so delivered first text is not engine-internal TTFT or an unbuffered streaming claim.",
        "",
        "## Answer inspection",
        "",
        "The assistant compared all 62 article-rerank outputs with their frozen references; this is not independent legal expert labeling. Arabic Article 94 omits the meeting-end acceptance condition, Article 147 omits the contrary-agreement void clause, and the person-name negative returns a generic legal category. Article 226 reaches the 256-token cap and ends midword while omitting reference conditions. These are practical failures to retain even if an automated gate passes.",
        "",
        "The Super judge also misread a clear Arabic court-address refusal and invented claims when grading the Article 374 answer. Their original machine scores are preserved. The evidence includes assistant-answer-review.json with exact case IDs; no corrected legal accuracy percentage is inferred. Alternative judges were rejected when unavailable or when calibration controls failed; their results were not mixed into this comparison.",
        "",
        "## Scope and remaining human decisions",
        "",
        "No new fine-tuning, remote deployment, index replacement, Canary/BentoML/Redis stack, or Cue/Kaggle work was performed. Existing runtime architecture remains intact. Model choice from the earlier acceptance study remains the untuned Qwen base; this comparison varies retrieval configuration, not trained adapters.",
        "",
        "Legal expert review and a larger independently labeled held-out benchmark remain human work. Automated judge errors must be resolved before treating these scores as legal accuracy. External Langfuse credentials, alert destinations, registry promotion and protected CI secrets are optional external setup, not completed experiments. Do not promise that a small benchmark eliminates model failure.",
        "",
        "## Evidence and reproduction",
        "",
        "See `eval/CIVIL_CODE_EVALUATION.md` for the frozen dataset, extraction and five-run command. Raw reports, checkpoints, calibration, exact contexts, MLflow tracking database, Locust CSV/HTML, streaming probes and metric snapshots remain local under `eval/reports/final-project/` and `reports/mlflow.db`. No secrets are included in the shareable evidence archive.",
        "",
    ]
    args.report.parent.mkdir(parents=True, exist_ok=True)
    lines += ["## Figures", ""]
    figure_directory = args.report.parent / "figures"
    figure_directory.mkdir(exist_ok=True)
    for name in ["accuracy", "ragas", "latency", "load-stages"]:
        shutil.copyfile(images / f"{name}.png", figure_directory / f"{name}.png")
        lines += [f"![{name}](figures/{name}.png)", ""]
    args.report.write_text("\n".join(lines))
    # The HTML report is an exportable evidence artifact, not an external deployment.
    content = '<!doctype html><html><head><meta charset="utf-8"><title>Civil Code RAG results</title><style>body{font:15px/1.6 sans-serif;max-width:1100px;margin:40px auto;color:#162c3a}table{border-collapse:collapse;width:100%;font-size:12px}td,th{padding:7px;border:1px solid #cdd8df;text-align:left}th{background:#eaf3f5}code{overflow-wrap:anywhere}img{max-width:100%}h1,h2{color:#147d92}@media print{body{margin:0}img,table{break-inside:avoid}h2{break-after:avoid}}</style></head><body>'
    content += markdown.markdown("\n".join(lines), extensions=["tables", "fenced_code"])
    content += "</body></html>"
    (root / "report.html").write_text(content)
    manifest = {}
    for path in sorted(root.rglob("*")):
        if (
            path.is_file()
            and path.suffix in {".json", ".csv", ".png", ".pdf", ".html", ".prom"}
            and "cache" not in str(path)
            and path.name != "evidence-manifest.json"
        ):
            manifest[str(path.relative_to(root))] = hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
    (root / "evidence-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"Report written ({summary['status']}):", args.report)


if __name__ == "__main__":
    main()
