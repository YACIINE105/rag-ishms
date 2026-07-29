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