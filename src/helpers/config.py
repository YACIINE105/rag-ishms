from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    APP_NAME : str
    APP_VERSION : str
    
    FILE_ALLOWED_TYPES : list
    FILE_MAX_SIZE : int
    FILE_CHHUNK_SIZE : int # as a limit / for memory effiency
    
    ################ DB CONFIG ################
    MONGO_URL: str | None = None
    MONGO_DATABASE: str | None = None
    GENERATION_PROVIDER : str
    EMBEDDING_PROVIDER : str
    
    POSTGRES_USERNAME : str
    POSTGRES_PASSWORD : str
    POSTGRES_HOST : str
    POSTGRES_PORT : int
    POSTGRES_MAIN_DATABASE : str
    
    
    ################ LLM CONFIG ################

    OPENAI_BASE_URL : str = None
    OPENAI_API_KEY : str = None
    COHERE_API_KEY : str = None
    GOOGLE_AI_API_KEY : str = None
    NARA_API_KEY : str = None
    
    GENERATION_MODEL_ID : str = None
    EMBEDDING_MODEL_ID : str = None
    INPUT_MAX_CHARACTERS : int = None
    GENERATION_MODEL_TEMPERATURE : float = None
    MAX_OUTPUT_TOKENS : int = None
    EMBEDDING_MODEL_SIZE : int = None
    VECTOR_DB_DISTANCE_METRIC : str
    VECTOR_DB_PATH : str
    VECTOR_DB_BACKEND : str
    LLAMA_CPP_N_GPU_LAYERS : int
    LLAMA_CPP_N_CTX : int
    EMBEDDING_MODEL_PATH : str
    LLAMA_CPP_URL :str
    NARA_BASE_URL:str
    
    DEFAULT_LANG : str = "en"
    PRIMARY_LANG : str = "en" 
    class Config:
        env_file = ".env"    
    
    
def get_settings():
    return Settings()

