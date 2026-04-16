from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from controllers import Interaction

check_router = APIRouter(
    prefix="/api/v1/drug",
    tags=["api_v1", "drug"]
)


@check_router.post("/check/{new_med}")
async def check(new_med:str):
    prev = ["warfarin", "metformin"]
    checked   = Interaction().full_interaction_check(current_meds = prev, new_med=new_med)
    
    return JSONResponse(status_code=status.HTTP_200_OK, content=checked)
        
    
    
    