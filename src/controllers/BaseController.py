from helpers.config import get_settings , Settings
import os
import random, string
# this file is for 

class BaseController:
    def __init__(self):
        self.app_settings = get_settings()
        self.base_dir  = os.path.dirname(os.path.dirname(__file__))
        self.files_dir = os.path.join(self.base_dir , "assets/files")
        
    def generate_random_strings(self, lenght:int=12):
        return ''.join(random.choices(string.ascii_lowercase+string.digits, k=lenght))   
        