# Egyptian Civil Code RAG evaluation

The handbook's Project 2 checklist (page 69) specifies a 20-question CI gate
at RAGAS faithfulness 0.75. Page 64 links the input corpus:
https://sadanykhalifa.com/uploads/Laws/1576751803.pdf

## Source and dataset

The source snapshot is saved as `corpus/egyptian-civil-code.pdf`.
`golden_set.json` contains 20 source-backed draft cases: 15 Arabic questions
and 5 English questions. Each includes an expected answer, reference passage,
article number, one-based PDF pages, and the source SHA256. The benchmark
measures answers about this source version, not current-law advice. Review
these draft expected answers before relying on the scores for production.

`corpus/articles.json` contains the 20 corresponding English article fixtures.
The extractor reads the left English column separately from the right Arabic
column and preserves Article 148's continuation across pages. Reproduce it:

```bash
uv run python scripts/build_eval_corpus.py
```

These fixtures are a limited CI benchmark, not the complete structured Arabic
corpus required by the handbook's separate ingestion/DVC deliverables.
The broader monitoring exercise (50+ questions and all four RAGAS metrics)
is also outside this CI task.

## Evaluation

Configure `src/.env` with application settings for the embedding and generation
providers. Set `RAG_EVAL_JUDGE_API_KEY` and `RAG_EVAL_JUDGE_MODEL` in your shell.
Optionally set `RAG_EVAL_JUDGE_BASE_URL` for an OpenAI-compatible JSON-capable
judge endpoint. Model generation, embedding, and judging can incur charges.
Questions, generated answers, source context, and expected answers are sent to
the judge. Choose an endpoint appropriate for the evaluation data.

From the repository root:

```bash
uv run --group eval python scripts/evaluate_rag.py --corpus eval/corpus/articles.json
```

With `--corpus`, evaluation builds a disposable embedded Qdrant index from the
article fixtures using the application's configured embedding provider, then
runs its retrieval, reranking, templates, and generation. The temporary index
is discarded afterward. It never resets the configured application index and
does not require an existing legal project or an external vector service.
Without `--corpus`, evaluation reads an existing isolated index instead.

The runner reuses application initialization, so a complete application settings
file is still required. Remote model services must be reachable. Local GGUF
models and weights must be provisioned if used. A model service is simpler for
GitHub-hosted runners; localhost on GitHub is not your computer.

## Scores and reports

Faithfulness uses pinned RAGAS 0.4.3 and the exact chunks passed to generation.
The mean score must be at least 0.75. A separate LLM rubric checks consistency
with the expected answer; its aggregate reference accuracy must also reach
0.75, preventing an evasive but supported answer from automatically passing.
This initial set expects answerable questions, so zero retrieval scores zero.
Malformed judge results and non-finite RAGAS values cannot pass.

Reports go under `eval/reports/`. Exit codes are 0 for passing, 1 for a failed
score gate, and 2 for a configuration, dataset, or provider error. Reports include
source text and answers; restrict access as appropriate. Calibrate the judge
against human labels before turning this draft baseline into a release gate.

## GitHub manual job

Create an environment named `rag-evaluation` with approval protection.
Add secrets `RAG_EVAL_APP_ENV` (the full application settings file) and
`RAG_EVAL_JUDGE_API_KEY`. Add variables `RAG_EVAL_JUDGE_MODEL` and optionally
`RAG_EVAL_JUDGE_BASE_URL`. The runner must reach the configured model providers.

Select **Actions > CI > Run workflow** and enable **Run the reviewed RAG
evaluation**. The manual job rebuilds the temporary index and saves the report
as an artifact for seven days, including failed evaluations. It does not publish
images. Main pushes must pass the same evaluation gate before publishing.
Missing configuration or failed scoring blocks publishing. Configure the
environment before merging this workflow into main. Never expose evaluation
secrets to untrusted pull-request code.

## Model identity and collection names

Collections use `collection_{model_slug}_{fingerprint}_{dimension}_{project_id}`.
The fingerprint includes the exact embedding model ID, provider, and dimension;
the readable slug is shortened to keep PostgreSQL index identifiers within
63 bytes. Names are shared by indexing, querying, and document deletion.
Changing the model ID or provider selects a different collection even when the
vector dimensions match. Reindex documents before querying with the new name.
Legacy collections are preserved, but are not used as a fallback: renaming their
old vectors does not make them compatible with a new embedding model.

Successful evaluation reports include `index_metadata` (full embedding model ID,
provider, dimension, fingerprint), `collections` by project, `generation_model`,
`generation_provider`, and `judge_model`. Application `prediction.done` logs
include the same index metadata and collection name, including zero-hit answers.
Use these fields as metadata when adding Langfuse tracing; this change does not
install or configure a Langfuse exporter.

This identifies model configuration, not an immutable model-weights snapshot.
Use revision-pinned model IDs/paths when available. Normalization, chunking,
corpus versions, and atomic alias switching are not implemented by this naming
change and need separate versioning if those settings change.

## Full-project evaluation tools

`eval/monitoring_set.json` contains 52 draft cases: 50 bilingual answerable/
paraphrase questions and two out-of-corpus cases. Human review is still required.
The 20-case CI benchmark remains unchanged.

For all four RAGAS metrics, set `RAG_EVAL_EMBEDDING_MODEL` to an embedding model
available at the judge's configured OpenAI-compatible endpoint, then run:

```bash
uv run --group eval python scripts/evaluate_rag.py --corpus eval/corpus/articles.json --dataset eval/monitoring_set.json --minimum-cases 50 --full-metrics
```

The judge uses temperature 0. Reports include each score, latency, prompt/model
identity and separate language summaries. Each language must meet the configured
faithfulness and reference-accuracy gates; a high English average cannot hide a
failing Arabic result. Out-of-corpus cases check exact safe refusal, do not receive
invented faithfulness scores, and still count toward reference accuracy. The safe
refusal check is intentionally strict. Adding valid refusal wording requires updating
the evaluator. Other three metric scores are reported, without uncalibrated gates.

Compare five configurations when inference is available:

```bash
uv run --group eval python scripts/run_experiments.py
```

The optional MLflow skinny client logs to reports/mlflow.db and report artifacts.
No tracking server is required. A full MLflow UI/registry deployment is not installed.
Experiments compare article chunks, 250/500-character windows, reranker off/on and
k=3/5. Legal article chunking stays the application default for Qalam documents.
Rebuild indexes are isolated; do not repoint this tool at patient-data projects.

The DVC pipeline rebuilds the complete 1,149-article bilingual corpus in
`data/corpus/articles.json`; the original fixtures are still the limited CI corpus.
Article 1022's missing Arabic source text is recorded in source-issues.json,
checksum-bound to this PDF. Validation rejects unexplained missing text/gaps.
The record is flagged needs_review, rather than populated with fabricated text.

Nightly runs are disabled unless GitHub variable RAG_NIGHTLY_EVAL_ENABLED=true.
When enabled they run the full set/four metrics, require the judge embedding variable
and existing protected evaluation secrets, and save the report artifact. They do
not publish images or push reports into your private Docker host automatically.
