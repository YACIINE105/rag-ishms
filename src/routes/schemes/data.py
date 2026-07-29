from pydantic import BaseModel
from typing import Optional
class ProcessRequest(BaseModel):
    #file_id is now optional if got it process it else procedss all file in the folder
    file_id : str = None
    chunk_size : Optional[int]=100
    overlap_size:Optional[int]=20
    reset:Optional[int]=0
    