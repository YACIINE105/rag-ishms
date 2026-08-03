from ..VectorDBinterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnum
from qdrant_client import models, QdrantClient
import logging
from typing import List

class QdrantDBProvider(VectorDBInterface):
    def __init__(self, db_path:str, distance_method:str):
        self.db_path = db_path
        self.client = None
        self.distance_method = None
        
        if distance_method == DistanceMethodEnum.COSINE.value:
            self.distance_method = models.Distance.COSINE
        elif distance_method == DistanceMethodEnum.DOT.value:
            self.distance_method = models.Distance.DOT  

        self.logger = logging.getLogger("__name__")
        
      
        
    def connect(self):
        self.client = QdrantClient(path=self.db_path)
        return self.client
        
    
    def disconnect(self):
        self.client.close()


    def collection_exists(self, collection_name:str) -> bool:
        return self.client.collection_exists(collection_name=collection_name)
        
        
    def list_collections(self ) -> List:  
        return self.client.get_collections()   
    
    
    def get_collection_info(self, collection_name:str) -> dict:
        return self.client.get_collection(collection_name=collection_name)
        
        
    def delete_collection(self, collection_name:str):
        if self.collection_exists(collection_name=collection_name):
            return self.client.client.delete_collection(collection_name=collection_name)
        else:
            raise "collection was not found"
        
    def create_collection(self, collecrtion_name:str, embedding_size:int, do_reset: bool=False):
        if do_reset:
            _ = self.delete_collection(collection_name=collecrtion_name)
        
        if not self.collection_exists(collection_name=collecrtion_name):    
            _ = self.client.create_collection(
                    collection_name=collecrtion_name,
                    vectors_config=models.VectorParams(size=embedding_size, distance=self.distance_method),)
            return True
        
        return False


    def insert_one(self, collection_name:str, text:str, vector:list, metadata:dict=None, record_id :str=None):
        if not self.collection_exists(collection_name=collection_name):
            self.logger.error(f"Can not insert new record to non_existed colection: {collection_name}")
            return False
        try:
            _= self.client.upsert(collection_name=collection_name,
                                points=[
                                        models.PointStruct(
                                        vector=vector,
                                        payload={"text":text, "metadata":metadata},
                                    )
                                ])
        
        except Exception as e:
          self.logger.error(f"Error while inserting Batch: {e}")
          
        return True
    
    
    def insert_many(self, collection_name:str, texts:list, vectors:list, metadata:list=None,record_ids :list=None, batch_size:int=50):
        if metadata is None:
            metadata = [None] * len(texts)
        
        if record_ids is None:
            record_ids = [None] * len(texts)
            
        for i in range(0, len(texts), batch_size):
            batch_end= i + batch_size
            
            batch_texts = texts[i:batch_end]
            batch_vectors = vectors[i:batch_end]
            batch_metadata = metadata[i:batch_end]
            
            batch_points = [models.PointStruct(
                            vector=batch_vectors[x],
                            payload={"text":batch_texts[x], "metadata":batch_metadata[x]}
                ) for x in range(len(batch_texts))]
            
            try:
                _ = self.client.upsert(collection_name=collection_name,
                                            points=batch_points,
                )
            
            except Exception as e:
                self.logger.error(f"Error while inserting Batch: {e}")
        
        
        return True
    
    
    def search_by_vector(self, collection_name: str, vector: list, limit: int = 5):
        result = self.client.query_points(
            collection_name=collection_name,
            query=vector,
            limit=limit,
        )
        return result.points