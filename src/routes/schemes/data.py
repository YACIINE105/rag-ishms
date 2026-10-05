from pydantic import BaseModel, Field, model_validator


class ProcessRequest(BaseModel):
    file_id: str | None = None
    chunk_size: int = Field(default=100, ge=1)
    overlap_size: int = Field(default=20, ge=0)
    breakpoint_threshold_type: str = "percentile"
    breakpoint_threshold_amount: float = 95
    do_emantic_chunk: int = 1
    do_reset: int = 0

    @model_validator(mode="after")
    def check_overlap(self):
        if self.overlap_size >= self.chunk_size:
            raise ValueError("overlap_size must be less than chunk_size")
        return self
