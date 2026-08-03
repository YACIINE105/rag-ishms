from .Providers import QdrantDBProvider
from VectorDBEnums import QdrantEnum
from controllers.BaseController import BaseController



class VectorDBPRoviderFactory:
    def __init__(self, config:str):
        self.config = config
        self.base_controller = BaseController()
    
    
    def create(self, provider:str):
        db_path = self.base_controller.get_database_path(db_name=self.config.VECTOR_DB_PATH)
        if provider == QdrantEnum.QDRANT.value:
            return QdrantDBProvider(
                    db_path=db_path,
                    distance_method=self.config.VECTOR_DB_DISTANCE_METRIC,
            )
        
        return None