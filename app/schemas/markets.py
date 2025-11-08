from typing import Optional,List
from pydantic import BaseModel, Field


class Log(BaseModel):
    name: str
    size: str
    price: float
    user_id: str = Field(..., alias="userID")          # vendor ID (FK)
    reservation_id: str = Field(..., alias="reservationID")
class Market(BaseModel):   
    id: str
    market_name: Optional[str] = Field(None)
    address: Optional[str] = None
    cover_image_key: Optional[str] = Field(None)
    logs: List[Log] = Field(default_factory=list)
    detail: Optional[str] = None
    rule: Optional[str] = None
    user_id: Optional[str] = Field(None)
    userid: Optional[str] = Field(None)
    cover_image_url: Optional[str] = Field(None)
    isOpen: Optional[bool] = None
    marketType: Optional[str] = None
 
    
class MarketResponse(BaseModel):
    data: Market
    
 