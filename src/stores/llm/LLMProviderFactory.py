from .LLMEnums import LLM_Enums
from .providers import (
    CohereProvider,
    GoogleAIProvider,
    LlamaCPPProvider,
    OpenAIProvider,
)


class LLMProviderFactory:
    def __init__(self, config: dict):
        self.config = config

    def create(self, provider: str, role: str = "embedding"):
        if provider == LLM_Enums.OPENAI.value:
            return OpenAIProvider(
                default_generation_temperature=getattr(
                    self.config, "GENERATION_MODEL_TEMPERATURE", None
                )
                if getattr(self.config, "GENERATION_MODEL_TEMPERATURE", None)
                is not None
                else 0.2,
                default_generation_max_output_token=getattr(
                    self.config, "MAX_OUTPUT_TOKENS", None
                )
                or 1000,
                api_key=(
                    getattr(self.config, "GENERATION_API_KEY", None)
                    or self.config.OPENAI_API_KEY
                )
                if role == "generation"
                else self.config.OPENAI_API_KEY,
                api_url=(
                    getattr(self.config, "GENERATION_BASE_URL", None)
                    or self.config.OPENAI_BASE_URL
                )
                if role == "generation"
                else self.config.OPENAI_BASE_URL,
            )

        if provider == LLM_Enums.COHERE.value:
            return CohereProvider(api_key=self.config.COHERE_API_KEY)

        if provider == LLM_Enums.GOOGLE_AI.value:
            return GoogleAIProvider(api_key=self.config.GOOGLE_AI_API_KEY)

        if provider == LLM_Enums.LLAMA_CPP.value:
            return LlamaCPPProvider(
                n_gpu_layers=self.config.LLAMA_CPP_N_GPU_LAYERS,
                n_ctx=self.config.LLAMA_CPP_N_CTX,
            )

        return None
