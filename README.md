# ishms-rag-app

this is a rag api that was created to serve the ISHMS software.


## REQUIREMENTS
- Python 3.12

#### Install Dependencies

```bash
sudo apt update
```
```bash
sudo apt install libpq-dev gcc python3-dev
```


### Install Python using Miniconda
1) Download and install mini coda from [here](https://docs.anaconda.com/free/miniconda/#quick-command-line-install)

2) Create a new enviroment using the follwing command:
```bash
 conda create -n rag-ishms python=3.12
```
3) Activate the enviroment :
```bash
 conda activate rag-ishms
```

### Install the requires packages
```bash
 pip install -r requirements.txt
```

### Run the FastAPI server

```bash  
 cd ~/rag-ishms/src
```

```bash
 uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Run Dokcer Compose Service
```bash
 cd docker
 cp .env.example .env
```

- update `.env` with your credentials


### for running the drug checker manually
```bash  
 cd ~/rag-ishms/src
```
```bash  
 pyhton drug_checker.py
```

### Run the model
```bash
 cd ~/llama.cpp/build/bin
```
```bash
 ./llama-server -m /mnt/g/ishms/modeel/medgemma-4b-it-Q8_0.gguf -ngl 99 --host 0.0.0.0 --port 8080
```

### installing cloudflare to access the server
 -downloading the cloudflare package
```bash
 wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
```
 - Install it
```bash
 sudo dpkg -i cloudflared-linux-amd64.deb
```
 - Verify
```bash
 cloudflared --version
```

### running cloudflare after runnig the depends

```bash
 cloudflared tunnel run rag-ishms
```



## API responses and readiness

Search and answer requests use POST with a JSON body containing `text` and an
optional `limit` (default 5, range 1–20). Empty/blank questions and questions over
`INPUT_MAX_CHARACTERS` return 422.

`POST /api/v1/nlp/index/answer/{project_id}` returns `signal`, `answer`,
`sources` (original `asset_name` and one-based PDF `page`), `request_id`, and
`prompt_version`. Text files have a null page. Sources identify the retrieved
context supplied to the model; they do not assert which passage supports each
individual generated claim. Prompt text and chat history are not public response
fields. Reprocess and rebuild indexes for legacy documents missing metadata;
new vector records also include `asset_id` for counting and asset deletion.

`GET /health` returns 200 when PostgreSQL, the vector store, generation and
embedding providers, and the reranker are ready; otherwise it returns 503.
`documents_indexed` counts distinct assets represented in the vector index,
not uploaded files or chunks. It is null if the vector check fails. Checks are
bounded to five seconds and errors do not expose connection strings or API keys.
Local model checks inspect the loaded model context; remote model probes check
authentication/reachability without generating tokens. These checks do not prove
that every remote model supports successful inference. Qdrant counting scans
payloads; large indexes may require a dedicated indexed asset registry later.

Synchronous embedding, reranking, and generation run in worker threads with
one lock per shared provider. The container uses one worker to keep one copy of
each model and allow exclusive access to embedded Qdrant storage. Docker probes
`/health` every 30 seconds after a 180-second startup allowance. Nginx waits for
initial application health through Compose; this is not ongoing traffic gating.

Run the test suite and coverage gate from the repository root:

```bash
uv sync --group dev
uv run pytest --cov=src --cov-fail-under=70
```

The tests use stubbed model providers and temporary local Qdrant storage; no
model weights or paid API calls are needed. Deployment verification still needs
the real PostgreSQL service, configured models, and an indexed PDF.


## Structured logging and tests

Responses return `X-Request-ID`; `/answer` uses the same value in `request_id`.
An incoming ID is reused when it contains 1–128 letters, digits, dots, underscores,
colons or hyphens; otherwise a new UUID is generated. JSON records include
`timestamp`, `level`, `logger`, `message`, `request_id`, and `project_id` (null
outside a project request). Worker-thread model logs keep the request context.

`retrieve.done`, `rerank.done`, and `generate.done` report scores/counts and
latency. Token counts come from provider usage when available, otherwise null.
`prediction.done` always logs query, retrieved IDs and answer; these records are
never sampled. `HTTP_ACCESS_LOG_SAMPLE_RATE` (default 0.1) only samples successful
HTTP access events. Errors are retained. `LOG_LEVEL=DEBUG` enables prompt logs.

Zero retrieval hits return HTTP 200 with an explicit no-information answer and
empty sources. Provider failures remain errors. Chunking now honors both size
and overlap within each page and preserves citation metadata; reprocess existing
documents to use the new chunk boundaries.

Pytest uses mocked model SDKs and temporary Qdrant storage, without downloading
weights. The default run enforces 70% source coverage; mark tests needing real
services or weights with `@pytest.mark.slow`. Only standalone demo scripts and
Alembic migration scripts are excluded from the coverage calculation.
See [Docker setup](docker/README.md) for non-root permissions, cache/model files,
and the optional Qdrant service profile.

## Code quality

Install the development tools and Git hook from the repository root:

```bash
uv sync --group dev
uv run pre-commit install
```

Check the complete repository before committing:

```bash
uv run pre-commit run --all-files
uv run pytest
```

The hooks format Python, sort imports, check common lint errors, and check YAML,
merge conflicts, whitespace, file endings, and private keys. Comments and
commented-out code are preserved. Review automatic fixes and stage the updated
files before retrying a commit. Each contributor must install the hook locally.
The private-key hook does not scan ordinary API tokens.
