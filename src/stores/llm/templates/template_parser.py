import os 
class TemplateParser:
    def __init__(self, language:str=None, default_language='en'):
        self.current_path = os.path.dirname(os.path.abspath(__file__))
        self.default_language = default_language
        self.language = None
        self.set_language(language=language)


    def set_language(self, language : str ):
        if not language :
           self.language  = self.default_language
            
        language_path = os.path.join(self.current_path, "locales", language)
        if os.path.exists(language_path):
         self.language = language
        
        else:
            self.language  = self.default_language
                     

    def get(self, group:str, key:str, vars:dict={}):
        
        if not (group or key ):
            None
        
        group_path = os.path.join(self.current_path, "locales", self.language, f"{group}.py")
        targeted_language = self.language
        if not os.path.exists(group_path):
            group_path = os.path.join(self.current_path, "locales", self.default_language, f"{group}.py")
            targeted_language = self.default_language
            
        if not os.path.exists(group_path):
            return None
        
        # import group module
        modules = __import__(f"stores.llm.templates.locales.{targeted_language}.{group}", fromlist=[group])
        
        key_attribuite = getattr(modules, key)
        # filing the template with the doc num and chunk text vars 
        return key_attribuite.substitute(vars)