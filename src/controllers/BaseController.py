from helpers.config import get_settings , Settings
# this file is for 

class BaseController:
    def __init__(self):
        self.app_settings = get_settings()

