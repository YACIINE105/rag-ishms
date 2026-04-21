from fastapi import  APIRouter, Depends, UploadFile, status
from fastapi.responses import JSONResponse
import os
from helpers.config import get_settings, Settings
from controllers import DataController, ProjectController, ProcessController
import aiofiles #    مكتبة تُستخدم للتعامل مع الملفات بشكل غير متزامن 
from models.enums import ResponseSignal
import logging
from .schemes.data import ProcessRequest


logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"]
)

@data_router.post("/upload/{project_id}")
async def upload_data(project_id:str, file:UploadFile,
                      app_settings : Settings =Depends(get_settings)):
    
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
             "file_id":file_unique_id})
    
    
    
    
    
@data_router.post("/process/{project_id}")
async def process_endpoint(project_id:str, process_request:ProcessRequest):
    
    file_id= process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    
    process_controller = ProcessController(project_id=project_id)
    
    file_content = process_controller.get_file_content(file_id=file_id)
    file_chunks = process_controller.process_file_content(file_content=file_content, file_id=file_id,
                                                     chunk_size=chunk_size, overlap_size=overlap_size)

    if file_chunks is None or  len(file_chunks)==0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST,
                            content={
                                "status":ResponseSignal.Processing_Failed.value
                            })

    return file_chunks

# , JSONResponse(status_code=status.HTTP_200_OK,
#                             content={
#                                 "status":ResponseSignal.Peocessing_Success.value
#                             })
