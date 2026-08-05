from ..LLMinterface import LLM_Interface
from ..LLMEnums import Cohere_Enums, DocumentTypeEnum
import logging
import cohere


class CohereProvider(LLM_Interface):
    def __init__(self , api_key:str, 
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
        
        self.client = cohere.Client(api_key=self.api_key) 
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
            self.logger.error("CoHere client was not set")
            return None
    
        if not self.generation_model_id:
                self.logger.error("Generation model for CoHere client wasn't set ")
                return None
            
        max_output_token = max_output_token if max_output_token else self.default_generation_max_output_token     
        temperature = temperature if temperature else self.default_generation_temperature
        user_message = self.process_text(text=prompt)
        chat_history = chat_history or []
        
        try:
            chat_history.append(self.construct_prompt(prompt=user_message,
                                                      role=Cohere_Enums.USER.value))
            
            response =  self.client.chat(
                        model=self.generation_model_id,
                        max_tokens=max_output_token,
                        temperature=temperature,
                        chat_history=chat_history,
                        message=(user_message)
            )
            
            
            if not response or not response.message.content or not response.message.content[0].text.strip():
                self.logger.error("Cohere returned a successful response, but the text is empty.")
                return None
            
            # adding user query to chat history
            # chat_history.append({
            #     "role":Cohere_Enums.USER.value,
            #     "content":user_message
            # })
            
            chat_history.append(self.construct_response(response))
            
            return response.message.content[0].text
        
        except Exception as e:
            self.logger.error(f"Error during text generation: {e}")
            return None
            
            
            
    def construct_prompt(self, prompt:str, role:str):
        return {"role":role, 
                "content":self.process_text(prompt)
                }


    def embed_text(self, text:str, document_type:str=None):

        if not self.client:
            self.logger.error("CoHere client wasn't set ")
            return None

        if not self.embedding_model_id:
            self.logger.error("Embedding model for CoHere client wasn't set ")
            return None
        
        input_type = Cohere_Enums.DOCUMENT.value
        if document_type == DocumentTypeEnum.QUERY.value:
            input_type  = Cohere_Enums.QUERY.value
        
        response = self.client.embed(
                   texts=[self.process_text(text)],
                   model=self.embedding_model_id,    
                   input_type=input_type,
                   embedding_types=['float'])
        
        if not response or not response.embeddings or not response.embeddings.float or len(response.embeddings.float) == 0:
                self.logger.error("Error while embedding text with CoHere")
                return None
        return response.embeddings.float
        

    def construct_response(self, response):
        return {
                "role":Cohere_Enums.ASSISTANT.value,
                "content":response.message.content[0].text
            }