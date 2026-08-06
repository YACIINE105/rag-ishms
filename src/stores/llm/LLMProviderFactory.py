from .LLMEnums import LLM_Enums
from .providers import CohereProvider, OpenAIProvider, GoogleAIProvider, LlamaCPPProvider


class LLMProviderFactory:
    def __init__(self, config: dict):
        self.config = config

    def create(self, provider: str):
        if provider == LLM_Enums.OPENAI.value:
            return OpenAIProvider(
               api_key=self.config.OPENAI_API_KEY,
               api_url=self.config.OPENAI_BASE_URL
            )
        
        if provider == LLM_Enums.COHERE.value:
            return CohereProvider(
                api_key=self.config.COHERE_API_KEY
            )
        
        if provider == LLM_Enums.GOOGLE_AI.value:
            return GoogleAIProvider(
                api_key=self.config.GOOGLE_AI_API_KEY
            )

        if provider == LLM_Enums.LLAMA_CPP.value:
            return LlamaCPPProvider(
                n_gpu_layers=self.config.LLAMA_CPP_N_GPU_LAYERS,
                n_ctx=self.config.LLAMA_CPP_N_CTX
            )
        
        return None