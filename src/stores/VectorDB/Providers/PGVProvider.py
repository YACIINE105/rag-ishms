from ..VectorDBinterface import VectorDBInterface
from ..VectorDBEnums import (PGVectorDistanceMethodEnums, DistanceMethodEnums,
                             PGVectorTableSchemeEnums, PGVectorIndexTypeEnums)
from qdrant_client import models, QdrantClient
import logging
from typing import List
from models.db_schems import RetrievedDocuments
from sqlalchemy.sql import text as sql_text
import json
import re



class PGVectorProvider(VectorDBInterface):
    def __init__(self, db_client, default_vector_size: int = 768, distance_method: str = None, index_threshold: int = 1000):
        self.db_client = db_client
        self.default_vector_size = default_vector_size
        self.distance_method = distance_method
        self.index_threshold = index_threshold

        self.pgvector_table_prefix = PGVectorTableSchemeEnums._PREFIX.value 
        self.logger = logging.getLogger('uvicorn')
        
        self.default_index_name = lambda collection_name:f"{collection_name}_vector_idx"

        if self.default_vector_size > 2000:  
            self.distance_method = (
                PGVectorDistanceMethodEnums.HALFVEC_COSINE.value 
                if self.distance_method == "cosine" 
                else PGVectorDistanceMethodEnums.HALFVEC_L2.value
            )
        else:
            self.distance_method = (
                PGVectorDistanceMethodEnums.COSINE.value 
                if self.distance_method == "cosine" 
                else PGVectorDistanceMethodEnums.L2.value
            )
        

     
    async def connect(self):
        async with self.db_client() as session:
            async with session.begin():
                await session.execute(sql_text(
                    "CREATE EXTENSION IF NOT EXISTS vector"
                ))
                await session.commit()
        pass
    
    async def disconnect(self):
        pass
    
    
    async def collection_exists(self, collection_name:str) -> bool:
        async with self.db_client() as session:
            record = None
            async with session.begin():
                list_tables = sql_text('SELECT * FROM pg_tables WHERE tablename = :collection_name')
                results = await session.execute(list_tables, {"collection_name":collection_name})
                record = results.first()
                
            return record
        
         
    async def list_collections(self)-> List:
        async with self.db_client() as session:
            records = []
            async with session.begin():
                tables = sql_text('SELECT tablename FROM pg_tables WHERE tablename LIKE :prefix')
                results = await session.execute(tables, {"prefix": f"{self.pgvector_table_prefix}%"})
                records = results.scalars().all()
            
            return records
    
    
    async def get_collection_info(self, collection_name: str) -> dict:
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', collection_name):
            raise ValueError(f"Invalid collection name: {collection_name}")

        async with self.db_client() as session:
            async with session.begin():
                table_info_sql = sql_text('''SELECT schemaname, tablename, tableowner, tablespace, hasindexes 
                                        FROM pg_tables 
                                        WHERE tablename = :collection_name''')
                count_sql = sql_text(f'SELECT COUNT(*) FROM "{collection_name}"')

                table_info = await session.execute(table_info_sql, {"collection_name": collection_name})
                table_count = await session.execute(count_sql)

                table_data = table_info.fetchone()

                if not table_data:
                    return None

                return {
                    "table_info": dict(table_data._mapping),
                    "record_count": table_count.scalar_one()
                }
                
                
    async def delete_collection(self, collection_name:str):
        if not re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', collection_name):
            raise ValueError(f"Invalid collection name: {collection_name}")
        
        async with self.db_client() as session:
            async with session.begin():
                self.logger.info(f"Deleting collection: {collection_name}")
                delete_sql = sql_text(f'DROP TABLE IF EXISTS "{collection_name}" ')
                await session.execute(delete_sql)
                await session.commit()
            
            exists = await self.collection_exists(collection_name=collection_name)
            
            if not exists:
                self.logger.info(f"Deleted collection: {collection_name}")
                return not exists
            
            return False


    async def delete_vectors_by_asset_id(self, collection_name: str, asset_id: int) -> bool:
        sql_query = sql_text(
            f'DELETE FROM {collection_name} WHERE {PGVectorTableSchemeEnums.CHUNK_ID.value} IN '
            f'(SELECT chunk_id FROM chunks WHERE chunk_asset_id = :asset_id)'
        )
        
        try:
            async with self.db_client() as session:
                async with session.begin():
                    await session.execute(sql_query, {"asset_id": asset_id})
            return True
        except Exception as e:
            self.logger.error(f"failed to delete vectors for asset {asset_id} in {collection_name}: {e}")
            return False

                
    async def create_collection(self, collection_name:str, 
                                embedding_size, do_reset = False):
        
        if do_reset:
            _ = await self.delete_collection(collection_name=collection_name)
        
        is_collection_existed = await self.collection_exists(collection_name=collection_name)
        
        if not is_collection_existed:
            self.logger.info(f"Creating New PGVector Collection: {collection_name}")

            async with self.db_client() as session:
                async with session.begin(): 
                    # Determine whether to use standard vector or halfvec
                    vector_type = f"halfvec({embedding_size})" if embedding_size > 2000 else f"vector({embedding_size})"
                    
                    columns = [
                                f'{PGVectorTableSchemeEnums.ID.value} bigserial PRIMARY KEY',
                                f'{PGVectorTableSchemeEnums.TEXT.value} text',
                                f'{PGVectorTableSchemeEnums.VECTOR.value} {vector_type}', # Use the dynamic type here
                                f"{PGVectorTableSchemeEnums.METADATA.value} jsonb DEFAULT '{{}}'::jsonb",
                                f'{PGVectorTableSchemeEnums.CHUNK_ID.value} integer',
                                f'FOREIGN KEY ({PGVectorTableSchemeEnums.CHUNK_ID.value}) REFERENCES chunks(chunk_id)',]
                    create_sql = sql_text(
                        f'CREATE TABLE IF NOT EXISTS {collection_name} ({", ".join(columns)})'
                    )
    
                    await session.execute(create_sql)
                    await session.commit()
                    
                return True
        
        return False
    
    
    async def is_existed_index(self, collection_name:str):
        index_name = self.default_index_name(collection_name=collection_name)
        
        async with self.db_client() as session:
            async with session.begin():
                
                sql_query = sql_text(
                                    "SELECT 1 FROM pg_indexes WHERE tablename = :table_name AND indexname = :index_name")
                results = await session.execute(
                        sql_query, {"table_name": collection_name, "index_name": index_name})

                return bool(results.scalar_one_or_none()) 
    
    
    
    async def create_vector_index(self, collection_name : str, 
                                  index_type : str = PGVectorIndexTypeEnums.HNSW.value, is_halfvec: bool = False):
        
        is_collection = await self.collection_exists(collection_name=collection_name)
        
        if not is_collection:
            return False
        
        async with self.db_client() as session:
            async with session.begin():
                index_sql = sql_text(f'SELECT COUNT(*) FROM {collection_name}')
                result = await session.execute(index_sql)
                
                records_count = result.scalar_one()

                if records_count <self.index_threshold:
                    return False
                
                self.logger.info(f"START: creating vector index for collection:{collection_name}")

                index_name = self.default_index_name(collection_name=collection_name)
                create_index_sql = sql_text(f'CREATE INDEX {index_name} ON {collection_name} '
                                            f'USING {index_type} ({PGVectorTableSchemeEnums.VECTOR.value} {self.distance_method})'
                                            )
                
                await session.execute(create_index_sql)
                
                
                self.logger.info(f"END: creating vector index for collection:{collection_name}")
                
                
    async def reset_vector_index(self, collection_name : str, 
                                  index_type : str = PGVectorIndexTypeEnums.HNSW.value):
        
        is_existed = await self.is_existed_index(collection_name=collection_name)
        if not is_existed:
            self.logger.error(f" can not reset nonexisting index to a collection: {collection_name}")
            return False
        
        index_name = self.default_index_name(collection_name=collection_name)
        
        async with self.db_client() as session:
            async with session.begin():
                drop_index_sql = sql_text(f'DROP INDEX IF EXISTS {index_name}')
                await session.execute(drop_index_sql)
        
        return await self.create_vector_index(collection_name=collection_name,
                                              index_type=index_type)
            
                
    async def insert_one(self, collection_name:str, text:str, 
                         vector:list, metadata:dict = None, record_id:str = None):
        
        is_collection_existed = await self.collection_exists(collection_name=collection_name)
        
        if not is_collection_existed:
            self.logger.error(f"cannot insert new record to non-existed collection : {collection_name}")
            return False
        
        if not record_id:
            self.logger.error(f"cannot insert new record without chunk_id : {collection_name}")
            return False

        async with self.db_client() as session:
            async with session.begin(): 
                insert_sql = sql_text(f'INSERT INTO {collection_name} ('
                                      f'{PGVectorTableSchemeEnums.TEXT.value}, 'f'{PGVectorTableSchemeEnums.VECTOR.value}, 'f'{PGVectorTableSchemeEnums.METADATA.value}, 'f'{PGVectorTableSchemeEnums.CHUNK_ID.value}'')'
                                      'VALUES(:text, :vector, :metadata, :record_id)'
                                      )
                await session.execute(insert_sql, {"text":text, 
                                                   "vector":"["+ ",".join([str(v) for v in vector]) +"]", 
                                                   "metadata": json.dumps(metadata) if metadata is not None else "{}", 
                                                   "record_id":record_id})
                await session.commit()
        # await self.create_vector_index(collection_name=collection_name)

        return True
    
    
    
    async def insert_many(self, collection_name, texts: list,
                       vectors: list, metadata: list = None,
                       record_ids: list = None, batch_size: int = 50):

        is_collection_existed = await self.collection_exists(collection_name=collection_name)
        if not is_collection_existed:
            self.logger.error(f"cannot insert new records to non-existed collection : {collection_name}")
            return False

        if not record_ids or not (len(texts) == len(vectors) == len(record_ids)):
            self.logger.error(f"invalid data items for collection: {collection_name}")
            return False

        if not metadata or len(metadata) == 0:
            metadata = [None] * len(record_ids)
            
        elif len(metadata) != len(record_ids):
            self.logger.error(f"invalid metadata length for collection: {collection_name}")
            return False

        columns = ", ".join([
            PGVectorTableSchemeEnums.TEXT.value,
            PGVectorTableSchemeEnums.VECTOR.value,
            PGVectorTableSchemeEnums.METADATA.value,
            PGVectorTableSchemeEnums.CHUNK_ID.value,
        ])
        batch_sql_insertion = sql_text(
            f'INSERT INTO {collection_name} ({columns}) '
            'VALUES (:text, :vector, :metadata, :record_id)'
        )

        try:
            async with self.db_client() as session:
                async with session.begin():
                    for i in range(0, len(texts), batch_size):
                        batch_texts = texts[i:i + batch_size]
                        batch_vectors = vectors[i:i + batch_size]
                        batch_metadata = metadata[i:i + batch_size]
                        batch_record_ids = record_ids[i:i + batch_size]

                        values = [
                            {
                                'text': _text,
                                'vector': "[" + ",".join(str(v) for v in _vector) + "]",
                                'metadata': json.dumps(_metadata) if _metadata is not None else "{}",
                                'record_id': _record_id,
                            }
                            for _text, _vector, _metadata, _record_id in
                            zip(batch_texts, batch_vectors, batch_metadata, batch_record_ids)
                        ]

                        await session.execute(batch_sql_insertion, values)
                # await self.create_vector_index(collection_name=collection_name)
                return True
            
        except Exception as e:
            self.logger.error(f"failed to insert records into {collection_name}: {e}")
            
        return False
                        
                        
    async def search_by_vector(self, collection_name: str, vector: list,
                               k: int, distance_method: PGVectorDistanceMethodEnums = PGVectorDistanceMethodEnums.COSINE):

        is_collection_existed = await self.collection_exists(collection_name=collection_name)
        if not is_collection_existed:
            self.logger.error(f"cannot search for records in a non-existed collection : {collection_name}")
            return None

        operator_map = {
            PGVectorDistanceMethodEnums.COSINE: "<=>",
            PGVectorDistanceMethodEnums.HALFVEC_COSINE: "<=>", # Add halfvec equivalent
            PGVectorDistanceMethodEnums.L2: "<->",
            PGVectorDistanceMethodEnums.HALFVEC_L2: "<->",     # Add halfvec equivalent
            PGVectorDistanceMethodEnums.IP: "<#>",
            # Add PGVectorDistanceMethodEnums.HALFVEC_IP: "<#>" here if you added it to your enums!
        }
        operator = operator_map.get(distance_method)
        if operator is None:
            self.logger.error(f"unsupported distance method: {distance_method}")
            return None

        vector_str = "[" + ",".join(str(v) for v in vector) + "]"

        # Dynamically determine the cast type (no colons)
        cast_type = "halfvec" if len(vector) > 2000 else "vector"
        # always alias as "score" so the Python side has one consistent name
        # Append the cast_type directly to the :query_vector placeholder
        
        # Use standard SQL CAST() to avoid SQLAlchemy colon parsing errors
        if distance_method in [PGVectorDistanceMethodEnums.COSINE, PGVectorDistanceMethodEnums.HALFVEC_COSINE]:
            score_expr = f'1 - ({PGVectorTableSchemeEnums.VECTOR.value} {operator} CAST(:query_vector AS {cast_type})) AS score'
        else:
            score_expr = f'{PGVectorTableSchemeEnums.VECTOR.value} {operator} CAST(:query_vector AS {cast_type}) AS score'

        search_sql = sql_text(
            f'SELECT {PGVectorTableSchemeEnums.ID.value}, '
            f'{PGVectorTableSchemeEnums.TEXT.value} AS text, '
            f'{PGVectorTableSchemeEnums.METADATA.value}, '
            f'{score_expr} '
            f'FROM {collection_name} '
            f'ORDER BY {PGVectorTableSchemeEnums.VECTOR.value} {operator} CAST(:query_vector AS {cast_type}) ' 
            f'LIMIT :limit'
        )

        try:
            async with self.db_client() as session:
                result = await session.execute(
                    search_sql, {"query_vector": vector_str, "limit": k}
                )
                records = result.fetchall()

                return [
                    RetrievedDocuments(text=record.text, score=record.score)
                    for record in records
                ]
        except Exception as e:
            self.logger.error(f"failed to search {collection_name}: {e}")
            return None
                