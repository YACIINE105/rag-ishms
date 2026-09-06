from .BaseController import BaseController
from models.db_schems import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from models.enums import DataBaseEnum
from typing import List
import time, json

class NLPController(BaseController):
    def __init__(self, generation_client, embedding_client, vector_db_client, template_parser = None):
        super().__init__()
        
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.vector_db_client = vector_db_client
        self.template_parser = template_parser

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
        metadata = [c.chunk_metadata for c in chunks]
        vectors = self.embedding_client.embed_text(text=texts, 
                                                   document_type = DocumentTypeEnum.DOCUMENT.value, input_type="passage")
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
        
        _ = await self.vector_db_client.insert_many(
            collection_name = self.create_collection_name(project_id=project.project_id),
            texts = texts,
            vectors = vectors,
            metadata = metadata,
            record_ids = chunks_ids,
            batch_size=batch_size
        )
        
        return True
    
    
    async def search_vector_db_collection(self, project:Project, text:str, limit: int=5):
        collection_name = self.create_collection_name(project_id=project.project_id)
        
        query_vector = None
        vectors = self.embedding_client.embed_text(
                        text=text, 
                        document_type=DocumentTypeEnum.QUERY.value, input_type="query"
                    )
        if not vectors or len(vectors)==0 :
            return False
        
        if isinstance(vectors, list) and len(vectors)>0:
            query_vector = vectors[0]
            
        if not query_vector:
            return False
        
        # print(query_vector, "\n", "\n")
        
        results = await self.vector_db_client.search_by_vector(collection_name=collection_name,
                                                        vector=query_vector,
                                                        k = limit)
        
        if not results:
            return False
        
        return results
        
        
    async def answer_rag_query(self, project:Project, query:str, limit:int = 5):
        # step 1 reterieve related docs 
        retrieved_docs = await self.search_vector_db_collection(project=project, text=query, limit=limit)
        if not retrieved_docs or len(retrieved_docs)==0:
            return None
        
        
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
                role = self.generation_client.enums.SYSTEM.value
            )
        ]
        
        answer  = self.generation_client.generate_text(prompt=full_prompt,
                                                       chat_history=chat_history)
        
        return answer, full_prompt, chat_history
        
        
    def get_conversation_history(project:Project, conversation_id):
        pass
    
    
    def save_chat_turn(self, project_id:str, chat_history:list):
        all_collection =  self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_CHUNK_NAME.value not in all_collection:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_CHATS_NAME.value]
    
    
    