from fastapi import  APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
from .schemes import PushRequest, SearchRequest
from models import ProjectModel, ChunkModel
from controllers import NLPController
from models.enums import ResponseSignal
from bson.objectid import ObjectId
import logging



logger = logging.getLogger('uvicorn.error')


nlp_router = APIRouter(
    prefix="/api/v1/nlp",
    tags=["api_v1", "nlp"]
    )

@nlp_router.post("/index/push/{project_id}")
async def index_project(request:Request, project_id:str, push_request:PushRequest):
    do_reset = push_request.do_reset
    
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal":ResponseSignal.PROJECT_NOT_FOUND_ERROR.value})
    
    chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    
    nlp_controller = NLPController(vector_db_client=request.app.vector_db_client,
                                   generation_client=request.app.generation_client,
                                   embedding_client=request.app.embedding_client)
        
    has_records = True
    page_number = 1
    inserted_items_count = 0
    idx = 0 
    while has_records:
        page_chunks = await chunk_model.get_project_chunks(project_id=project.id, page_number=page_number)
        
            
        if not page_chunks or len(page_chunks) == 0:
            has_records=False
            break
        
        chunks_ids = list(range(idx, (idx + len(page_chunks))))
        
        idx += len(page_chunks)
        is_inserted = nlp_controller.index_into_vector_db(project=project, chunks=page_chunks, 
                                                          chunks_ids =chunks_ids, 
                                                          do_reset=do_reset if page_number == 1 else False)
        page_number+=1
        
        if not is_inserted:
            return JSONResponse(
                status_code=status.HTTP_400_BAD_REQUEST,
                            content={"signal":ResponseSignal.INSERT_INTO_VECTOR_DB_ERROR.value}
            )
        
        inserted_items_count += len(page_chunks)
        
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"signal":ResponseSignal.INSERT_INTO_VECTOR_DB_SUCCESS.value,
                                 "inserted_items_count":inserted_items_count
                                }
            )
    
    
@nlp_router.get("/index/info/{project_id}")
async def get_project_index_info(request:Request, project_id:str):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal":ResponseSignal.PROJECT_NOT_FOUND_ERROR.value})

    nlp_controller = NLPController(vector_db_client=request.app.vector_db_client,
                                generation_client=request.app.generation_client,
                                embedding_client=request.app.embedding_client)
    
    collection_info = nlp_controller.get_vector_db_collection_info(project=project)
    
    
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"signal":ResponseSignal.VECTOR_DB_COLLECTION_RETRIEVED.value,
                                 "collection_info":collection_info.model_dump()
                                }
                )
    
    
@nlp_router.get("/index/search/{project_id}")
async def search_index(request:Request, project_id:str, search_request:SearchRequest):
    project_model = await ProjectModel.create_instance(db_client=request.app.db_client)
    project = await project_model.get_project_or_create_one(project_id=project_id)

    if not project:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"signal":ResponseSignal.PROJECT_NOT_FOUND_ERROR.value})

    nlp_controller = NLPController(vector_db_client=request.app.vector_db_client,
                                generation_client=request.app.generation_client,
                                embedding_client=request.app.embedding_client)
    
    indexed_vectors =  nlp_controller.search_vector_db_collection(project=project,
                                                                  text=search_request.text,
                                                                  limit=search_request.limit)
    
    
    if not indexed_vectors:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                        content={"signal":ResponseSignal.VECTORS_SEARCH_Failed.value,
                                    "indexed_vectors":indexed_vectors
                                }
                )
    
    return JSONResponse(status_code=status.HTTP_200_OK,
                        content={"signal":ResponseSignal.VECTORS_SEARCH_Success.value,
                                 "indexed_vectors":indexed_vectors
                                }
                )