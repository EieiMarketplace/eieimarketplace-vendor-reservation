

from typing import Optional
from pydantic import BaseModel, Field

class Market(BaseModel):   
    id: str
    market_name: Optional[str] = Field(None, alias="marketName")
    address: Optional[str] = None
    detail: Optional[str] = None
    rule: Optional[str] = None
    user_id: Optional[str] = Field(None, alias="userid")
    cover_image_url: Optional[str] = Field(None, alias="coverImageUrl")
    isOpen: Optional[bool] = None
    
class MarketResponse(BaseModel):
    data: Market