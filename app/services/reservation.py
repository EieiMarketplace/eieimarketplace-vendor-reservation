 
from typing import Optional
from fastapi import HTTPException, status
import httpx
from crud.reservations import ReservationRepository
from schemas.reservations import ReservationCreate, ReservationInfo, ReservationResponse, ReservationVenderResponse, MarketInfo, LogInfo, UserInfo
from core.config import settings

class ReservationService:
    @staticmethod
    async def get_reservation(reservationId: str, userInfo: UserInfo) -> Optional[ReservationInfo]:
        reservation = await ReservationRepository.get_reservation_by_id(reservationId, userInfo.role)
        vendorId = reservation.vendorId if reservation else ""
        vendorInfo = await ReservationRepository.get_user_info(vendorId, userInfo.token)
        
        if not reservation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Reservation with id '{reservationId}' not found.",
            )
        
        reservation.vendorName = getattr(vendorInfo, "first_name", "NaN") + " " + getattr(vendorInfo, "last_name", "NaN")
        return reservation


    @staticmethod
    async def create_reservation(vendor_id: str, payload: ReservationCreate) -> ReservationResponse:
 
        market_id = payload.marketId
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