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
images. Evaluation remains manual until model access and the dataset baseline
are verified. To make it a release gate later, arrange trusted evaluation on
main pushes and make publishing depend on its success. Never expose evaluation
secrets to untrusted pull-request code.
