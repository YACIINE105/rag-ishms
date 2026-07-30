from enum import Enum

class LLM_Enums(Enum):
    OPENAI = "OPENAI"
    COHERE= "COHERE"
    
class OpenAI_Enums(Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"
    
class Cohere_Enums(Enum):
    USER = "user"
    SYSTEM = "system"
    ASSISTANT = "assistant"
    
    DOCUMENT = "search_document"
    QUERY = "search_query"

    
class DocumentTypeEnum(Enum):
    DOCUMENT = "document"
    QUERY = "query"

