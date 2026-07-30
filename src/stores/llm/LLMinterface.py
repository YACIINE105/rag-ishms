from abc import ABC, abstractmethod

class LLM_Interface(ABC):
    @abstractmethod
    def set_generation_model(self, model_id:str):
        pass
    
    @abstractmethod
    def set_embedding_model(self, model_id:str, embedding_size:int):
        pass
    
    @abstractmethod
    def generate_text(self, prompt:str, chat_history:list=[], max_output_token:int=None, temprature:float=None):
        pass
    
    @abstractmethod
    def embed_text(self, text:str, document_type:str=None):
        pass
    
    @abstractmethod
    def construct_prompt(self, prompt:str, role:str):
        pass
    
    @abstractmethod
    def constuct_response(self, response:dict):
        pass
    