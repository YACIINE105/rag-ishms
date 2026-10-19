# Try the PDF → Qalam → RAG pipeline

Upload the original **170-page Civil Code PDF** directly. The existing Qalam
library extracts bilingual articles; the application creates separate Arabic and
English article chunks, indexes them, retrieves and reranks passages, then asks
local Qwen. You do not need to convert the PDF into JSON yourself.

Start the services from the repository root if needed:

```bash
systemctl --user start rag-ishms-reranker.service rag-ishms-generator.service
docker compose -f docker/docker-compose.yml up -d
curl --fail-with-body http://localhost/health
```

## Import into Postman

1. Import `postman/RAG_ISHMS_Full_Pipeline.postman_collection.json` and
   `postman/Local.postman_environment.json`. Copies are in `G:\Downloads`.
2. Select **RAG-ISHMS local**. Set `api_key` to `RAG_API_KEY` from
   `docker/env/.env.client`. The collection sends it as `X-API-Key`; provider
   credentials are separate. Both exported files have a blank API key.
3. Keep `base_url=http://localhost`, `project_id=900201`, and `use_qalam=true`.
   In **02 Upload PDF → Body → form-data → file**, select the original
   **`G:\Downloads\1576751803.pdf`**. Do not manually set a JSON content type for
   this multipart upload; Postman sets the multipart boundary.
4. Send requests manually in numeric order. Repeat status requests 04 and 06
   until `state` is `succeeded` and the corresponding count is positive. A single
   unpaused collection run does not wait for background jobs.

The collection captures file IDs, job IDs and the last normal answer's request
ID using [Postman response scripts](https://learning.postman.com/docs/tests-and-scripts/write-scripts/postman-sandbox-reference/pm-response/).
Request **03 Start processing** sends:

```json
{
  "file_id": "{{file_id}}",
  "W_qalam": true,
  "do_reset": 0
}
```

`file_id` comes from upload. `W_qalam=true` selects the existing Qalam parser;
character chunk-size/overlap options do not control article chunks in this mode.
Wait for processing to finish before indexing with `{"do_reset":0}`.

| Request | What to check |
|---|---|
| 01 Health | HTTP 200; all dependencies ready |
| 02 Upload PDF | `file_id` returned |
| 03 Start processing | HTTP 202; processing job ID |
| 04 Poll processing | `succeeded`, `processing_mode=qalam`, `inserted_chunks=2297` for this PDF |
| 05 Start indexing | HTTP 202; indexing job ID |
| 06 Poll indexing | `succeeded`, `inserted_items_count=2297` for this project |
| 07 Index information | `record_count=2297` |
| 08 Search | Nonempty `indexed_vectors`; article/language/page metadata |
| 09 Answer English | Answer, cited sources and `request_id` |
| 10 Answer Arabic | Arabic answer and cited sources |
| 11 Stream answer | `sources`, `token`, then `done`; no `error` event |
| 12 Feedback | HTTP 200; neutral score 0 by default |
| 13 Out-of-scope question | Inspect refusal of the cake-recipe request |

Project **900201 is already indexed** from the verification run. To ask now,
skip requests 02–06 and start with 07 or 08. To repeat the entire upload/process/
index flow, choose another unused positive project ID first; the full re-index
consumes another 36 upstream embedding requests.

To ask a question, send request 09 with:

```json
{"text":"According to Article 2, how can an existing legislative provision be repealed?","limit":5}
```

## Keep the full source and article structure

The supplied PDF is `G:\Downloads\1576751803.pdf`, also available inside WSL at
`/mnt/g/Downloads/1576751803.pdf`. Its SHA-256 is
`2d6419fb262dab712f7bf5f6e31834bea74fbcf03b78ae081dd35d156915eebf`.
Qalam produces 1,149 article records and 2,297 nonempty language chunks: 1,148
Arabic and 1,149 English. Known source defects around Articles 1021–1022 remain;
the parser does not invent the missing Arabic text for Article 1022.

The earlier copied two-page sample in project 900200 uses ordinary extraction;
copying pages removed table structure Qalam needs. Use the unchanged full PDF
and Qalam for this walkthrough. Existing user projects 6 and 8 remain separate.

To test another document, choose an unused positive project ID and change the
questions to match it. Qalam supports structured legal PDFs with article
headings. Ordinary processing remains available for general PDFs/TXT files by
setting `use_qalam=false`. Uploading the same filename replaces that asset within
the selected project. Leave `do_reset=0`.

## Upload size and upstream limits

Nginx allows request bodies up to 100 MiB; the application also enforces its
configured `FILE_MAX_SIZE` in MiB. Reload nginx after changing its mounted
configuration. The original 2.6 MB PDF previously hit nginx's implicit 1 MiB
limit before reaching Qalam; the explicit limit fixes that upload failure.

The current local API uses `INDEX_BATCH_SIZE=64` and
`INDEX_BATCH_DELAY_SECONDS=3.5`: 2,297 chunks require 36 embedding requests.
The embedding model/provider are unchanged. Each search or answer also needs an
upstream query embedding. Free-provider quotas can still interrupt indexing or
queries. Inspect the existing job and partial collection before retrying; an
index retry embeds all project chunks again. Once indexed, ask questions without
re-uploading or re-indexing the document.

## Verification scope

The full-PDF test completed upload, Qalam processing, all 36 indexing batches
(2,297 vectors), reranked retrieval, cited English/Arabic answers, SSE `done`,
neutral feedback and out-of-scope refusal through the normal nginx/Docker API.
English and Arabic Article 2 answers retained all three repeal routes. Observed
answer times were 7.34 seconds English, 9.09 seconds Arabic and 6.46 seconds for
buffered SSE completion; these are single observations. Refusal still returned
legal sources; sources alone do not establish correctness.

Actual API evidence for this full PDF is saved locally in
`eval/reports/qalam-pipeline-2026-10-16/`. The earlier sample smoke remains under
`eval/reports/pipeline-smoke-2026-10-16/`. Structural checks do not establish legal
accuracy. The existing 249-test run and 12 subtests passed with 86.79% coverage;
this follow-up changes proxy configuration and the Postman walkthrough.

The earlier 310-answer evaluation and verified archive remain a frozen snapshot.
No benchmark answers were regenerated. Model omissions/numerical errors, judge
errors and the failed 50-user capacity target remain. Legal expert review and a
larger independent benchmark are separate work.
