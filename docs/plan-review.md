# Final-project plan status

Follow-up on 2026-10-12: the user authorized using the current API. OpenRouter's
configured free MiniMax generation endpoint returned 404 and was replaced in the
local Docker environment by the successfully tested free Nemotron 3 Ultra model.
Embedding settings remain unchanged. Live readiness, authenticated contracts,
background upload/process/index, cited English/Arabic answers, SSE and feedback
passed with a separate public-corpus test project. See docs/model-serving.md.
Fine-tuned serving, RAGAS grades and load/optimization measurements remain pending.
Project 6's 1,242 existing chunks now have a current fingerprinted index; its
legacy index is retained. Free-provider indexing batches are paced locally.
The model-independent review below records the scope of the preceding work.

Reviewed against the repository and the downloaded 81-page course handbook on
2026-10-11. Work is scoped to the final RAG project; generation-model setup,
inference measurements and optimization are deferred by request. The existing
FastAPI/controllers/provider factories and PostgreSQL/PGVector/Qdrant architecture
are retained. `certifcates_sys/` is a separate assignment.

## Sessions 1–2: prerequisite review

Existing provider contract fixes, POST validation, source metadata, no-hit behavior,
health, JSON request IDs, threaded model calls, non-root Docker, single worker and
CI were retained. Packaging now explicitly supports an editable installation while
preserving the existing imports; installation/import checks passed.

Encoder-fingerprinted collections are retained. Settings for unused llama.cpp/NARA
backends are no longer mandatory. Reranker identity/batch/pool/on-off and optional
calibrated score threshold are configurable. Local prompts are content-versioned.

DVC now tracks a reproducible source snapshot and the complete structured corpus
through dvc.yaml/dvc.lock. The committed raw PDF can reproduce these outputs
without a storage remote. Git continues to version the small evaluation datasets.
A five-configuration MLflow experiment runner logs parameters, metrics and reports
using disposable indexes. No model/config registry promotion or five measured runs
are claimed; these need actual evaluated configurations.

## Session 3

| Plan item | Applied result |
|---|---|
| 3.1 Inference pattern | Background processing and indexing endpoints, polling, bounded queue, same-project mutation exclusions and atomic job snapshots in the assets volume. Interrupted jobs become failed on restart. |
| 3.2 Load behavior | Blocking processing is off the event loop; existing serialized embed/rerank/generation retained. Explicit provider timeout/retries and configurable reranker batches. HTTP latency now measures the full response including SSE consumption. |
| 3.3 Serving/streaming | Real OpenAI-compatible token streaming, stream cleanup, outcome/TTFT/duration metrics, guarded output buffering. Future external generation URL/key support retained; vLLM untouched. |
| 3.4 Load harness | Authenticated answer/health Locust workload, 50-user command and isolated-project instructions. Real report deferred. |
| 3.5 Release strategy | Configuration/image rollback documented. Canary/shadow services deferred until there is a candidate and shared-state coordination; duplicating embedded Qdrant and job processes now would conflict with the current architecture. |
| 3.6 Scheduling | Opt-in nightly GitHub evaluation with report artifacts. No Airflow/cron service. Batch re-indexing client submits/polls processing and indexing through the existing API. |

Redis workers, BentoML, Triton/TensorRT and ONNX/INT8 reranking are omitted from
this implementation. Their purpose is scaling/optimization; introduce them only
when measured bottlenecks or course requirements justify changing this scope.

## Session 4

| Plan item | Applied result |
|---|---|
| 4.1 RAG drift | Encoder identities, rerank distributions, zero-hit/outcome counters by Arabic/English, prompt hashes and per-language quality reports. Distribution-based embedding drift deferred until baseline query embeddings exist. |
| 4.2 Prometheus | Bounded route/method labels, full-response/error instrumentation, corrected scrape targets, normal /metrics blocked by nginx, stage/hit/score/token/inflight/stream/guardrail metrics. Single worker avoids multiprocess complexity. |
| 4.3 Grafana/alerts | Provisioned datasource and 13 panels including per-language quality, TTFT and guardrails. Six alert rules; recorded evaluation metrics use node_exporter's textfile collector. No fabricated baseline, token prices, GPU data or outbound notification destination. |
| 4.4 Evidently | Tabular drift tooling skipped; it does not match this API's input or the current baseline. |
| 4.5 Langfuse | Pinned opt-in SDK, answer/retrieve/provider/stream spans, correlation/index/project/prompt metadata, actual non-stream usage and scoped feedback. Raw content omitted before export. Optional system-prompt labels with local fallback. No additional hosting stack or external keys provisioned. |
| 4.6 RAGAS | Preserved 20-case gate; added 52-case draft monitoring set and optional four-metric evaluation. Judge temperature 0, finite-score validation, per-language gates, exact abstention checks, latency/config reports and isolated experiment indexes. Human label review, judge agreement and actual scores remain unperformed. |
| 4.7 Guardrails/access | API-key identities, explicit project ACLs (including job status/feedback), bounded key quotas with 429/Retry-After, deterministic Arabic/English input/document injection checks, bounded PII redaction, buffered stream filtering, source-required fallback and optional calibrated retrieval refusal. Docker auth enabled with an ignored local client secret. These rules do not establish medical-data safety or claim-by-claim groundedness. |
| 4.8 Operations | Updated runbook, architecture, setup commands, model/observability/evaluation instructions and source-issue documentation. |

## Corpus findings

The extraction produces 1,149 contiguous article records, captures hierarchy/pages
and flags repeal notices. Unexpected gaps, missing languages and implausible record
lengths fail validation. The source itself has a bilingual alignment defect at
Articles 1021/1022 (PDF pages 147–148): Arabic 1021 has paragraphs spanning English
1021/1022, and Arabic 1022 has no separately headed text. The rendered page was
inspected. Both records are flagged for review, and the one missing language field
is accepted only through a manifest pinned to this exact source checksum. No Arabic
text was manufactured or relabeled. Human Arabic spot-checking remains necessary.

## Remaining evidence and scope limits

- Actual model setup, real Q&A/quality/load/TTFT results and optimization benchmarks
  are deferred by the user's instruction to ignore the model for now.
- Langfuse credentials/hosting, an alert notification destination and protected
  GitHub evaluation secrets/variables are external configuration. No external
  project, notification or CI run has been created or claimed verified.
- Dataset approval, judge calibration, screenshots of actual results, registry
  promotion and peer review are submission tasks that cannot be fabricated.
- The project's existing API paths are preserved rather than adding a BentoML
  wrapper or renaming them to the handbook's example /ask path. This is a scoped
  architectural deviation from that checklist, not a claim of exact compliance.
- Single-worker background jobs/status survive restart, but work does not resume
  automatically and failed jobs may leave partial writes. Retry after inspection.
  Quotas/answer receipts are in memory; receipts expire after restart/1,000 entries.

## Verification

See docker/VERIFICATION.md for current source/container checks. DVC repro/status,
editable installation and local tests are independent of an inference model.
No existing application database or vector volume was reset, and no fine-tuned
model was supplied or loaded as part of this work.
