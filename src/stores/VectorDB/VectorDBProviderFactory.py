from .Providers import QdrantDBProvider, PGVectorProvider
from .VectorDBEnums import VectorDBEnums
from controllers.BaseController import BaseController

from sqlalchemy.orm import sessionmaker


class VectorDBPRoviderFactory:
    def __init__(self, config:str, db_client:sessionmaker = None):
        self.config = config
        self.base_controller = BaseController()
        self.db_client = db_client
    
    
    def create(self, provider:str):
        qdrant_db_client = self.base_controller.get_database_path(db_name=self.config.VECTOR_DB_PATH)
        
        if provider == VectorDBEnums.QDRANT.value:
        
            return QdrantDBProvider(
                    db_client=qdrant_db_client,
                    distance_method=self.config.VECTOR_DB_DISTANCE_METRIC,
            )
        
        elif provider == VectorDBEnums.PGVector.value:
            return PGVectorProvider(db_client=self.db_client,
                                    distance_method=self.config.VECTOR_DB_DISTANCE_METRIC,
                                    default_vector_size=self.config.EMBEDDING_MODEL_SIZE,
                                    index_threshold=self.config.VECTOR_DB_PGVEC_INDEX_THRESHOLD,)
        
        return None