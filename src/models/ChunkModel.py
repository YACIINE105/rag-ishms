from .BaseDataModel import BaseDataModel
from .enums.DataBaseEnum import DataBaseEnum
from .db_schems.data_chunk import DataChunk
from bson.objectid import ObjectId
# the operation type not the operation it self
from pymongo import InsertOne

class ChunkModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        # for collection we get the chunk name instead of project name.
        self.collection = self.db_client[DataBaseEnum.COLLECTION_CHUNK_NAME.value]


    @classmethod
    async def create_instance(cls, db_client:object):
        instance = cls(db_client)
        await instance.init_collection()    
        return instance


    async def init_collection(self):
        all_collection = await self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_CHUNK_NAME not in all_collection:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_CHUNK_NAME.value]
            indexes = DataChunk.get_indexes()
            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    name=index["name"],
                    unique = index["unique"]
                )


    async def create_chunk(self, chunk:DataChunk):
        result = self.collection.insert_one(chunk.dict(exclude_none=True))
        chunk.id = result.inserted_id

        return chunk
    
    
    async def get_chunk(self, chunk_id:str):
        result = await self.collection.find_one(
            {
                "_id":ObjectId(chunk_id)
            }
        )
        
        if result is None:
            None
        
        return DataChunk(**result)
        
    # this funciton insert a batch of chunk at once rather than inserting chunk by chunk ,
    # returns the amount of chunks inserted.
    async def insert_many_chunks(self,chunks:list, batch_size:int=100):
        for i in range (0, len(chunks),batch_size ):
            batch = chunks[i:i+batch_size]
            
            operations = [
            InsertOne(chunk.dict(exclude_none=True))
            for chunk in batch     
            ]
            await self.collection.bulk_write(operations)
            
        return len(chunks)
    
    
    async def delete_chunk_by_project_id(self, project_id:ObjectId):
        result = await self.collection.delete_many({
            "chunk_project_id":project_id
        })
        
        return result.deleted_count
            