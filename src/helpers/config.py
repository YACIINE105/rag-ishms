from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    APP_NAME:str
    APP_VERSION:str
    
    FILE_ALLOWED_TYPES:list
    FILE_MAX_SIZE:int
    FILE_CHHUNK_SIZE:int # as a limit / for memory effiency
    
    MONGO_URL:str
    MONGO_DATABASE:str
    GENERATION_PROVIDER:str
    EMBEDDING_PROVIDER:str
    
    ################ LLM CONFIG ################

    OPENAI_BASE_URL:str=None
    OPENAI_API_KEY:str=None
    COHERE_API_KEY:str=None
    GOOGLE_AI_API_KEY:str=None
    NARA_API_KEY:str=None
    
    GENERATION_MODEL_ID:str=None
    EMBEDDING_MODEL_ID:str=None
    INPUT_MAX_CHARACTERS:int=None
    GENERATION_MODEL_TEMPERATURE:float=None
    MAX_OUTPUT_TOKENS:int=None
    EMBEDDING_MODEL_SIZE:int=None
    VECTOR_DB_DISTANCE_METRIC:str
    VECTOR_DB_PATH:str
    VECTOR_DB_BACKEND:str
    LLAMA_CPP_N_GPU_LAYERS:int
    LLAMA_CPP_N_CTX:int
    
    class Config:
        env_file = ".env"    
    
    
def get_settings():
    return Settings()

