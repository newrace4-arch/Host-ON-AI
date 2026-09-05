"""SQLAlchemy 모델 패키지 — DB명세서 v1.3의 16개 테이블.

Alembic autogenerate가 모든 테이블을 인식하려면 여기서 전부 임포트해야 한다.
"""

from app.core.database import Base
from app.models.action_item import ActionItem
from app.models.channel import ChannelConnection
from app.models.cleaning import CleaningTask
from app.models.compliance import ChecklistItem
from app.models.host import Host
from app.models.inquiry import (
    Inquiry,
    InquiryApproval,
    InquiryClassification,
    InquiryResponse,
)
from app.models.property import Bed, Property, Room
from app.models.rag import KnowledgeChunk
from app.models.reservation import Reservation
from app.models.settlement import FinancialConfig, MonthlySettlement

__all__ = [
    "Base",
    # 1. hosts
    "Host",
    # 2~4. properties / rooms / beds
    "Property",
    "Room",
    "Bed",
    # 5. channel_connections
    "ChannelConnection",
    # 6. reservations
    "Reservation",
    # 7~8. financial_configs / monthly_settlements
    "FinancialConfig",
    "MonthlySettlement",
    # 9. cleaning_tasks
    "CleaningTask",
    # 10~13. inquiries 계열
    "Inquiry",
    "InquiryClassification",
    "InquiryResponse",
    "InquiryApproval",
    # 14. knowledge_chunks
    "KnowledgeChunk",
    # 15. action_items
    "ActionItem",
    # 16. checklist_items
    "ChecklistItem",
]
