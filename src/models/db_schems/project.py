from pydantic import BaseModel, Field, validator
from typing import Optional
from bson.objectid import ObjectId # is an  object from motor 

class Project(BaseModel):
    _id : Optional[ObjectId]
    project_id:str = Field(..., min_length=1) # 3 dots means take all default vals of the class 


    #why validator is having a line ? It tells the interpreter: wrap the next function with this validation behavior.
    @validator('project_id') 
    def validate_project_id(cls, value):
        if not value.isalnum(): # check if the value is alpha numeric
            raise ValueError('project_id is n ot alphanumeric')


        return value
    
    class Config: # this class is allowing types that the validator don't no how to deal with it. 
        arbitrary_tybes_allowed = True
        
        
        