from enum import Enum

class LLM_Enums(Enum):
    OPENAI = "OPENAI"
    COHERE= "COHERE"
    
class OpenAI_Enums(Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"
    