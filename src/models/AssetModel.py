from .BaseDataModel import BaseDataModel
from .enums.DataBaseEnum import DataBaseEnum
from .db_schems import Asset
from bson import ObjectId

class AssetModel(BaseDataModel):
    def __init__(self, db_client:object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_ASSET_NAME.value] 
    
    
    
    @classmethod
    async def create_instance(cls, db_client:object):
        instance = cls(db_client)
        await instance.init_collection()    
        return instance 
    
    
    
    async def init_collection(self):
        all_collection = await self.db_client.list_collection_names()
        if DataBaseEnum.COLLECTION_ASSET_NAME.value not in all_collection:
            self.collection = self.db_client[DataBaseEnum.COLLECTION_ASSET_NAME.value]
            indexes = Asset.get_indexes()
            for index in indexes:
                await self.collection.create_index(
                    index["key"],
                    name=index["name"],
                    unique = index["unique"]
                )
                
                
    async def create_asset(self, asset:Asset):
        
        result = await self.collection.insert_one(asset.model_dump(by_alias=True, exclude_none=True, exclude_unset=True))
        asset.id = result.inserted_id
        
        return asset
        
    # adding asset type param to get all types like files, urls, etc
    async def get_all_project_assets(self, asset_project_id:str, asset_type:str):
        
        records = await self.collection.find({
            # self.collaction accepts only OBJECTID so i had to cast it.
            "asset_project_id":ObjectId(asset_project_id) if isinstance(asset_project_id, str) else asset_project_id , 
            "asset_type":asset_type
            # to get all assets with the same asset id
        }).to_list(length=None)
        
        return [Asset(**record) for record in records]
    
    async def get_asset_record(self, asset_project_id:str, unique_asset_name:str):
        record = await self.collection.find_one({
            "asset_project_id":ObjectId(asset_project_id) if isinstance(asset_project_id, str) else asset_project_id ,
            "unique_asset_name":unique_asset_name,
        })
        
        if record:
            return Asset(**record)
        
        else:
            return None
        
        
    async def delete_asset_by_name(self, asset_project_id: str, asset_name: str, exclude_asset_id=None):
        query = {
            "asset_project_id": ObjectId(asset_project_id) if isinstance(asset_project_id, str) else asset_project_id,
            "asset_name": asset_name,
        }

        if exclude_asset_id:
            query["_id"] = {"$ne": ObjectId(exclude_asset_id) if isinstance(exclude_asset_id, str) else exclude_asset_id}

        old_records = await self.collection.find(query).to_list(length=None)
        old_assets_info = [
        {"id": record["_id"], "unique_asset_name": record["unique_asset_name"]}
        for record in old_records
                                ]

        result = await self.collection.delete_many(query)

        return old_assets_info, result.deleted_count
            
               
    
        
        
    