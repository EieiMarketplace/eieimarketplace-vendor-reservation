 
from fastapi import HTTPException, status
import httpx
from crud.reservations import ReservationRepository
from schemas.reservations import ReservationCreate, ReservationResponse, UserInfo
from core.config import settings

class ReservationService:
    @staticmethod
    async def create_reservation(userInfo: UserInfo, payload: ReservationCreate) -> ReservationResponse:
        vendor_id= userInfo.user_id
        role= userInfo.role
        market_id = payload.marketId
        
        if(role!="vendor"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"You action is not permitted",
            )  
        
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(f"{settings.MARKET_SERVICE_URL}/{market_id}")
                print("response ",response)
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Cannot connect to Market Service: {str(e)}",
                )

        if response.status_code == 404:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Market with id '{market_id}' not found.",
            )
        elif response.status_code != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Unexpected response from Market Service: {response.status_code}",
            )
            
        doc = await ReservationRepository.create_reservation(vendor_id, payload)
 
        return ReservationResponse(
            id=doc["id"],  
            product=doc["product"],
            marketId=doc["marketId"],
            detail=doc["detail"],
            vendorId=doc["vendorId"],
            vendorReservationStatus=doc["vendorReservationStatus"],
        )