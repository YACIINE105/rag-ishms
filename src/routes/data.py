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
async def upload_data(request:Request, project_id:int, file:UploadFile,
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
        asset_project_id=project.project_id,
        asset_type=AssetTypeEnum.FILE.value,
        unique_asset_name=file_unique_id,
        asset_size=os.path.getsize(file_path),
        asset_name=file.filename
    )
    
    asset_record = await asset_model.create_asset(asset=asset_resource)
    
    old_asset_info, deleted_count = await asset_model.delete_asset_by_name(
                                        asset_project_id=project.project_id,
                                        asset_name=file.filename,
                                        exclude_asset_id=asset_record.asset_id  
                                    )
    
    chunk_model = await ChunkModel.create_instance(
                        db_client=request.app.db_client)
    
    # old_asset_ids = [id["id"] for id in old_asset_info]
    
    # old_asset_unique_name = [id["unique_asset_name"] for id in old_asset_info]
    
    for old_asset in old_asset_info:
        await chunk_model.delete_chunk_by_asset_id(asset_id=old_asset["id"])
        
        old_file_path = os.path.join(project_dir_path, old_asset["unique_asset_name"])
        try:
            if os.path.exists(old_file_path):
                os.remove(old_file_path)
        except Exception as e:
            logger.error(f"Error while deleting old file {old_file_path}: {e}")
        
    
    return JSONResponse(content={"status":ResponseSignal.File_Upload_Success.value,
             "file_id":str(asset_record.asset_id)
             })
    
    
    
    
@data_router.post("/process/{project_id}")
async def process_endpoint(request :Request, project_id:int, process_request:ProcessRequest):
    
    # file_id is now optional if got it process it else procedss all file in the folder.     
    # file_id= process_request.file_id
    chunk_size = process_request.chunk_size
    overlap_size = process_request.overlap_size
    do_reset  =process_request.do_reset
    
    
    projectmodel = await ProjectModel.create_instance(db_client=request.app.db_client)
    
    project = await projectmodel.get_project_or_create_one(project_id=project_id)
    asset_model = await AssetModel.create_instance(db_client=request.app.db_client)
    project_file_ids = {}
    
    no_file_id = None
    if process_request.file_id:
        asset_record = await asset_model.get_asset_record(asset_project_id=project.project_id,
                                                   unique_asset_name=process_request.file_id)
        
        if asset_record is None:
            return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"signal":ResponseSignal.FILE_RECORD_ERROR.value})
            
        
        project_file_ids = {asset_record.asset_id:asset_record.unique_asset_name}
    
    else:

        project_files = await asset_model.get_all_project_assets(asset_project_id=project.project_id,
                                                                 asset_type=AssetTypeEnum.FILE.value)
        project_file_ids = {record.asset_id: record.unique_asset_name for record in project_files}
        no_file_id = True
    
    
    if len(project_file_ids)==0:
        return JSONResponse(status_code=status.HTTP_400_BAD_REQUEST, content={"status":ResponseSignal.FILES_NOT_FOUND_ERROR.value})
    
    process_controller = ProcessController(project_id=project_id)
    
    
    number_of_records=0
    number_of_files = 0
    chunk_model = await ChunkModel.create_instance(
    db_client=request.app.db_client)
    
    ############## BUG FIX: do_reset==1 previously only cleared chunks when
    ############## no_file_id was True, so passing a specific file_id with
    ############## do_reset=1 never cleared that asset's old chunks before
    ############## reprocessing (would have caused duplicate chunks).
    if do_reset==1:
        if no_file_id:
            _ = await chunk_model.delete_chunk_by_project_id(
                project_id=project.project_id
            )
        else:
            asset_id = next(iter(project_file_ids))
            _ = await chunk_model.delete_chunk_by_asset_id(asset_id=asset_id)

    ############## BUG FIX: old logic used delete_chunk_by_asset_id's rowcount
    ############## as a truthy filter, which meant:
    ############## - assets that already HAD chunks got deleted+kept (reprocessed
    #############    every call even with nothing new to do)
    ############## - brand-new assets with NO chunks yet returned rowcount 0 and
    #############    got silently dropped, so new files were NEVER processed
    ############## unless do_reset=1 was passed. Replaced with a pure has-chunks
    ############## check (has_chunks_for_asset) that doesn't delete anything and
    ############## correctly keeps only assets that still need processing.
    elif do_reset!=1 and no_file_id:
        filtered_file_ids = {}
        for asset_id, unique_name in project_file_ids.items():
            if not await chunk_model.has_chunks_for_asset(asset_id):
                filtered_file_ids[asset_id] = unique_name
        project_file_ids = filtered_file_ids
        
        
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

        ############## NOTE: kept as a defensive no-op. With the branch above
        ############## fixed, any asset reaching this point should have zero
        ############## existing chunks already, so this delete is a safety net,
        ############## not load-bearing logic anymore.
        await chunk_model.delete_chunk_by_asset_id(asset_id=asset_id)

        file_chunks_records = [
            DataChunk(
                chunk_metadata=chunk.metadata,
                chunk_order=i+1,
                chunk_project_id=project.project_id,
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
