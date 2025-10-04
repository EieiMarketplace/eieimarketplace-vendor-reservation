from typing import Optional, List
from pydantic import BaseModel, Field


class ReservationCreate(BaseModel):
    product: str = Field(...,max_length=200, description="product must be 1-200 characters")
    detail: Optional[str]= Field(...,max_length=500)
    marketId: str=Field(...,description="marketId must have")
    # vendorId: str = Field(description="vendor reservation must have vendorId") #TODO: Might be use from Bearer Token
    vendorReservationStatus: str=Field(...,description="vendorReservation status must have") #Id of Vendor Reservation Status

class ReservationResponse(BaseModel):
    id:str
    product:str
    detail:str
    vendorId: str
    marketId:str
    vendorReservationStatus:str

class MarketInfo(BaseModel):
    market_name: str
    isOpen: bool
    marketType: str

class LogInfo(BaseModel):
    name: str
    size: str
    price: int
    user_id: str
    reservation_id: str

class ReservationVenderResponse(BaseModel):
    id: str
    vendorId: str
    product: str
    markets: MarketInfo
    vendorReservationStatus:str
    log: Optional[LogInfo] = None
    #createdTime: str  # You can use datetime
    #updatedTime: str  # You can use datetime

class SlipImage(BaseModel):
    url: str
    description: Optional[str] = None

class ReservationInfo(BaseModel):
    vendorName: str
    vendorReservationStatus: str
    vendorId: str
    marketID: str
    marketInfo: MarketInfo
    # reservationTime: str # To Add Later
    reservationProduct: str
    reservationDetail: str
    Log: Optional[List[LogInfo]]
    # Slip: List[SlipImage] # To Add Later

class UserInfo(BaseModel):
    user_id: str
    role: str
    token: str
    first_name: str
    last_name: str
 