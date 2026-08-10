from enum import Enum

class ResponseSignal(Enum):
    File_Type_Is_Not_Supported = "file_type_is_not_supported"
    File_Size_Exceeded = "file_size_exceeded"
    File_Upload_Success = "file_upload_success"
    File_Upload_Failed = "file_upload_failed"
    Processing_Failed = "Processing_Failed"
    Peocessing_Success = "Processing_Success"
    File_Empty = "Empty_file"
    FILES_NOT_FOUND_ERROR = "FILES_NOT_FOUND"
    FILE_RECORD_ERROR = "NO_RECORD_WAS_FOUND_FOR_THIS_FILE_ID"
    PROJECT_NOT_FOUND_ERROR = "Project_not_found_error"
    INSERT_INTO_VECTOR_DB_ERROR = "Insert_into_vector_db_error"
    INSERT_INTO_VECTOR_DB_SUCCESS = "Insert_into_vector_db_success"
    VECTOR_DB_COLLECTION_RETRIEVED = "vectordb_collection_retrieved"
    VECTORS_SEARCH_Success = "vectors_search_Success"
    VECTORS_SEARCH_Failed = "vectors_search_failed"
    RAG_ANSWER_FAILED = "rag_answer_failed"
    RAG_ANSWER_SUCCESS = "rag_answer_success"
    