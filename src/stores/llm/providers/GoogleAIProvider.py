from ..LLMinterface import LLM_Interface
from ..LLMEnums import GoogleAI_Enums, DocumentTypeEnum
import logging
from google import genai
from google.genai import types

class GoogleAIProvider(LLM_Interface):
    def __init__(self , api_key:str, 
                            # api_url:str,
                            default_generation_max_output_characters:int=1000,
                            default_generation_max_output_token:int=1000, 
                            default_generation_temperature:float=0.2):     
        self.api_key = api_key
        self.default_generation_max_output_characters = default_generation_max_output_characters
        self.default_generation_max_output_token = default_generation_max_output_token
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        
        self.embedding_model_id = None
        self.embedding_size = None
        self.client = genai.Client(api_key=self.api_key)
        self.logger = logging.getLogger(__name__)
        
            
    def set_generation_model(self, model_id:str):
        self.generation_model_id = model_id
    

    def set_embedding_model(self, model_id:str, embedding_size:int):
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size
        
        
    def process_text(self, text:str):
        return text[:self.default_generation_max_output_characters].strip()
    

    def generate_text(self, prompt:str, chat_history:list=None, 
                      max_output_token:int=None, temperature:float=None):
        
        if not self.client:
            self.logger.error("GoogleAI client was not set")
            return None
        
        if not self.generation_model_id:
                self.logger.error("Generation model for GoogleAI client wasn't set ")
                return None
            
        max_output_token = max_output_token if max_output_token else self.default_generation_max_output_token     
        temperature = temperature if temperature else self.default_generation_temperature
        user_message = self.construct_prompt(prompt=self.process_text(text=prompt), 
                                             role=GoogleAI_Enums.USER.value)
        chat_history = chat_history or []
        
        chat_history.append(user_message)

        try:
            response = self.client.models.generate_content(
                        model = self.generation_model_id,
                        contents = chat_history,
                        config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_output_token
                )
                    )
            
            if not response.text or not response.text.strip():
                self.logger.error("GoogleAI returned a successful response, but the text is empty.")
                return None

            chat_history.append(self.construct_response(response=response.text))
            
            return response.text
        
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
        task = "RETRIEVAL_DOCUMENT" if document_type == DocumentTypeEnum.DOCUMENT.value else "RETRIEVAL_QUERY"
        try:
            response = self.client.models.embed_content(model = self.embedding_model_id,
                                                        contents = text,
                                                        config = types.EmbedContentConfig(
                                                            # For Qdrant, specify the exact task type
                                                            task_type=task)
                                                        )
            
            if not response or not response.embeddings or len(response.embeddings) == 0:
                    self.logger.error("GoogleAI returned an empty embedding response.")
                    return None
                
            first_embedding = response.embeddings[0]

            # 2. Check if the values attribute exists and contains floats
            if not hasattr(first_embedding, "values") or not first_embedding.values:
                self.logger.error("Embedding object contains no values vector.")
                return None

            # Verify vector dimension size (e.g., 768 for text-embedding-004)
            if self.embedding_size and len(first_embedding.values) != self.embedding_size:
                self.logger.warning(
                    f"Expected dimension {self.embedding_size}, but got {len(first_embedding.values)}"
                )

            return first_embedding.values

        except Exception as e:
            self.logger.error(f"Error during embedding generation: {e}")
            return None
         
         
    def construct_response(self, response):
        return {
            "role" : GoogleAI_Enums.ASSISTANT.value,
            "parts" : response      
        }
     
         
    def construct_prompt(self, prompt:str, role:str):
        return {"role":role, 
                "parts":[self.process_text(prompt)]
                }