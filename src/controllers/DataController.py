from .BaseController import BaseController
from fastapi import UploadFile, Depends
from models.enums import ResponseSignal
from .ProjectController import ProjectController
import re # regex is a lib for processing texts 
import os

class DataController(BaseController):
    #data contrpller calling child controller
    def __init__(self):
        super().__init__()
        self.size_scaler =1048576
        
         
    def validate_uploaded_file(self, file:UploadFile):
        if file.content_type not in self.app_settings.FILE_ALLOWED_TYPES:
            return False, ResponseSignal.File_Type_Is_Not_Supported.value
        if file.size > self.app_settings.FILE_MAX_SIZE*self.size_scaler:
            return False, ResponseSignal.File_Size_Exceeded.value
        return True, ResponseSignal.File_Upload_Success.value


    def get_clean_file_name(self,orign_file_name:str ):
        # for removing any special charachters , except dots and underscores .
        cleaned_file_name = re.sub(r'[^\w.]', '', orign_file_name.strip())
        return cleaned_file_name
    
    def unique_file_name_generator(self, orign_file_name:str, project_id:str):
        random_file_name = self.generate_random_strings()
        project_path = ProjectController().get_project_path(project_id=project_id)
        cleaned_file_name  = self.get_clean_file_name(orign_file_name=orign_file_name)
         
        new_file_path = os.path.join( project_path,
                                     random_file_name+"_"+cleaned_file_name)
        
        while os.path.exists(new_file_path):
            random_file_name = self.generate_random_strings()
            new_file_path = os.pat.join( project_path ,
                                        random_file_name+"_"+cleaned_file_name)

        return new_file_path

        
        
        
