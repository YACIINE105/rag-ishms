from fastapi import  APIRouter, Depends, UploadFile, status, Request
from fastapi.responses import JSONResponse
import os
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController, ProcessController
import aiofiles #    مكتبة تُستخدم للتعامل مع الملفات بشكل غير متزامن 
from models.enums import ResponseSignal
import logging
from .schemes.data import ProcessRequest
from models import ProjectModel
from models.db_schems import DataChunk
from models.db_schems.ChunkModel import ChunkModel

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"]
)

@data_router.post("/upload/{project_id}")
async def upload_data(request:Request, project_id:str, file:UploadFile,
                      app_settings : Settings =Depends(get_settings)):
    
    
    projectmodel = ProjectModel(db_client=request.app.db_client)
    
    project = await projectmodel.get_project_or_create_one(project_id=project_id)
    # Vaildating the uploaded file properities.
    data_controller = DataController()
    
    is_valid, result_signal = data_controller.validate_uploaded_file(file=file)
    
    if not is_valid:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={
                "signal":result_signal
            }
        )

    project_dir_path = ProjectController().get_project_path(project_id=project_id)
    
    file_path, file_unique_id = data_controller.unique_file_path_generator(
        orign_file_name=file.filename,
        project_id=project_id)
    
    # the best way to write a file on server 
    try:    
        async with aiofiles.open(file_path, "wb") as f:
            while chunk := await file.read(app_settings.FILE_CHHUNK_SIZE):
                await f.write(chunk)
    except Exception as e:
        logger.error(f"Error while uploading file: {e}")
        
        return JSONResponse(
        content=ResponseSignal.File_Upload_Failed.value)
        
    return JSONResponse(content={"status":ResponseSignal.File_Upload_Success.value,
             "file_id":file_unique_id
             })
    
    
    
    
    
@data_router.post("/process/{project_id}")
async def process_endpoint(request :Request, project_id:str, process_request:ProcessRequest):
    
    file_id= process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset  =process_request.reset
    
    
    projectmodel = ProjectModel(db_client=request.app.db_client)
    
    project = await projectmodel.get_project_or_create_one(project_id=project_id)

    
    
    process_controller = ProcessController(project_id=project_id)
    
    file_content = process_controller.get_file_content(file_id=file_id)
    file_chunks = process_controller.process_file_content(file_content=file_content, file_id=file_id,
                                                     chunk_size=chunk_size, overlap_size=overlap_size)

    if file_chunks is None or  len(file_chunks)==0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={
                                "status":ResponseSignal.Processing_Failed.value
                            })

    file_chunks_records = [
        DataChunk(
            chunk_metadata=chunk.metadata,
            chunk_order=i+1,
            chunk_project_id=project.id,
            chunk_text=chunk.page_content
        )
        for i, chunk in enumerate(file_chunks)
    ]

    chunk_model = ChunkModel(
        db_client=request.app.db_client
    )
    
    if do_reset==1:
        _ = await chunk_model.delete_chunk_by_project_id(
            project_id=project.id
        )

    number_of_records = await chunk_model.insert_many_chunks(chunks=file_chunks_records)

    return JSONResponse(
        content={
            "signal":ResponseSignal.Peocessing_Success.value,
            "inserted_chunks":number_of_records
        }
    )

# , JSONResponse(status_code=status.HTTP_200_OK,
#                             content={
#                                 "status":ResponseSignal.Peocessing_Success.value
#                             })
