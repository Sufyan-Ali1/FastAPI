from enum import Enum

class order_status(str,Enum):
    DRAFT = "draft"
    RECEIVED = "received"
    CANCELLED = "cancelled"