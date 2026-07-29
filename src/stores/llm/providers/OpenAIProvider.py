from ...LLMinterface import LLM_Interface
from openai import OpenAI
import logging
from LLMEnums import OpenAI_Enums

class OpenAIProvider(LLM_Interface):
    def __init__(self , api_key:str, api_url:str=None, 
                        default_generation_max_output_characters:int=1000,
                        default_generation_max_output_token:int=1000, 
                        default_generation_temprature:float=0.2):
        
        self.api_key = api_key
        self.api_url = api_url
        self.default_generation_max_output_characters = default_generation_max_output_characters
        self.default_generation_max_output_token = default_generation_max_output_token
        self.default_generation_temprature = default_generation_temprature

        self.generation_model_id = None
        
        self.embedding_model_id = None
        self.embedding_size = None
        
        # this way of client nitializing is deprecated  
        # self.client = OpenAI(
        #     api_key=self.api_key, api_url = self.api_url
        #     )
        
        client_kwargs = {"api_key": self.api_key}
        if self.api_url:
            client_kwargs["base_url"] = self.api_url
        
        self.client =OpenAI(**client_kwargs)

        self.logger = logging.getLogger(__name__)
     
     
     
        
    def set_generation_model(self, model_id:str):
        self.generation_model_id = model_id
    
    
    
    def set_embedding_model(self, model_id:str, embedding_size:int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size
    
    
    
    def generate_text(self, prompt:str, chat_history:list=[], 
                      max_output_token:int=None, temprature:float=None):
        if not self.client:
            self.logger.error("OpenAI client wasn't set ")
            return None
        
        if not self.generation_model_id:
            self.logger.error("Generation model for OpenAI client wasn't set ")
            return None
        
        max_output_token = max_output_token if max_output_token else self.default_generation_max_output_token     
        temprature = temprature if temprature else self.default_generation_temprature
        
        chat_history.append(self.construct_prompt(prompt=prompt, role=OpenAI_Enums.USER.value))
        
        try:
            response = self.client.chat.completions.create(
                model=self.generation_model_id,
                messages=chat_history,
                max_tokens=max_output_token,
                temperature=temprature
            )
            return response.choices[0].message.content
        
        except Exception as e:
            self.logger.error(f"Error during text generation: {e}")
            return None
        
        
        
    def embed_text(self, text:str, document_type:str=None):
        
        if not self.client:
            self.logger.error("OpenAI client wasn't set ")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding model for OpenAI client wasn't set ")
            return None
        
        respoense = self.client.embeddings.create(
            model=self.embedding_model_id, input=text
        ) 
        
        if not respoense or not respoense.data or len(respoense.data) == 0 or not respoense.data[0].embedding:
            self.logger.error("Error while embedding text with OpenAI")
            return None
        return respoense.data[0].embedding
    
    
    
    def construct_prompt(self, prompt:str, role:str):
        return {"role":role, 
                "content":self.process_text(prompt)
                }
        
        
        
    def process_text(self, text:str):
        return text[:self.default_generation_max_output_characters].strip()
        
        
              