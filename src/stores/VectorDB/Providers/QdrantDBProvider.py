from ..VectorDBinterface import VectorDBInterface
from ..VectorDBEnums import DistanceMethodEnums
from qdrant_client import models, QdrantClient
import logging

from models.db_schems import RetrievedDocuments
from utils.inference import run_serialized


class QdrantDBProvider(VectorDBInterface):
    def __init__(self, db_client: str, default_vector_size: int = 768,
                 distance_method: str = None, index_threshold: int = 1000,
                 url: str = None, api_key: str = None):
        self.db_client = db_client
        self.url = url
        self.api_key = api_key
        self.client = None
        self.default_vector_size = default_vector_size
        self.index_threshold = index_threshold
        self.distance_method = {
            DistanceMethodEnums.COSINE.value: models.Distance.COSINE,
            DistanceMethodEnums.DOT.value: models.Distance.DOT,
        }.get(distance_method, models.Distance.COSINE)
        self.logger = logging.getLogger("uvicorn")
        
    async def connect(self):
        options = {"url": self.url, "api_key": self.api_key, "timeout": 3} if self.url else {"path": self.db_client}
        self.client = await run_serialized(self, QdrantClient, **options)
        return self.client
        
    async def disconnect(self):
        if self.client is not None:
            await run_serialized(self, self.client.close)

    async def collection_exists(self, collection_name: str) -> bool:
        return await run_serialized(self, self.client.collection_exists,
                                    collection_name=collection_name)

    async def list_collections(self):
        return await run_serialized(self, self.client.get_collections)

    async def get_collection_info(self, collection_name: str) -> dict:
        info = await run_serialized(self, self.client.get_collection,
                                    collection_name=collection_name)
        return info.model_dump(mode="json")

    async def delete_collection(self, collection_name: str):
        if await self.collection_exists(collection_name):
            return await run_serialized(self, self.client.delete_collection,
                                        collection_name=collection_name)
        return False

    async def create_collection(self, collection_name: str, embedding_size: int,
                                do_reset: bool = False):
        def create():
            exists = self.client.collection_exists(collection_name)
            if exists and do_reset:
                self.client.delete_collection(collection_name)
                exists = False
            if not exists:
                return self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config=models.VectorParams(size=embedding_size,
                                                       distance=self.distance_method),
                )
            return False
        return await run_serialized(self, create)

    async def insert_one(self, collection_name: str, text: str, vector: list,
                         metadata: dict = None, record_id=None):
        return await self.insert_many(collection_name, [text], [vector],
                                      [metadata or {}], [record_id])

    async def insert_many(self, collection_name: str, texts: list, vectors: list,
                          metadata: list = None, record_ids: list = None,
                          batch_size: int = 50):
        metadata = metadata if metadata is not None else [{} for _ in texts]
        if (not record_ids or not vectors or batch_size < 1 or
                not (len(texts) == len(vectors) == len(metadata) == len(record_ids)) or
                any(record_id is None for record_id in record_ids)):
            return False
        if not await self.collection_exists(collection_name):
            return False
        try:
            for start in range(0, len(texts), batch_size):
                points = [models.PointStruct(
                    id=record_ids[i], vector=vectors[i],
                    payload={"text": texts[i], "metadata": metadata[i] or {}},
                ) for i in range(start, min(start + batch_size, len(texts)))]
                await run_serialized(self, self.client.upsert,
                                     collection_name=collection_name, points=points)
            return True
        except Exception:
            self.logger.exception("Failed to insert vector batch")
            return False
        
    async def search_by_vector(self, collection_name: str, vector: list, k: int = 5):
        results = await run_serialized(self, self.client.query_points,
                                      collection_name=collection_name, query=vector,
                                      limit=k, with_payload=True)
        return [RetrievedDocuments(
            text=result.payload["text"], score=result.score, id=result.id,
            metadata=result.payload.get("metadata") or {},
        ) for result in results.points]

    async def create_vector_index(self, collection_name: str):
        # Qdrant manages its vector index as part of collection creation/upsert.
        return await self.collection_exists(collection_name)

    async def delete_vectors_by_asset_id(self, collection_name: str, asset_id: int):
        if not await self.collection_exists(collection_name):
            return True
        await run_serialized(self, self.client.delete,
            collection_name=collection_name,
            points_selector=models.FilterSelector(filter=models.Filter(must=[
                models.FieldCondition(key="metadata.asset_id",
                                      match=models.MatchValue(value=asset_id))
            ])),
        )
        return True

    async def get_indexed_documents_count(self) -> int:
        def count():
            assets = set()
            for collection in self.client.get_collections().collections:
                if not collection.name.startswith("collection_"):
                    continue
                offset = None
                while True:
                    points, offset = self.client.scroll(
                        collection_name=collection.name, limit=256, offset=offset,
                        with_payload=True, with_vectors=False,
                    )
                    for point in points:
                        metadata = (point.payload or {}).get("metadata") or {}
                        if metadata.get("asset_id") is not None:
                            assets.add(("asset_id", metadata["asset_id"]))
                        else:
                            source = metadata.get("source") or metadata.get("asset_name")
                            if not source:
                                raise ValueError("Reindex legacy points to recover asset identity")
                            assets.add((collection.name, source))
                    if offset is None:
                        break
            return len(assets)
        return await run_serialized(self, count)
