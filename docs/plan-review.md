# Final-project plan status

Latest update, 2026-10-16: Cue's bounded fine-tuning comparison and release handoff
are complete. The selected candidate is the pinned **untuned Qwen base**, not
either pilot adapter. Its weights are verified locally, generation and reranking
run in the existing separate vLLM environment, and Docker health, authenticated
English/Arabic completions, real retrieved-context answers, refusal and SSE smoke
checks pass after the laptop restart. See `docs/model-serving.md` for measured
limits and `docs/cue-memory.md` for the experiment/audit distinction.

Measured evidence is now in [the final-project report](final-project-report.md).
Qalam extracted all 1,149 Civil Code articles; the frozen set has 62 bilingual
questions. All five configurations captured 62 real answers each. Complete
RAGAS/reference scores and pending provider-limited scores are distinguished in
the report; no five-way quality winner is claimed while grading is incomplete.
The real PGVector run observed 50 users but failed 50/58 answer requests; its
six guarded SSE probes completed. This hardware does not pass the capacity target.
External Langfuse, alerting and protected CI settings remain optional configuration.
The historical implementation review below is retained with these updates. Both
GPU services and nginx/API readiness recovered after the latest laptop restart;
authentication checks again returned the expected 401/422 responses. The latest
suite passes 242 tests with 86.55% coverage. The legacy rubric failed 11/28 controls
with Super VL. After fixing readable Arabic and candidate/reference separation,
the versioned rubric passed 28/28 controls and started a separate consistent
regrade. Two configurations have complete new scores; the remaining grades are
limited by NVIDIA 429 responses even after cooldown and slower request pacing.
Real-answer inspection still finds judge false positives; its passing controls
and engineering gates do not establish legal correctness.

The report is exported as an actual PDF with four figures, per-case review CSV
and screenshots of Locust and Grafana. Five explicitly tagged final MLflow runs
separate complete quality scores from provider-limited capture measurements.
The evidence export scans configured secrets and verifies ZIP integrity and
every payload checksum. The exported tracking database preserves original local
artifact paths; the actual result files are included separately.

Historical GPU follow-up, 2026-10-12: the existing separate vLLM environment serves the same BGE
reranker on the RTX 3060, through a small HTTP adapter retaining the controller
contract. The 30-candidate project-8 search was checked at 3.214 seconds initially
and 0.508/0.413 seconds on repeats. GPU startup/operations and the 512-token/FP16
limits are documented in docs/model-serving.md; concurrency/quality evidence is
still pending. No vLLM dependencies were added to the API environment.

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
using disposable indexes. All five measured capture runs are now recorded; two
have complete versioned automated grades. No model/config registry promotion or complete
five-way quality ranking is claimed while the remaining grading is incomplete.

## Session 3

| Plan item | Applied result |
|---|---|
| 3.1 Inference pattern | Background processing and indexing endpoints, polling, bounded queue, same-project mutation exclusions and atomic job snapshots in the assets volume. Interrupted jobs become failed on restart. |
| 3.2 Load behavior | Blocking processing is off the event loop; existing serialized embed/rerank/generation retained. Explicit provider timeout/retries and configurable reranker batches. HTTP latency now measures the full response including SSE consumption. |
| 3.3 Serving/streaming | OpenAI-compatible generation/streaming, cleanup and TTFT/duration metrics; guarded output buffers. Pinned Qwen generation and BGE reranking now run externally in the existing vLLM environment, preserving the API architecture. |
| 3.4 Load harness | Real full-PDF upload/Qalam/index/SSE/50-user Locust evidence saved. Fifty temporary identities and PGVector match the application path. Capacity target failed; final JSON, CSV/HTML, GPU samples and stage snapshots retained. |
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
| 4.6 RAGAS | Preserved the 20-case gate; froze a 62-case assistant-reviewed Civil Code set. Actual four-metric and reference-rubric reports are saved where complete; 429/incomplete-JSON failures preserve checkpoints. All five configurations captured answers/contexts. Semantic refusal, numerical conditions and source articles are inspected. No legal expert review or certified judge agreement is claimed. |
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

- Model setup, full-corpus extraction, 310 captured comparison answers, 50-user
  load/SSE measurements, report/figures/screenshots and real Docker checks are
  recorded. Remaining automated scores are explicitly pending while the NVIDIA
  judge is throttled; partial scores do not establish a five-way quality winner.
  The measured load target failed and generator numerical errors/omissions remain.
- Langfuse credentials/hosting, an alert notification destination and protected
  GitHub evaluation secrets/variables are external configuration. No external
  project, notification or CI run has been created or claimed verified.
- Assistant source review, judge sanity checks and screenshots of actual results
  are executed. Dataset approval by a legal expert, peer review and optional
  registry promotion are separate human/external decisions. Simple calibration
  does not establish reliable legal grading; observed judge errors are retained.
- The project's existing API paths are preserved rather than adding a BentoML
  wrapper or renaming them to the handbook's example /ask path. This is a scoped
  architectural deviation from that checklist, not a claim of exact compliance.
- Single-worker background jobs/status survive restart, but work does not resume
  automatically and failed jobs may leave partial writes. Retry after inspection.
  Quotas/answer receipts are in memory; receipts expire after restart/1,000 entries.

## Verification

See docker/VERIFICATION.md for current source/container checks. DVC repro/status,
editable installation and local tests are independent of an inference model.
Latest full suite: 242 tests, 86.55% source coverage. Actual API findings led to
the numeric asset-ID lookup fix, asynchronous model wait gate, bulk SQL budget
and idempotent PGVector batches. The existing Docker API was rebuilt and checked.
No existing user database/vector volume was reset; isolated evaluation projects
were added. No new training or adapter integration was performed.
