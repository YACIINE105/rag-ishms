from .BaseController import BaseController
from models.db_schems import Project, DataChunk
from stores.llm.LLMEnums import DocumentTypeEnum
from typing import List
import time, json

class NLPController(BaseController):
    def __init__(self, generation_client, embedding_client, vector_db_client):
        super().__init__()
        
        self.generation_client = generation_client
        self.embedding_client = embedding_client
        self.vector_db_client = vector_db_client


    def create_collection_name(self, project_id:str):
        return f"collection_{project_id}".strip()
    

    def reset_vector_db_colection(self,project:Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        self.vector_db_client.delete_collection(collection_name=collection_name)

    
    def get_vector_db_collection_info(self, project:Project):
        collection_name = self.create_collection_name(project_id=project.project_id)
        collection_info = self.vector_db_client.get_collection_info(collection_name=collection_name)
        
        return collection_info
        
        
    def index_into_vector_db(self, project:Project, chunks:List[DataChunk], 
                             chunks_ids:List[int], 
                             do_reset:bool = False):
        # step 1 : get collection name
        
        collection_name = self.create_collection_name(project_id=project.project_id)

        # step 2 : manage items
        
        texts = [c.chunk_text for c in chunks]
        metadata = [c.chunk_metadata for c in chunks]
        vectors = []
        for text in texts:
            vector = self.embedding_client.embed_text(
                text=text, 
                document_type=DocumentTypeEnum.DOCUMENT.value
            )
            vectors.append(vector)
                
        
        # step 3 : create collection if not exists (if do reset : delete collections)
        
        _ = self.vector_db_client.create_collection(collection_name=collection_name,
                                                embedding_size = self.embedding_client.embedding_size,
                                                do_reset = do_reset                                     
                )
        # step 4 : insert into  vector db 
        
        _ = self.vector_db_client.insert_many(
            collection_name = self.create_collection_name(project_id=project.project_id),
            texts = texts,
            vectors = vectors,
            metadata = metadata,
            record_ids = chunks_ids
        )
        
        return True
    
    
    def search_vector_db_collection(self, project:Project, text:str, limit: int=5):
        collection_name = self.create_collection_name(project_id=project.project_id)
        
        vector = self.embedding_client.embed_text(
                        text=text, 
                        document_type=DocumentTypeEnum.QUERY.value
                    )
        if not vector or len(vector)==0 :
            return False
        
        results = self.vector_db_client.search_by_vector(collection_name=collection_name,
                                                        vector=vector,
                                                        limit = limit)
        
        if not results:
            return False
        
        return json.loads(
            json.dumps(results, default=lambda x: x.__dict__)
        )