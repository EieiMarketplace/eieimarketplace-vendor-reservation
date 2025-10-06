 
 
from typing import List, Optional
from fastapi import HTTPException, status
import httpx
from dependencies.constant import ALL_STATUS
from schemas.markets import Market, MarketResponse
from crud.reservations import ReservationRepository
from schemas.reservations import ReservationByMarketIdResponse, ReservationCreate, ReservationInfo, ReservationResponse, ReservationVenderResponse, MarketInfo, LogInfo, UserInfo
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
                response  = await client.get(f"{settings.MARKET_SERVICE_URL}/{market_id}")
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
            
        response_data:Market = response.json()
        print("res",response_data)
        if(response_data['isOpen']==False):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"The market with id {market_id} is already close: {response.status_code}",
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
        
    @staticmethod
    async def search_reservation(userInfo: UserInfo,marketId: str, vendorReservationStatus: str) -> List[ReservationByMarketIdResponse]:
        organizorId=userInfo.user_id
        try:
            if vendorReservationStatus not in ALL_STATUS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"There is no {vendorReservationStatus} in System !!",
            )
            
         
            async with httpx.AsyncClient() as client:
                try:
                    response  = await client.get(f"{settings.MARKET_SERVICE_URL}/{marketId}")
                   
                except httpx.RequestError as e:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"Cannot connect to Market Service: {str(e)}",
                    )

            if response.status_code == 404:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Market with id '{marketId}' not found.",
                )
            elif response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail=f"Unexpected response from Market Service: {response.status_code}",
                )
                
            response_data:Market = response.json()
            # print(response_data)
            # if(response_data['userid']!=organizorId):
            #     raise HTTPException(
            #         status_code=status.HTTP_401_UNAUTHORIZED,
            #         detail=f"You are not owner of this market",
            #     )    
                
            reservations_cursor = await ReservationRepository.search_reservation_by_marketid(
                market_id=marketId, vendor_reservation_status=vendorReservationStatus
            )
            return reservations_cursor
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    
        