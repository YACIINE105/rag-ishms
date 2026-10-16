# Try the complete pipeline

The local application is ready for a single-user demonstration. A fresh test on
16 October 2026 used the normal nginx/Docker API, PGVector, the configured
OpenRouter embeddings, the GPU BGE reranker and local Qwen. Project **900200**
contains a two-page excerpt from the supplied Civil Code PDF, indexed as **16
chunks**. Existing projects 6 and 8 were preserved.

Start the services from the repository root if needed:

```bash
systemctl --user start rag-ishms-reranker.service rag-ishms-generator.service
docker compose -f docker/docker-compose.yml up -d
curl --fail-with-body http://localhost/health
```

## Import into Postman

1. Import `postman/RAG_ISHMS_Full_Pipeline.postman_collection.json` and
   `postman/Local.postman_environment.json` from this repository. Copies are also
   in `G:\Downloads`.
2. Select the **RAG-ISHMS local** environment. Set `api_key` to the value of
   `RAG_API_KEY` in `docker/env/.env.client`. The collection sends that value as
   `X-API-Key`; generation/embedding provider keys are separate.
3. Keep `base_url=http://localhost`, `project_id=900200`, and `use_qalam=false`
   for the supplied sample. In request **02 Upload PDF**, select
   `G:\Downloads\RAG_ISHMS_Pipeline_Sample.pdf` under **Body → form-data → file**.
4. Send requests manually in numeric order. Repeat status requests 04 and 06
   until `state` is `succeeded` and the returned chunk/vector count is positive.
   A single unpaused collection run does not wait for background jobs.

The collection captures file IDs, job IDs and the last normal answer's request
ID automatically using response scripts. Both exported files have a blank API
key. Response-script behavior follows the
[Postman response scripting reference](https://learning.postman.com/docs/tests-and-scripts/write-scripts/postman-sandbox-reference/pm-response/).

| Request | What to check |
|---|---|
| 01 Health | HTTP 200; all dependencies ready |
| 02 Upload PDF | `file_id` returned |
| 03 Start processing | HTTP 202; processing job ID |
| 04 Poll processing | `succeeded`, with nonzero `inserted_chunks` |
| 05 Start indexing | HTTP 202; indexing job ID |
| 06 Poll indexing | `succeeded`, with nonzero `inserted_items_count` |
| 07 Index information | `record_count` is positive; sample has 16 |
| 08 Search | Nonempty `indexed_vectors` |
| 09 Answer English | Answer, cited sources and `request_id` |
| 10 Answer Arabic | Arabic answer and cited sources |
| 11 Stream answer | `sources`, `token`, then `done`; no `error` event |
| 12 Feedback | HTTP 200; neutral score 0 by default |
| 13 Out-of-scope question | Inspect that the model refuses the cake-recipe request |

To try a question immediately, skip upload/indexing and send request 09 to the
already indexed project 900200:

```json
{"text":"According to Article 2, how can an existing legislative provision be repealed?","limit":5}
```

The fresh English response preserved all three routes: express repeal by a
later law, an inconsistent later provision, or regulation of the same matter
anew. Arabic wording was less polished. The out-of-scope test refused and still
returned retrieved legal passages; sources alone do not establish correctness.

## Use your own document

Choose an unused positive project ID, select your file in request 02, and change
the question in requests 08–11 to match it. Leave `do_reset=0`. Uploading the same
filename replaces that asset within the selected project.

Use `use_qalam=false` for general PDFs and this two-page sample. The sample was
copied from source pages 1–2; the copy loses table structure used by Qalam.
The unchanged original `G:\Downloads\1576751803.pdf` still produces 1,149 articles
with Qalam; set `use_qalam=true` for that original structured legal document.
The full-corpus API ingestion and evaluation are documented separately in the
[measured report](final-project-report.md).

Indexing the full PDF consumes substantially more free-provider requests than
the sample. Poll an existing failed/pending job and inspect its result before
retrying. Do not repeatedly upload/re-index solely to ask another question.

## Verified results and limits

The fresh test completed upload, extraction, indexing, retrieval, English/Arabic
answers, SSE, feedback and refusal through `http://localhost`. English answer
time was 6.86 seconds, Arabic 12.93 seconds, and buffered SSE completion 8.25
seconds; these are single observations. Evidence is saved locally under
`eval/reports/pipeline-smoke-2026-10-16/`.

The test found and fixed misleading success for empty extraction/indexing.
Live failure checks passed after rebuilding Docker; 249 tests and 12 subtests
passed with 86.79% coverage. The Postman v2.1 collection schema and all 13 script
syntaxes were validated. API calls were executed with Python requests; no
Postman GUI execution is claimed.

The earlier 310-answer evaluation and verified archive remain a frozen snapshot
of their recorded source commit and 244-test run. No benchmark answers were
regenerated for this follow-up. Model omissions/numerical errors, judge errors
and the failed 50-user capacity target remain. Legal expert review, a larger
independent benchmark and optional external integrations are separate work.
