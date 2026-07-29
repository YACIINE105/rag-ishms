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
from models.db_schems import DataChunk, Asset
from models.AssetModel import AssetModel
from models.ChunkModel import ChunkModel
from models.enums.AssetTypeEnum import AssetTypeEnum

logger = logging.getLogger('uvicorn.error')

data_router = APIRouter(
    prefix="/api/v1/data",
    tags=["api_v1", "data"]
)

@data_router.post("/upload/{project_id}")
async def upload_data(request:Request, project_id:str, file:UploadFile,
                      app_settings : Settings =Depends(get_settings)):
    
    
    projectmodel = await ProjectModel.create_instance(db_client=request.app.db_client)
    
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
    
    
# storing the File / Asset in DB
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
   
    asset_resource = Asset(
        asset_project_id=project.id,
        asset_type=AssetTypeEnum.FILE.value,
        asset_name=file_unique_id,
        asset_size=os.path.getsize(file_path)
    )
    
    asset_record = await asset_model.create_asset(asset=asset_resource)
    
    return JSONResponse(content={"status":ResponseSignal.File_Upload_Success.value,
             "file_id":str(asset_record.id)
             })
    
    
    
    
@data_router.post("/process/{project_id}")
async def process_endpoint(request :Request, project_id:str, process_request:ProcessRequest):
    
    # file_id is now optional if got it process it else procedss all file in the folder.     
    # file_id= process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset  =process_request.reset
    
    
    projectmodel = await ProjectModel.create_instance(db_client=request.app.db_client)
    
    project = await projectmodel.get_project_or_create_one(project_id=project_id)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    project_file_ids = {}
    
    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(asset_project_id=project.id,
                                                   asset_name=process_request.file_id)
        
        if asset_record is None:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal":ResponseSignal.FILE_RECORD_ERROR.value})
            
        
        project_file_ids = {asset_record.id:asset_record.asset_name}
    
    else:

        project_files = await asset_model.get_all_project_assets(asset_project_id=project.id,
                                                                 asset_type=AssetTypeEnum.FILE.value)
        project_file_ids = {record.id:record.asset_name for record in project_files}
    
    
    if len(project_file_ids)==0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status":ResponseSignal.FILES_NOT_FOUND_ERROR.value})
    
    process_controller = ProcessController(project_id=project_id)
    
    
    number_of_records=0
    number_of_files = 0
    chunk_model = await ChunkModel.create_instance(
    db_client=request.app.db_client)
    
    if do_reset==1:
        _ = await chunk_model.delete_chunk_by_project_id(
            project_id=project.id
        )
    for asset_id, file_id in project_file_ids.items():
        file_content = process_controller.get_file_content(file_id=file_id)
        
        if not file_content:
            logger.error(f"error while processing  file: {file_id}")
            continue
        
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
                chunk_text=chunk.page_content,
                chunk_asset_id = asset_id
            )
            for i, chunk in enumerate(file_chunks)
        ]

        # is the number of inserted chunks.
        number_of_records += await chunk_model.insert_many_chunks(chunks=file_chunks_records)
        number_of_files+=1

    return JSONResponse(
        content={
            "signal":ResponseSignal.Peocessing_Success.value,
            "inserted_chunks":number_of_records, 
            "processed_files":number_of_files
        }
    )

# , JSONResponse(status_code=status.HTTP_200_OK,
#                             content={
#                                 "status":ResponseSignal.Peocessing_Success.value
#                             })


######## TESTING IF GIVEN A NON EXIST CHUNK_ID##########

# from fastapi.responses import JSONResponse
# import json
# from bson import json_util

# @data_router.get("/chunks/{chunk_id}")
# async def get_single_chunk(request: Request, chunk_id: str):
#     chunk_model = await ChunkModel.create_instance(db_client=request.app.db_client)
    
#     result = await chunk_model.get_chunk(chunk_id)
    
#     if result is None:
#         from fastapi import HTTPException
#         raise HTTPException(status_code=404, detail="Chunk not found")
        
#     # 1. بنحول الـ Pydantic model لـ dict عادي
#     chunk_dict = result.model_dump()
    
#     # 2. بنستخدم الـ json_util بتاع MongoDB عشان يحول أي ObjectId أو داتا غريبة لنصوص فورا
#     clean_json_str = json_util.dumps(chunk_dict)
    
#     # 3. بنرجع الداتا المنظفة كـ JSONResponse رسمي
#     return JSONResponse(content=json.loads(clean_json_str))
