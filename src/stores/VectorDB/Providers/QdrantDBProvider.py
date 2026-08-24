from ..VectorDBinterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums
from qdrant_client import models, QdrantClient
import logging
from typing import List
from models.db_schems import RetrievedDocuments


class QdrantDBProvider(VectorDBInterface):
    def __init__(self, db_client:str, default_vector_size: int = 768, distance_method: str = None, index_threshold: int = 1000):
        self.db_client = db_client
        self.client = None
        self.distance_method = None
        self.default_vector_size = default_vector_size
        self.index_threshold = index_threshold
        
        if distance_method == DistanceMethodEnums.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnums.DOT.value:
            self.distance_method = models.Distance.DOT  

        self.logger = logging.getLogger('uvicorn')
        
      
        
    async def connect(self):
        self.client = QdrantClient(path=self.db_client)
        return self.client
        
    
    async def disconnect(self):
        self.client.close()


    async def collection_exists(self, collection_name:str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)
        
        
    async def list_collections(self ) -> List:  
        return self.client.get_collections()   
    
    
    async def get_collection_info(self, collection_name:str) -> dict:
        return self.client.get_collection(collection_name=collection_name)
        
        
    async def delete_collection(self, collection_name:str):
        if self.collection_exists(collection_name=collection_name):
            return self.client.delete_collection(collection_name=collection_name)
        else:
            raise ValueError("collection was not found")
        
    async def create_collection(self, collection_name: str, embedding_size: int, do_reset: bool = False):
        # Only try to delete if do_reset is True AND the collection actually exists
        if do_reset and self.collection_exists(collection_name=collection_name):
            _ = self.delete_collection(collection_name=collection_name)
        
        if not self.collection_exists(collection_name=collection_name):   
            self.logger.info(f"Creating New Qdrant Collection : {collection_name}") 
            
            _ = self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(size=embedding_size, distance=self.distance_method),
            )
            return True
        
        return False


    async def insert_one(self, collection_name:str, text:str, vector:list, metadata:dict=None, record_id :str=None):
        if not self.collection_exists(collection_name=collection_name):
            self.logger.error(f"Can not insert new record to non_existed colection: {collection_name}")
            return False
        try:
            _= self.client.upsert(collection_name=collection_name,
                                points=[
                                        models.PointStruct(
                                        vector=vector,
                                        payload={"text":text, "metadata":metadata},
                                        id=[record_id]
                                    )
                                ])
        
        except Exception as e:
          self.logger.error(f"Error while inserting Batch: {e}")
          
        return True
    
    
    async def insert_many(self, collection_name:str, texts:list, vectors:list, 
                    metadata:list=None,
                    record_ids :list=None, batch_size:int=50):
       
        if metadata is None:
            metadata = [None] * len(texts)
        
        if record_ids is None:
            record_ids = [None] * len(texts)
            
        for i in range(0, len(texts), batch_size):
            batch_end= i + batch_size
            
            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            batch_record_ids = record_ids[i:batch_end]
            
            batch_points = [models.PointStruct(
                            vector=batch_vectors[x],
                            payload={"text":batch_texts[x], "metadata":batch_metadata[x]},
                            id = batch_record_ids[x]
                ) for x in range(len(batch_texts))]
            
            try:
                _ = self.client.upsert(collection_name=collection_name,
                                            points=batch_points,
                )
            
            except Exception as e:
                self.logger.error(f"Error while inserting Batch: {e}")
        
        
        return True
    
    
    async def search_by_vector(self, collection_name: str, vector: list, limit: int = 5):
        results = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
        )

        return [RetrievedDocuments(
                    text=result.payload['text'], 
                    score=result.score
                ).model_dump()
                for result in results.points
            ]
        
        