from .BaseController import BaseController
from models.db_schems import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from models.enums import DataBaseEnum
from typing import List
import time, json
import logging
from utils.inference import run_serialized
from time import perf_counter

NO_INFORMATION = "I could not find information in the indexed documents to answer your question."
prediction_logger = logging.getLogger("rag.prediction")


class NLPController(BaseController):
    def __init__(self, generation_client, embedding_client, vector_db_client, reranker_client=None, template_parser = None):
        super().__init__()
        
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.vector_db_client = vector_db_client
        self.template_parser = template_parser
        self.reranker_client = reranker_client
        self.logger = logging.getLogger('uvicorn.error')


    def create_collection_name(self, project_id:str):
        return f"collection_{self.vector_db_client.default_vector_size}_{project_id}".strip()
    

    async def reset_vector_db_colection(self,project:Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        await self.vector_db_client.delete_collection(collection_name=collection_name)

    
    async def get_vector_db_collection_info(self, project:Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = await self.vector_db_client.get_collection_info(collection_name=collection_name)
        
        return collection_info
        
        
    async def index_into_vector_db(self, project:Project, chunks:List[DataChunk], 
                             chunks_ids:List[int], 
                             do_reset:bool = False):
        # step 1 : get collection name
        
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step 2 : manage items
        
        texts = [c.chunk_text for c in chunks]
        metadata = [{**(c.chunk_metadata or {}), "asset_id": c.chunk_asset_id, "chunk_id": chunk_id}
                    for c, chunk_id in zip(chunks, chunks_ids)]
        vectors = await run_serialized(self.embedding_client, self.embedding_client.embed_text, text=texts,
                                                   document_type = DocumentTypeEnum.DOCUMENT.value, input_type="passage")
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
        
        _ = await self.vector_db_client.create_collection(collection_name=collection_name,
                                                embedding_size = self.embedding_client.embedding_size,
                                                do_reset = do_reset                                     
                )
        # step 4 : insert into  vector db 
        
        is_inserted = await self.vector_db_client.insert_many(
            collection_name = self.create_collection_name(project_id=project.project_id),
            texts = texts,
            vectors = vectors,
            metadata = metadata,
            record_ids = chunks_ids,
            batch_size=batch_size
        )
        
        return bool(is_inserted)
    
    
    async def search_vector_db_collection(self, project: Project, text: str,
                                          limit: int = 5, rerank_pool: int = 30):
        collection_name = self.create_collection_name(project_id=project.project_id)
        start = perf_counter()
        try:
            vectors = await run_serialized(self.embedding_client, self.embedding_client.embed_text,
                text=text, document_type=DocumentTypeEnum.QUERY.value, input_type="query")
            if not vectors or not vectors[0]:
                raise RuntimeError("Embedding provider returned no vector")
            candidates = await self.vector_db_client.search_by_vector(
                collection_name=collection_name, vector=vectors[0], k=max(limit, rerank_pool))
            if candidates is None or candidates is False:
                raise RuntimeError("Vector provider failed")
        except Exception:
            self.logger.exception("retrieve.failed")
            raise
        self.logger.info("retrieve.done", extra={"n_candidates": len(candidates),
            "top1_score": candidates[0].score if candidates else None,
            "latency_ms": round((perf_counter()-start)*1000, 2)})
        if not candidates:
            self.logger.warning("retrieve.zero_hits")
            return []
        if self.reranker_client is None:
            return candidates[:limit]
        start = perf_counter()
        try:
            reranked = await run_serialized(self.reranker_client, self.reranker_client.rerank,
                query=text, documents=[c.text for c in candidates], top_n=limit)
        except Exception:
            self.logger.exception("rerank.failed")
            raise
        top_score = float(reranked[0][1]) if reranked else None
        self.logger.info("rerank.done", extra={"top1_score": top_score,
            "latency_ms": round((perf_counter()-start)*1000, 2)})
        if top_score is not None and top_score < getattr(self.app_settings, "RERANK_WARNING_THRESHOLD", 0.0):
            self.logger.warning("rerank.low_score", extra={"top1_score": top_score})
        return [candidates[i] for i, _ in reranked[:limit]] if reranked else candidates[:limit]

    async def answer_rag_query(self, project:Project, query:str, limit:int = 5):
        # step 1 reterieve related docs 
        retrieved_docs = await self.search_vector_db_collection(project=project, text=query, limit=limit)
        if not retrieved_docs:
            prediction_logger.info("prediction.done", extra={"query": query,
                "retrieved_ids": [], "answer": NO_INFORMATION})
            return {"answer": NO_INFORMATION, "sources": [], "prompt_version": "rag-v1"}
        
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

            key = (asset_name, page)

            if key in seen:
                continue

            seen.add(key)

            sources.append({
                "asset_name": asset_name,
                "page": page,
            })


        
        # step 2 construct prompt 
        system_prompt = self.template_parser.get("rag", "system_prompt")
       
        document_prompt = "\n".join([ self.template_parser.get(
                            "rag", "document_prompt", 
                            {    "document_no":i+1,  
                                "chunk_text": doc.text}) 
                            for i , doc in enumerate(retrieved_docs) ])
    
        footer_prompt = self.template_parser.get("rag", "footer_prompt", {"query":query})
        
        full_prompt = "\n\n".join([document_prompt, "\n" , footer_prompt])
        
        chat_history = [
            self.generation_client.construct_prompt(
                prompt=system_prompt,
                role = "system"
            )
        ]
        
        self.logger.debug("generate.prompt", extra={"prompt": full_prompt})
        start = perf_counter()
        try:
            answer = await run_serialized(self.generation_client, self.generation_client.generate_text,
                                          prompt=full_prompt, chat_history=chat_history)
        except Exception:
            self.logger.exception("generate.failed")
            raise
        self.logger.info("generate.done", extra={
            "tokens_in": getattr(answer, "tokens_in", None),
            "tokens_out": getattr(answer, "tokens_out", None),
            "latency_ms": round((perf_counter()-start)*1000, 2),
        })
        
        if not answer:
            self.logger.error("generate.failed")
            return None
        prediction_logger.info("prediction.done", extra={"query": query,
            "retrieved_ids": [doc.metadata.get("chunk_id", doc.id) for doc in retrieved_docs],
            "answer": str(answer)})

        return {
            "answer": answer,
            "sources": sources,
            "prompt_version": "rag-v1",
        }
        
        
    def get_conversation_history(project:Project, conversation_id):
        pass
    
    
    def save_chat_turn(self, project_id:str, chat_history:list):
        all_collection =  self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_CHUNK_NAME.value not in all_collection:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_CHATS_NAME.value]
