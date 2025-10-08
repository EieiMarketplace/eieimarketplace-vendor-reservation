 
 
from typing import List, Optional
from fastapi import HTTPException, status
import httpx
import json
from dependencies.constant import ALL_STATUS
from schemas.markets import Market, MarketResponse
from crud.reservations import ReservationRepository
from schemas.reservations import ChangeReservationStatusRequest, ReservationByMarketIdResponse, ReservationCreate, ReservationInfo, ReservationResponse, ReservationVenderResponse, MarketInfo, LogInfo, UserInfo
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
    
    @staticmethod
    async def get_market_by_id(marketId:str)->Market:
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
        return response_data
    
    async def update_market_logs(market:Market,token:str):
     
        url = f"{settings.MARKET_SERVICE_URL}/{market['id']}"
        print("moodeng")
        #  เตรียม multipart form-data
        form_data = {
            "marketName": market["marketName"],
            "address": market["address"],
            "coverImageKey": market.get("coverImageKey", ""),
            "logs": json.dumps(market["logs"]),  
            "marketPlanKeys": json.dumps([key["marketPlanKey"] for key in market.get("marketPlanKeys", [])]),
            "deletedMarketKeys": json.dumps([]),   
            "detail": market.get("detail", ""),
            "rule": market.get("rule", ""),
            "isOpen": str(market.get("isOpen", True)).lower(),
            "marketType": market.get("marketType", ""),
        }
        headers = {
            "Authorization": f"Bearer {token}"
        }



        async with httpx.AsyncClient() as client:
            response = await client.put(url, data=form_data,headers=headers)

        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)

        return response.json()
    
    @staticmethod
    async def change_reservation_status(reservationID:str,changeStatus:ChangeReservationStatusRequest,userInfo:UserInfo) -> List[ReservationByMarketIdResponse]:
        try:
            reservation= await ReservationRepository.get_reservation_by_id(reservationID,"organizer")
            if not reservation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reservation with id '{reservationID}' not found.",
            )
                
            if changeStatus.vendorReservationPresentStatus not in ALL_STATUS or changeStatus.vendorReservationNextStatus not in ALL_STATUS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"There is no present or next status that you provide in System !!",
            )
               
            #Main Logic    
            if(changeStatus.vendorReservationPresentStatus=="APPLICATION" and changeStatus.vendorReservationNextStatus=="WAITFORPAY"):
                print("Update Reservation Status and Log for him/her !!")
                if(changeStatus.logName==""):
                     raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"The log is required",
                 )
                     
                market=await ReservationService.get_market_by_id(changeStatus.marketId)
                
                found = False
                for log in market["logs"]:
                    if log["name"] == changeStatus.logName:
                        
                        log["userID"] = changeStatus.vendorId
                        log["reservationID"] = reservationID
                        found = True
                        print(f"Updated log: {log}")
                        break

                if not found:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Log name '{changeStatus.logName}' not found in market '{market['marketName']}'",
                    )

                updatedMarket=await ReservationService.update_market_logs(market,userInfo.token)
                print("Updated Market Management  Successfully")
                response=await ReservationRepository.update_reservation_status(reservationID, changeStatus.vendorReservationNextStatus)
                return response
                
            elif (changeStatus.vendorReservationPresentStatus=="WAITFORPAY" and changeStatus.vendorReservationNextStatus=="RETIRE"):
                print("Update Status and delete Log if it send and check that the reservation id is surely correct")
                
                if(changeStatus.logName==""):
                     raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"The log is required",
                 )
                     
                market = await ReservationService.get_market_by_id(changeStatus.marketId)

         
                found = False
                for log in market["logs"]:
                    if log["name"] == changeStatus.logName and log.get("reservationID") == reservationID:
                        print(f"Found matching log: {log}")
                        log["userID"] = ""
                        log["reservationID"] = ""
                        found = True
                        break

                if not found:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cannot find a log in market '{market['marketName']}' with reservationID '{reservationID}'",
                    )
                    
                updatedMarket = await ReservationService.update_market_logs(market, userInfo.token)
                print("Removed reservation from Market logs successfully")

                response = await ReservationRepository.update_reservation_status(reservationID, changeStatus.vendorReservationNextStatus)
                print("Updated reservation status to RETIRE successfully")
                return response
            elif (changeStatus.vendorReservationNextStatus=="WAITFORPAT" and changeStatus.vendorReservationNextStatus=="VALIDATESLIP"):
                print("MAY BE USE ANOTHER SERVICE THAT IMPLEMENT WITH CALL BACK")
            elif (changeStatus.vendorReservationPresentStatus=="VALIDATESLIP" and changeStatus.vendorReservationNextStatus=="MERCHANT"):
                print("Update Reservation Status")
            elif (changeStatus.vendorReservationPresentStatus=="MERCHANT" and changeStatus.vendorReservationNextStatus=="WAITFORPAY"):
                print("UPDATE Reservation Status")
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unexpected Present or Next Status",
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
         