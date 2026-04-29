from ..BaseDataModel import BaseDataModel
from ..enums.DataBaseEnum import DataBaseEnum
from .project import Project

class ProjectModel(BaseDataModel):
    def __init__(self , db_client:object):
        super().__init__(db_client=db_client)
        self.collection = self.db_client[DataBaseEnum.COLLECTION_PROJECT_NAME.value]
        
    async def create_project(self, project:Project):
        result = await self.collection.insert_one(project.dict()) # insert functoin allow only dicts.
        project.id = result.inserted_id
        return project
    
    async def get_project_or_create_one(self, project_id:str):
        # checking and getting part. 
        record = await self.collection.find_one({
            "project_id":project_id
        })

        # creating the project.
        if record is None: 
            project= Project(project_id=project_id)
            project = await self.create_project(project=project)
            
            return project
        
        return Project(**record) # this returns project data model.
    
    
    async def get_all_projects(self, page:int=1, page_size:int=10):
    # this is called paggination.
        # count total number of documents
        total_documents = await self.collection.count_documents({})
        
        # calculate total number of pages
        total_number_of_pages = total_documents//page_size
        if total_documents % page_size >0:
            total_number_of_pages+=1
        # skipping pages
        cursor = self.collection.find().skip((page-1)*page_size).limit(page_size)
        
        #listing all pages
        # document = list(cursor) 
        projects = []
        async for document in cursor:
            projects.append(
                Project(**document)
            )
        
        return projects , total_number_of_pages