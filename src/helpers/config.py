from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List

class Settings(BaseSettings):
    
    APP_NAME : str
    APP_VERSION : str
    
    FILE_ALLOWED_TYPES : list
    FILE_MAX_SIZE : int
    FILE_CHHUNK_SIZE : int # as a limit / for memory effiency
    
    DEFAULT_LANG : str = "en"
    PRIMARY_LANG : str = "en"
    
    ################ DB CONFIG ################
    MONGO_URL: str | None = None
    MONGO_DATABASE: str | None = None
    
    POSTGRES_USERNAME : str
    POSTGRES_PASSWORD : str
    POSTGRES_HOST : str
    POSTGRES_PORT : int
    POSTGRES_MAIN_DATABASE : str
    
    ################ LLM CONFIG ################
    GENERATION_PROVIDER : str
    EMBEDDING_PROVIDER : str

    OPENAI_BASE_URL : str = None
    OPENAI_API_KEY : str = None
    
    COHERE_API_KEY : str = None
    
    GOOGLE_AI_API_KEY : str = None
    
    NARA_API_KEY : str = None
    NARA_BASE_URL:str
    
    OPENROUTER_API_KEY : str = None 
    OPENROUTER_BASE_URL : str = None 
    
    GENERATION_MODEL_ID_LITTERAL:List[str] = None
    GENERATION_MODEL_ID : str = None
    GENERATION_MODEL_PATH:str = None
    GENERATION_MODEL_TEMPERATURE : float = None
    
    EMBEDDING_MODEL_ID : str = None
    EMBEDDING_MODEL_PATH : str
    EMBEDDING_MODEL_SIZE : int = None
    
    INPUT_MAX_CHARACTERS : int = None
    MAX_OUTPUT_TOKENS : int = None
    
    LLAMA_CPP_N_GPU_LAYERS : int
    LLAMA_CPP_N_CTX : int
    LLama_CPP_API_KEY:str
    LLAMA_CPP_URL :str
    
    ################ VECTOR DB CONFIG ################
    VECTOR_DB_BACKEND_LITTERAL: List[str] = None
    VECTOR_DB_BACKEND : str
    VECTOR_DB_DISTANCE_METRIC : str
    VECTOR_DB_PATH : str
    VECTOR_DB_PGVEC_INDEX_THRESHOLD:int
    
    class Config:
        env_file = ".env"    
    
    
def get_settings():
    return Settings()