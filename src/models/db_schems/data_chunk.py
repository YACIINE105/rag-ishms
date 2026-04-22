from pydantic import BaseModel, Field, validator
from bson.objectid import ObjectId
from typing  import Optional

class DataChunk(BaseModel):
    _id : Optional[ObjectId]
    chunk_size: str = Field(..., min_length=1)
    chunk_metadata : dict = Field(..., min_length=1)
    chunk_order : int= Field(..., gt=0) # refer to greater than 0.
    chunk_project_id : ObjectId
    
    
    
    class Config:
        arbitrary_tybes_allowed = True  
    