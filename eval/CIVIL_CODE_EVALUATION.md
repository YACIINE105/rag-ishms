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

Use the ignored `.env.evaluation` profile for this local run. It uses the existing
NVIDIA endpoint for Nemotron VL 1B v2 embeddings and an independent Nemotron 120B
judge because the production OpenRouter free endpoint has a 50-request daily cap.
Production Docker settings and collections are unchanged. Record this endpoint and
model-alias distinction; this is not a measurement of OpenRouter capacity.

```bash
.venv/bin/python scripts/run_experiments.py \
  --dataset eval/civil_code_full.json \
  --corpus eval/reports/final-project/corpus/articles.json \
  --reports eval/reports/final-project/configurations \
  --env-file .env.evaluation --full-metrics --resume
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
