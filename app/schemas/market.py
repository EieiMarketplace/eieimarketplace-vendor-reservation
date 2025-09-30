from typing import Optional
from pydantic import BaseModel, Field


class ReservationCreate(BaseModel):
    product: str = Field(...,max_length=200, description="product must be 1-200 characters")
    detail: Optional[str]= Field(...,max_length=500)
    #vendorId: str = Field(description="vendor reservation must have vendorId") #TODO: Might be use from Bearer Token
    vendorReservationStatus: str=Field(...,description="vendorReservation status must have") #Id of Vendor Reservation Status

class ReservationResponse(BaseModel):
    id:str
    product:str
    detail:str
    vendorId: str
    vendorReservationStatus:str
 