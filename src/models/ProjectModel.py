from .BaseDataModel import BaseDataModel
from .enums.DataBaseEnum import DataBaseEnum
from .db_schems.rag_ishms.schemes import Project

from sqlalchemy.future import select
from sqlalchemy import func


class ProjectModel(BaseDataModel):
    def __init__(self, db_client: object):
        super().__init__(db_client=db_client)
        self.db_client = db_client


    @classmethod
    async def create_instance(cls, db_client: object):
        instance = cls(db_client)
        return instance


    async def create_project(self, project: Project):
        async with self.db_client() as session:
            async with session.begin():
                session.add(project)
            await session.refresh(project)
        return project


    async def get_project_or_create_one(self, project_id: int):
        async with self.db_client() as session:
            async with session.begin():
                query = select(Project).where(Project.project_id == project_id)
                result = await session.execute(query)
                project = result.scalar_one_or_none()

                if project is None:
                    project = Project(project_id=project_id)
                    session.add(project)
                    await session.flush()   # get generated fields (e.g. PK) without ending the transaction 
                    await session.refresh(project)

                return project


    async def get_all_projects(self, page: int = 1, page_size: int = 10):
        async with self.db_client() as session:
            async with session.begin():
                count_result = await session.execute(select(func.count(Project.project_id)))
                total_documents = count_result.scalar_one()

                total_number_of_pages = total_documents // page_size
                if total_documents % page_size > 0:
                    total_number_of_pages += 1

                query = select(Project).offset((page - 1) * page_size).limit(page_size)
                result = await session.execute(query)
                projects = result.scalars().all()

                return projects, total_number_of_pages
            