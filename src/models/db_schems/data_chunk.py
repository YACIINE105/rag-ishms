from pydantic import BaseModel, Field, field_validator
from bson.objectid import ObjectId
from typing  import Optional

class DataChunk(BaseModel):
    id : Optional[ObjectId]  = Field(default=None, alias="_id")
    chunk_text: str = Field(..., min_length=1)
    chunk_metadata : dict = Field(..., min_length=1)
    chunk_order : int= Field(..., gt=0) # refer to greater than 0.
    chunk_project_id : ObjectId
    
    
    
    class Config:
        # it fails previously because of a typo
        arbitrary_types_allowed = True  
    