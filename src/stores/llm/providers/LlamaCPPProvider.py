# src/stores/llm/providers/LlamaCPPProvider.py
from ..LLMinterface import LLM_Interface
from ..LLMEnums import DocumentTypeEnum
import logging
from llama_cpp import Llama
from typing import List, Union


class LlamaCPPProvider(LLM_Interface):
    def __init__(self,
                 n_gpu_layers: int = -1,
                 n_ctx: int = 2048,
                 default_generation_max_output_characters: int = 1000,
                 default_generation_max_output_token: int = 1000,
                 default_generation_temperature: float = 0.2):

        self.n_gpu_layers = n_gpu_layers
        self.n_ctx = n_ctx
        self.default_generation_max_output_characters = default_generation_max_output_characters
        self.default_generation_max_output_token = default_generation_max_output_token
        self.default_generation_temperature = default_generation_temperature

        self.generation_model_id = None
        self.generation_client = None

        self.embedding_model_id = None
        self.embedding_size = None
        self.embedding_client = None

        self.logger = logging.getLogger(__name__)


    def set_generation_model(self, model_id: str):
        # model_id here = path to the GGUF generation model (e.g. MedGemma)
        self.generation_model_id = model_id
        self.generation_client = Llama(
            model_path=self.generation_model_id,
            n_gpu_layers=self.n_gpu_layers,
            n_ctx=self.n_ctx,
            verbose=True
        )


    def set_embedding_model(self, model_id: str, embedding_size: int):
        # model_id here = path to the GGUF embedding model (e.g. nomic-embed-text)
        self.embedding_model_id = model_id
        self.embedding_size = embedding_size
        self.embedding_client = Llama(
            model_path=self.embedding_model_id,
            embedding=True,
            n_gpu_layers=self.n_gpu_layers,
            n_ctx=self.n_ctx,
            verbose=False
        )


    def process_text(self, text: str):
        return text[:self.default_generation_max_output_characters].strip()


    def generate_text(self, prompt: str, chat_history: list = None,
                       max_output_token: int = None, temperature: float = None):

        if not self.generation_client:
            self.logger.error("LlamaCPP generation client was not set")
            return None

        if not self.generation_model_id:
            self.logger.error("Generation model for LlamaCPP client wasn't set")
            return None

        max_output_token = max_output_token if max_output_token else self.default_generation_max_output_token
        temperature = temperature if temperature else self.default_generation_temperature
        user_message = self.construct_prompt(prompt=prompt,
                                              role="user")
        chat_history = chat_history or []
        chat_history.append(user_message)

        try:
            response = self.generation_client.create_chat_completion(
                messages=chat_history,
                max_tokens=max_output_token,
                temperature=temperature
            )

            response_text = response["choices"][0]["message"]["content"]

            if not response_text or not response_text.strip():
                self.logger.error("LlamaCPP returned a successful response, but the text is empty.")
                return None

            chat_history.append(self.construct_response(response=response_text))

            return response_text

        except Exception as e:
            self.logger.error(f"Error during text generation: {e}")
            return None


    def embed_text(self, text: Union[str, List[str]], document_type: str = None):
        if not self.embedding_client:
            self.logger.error("LlamaCPP embedding client wasn't set")
            return None
        if not self.embedding_model_id:
            self.logger.error("Embedding model for LlamaCPP client wasn't set")
            return None

        if isinstance(text, str):
            text = [text]

        try:
            results = self.embedding_client.embed(text)

            if not results:
                self.logger.error("LlamaCPP returned an empty embedding response.")
                return None

            if self.embedding_size:
                for r in results:
                    if len(r) != self.embedding_size:
                        self.logger.warning(
                            f"Expected dimension {self.embedding_size}, but got {len(r)}"
                        )

            return results

        except Exception as e:
            self.logger.error(f"Error during embedding generation: {e}")
            return None


    def construct_response(self, response):
        return {
            "role": "assistant",
            "content": response
        }


    def construct_prompt(self, prompt: str, role: str):
        return {
            "role": role,
            "content": self.process_text(prompt)
        }
        
    def embed_texts(self, texts: list, document_type: str = None):
        if not self.embedding_client:
            self.logger.error("LlamaCPP embedding client wasn't set")
            return None
        if not self.embedding_model_id:
            self.logger.error("Embedding model for LlamaCPP client wasn't set")
            return None

        try:
            results = self.embedding_client.embed(texts)  # texts is a list -> batched internally

            if not results:
                self.logger.error("LlamaCPP returned an empty embedding response.")
                return None

            if self.embedding_size:
                for r in results:
                    if len(r) != self.embedding_size:
                        self.logger.warning(
                            f"Expected dimension {self.embedding_size}, but got {len(r)}"
                        )
            return results

        except Exception as e:
            self.logger.error(f"Error during batch embedding generation: {e}")
            return None
        
        
    