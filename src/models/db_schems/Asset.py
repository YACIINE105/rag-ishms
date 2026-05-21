from pydantic import BaseModel, Field
from typing import Optional
from bson.objectid import ObjectId # is an  object from motor 
from datetime import datetime


class Asset(BaseModel):
    id : Optional[ObjectId] = Field(default=None, alias="_id")
    asset_project_id:ObjectId
    # sql connection , url , wny file type that has data
    asset_type:str=Field(..., min_length=1)
    # 3 dots means optional
    asset_name:str = Field(..., min_length=1)
    asset_size:int = Field(ge=0, default=None)
    asset_pushed_at : datetime = Field(default=datetime.utcnow)
    
    
    
    class Config: # this class is allowing types that the validator don't no how to deal with it. 
        arbitrary_types_allowed=True
        populate_by_name=True
        
    
    
    
    @classmethod
    def get_indexes(cls)->list[dict]:
        
        return[{
            "key":[("asset_project_id",1)],
            "name":"asset_project_id_index_1",
            "unique":False
        },
        {
            "key":[("asset_project_id",1)
                   ,("asset_name")
                  ],
            "name":"asset_project_id_name_index_1",
            "unique":False
        } 
                  
               ]
        
        
        
        
         