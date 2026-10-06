import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship

from .rag_ishms_base import SQLAlchemyBase


class Asset(SQLAlchemyBase):
    __tablename__ = "assets"

    asset_id = Column(Integer, autoincrement=True, primary_key=True)
    asset_uuid = Column(
        UUID(as_uuid=True), nullable=False, default=uuid.uuid4, unique=True
    )

    asset_type = Column(String, nullable=False)
    asset_size = Column(Integer, nullable=False)
    asset_config = Column(JSONB, nullable=True)

    asset_pushed_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    asset_name = Column(String, nullable=False)
    unique_asset_name = Column(String, nullable=False)

    asset_project_id = Column(
        Integer, ForeignKey("projects.project_id"), nullable=False
    )
    project = relationship("Project", back_populates="assets")
    chunks = relationship("DataChunk", back_populates="asset")

    __table_args__ = (
        Index("ix_asset_project_id", asset_project_id),
        Index("ix_asset_type", asset_type),
    )
