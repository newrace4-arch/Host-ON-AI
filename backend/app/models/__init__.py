"""SQLAlchemy 모델 패키지 — DB명세서 v1.4의 19개 테이블.

Alembic autogenerate가 모든 테이블을 인식하려면 여기서 전부 임포트해야 한다.

v1.4 신설 3개(17~19)는 **새 파일이 아니라 기존 파일 안**에 들어가 있다 —
`ResponseSource`는 `inquiry.py`, `CleaningTaskPhoto`는 `cleaning.py`,
`ChannelFeeRate`는 `settlement.py`. 셋 다 기존 도메인에 붙는 테이블이라
그 도메인 파일에 두는 편이 읽기 쉽다.
"""

from app.core.database import Base
from app.models.action_item import ActionItem
from app.models.channel import ChannelConnection
from app.models.cleaning import CleaningTask, CleaningTaskPhoto
from app.models.compliance import ChecklistItem
from app.models.host import Host
from app.models.inquiry import (
    Inquiry,
    InquiryApproval,
    InquiryClassification,
    InquiryResponse,
    ResponseSource,
)
from app.models.property import Bed, Property, Room
from app.models.rag import KnowledgeChunk
from app.models.reservation import Reservation
from app.models.settlement import (
    ChannelFeeRate,
    FinancialConfig,
    MonthlySettlement,
)

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
    # 17. response_sources [v1.4 신규]
    "ResponseSource",
    # 18. cleaning_task_photos [v1.4 신규]
    "CleaningTaskPhoto",
    # 19. channel_fee_rates [v1.4 신규]
    "ChannelFeeRate",
]
