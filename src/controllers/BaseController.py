from helpers.config import get_settings , Settings
import os
import random, string
# this file is for 

class BaseController:
    def __init__(self):
        self.app_settings = get_settings()
        self.base_dir  = os.path.dirname(os.path.dirname(__file__))
        self.files_dir = os.path.join(self.base_dir , "assets/files")
        self.vector_DB_dir = os.path.join(self.base_dir, "assets/Vectordatabase" )
        
        
    def generate_random_strings(self, lenght:int=12):
        return ''.join(random.choices(string.ascii_lowercase+string.digits, k=lenght))   
        
        
    def get_database_path(self, db_name:str):
        vector_DB_path = os.path.join(self.vector_DB_dir, db_name)
        
        if not os.path.exists(vector_DB_path):
            os.makedirs(vector_DB_path)
            
        return vector_DB_path