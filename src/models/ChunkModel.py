from .BaseDataModel import BaseDataModel
from .enums.DataBaseEnum import DataBaseEnum
from .db_schems.rag_ishms.schemes import DataChunk
from sqlalchemy import exists
from sqlalchemy.future import select
from sqlalchemy import func, delete

# the operation type not the operation it self


class ChunkModel(BaseDataModel):
    def __init__(self, db_client):
        super().__init__(db_client)
        # for collection we get the chunk name instead of project name.
        self.db_client = db_client

    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        return instance


    async def create_chunk(self, chunk: DataChunk):
        async with self.db_client() as session:
            async with session.begin():
                session.add(chunk)
            await session.refresh(chunk)

        return chunk


    async def get_chunk(self, chunk_id: int):
        async with self.db_client() as session:
            query = select(DataChunk).where(DataChunk.chunk_id == chunk_id)
            results = await session.execute(query)
            return results.scalar_one_or_none()


    # this funciton insert a batch of chunk at once rather than inserting chunk by chunk ,
    # returns the amount of chunks inserted.
    async def insert_many_chunks(self, chunks: list, batch_size: int = 100):
        async with self.db_client() as session:
            async with session.begin():
                for i in range(0, len(chunks), batch_size):
                    batch = chunks[i:i + batch_size]
                    session.add_all(batch)

        return len(chunks)


    async def delete_chunk_by_project_id(self, project_id: int):
        async with self.db_client() as session:
            async with session.begin():
                query = delete(DataChunk).where(DataChunk.chunk_project_id == project_id)
                results = await session.execute(query)

        return results.rowcount


    async def delete_chunk_by_asset_id(self, asset_id):
        async with self.db_client() as session:
            async with session.begin():
                query = delete(DataChunk).where(DataChunk.chunk_asset_id == asset_id)
                results = await session.execute(query)

        return results.rowcount


    async def get_project_chunks(self, project_id: int, page_number: int, page_size: int = 50):
        async with self.db_client() as session:
            query = (
                select(DataChunk)
                .where(DataChunk.chunk_project_id == project_id)
                .offset((page_number - 1) * page_size)
                .limit(page_size)
            )
            result = await session.execute(query)
            return result.scalars().all()


    async def has_chunks_for_asset(self, asset_id: int) -> bool:
        """
        Returns True if at least one chunk exists for this asset, False otherwise.
        Useful for checking whether an asset still needs processing.
        """
        async with self.db_client() as session:
            query = select(exists().where(DataChunk.chunk_asset_id == asset_id))
            result = await session.execute(query)
            return result.scalar()
        