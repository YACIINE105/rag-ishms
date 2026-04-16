from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    
    APP_NAME:str
    APP_VERSION:str
    FILE_ALLOWED_TYPES:list
    FILE_MAX_SIZE:int
    FILE_CHHUNK_SIZE:int # as a limit / for memory effiency
    class Config:
        env_file = ".env"    
    
    
def get_settings():
    return Settings()

