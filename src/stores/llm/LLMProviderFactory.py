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
            api_key = self.config.OPENAI_API_KEY
            api_url = self.config.OPENAI_BASE_URL
            generation_api_key = None
            if role == "generation":
                generation_api_key = getattr(self.config, "GENERATION_API_KEY", None)
                api_key = generation_api_key or api_key
                api_url = getattr(self.config, "GENERATION_BASE_URL", None) or api_url

            openrouter_url = (
                getattr(self.config, "OPENROUTER_BASE_URL", None)
                or "https://openrouter.ai/api/v1"
            )
            api_keys = []
            if (
                api_url
                and api_url.rstrip("/") == openrouter_url.rstrip("/")
                and not generation_api_key
            ):
                configured_keys = getattr(self.config, "OPENROUTER_API_KEYS", [])
                key_index = getattr(self.config, "OPENROUTER_API_KEY_INDEX", 0)
                ordered_keys = configured_keys[key_index:] + configured_keys[:key_index]
                api_keys = [key.get_secret_value() for key in ordered_keys]
                if api_keys:
                    api_key = api_keys[0]

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
                api_key=api_key,
                api_url=api_url,
                api_keys=api_keys or None,
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
