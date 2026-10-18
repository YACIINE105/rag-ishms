import hashlib
import json
import logging
import re
from time import perf_counter
from typing import List

from starlette.concurrency import run_in_threadpool

from models.db_schems import DataChunk, Project
from models.enums import DataBaseEnum
from stores.llm.LLMEnums import DocumentTypeEnum
from utils.guardrails import INJECTION, protect_query, redact_pii, redact_stream
from utils.inference import run_serialized
from utils.metrics import (
    GUARDRAIL_DECISIONS,
    LLM_INFLIGHT,
    LLM_STREAM_DURATION,
    LLM_TOKENS,
    LLM_TTFT,
    RAG_REQUESTS,
    RAG_RETRIEVED,
    RAG_STAGE_LATENCY,
    RAG_TOP_SCORE,
)
from utils.observability import traced, traced_stream

from .BaseController import BaseController

NO_INFORMATION = (
    "I could not find information in the indexed documents to answer your question."
)
prediction_logger = logging.getLogger("rag.prediction")


class NLPController(BaseController):
    def __init__(
        self,
        generation_client,
        embedding_client,
        vector_db_client,
        reranker_client=None,
        template_parser=None,
    ):
        super().__init__()

        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.vector_db_client = vector_db_client
        self.template_parser = template_parser
        self.reranker_client = reranker_client
        self.logger = logging.getLogger("uvicorn.error")

    def prompt_version(self):
        version = getattr(self.template_parser, "version", None)
        return version if isinstance(version, str) else "rag-v1"

    def get_index_metadata(self):

        # step 1 : get the embedding model name

        embedding_model_id = getattr(self.embedding_client, "embedding_model_id", None)

        if not isinstance(embedding_model_id, str) or not embedding_model_id.strip():
            embedding_model_id = self.app_settings.EMBEDDING_MODEL_ID

        if not isinstance(embedding_model_id, str) or not embedding_model_id.strip():
            raise ValueError("An embedding model ID is required to identify the index")

        # step 2 : collect the model settings

        embedding_provider = getattr(self.app_settings, "EMBEDDING_PROVIDER", "unknown")
        embedding_size = self.vector_db_client.default_vector_size

        index_metadata = {
            "embedding_provider": embedding_provider,
            "embedding_model_id": embedding_model_id,
            "embedding_size": embedding_size,
        }

        # step 3 : create a fingerprint from the model settings

        model_settings = json.dumps(
            index_metadata, sort_keys=True, separators=(",", ":")
        )
        model_hash = hashlib.sha256(model_settings.encode("utf-8"))
        model_fingerprint = model_hash.hexdigest()[:12]

        index_metadata["embedding_fingerprint"] = model_fingerprint

        return index_metadata

    def create_collection_name(self, project_id: str):

        # step 1 : get the model settings and check the project id

        index_metadata = self.get_index_metadata()
        project_id = str(project_id)

        if not re.fullmatch(r"[0-9]+", project_id):
            raise ValueError("Project ID must contain digits only")

        # step 2 : make the model name safe for the collection name

        embedding_model_id = index_metadata["embedding_model_id"]
        model_slug = re.sub(r"[^a-z0-9]+", "_", embedding_model_id.lower())
        model_slug = model_slug.strip("_") or "model"

        # step 3 : add the fingerprint, vector size and project id

        collection_suffix = (
            f"_{index_metadata['embedding_fingerprint']}"
            f"_{index_metadata['embedding_size']}_{project_id}"
        )

        # PostgreSQL allows 63 bytes, including the 11 bytes used by _vector_idx.
        model_name_limit = 52 - len("collection_") - len(collection_suffix)

        if model_name_limit < 1:
            raise ValueError("Index identity exceeds the collection name limit")

        model_slug = model_slug[:model_name_limit]
        collection_name = f"collection_{model_slug}{collection_suffix}"

        return collection_name

    async def reset_vector_db_colection(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        await self.vector_db_client.delete_collection(collection_name=collection_name)

    async def get_vector_db_collection_info(self, project: Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vector_db_client.get_collection_info(
            collection_name=collection_name
        )

        return collection_info

    async def index_into_vector_db(
        self,
        project: Project,
        chunks: List[DataChunk],
        chunks_ids: List[int],
        do_reset: bool = False,
    ):
        if (
            not chunks
            or len(chunks) != len(chunks_ids)
            or len(set(chunks_ids)) != len(chunks_ids)
            or any(chunk_id is None for chunk_id in chunks_ids)
        ):
            return False

        # step 1 : get collection name

        collection_name = self.create_collection_name(project_id=project.project_id)

        # step 2 : manage items

        texts = [c.chunk_text for c in chunks]
        metadata = [
            {
                **(c.chunk_metadata or {}),
                "asset_id": c.chunk_asset_id,
                "chunk_id": chunk_id,
            }
            for c, chunk_id in zip(chunks, chunks_ids)
        ]
        vectors = await run_serialized(
            self.embedding_client,
            self.embedding_client.embed_text,
            text=texts,
            document_type=DocumentTypeEnum.DOCUMENT.value,
            input_type="passage",
        )
        if not vectors or len(vectors) != len(texts):
            return False
        batch_size = 50

        ###################
        # for i in range(0, len(texts), batch_size):
        #     batch_texts = texts[i:i + batch_size]
        #     batch_vectors = self.embedding_client.embed_texts(
        #         texts=batch_texts,
        #         document_type=DocumentTypeEnum.DOCUMENT.value
        #     )
        #     if batch_vectors is None:
        #         self.logger.error(f"Failed to embed batch starting at index {i}")
        #         continue
        #     vectors.extend(batch_vectors)
        #####################

        # step 3 : create collection if not exists (if do reset : delete collections)

        _ = await self.vector_db_client.create_collection(
            collection_name=collection_name,
            embedding_size=self.embedding_client.embedding_size,
            do_reset=do_reset,
        )
        # step 4 : insert into  vector db

        is_inserted = await self.vector_db_client.insert_many(
            collection_name=self.create_collection_name(project_id=project.project_id),
            texts=texts,
            vectors=vectors,
            metadata=metadata,
            record_ids=chunks_ids,
            batch_size=batch_size,
        )

        return bool(is_inserted)

    @traced("retrieve")
    async def search_vector_db_collection(
        self,
        project: Project,
        text: str,
        limit: int = 5,
        rerank_pool: int | None = None,
    ):
        rerank_pool = rerank_pool or getattr(self.app_settings, "RERANK_POOL", 30)
        collection_name = self.create_collection_name(project_id=project.project_id)
        start = perf_counter()
        stage = "embed"
        try:
            vectors = await run_serialized(
                self.embedding_client,
                self.embedding_client.embed_text,
                text=text,
                document_type=DocumentTypeEnum.QUERY.value,
                input_type="query",
            )
            if not vectors or not vectors[0]:
                raise RuntimeError("Embedding provider returned no vector")
            elapsed = perf_counter() - start
            RAG_STAGE_LATENCY.labels("embed").observe(elapsed)
            self.logger.info(
                "embed.done", extra={"latency_ms": round(elapsed * 1000, 2)}
            )
            start = perf_counter()
            stage = "search"
            candidates = await self.vector_db_client.search_by_vector(
                collection_name=collection_name,
                vector=vectors[0],
                k=max(limit, rerank_pool),
            )
            if candidates is None or candidates is False:
                raise RuntimeError("Vector provider failed")
        except Exception:
            self.logger.exception(
                "retrieve.failed",
                extra={
                    "stage": stage,
                    "latency_ms": round((perf_counter() - start) * 1000, 2),
                },
            )
            raise
        self.logger.info(
            "retrieve.done",
            extra={
                "n_candidates": len(candidates),
                "top1_score": candidates[0].score if candidates else None,
                "latency_ms": round((perf_counter() - start) * 1000, 2),
            },
        )
        RAG_STAGE_LATENCY.labels("search").observe(perf_counter() - start)
        RAG_RETRIEVED.observe(len(candidates))
        if not candidates:
            self.logger.warning("retrieve.zero_hits")
            return []
        if self.reranker_client is None:
            return candidates[:limit]
        start = perf_counter()
        try:
            reranked = await run_serialized(
                self.reranker_client,
                self.reranker_client.rerank,
                query=text,
                documents=[c.text for c in candidates],
                top_n=limit,
            )
        except Exception:
            self.logger.exception(
                "rerank.failed",
                extra={"latency_ms": round((perf_counter() - start) * 1000, 2)},
            )
            raise
        RAG_STAGE_LATENCY.labels("rerank").observe(perf_counter() - start)
        top_score = float(reranked[0][1]) if reranked else None
        if top_score is not None:
            RAG_TOP_SCORE.observe(top_score)
        self.logger.info(
            "rerank.done",
            extra={
                "top1_score": top_score,
                "latency_ms": round((perf_counter() - start) * 1000, 2),
            },
        )
        threshold = getattr(self.app_settings, "RERANK_MIN_SCORE", None)
        if threshold is not None and top_score is not None and top_score < threshold:
            GUARDRAIL_DECISIONS.labels("retrieval_score", "refused").inc()
            return []
        if top_score is not None and top_score < getattr(
            self.app_settings, "RERANK_WARNING_THRESHOLD", 0.0
        ):
            self.logger.warning("rerank.low_score", extra={"top1_score": top_score})
        return (
            [candidates[i] for i, _ in reranked[:limit]]
            if reranked
            else candidates[:limit]
        )

    @traced("answer")
    async def answer_rag_query(
        self, project: Project, query: str, limit: int = 5, stream: bool = False
    ):
        self.last_contexts = []
        guarded = getattr(self.app_settings, "GUARDRAILS_ENABLED", False)
        if guarded:
            query = protect_query(query)
        # step 1 reterieve related docs
        retrieved_docs = await self.search_vector_db_collection(
            project=project, text=query, limit=limit
        )
        if guarded:
            filtered = [doc for doc in retrieved_docs if not INJECTION.search(doc.text)]
            if len(filtered) != len(retrieved_docs):
                GUARDRAIL_DECISIONS.labels("document_injection", "filtered").inc()
            retrieved_docs = filtered
        language = "ar" if re.search(r"[\u0600-\u06ff]", query) else "en"
        no_information = (
            "لم أجد معلومات في المستندات المفهرسة للإجابة عن سؤالك."
            if language == "ar"
            else NO_INFORMATION
        )
        if not retrieved_docs:
            RAG_REQUESTS.labels("no_hits", language).inc()
            prediction_logger.info(
                "prediction.done",
                extra={
                    "query": query,
                    "index_metadata": self.get_index_metadata(),
                    "collection_name": self.create_collection_name(project.project_id),
                    "retrieved_ids": [],
                    "answer": no_information,
                },
            )
            return {
                "answer": no_information,
                "sources": [],
                "prompt_version": self.prompt_version(),
            }

        sources = []
        seen = set()

        for doc in retrieved_docs:
            metadata = doc.metadata or {}

            asset_name = metadata.get("asset_name")

            if not asset_name:
                continue

            raw_page = metadata.get("page")

            if isinstance(raw_page, int):
                page = raw_page + 1
            else:
                page = None

            article_number = metadata.get("article_number")
            if page is None and type(metadata.get("source_page")) is int:
                page = metadata["source_page"]
            if page is None and metadata.get("source_pages"):
                page = metadata["source_pages"][0]
            key = (asset_name, page, article_number)

            if key in seen:
                continue

            seen.add(key)

            source = {"asset_name": asset_name, "page": page}
            if type(article_number) is int and article_number > 0:
                source["article_number"] = article_number
                source["citation"] = (
                    metadata.get("citation")
                    or f"{asset_name}, Article {article_number}"
                )
                if metadata.get("source_pages"):
                    source["source_pages"] = metadata["source_pages"]
            sources.append(source)

        if guarded and not sources:
            GUARDRAIL_DECISIONS.labels("grounding", "refused").inc()
            RAG_REQUESTS.labels("refused", language).inc()
            return {
                "answer": no_information,
                "sources": [],
                "prompt_version": self.prompt_version(),
            }

        self.last_contexts = [
            {
                "text": redact_pii(doc.text) if guarded else doc.text,
                "metadata": doc.metadata or {},
            }
            for doc in retrieved_docs
        ]
        # step 2 construct prompt
        start = perf_counter()
        system_prompt = await run_in_threadpool(
            self.template_parser.get, "rag", "system_prompt"
        )

        document_prompt = "\n".join(
            [
                self.template_parser.get(
                    "rag",
                    "document_prompt",
                    {
                        "document_no": i + 1,
                        "chunk_text": redact_pii(doc.text) if guarded else doc.text,
                    },
                )
                for i, doc in enumerate(retrieved_docs)
            ]
        )

        footer_prompt = self.template_parser.get(
            "rag", "footer_prompt", {"query": query}
        )

        full_prompt = "\n\n".join([document_prompt, "\n", footer_prompt])

        chat_history = [
            self.generation_client.construct_prompt(prompt=system_prompt, role="system")
        ]
        elapsed = perf_counter() - start
        self.logger.info("prompt.done", extra={"latency_ms": round(elapsed * 1000, 2)})

        if stream:
            return {
                "stream": self.stream_generation(
                    full_prompt, chat_history, language, query, guarded
                ),
                "sources": sources,
                "prompt_version": self.prompt_version(),
            }

        self.logger.debug("generate.prompt", extra={"prompt": full_prompt})
        start = perf_counter()
        LLM_INFLIGHT.inc()
        try:
            answer = await run_serialized(
                self.generation_client,
                self.generation_client.generate_text,
                prompt=full_prompt,
                chat_history=chat_history,
            )
        except Exception:
            RAG_REQUESTS.labels("llm_error", language).inc()
            self.logger.exception(
                "generate.failed",
                extra={"latency_ms": round((perf_counter() - start) * 1000, 2)},
            )
            raise
        finally:
            LLM_INFLIGHT.dec()
            RAG_STAGE_LATENCY.labels("generate").observe(perf_counter() - start)
        self.logger.info(
            "generate.done",
            extra={
                "tokens_in": getattr(answer, "tokens_in", None),
                "tokens_out": getattr(answer, "tokens_out", None),
                "latency_ms": round((perf_counter() - start) * 1000, 2),
            },
        )

        if not answer:
            RAG_REQUESTS.labels("llm_error", language).inc()
            self.logger.error("generate.failed")
            return None
        if guarded:
            filtered_answer = redact_pii(str(answer))
            if filtered_answer != str(answer):
                GUARDRAIL_DECISIONS.labels("output_pii", "redacted").inc()
                from utils.generation import GenerationText

                answer = GenerationText(
                    filtered_answer,
                    getattr(answer, "tokens_in", None),
                    getattr(answer, "tokens_out", None),
                )
        prediction_logger.info(
            "prediction.done",
            extra={
                "query": query,
                "index_metadata": self.get_index_metadata(),
                "collection_name": self.create_collection_name(project.project_id),
                "retrieved_ids": [
                    doc.metadata.get("chunk_id", doc.id) for doc in retrieved_docs
                ],
                "answer": str(answer),
            },
        )

        RAG_REQUESTS.labels("answered", language).inc()
        for token_type, attribute in (("input", "tokens_in"), ("output", "tokens_out")):
            count = getattr(answer, attribute, None)
            if isinstance(count, int) and count >= 0:
                LLM_TOKENS.labels(token_type).inc(count)
        return {
            "answer": answer,
            "sources": sources,
            "prompt_version": self.prompt_version(),
        }

    @traced_stream
    def stream_generation(self, prompt, history, language, query, guarded):
        start = perf_counter()
        LLM_INFLIGHT.inc()
        completed = False
        pieces = []
        first_token_ms = None
        raw_iterator = self.generation_client.stream_text(prompt, history)
        iterator = redact_stream(raw_iterator) if guarded else raw_iterator
        try:
            for token in iterator:
                if token and first_token_ms is None:
                    elapsed = perf_counter() - start
                    LLM_TTFT.observe(elapsed)
                    first_token_ms = round(elapsed * 1000, 2)
                    self.logger.info(
                        "generate.first_token", extra={"latency_ms": first_token_ms}
                    )
                pieces.append(token)
                yield token
            if not pieces:
                raise RuntimeError("Generation provider returned no tokens")
            completed = True
            RAG_REQUESTS.labels("answered", language).inc()
            prediction_logger.info(
                "prediction.done",
                extra={"query": query, "answer": "".join(pieces), "streamed": True},
            )
        except Exception:
            RAG_REQUESTS.labels("llm_error", language).inc()
            raise
        finally:
            if not completed:
                GUARDRAIL_DECISIONS.labels("stream", "interrupted").inc()
            LLM_INFLIGHT.dec()
            elapsed = perf_counter() - start
            LLM_STREAM_DURATION.observe(elapsed)
            RAG_STAGE_LATENCY.labels("generate").observe(elapsed)
            self.logger.info(
                "generate.done" if completed else "generate.interrupted",
                extra={
                    "latency_ms": round(elapsed * 1000, 2),
                    "first_token_ms": first_token_ms,
                    "streamed": True,
                    "completed": completed,
                },
            )
            iterator.close()

    def get_conversation_history(project: Project, conversation_id):
        pass

    def save_chat_turn(self, project_id: str, chat_history: list):
        all_collection = self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_CHUNK_NAME.value not in all_collection:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_CHATS_NAME.value]
