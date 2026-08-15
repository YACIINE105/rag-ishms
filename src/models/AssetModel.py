from .BaseDataModel import BaseDataModel
from .enums.DataBaseEnum import DataBaseEnum
from .db_schems.rag_ishms.schemes import Asset
from sqlalchemy import exists
from sqlalchemy.future import select
from sqlalchemy import func, delete

class AssetModel(BaseDataModel):
    def __init__(self, db_client:object):
        super().__init__(db_client=db_client)
        self.db_client= db_client
    
    
    
    @classmethod
    async def create_instance(cls, db_client:object):
        instance = cls(db_client)
        return instance 
    
    
    async def create_asset(self, asset:Asset):
        async with self.db_client() as session:
            async with session.begin():
                session.add(asset)
            await session.refresh(asset)
        
        return asset
        
    # adding asset type param to get all types like files, urls, etc
    async def get_all_project_assets(self, asset_project_id:int, asset_type:str):
        async with self.db_client() as session:
            query = select(Asset).where(Asset.asset_project_id == asset_project_id, Asset.asset_type == asset_type)
            results = await session.execute(query)
            return results.scalars().all()
        
    
    async def get_asset_record(self, asset_project_id:int, unique_asset_name:str):
        async with self.db_client() as session:
            query = select(Asset).where(Asset.asset_project_id == asset_project_id, Asset.unique_asset_name == unique_asset_name)
            results = await session.execute(query)
            records = results.scalar_one_or_none()
            return records
        
        
    async def delete_asset_by_name(self, asset_project_id: int, asset_name: str, exclude_asset_id: int = None):
        async with self.db_client() as session:
            async with session.begin():
                # first, find out exactly what we're about to delete
                select_query = select(Asset.asset_id, Asset.asset_name).where(
                    Asset.asset_project_id == asset_project_id,
                    Asset.asset_name == asset_name,
                )
                if exclude_asset_id is not None:
                    select_query = select_query.where(Asset.asset_id != exclude_asset_id)

                result = await session.execute(select_query)
                old_assets_info = [
                    {"id": row.asset_id, "unique_asset_name": row.asset_name}
                    for row in result.all()
                ]

                if not old_assets_info:
                    return old_assets_info, 0

                ids_to_delete = [a["id"] for a in old_assets_info]

                delete_query = delete(Asset).where(Asset.asset_id.in_(ids_to_delete))
                delete_result = await session.execute(delete_query)

        return old_assets_info, delete_result.rowcount
        