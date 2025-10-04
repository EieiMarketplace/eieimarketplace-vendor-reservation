from typing import Optional
from pydantic import BaseModel, Field

class VendorReservationStatus(BaseModel):
    id: str=Field(primary_key=True)
    status: str= Field(max_length=200)

class VendorReservation(BaseModel):
    id: str=Field(primary_key=True)
    product: str = Field(max_length=200)
    detail: Optional[str]= Field(max_length=500)
    vendorId: str
    vendorReservationStatus: str=Field() #Id of Vendor Reservation Status
    model_config = {
        "populate_by_name": True,    
        "extra": "ignore"            
    }
