from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from controllers import Interaction, ISBAR_GEN


check_router = APIRouter(
    prefix="/api/v1/drug",
    tags=["api_v1", "drug"]
)




class DrugCheckRequest(BaseModel):
    current_medications: list[str]
    new_medication: str


class ISBARRequest(BaseModel):
    identification: str
    background: str



@check_router.post("/check")
async def check(body: DrugCheckRequest):
    checked = Interaction().full_interaction_check(
        current_meds=body.current_medications,
        new_med=body.new_medication
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=checked)



@check_router.post("/isbar")
async def generate_isbar(body: ISBARRequest):
    result = ISBAR_GEN().isbar_gen(
        identification=body.identification,
        background=body.background
    )
    return JSONResponse(status_code=status.HTTP_200_OK, content=result)
