# Frozen Civil Code evaluation

`civil_code_full.json` contains 62 cases: 25 answerable and six deliberately
unanswerable questions in each language. It covers 25 distinct provisions across
the 170-page source, including numerical conditions, exceptions, contracts,
limitation, ownership and privileges. `civil_code_full.manifest.json` freezes the
source and dataset SHA-256 before generation. It is an assistant-reviewed pilot,
not a human-approved legal benchmark. The 52 historical acceptance questions are
retained, with ten additional questions about Articles 226, 374, 558, 802 and 1148.
Their previous oracle passages are discarded: every experiment retrieves from all
1,149 Qalam article records (2,297 nonempty language fields).

The requested `G:\Downloads\1576751803.pdf` is byte-identical to the committed
`eval/corpus/egyptian-civil-code.pdf`. Extraction command:

```bash
.venv/bin/python scripts/build_legal_corpus.py \
  --source /mnt/g/Downloads/1576751803.pdf \
  --output eval/reports/final-project/corpus/articles.json
```

Articles 1021/1022 have a known source alignment issue; neither is a reference
answer. Do not invent the missing Arabic heading/text. Qalam chunks preserve their
article citation so questions about numbered provisions have that identity in the
retrieved text as well as the source metadata. Existing indexes require explicit
reprocessing/reindexing to pick up the restored citation.

Use the ignored `.env.evaluation-super-candidate` profile for quality scoring. It uses the existing
NVIDIA endpoint for Nemotron VL 1B v2 embeddings and an independent Nemotron 120B
judge because the production OpenRouter free endpoint has a 50-request daily cap.
Production Docker settings and collections are unchanged. Record this endpoint and
model-alias distinction; this is not a measurement of OpenRouter capacity.

```bash
.venv/bin/python scripts/run_experiments.py \
  --dataset eval/civil_code_full.json \
  --corpus eval/reports/final-project/corpus/articles.json \
  --reports reports/civil-code-new-run \
  --env-file .env.evaluation-super-candidate --full-metrics
```

The five predefined configurations vary article/250/500-character chunking,
reranking and top-k. Every run uses disposable Qdrant storage and the same frozen
questions, local Qwen generator and source. MLflow records parameters, metrics
and reports in the local tracking database. No production index is reset.
Checkpoints retain answers before judging and permit interrupted judging to
resume without generating that answer again. Keep a checkpoint with its original
configuration/profile; use a new report directory when either changes.

The four RAGAS metrics are faithfulness, response relevancy, context precision
without reference and context recall. An additional rubric checks complete
reference correctness, including all numerical conditions and exceptions.
Negative questions use semantic refusal correctness: alternate clear refusals
are accepted, while a refusal followed by an invented answer is rejected.
Faithfulness is undefined for these expected refusals and excluded from its mean.
Accuracy is reported separately for answerable and unanswerable cases and per
language. The 0.75 gate is a pre-existing engineering threshold, not certification.

The independent judge is checked on correct and deliberately wrong Arabic and
English answers before the comparison. This sanity check is not evidence of
agreement with legal experts. Inspect individual predictions and retrieved
articles alongside aggregate metrics; source-grounded but incomplete answers can
still fail reference correctness.

## Local load test and report export

Install measurement tools separately from the application and vLLM environments:

```bash
uv venv ~/.cache/rag-final-tools
uv pip install --python ~/.cache/rag-final-tools/bin/python -r loadtest/requirements.txt
~/.cache/rag-final-tools/bin/python -m playwright install chromium --only-shell
```

After quality evaluation has finished, run the isolated API test. It uploads the
actual PDF, uses Qalam processing, indexes it into an isolated PGVector project, runs
six sequential SSE probes, then runs Locust with 50 users for three minutes and
up to three minutes of request draining. Fifty temporary project-scoped keys model
independent identities; application per-key rate limits remain enabled. The
runner stops its temporary API and removes those keys. The isolated test project's
source/chunks and PGVector collection remain for inspection. Choose an unused
project ID >= 900100 for a new independent run. `--vector-backend QDRANT` instead
uses disposable embedded storage that is removed when the run exits.

```bash
.venv/bin/python scripts/run_loadtest.py \
  --env-file .env.evaluation \
  --source /mnt/g/Downloads/1576751803.pdf \
  --project 900102 --port 8003 \
  --locust ~/.cache/rag-final-tools/bin/locust \
  --reports eval/reports/final-project/load

~/.cache/rag-final-tools/bin/python scripts/report_final_project.py \
  --configurations eval/reports/final-project/configurations-super-candidate-v2
```

Do not run load and quality tests concurrently on the shared laptop GPU. A
nonzero Locust exit code is retained as measured failure, not changed to a pass.
Vendor limits, queueing and request timeouts are part of the observed profile.
This direct-API test does not measure nginx or the production OpenRouter route.
The final JSON records counts and histograms after request draining; periodic CSV
and HTML snapshots can omit a trailing request. Stage histograms include
queue waits and use extended buckets; reported p95 bucket bounds are approximate.
SSE timing measures the first delivered nonempty text, excluding the earlier
`sources` event. Guarded output is buffered, so it must not be described as an
unbuffered 200-ms token stream. Output counts use the served Qwen tokenizer;
tokens per second are labeled as end-to-end throughput.

The report generator requires all five complete 62-case reports and actual load
and SSE artifacts. It exports Markdown, HTML, PNG and PDF figures. Browser exports
and screenshots are taken from those real results. Its conclusions retain
observed Arabic generator errors and LLM-judge disagreements; passing an automated
threshold does not remove those findings.

When judge capacity is unavailable, finish actual generation independently with
`run_experiments.py --capture-only --resume` using the same arguments. This writes
`.capture.json` and `capture-comparison.json`, with `awaiting_judge` status and no
invented quality scores. Score those exact saved outputs without a GPU or new
generation:

```bash
.venv/bin/python scripts/score_captured.py \
  --env-file .env.evaluation-super-candidate \
  --reports eval/reports/final-project/configurations-super-candidate-v2
```

After all five score files exist, the ordinary `run_experiments.py --resume`
command records them in MLflow and writes the scored comparison without rerunning
generation. Use the same new scoring directory and `.env.evaluation-super-candidate` for
that command. Keep judges consistent across configurations. A different judge or
rubric requires a separate report directory and complete regrading. A persisted
`judge-profile.json` prevents accidental mixing; unversioned legacy grades cannot
be resumed into the revised rubric. The report's explicit
`--allow-incomplete` mode accepts all five captured runs but marks pending scores
as n/a; it never claims that scoring or quality selection is complete.

The final `mlflow-release.json` identifies five finished `final-scored-*` runs
under `2026-10-16-super-candidate-v2`, each with all 62 scores from the original
Super endpoint and revised rubric. The final audit verifies all 310 grades against
the original captured answers and reproduces all overall/per-language aggregates.
Eighteen earlier runs remain in the database. The earlier VL snapshot is preserved
as `mlflow-release-unicode-v2.json`: its five `final-measured-*` runs under
`2026-10-16-unicode-v2` include two complete scores and three capture/partial
measurements. Their `provider_limited` tags are not failed legal judgments.
The exported database retains its original local artifact paths; the actual
report files are also included separately in the evidence ZIP.

The completed comparison uses `nvidia/nemotron-3-super-120b-a12b` with the same revised
rubric. A real RAGAS request and all 28 controls passed, including a repeat after
the format-retry fix. It uses `configurations-super-candidate-v2/`, separate from
the VL regrade and legacy reference scores. Its initial successful profile used
2.1-second request spacing, two HTTP slots and three grading workers. After 429s
recurred during the last configuration, recovery switched to five-second spacing,
one HTTP slot and one grading worker. A malformed rubric gets
one format-only retry at 4,096 tokens; a second invalid response fails. Missing or
quoted booleans are never cast into grades. Valid saved grades and exact
input/model/options RAGAS cache entries remain reusable.

If a measurement fails after a successful PGVector ingestion, preserve its report
directory and use `--reuse-index PATH_TO_PRIOR_REPORTS` for a measurement-only
retry. The runner compares saved/current index information before reuse. This
does not reset a collection or repeat uploads/embeddings. The original baseline
used Qdrant and an unseeded workload; the later PGVector run has a fixed seed, so
they are operational observations rather than a controlled backend or fix study.

The initial local profile spaced judge HTTP requests by 2.1 seconds; the latest
recovery profile increases that spacing to five seconds
(`RAG_EVAL_REQUEST_INTERVAL_SECONDS`) and permits one in flight. One case-grading
worker (`RAG_EVAL_GRADING_CONCURRENCY=1`) reduces prototype pressure after the
initial two-request/three-worker profile encountered repeated 429 responses. A 429
response suspends judge requests for at least 60 seconds or the supplied numeric
`Retry-After`, whichever is longer. Transient provider failures resume from saved
answers/scores with bounded retries; authentication/configuration errors do not.
Vendor capacity can still be unavailable below an advertised request-rate limit.
Successful reference rubrics are cached separately from RAGAS stages. Invalid
JSON/schema or length-terminated judge output cannot become a score. A rubric
request that reports length termination at 2,048 output tokens receives one retry
at 4,096. Other malformed output receives one format-only reminder at 4,096 tokens;
a second invalid response enters bounded recovery. Neither missing nor quoted
booleans are accepted as grades.
Diagnostics retain the actual stop reason and output in the ignored judge cache.

The earlier VL recovery profile used `nvidia/nemotron-3.5-super-vl-120b-a12b` on the
same existing NVIDIA account, with temperature zero and
`RAG_EVAL_JUDGE_EXTRA_BODY={"chat_template_kwargs":{"enable_thinking":false}}`.
It reached five-second request spacing, one HTTP request in flight and one grading
worker after repeated 429 responses with the original 2.1-second spacing. A fresh
availability probe alone is insufficient: actual scoring can still be throttled.
An attempted two-request/three-worker schedule encountered provider 500s;
the serial schedule resumed from its saved grades/cache. Generation has already
completed and is never called by offline scoring. The request concurrency option
`RAG_EVAL_MAX_INFLIGHT_REQUESTS` accepts 1–4, with a conservative default of 1;
`RAG_EVAL_GRADING_CONCURRENCY` defaults to 1. These are scheduling choices, not
changes to the frozen answers or grading criteria. Optional
`RAG_EVAL_HTTP_DIAGNOSTICS=1` saves failed request bodies and response status/body
inside the private judge cache, excluding authorization headers.
Recovery stops after four consecutive failures without completed-case or new
persisted-stage progress. The actual DiskCache row count detects successful
partial grading work; diagnostic files and failed responses do not reset the
counter. `--wait-seconds` bounds waiting/recovery even when stages keep advancing.
After provider capacity recovers, rerun the same command to reuse saved answers,
scores and cached stages. Keep incomplete aggregate metrics n/a.

The `candidate-unicode-v2` rubric sends Arabic directly rather than JSON Unicode
escapes, identifies `candidate_answer` separately from the reference, forbids
replacing candidate numbers/claims with reference text, and explicitly rejects
missing required conditions. All 28 bilingual numerical/completeness/refusal
controls passed with this profile. The preceding legacy-rubric attempt failed
11 controls and is retained for audit; it was not used to score the comparison.
The new scores must cover all five configurations independently, including the
two with legacy reports. Existing captured answers and exact contexts are reused.
