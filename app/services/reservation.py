 
 
import asyncio
from typing import List, Optional
import aio_pika
from fastapi import HTTPException, status
import httpx
import json
 
from  messaging.rabbitmq import send_request_for_userInfo
from dependencies.constant import ALL_STATUS
from schemas.markets import Market, MarketResponse
from crud.reservations import ReservationRepository
from schemas.reservations import ChangeReservationStatusRequest, ReservationByMarketIdResponse, ReservationCreate, ReservationInfo, ReservationResponse, ReservationVenderResponse, MarketInfo, LogInfo, UserInfo
from core.config import settings

class ReservationService:
    @staticmethod
    async def get_market_by_id(marketId:str,organizerId:str)->Market:
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
            
        # if(response_data['userid']!=organizorId):
            #     raise HTTPException(
            #         status_code=status.HTTP_401_UNAUTHORIZED,
            #         detail=f"You are not owner of this market",
            #     )    
            
        response_data:Market = response.json()
        return response_data

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
    async def search_reservation(userInfo: UserInfo, marketId: str, vendorReservationStatus: str) -> List[ReservationByMarketIdResponse]:
        organizorId = userInfo.user_id
        try:
            if vendorReservationStatus not in ALL_STATUS:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"There is no {vendorReservationStatus} in System !!",
                )
            
            # Validate market
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(f"{settings.MARKET_SERVICE_URL}/{marketId}")
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
            
            # Get reservations
            reservations_cursor = await ReservationRepository.search_reservation_by_marketid(
                market_id=marketId, vendor_reservation_status=vendorReservationStatus
            )
            
            vendor_ids = list(set([r.vendorId for r in reservations_cursor]))  # Remove duplicates
            
            if not vendor_ids:
                return reservations_cursor

            # Setup RabbitMQ
            connection = await aio_pika.connect_robust(settings.RABBITMQ_URL)
            try:
                channel = await connection.channel()
                exchange = await channel.declare_exchange(
                    settings.USER_TOPIC1, 
                    aio_pika.ExchangeType.TOPIC, 
                    durable=True
                )
                
                # Exclusive queue for responses
                response_queue = await channel.declare_queue(exclusive=True)
                await response_queue.bind(exchange, routing_key="user_info.response")
                
                # Event to wait for response
                response_received = asyncio.Event()
                vendor_name_map = {}
                
                # Background task to consume response
                async def consume_response():
                    async with response_queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            async with message.process():
                                try:
                                    data = json.loads(message.body)
                                    correlation_id = message.correlation_id
                                    
                                    if correlation_id == "batch-user-request":
                                        # data should be list of {vendorId, first_name}
                                        user_list = data.get("users", [])
                                        
                                        for user_info in user_list:
                                            vendor_id = user_info.get("vendorId") or user_info.get("user_id")
                                            first_name = user_info.get("first_name", "Unknown")
                                            vendor_name_map[vendor_id] = first_name
                                        
                                        print(f"✅ Received {len(user_list)} vendor names")
                                        response_received.set()
                                        break
                                        
                                except Exception as e:
                                    print(f"❌ Error processing message: {e}")
                                    response_received.set()  # Set anyway to prevent hanging
                
                # Start consumer task
                consumer_task = asyncio.create_task(consume_response())
                
   
                print(f"📤 Sending batch request for {len(vendor_ids)} vendors...")
                payload = {
                    "event": "batch_user_info_request",
                    "userIds": vendor_ids,
                    "token": userInfo.token,
                }
         
                await exchange.publish(
                    aio_pika.Message(
                        body=json.dumps(payload).encode(),
                        correlation_id="batch-user-request",
                        reply_to=response_queue.name
                    ),
                    routing_key=settings.USER_STATUS
                )
                
                print("⏳ Waiting for batch response...")
                
                # # Wait for response with timeout
                # try:
                #     await asyncio.wait_for(response_received.wait(), timeout=5.0)
                #     print("✅ Batch response received!")
                # except asyncio.TimeoutError:
                #     print("⚠️ Timeout waiting for batch response")
                
                # Cancel consumer task
                consumer_task.cancel()
                try:
                    await consumer_task
                except asyncio.CancelledError:
                    pass
                
                # Merge vendor names into reservations
                for reservation in reservations_cursor:
                    reservation.vendorName = vendor_name_map.get(
                        reservation.vendorId,
                        "Unknown"
                    )
                
                print(f"✅ Successfully merged {len(vendor_name_map)} vendor names")
                
            finally:
                await connection.close()
            
            return reservations_cursor
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
        
    async def update_market_logs(market:Market,token:str):
            print("Test5")
            url = f"{settings.MARKET_SERVICE_URL}/{market['id']}"
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

            print(url)
            async with httpx.AsyncClient() as client:
                response = await client.put(url, data=form_data,headers=headers)

            print(response)
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)

            return response.json()
    
    @staticmethod
    async def change_reservation_status(reservationID:str,changeStatus:ChangeReservationStatusRequest,userInfo:UserInfo) -> List[ReservationByMarketIdResponse]:
        try:
            reservation:ReservationInfo = await ReservationRepository.get_reservation_by_id(reservationID,"organizer")
            if not reservation:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reservation with id '{reservationID}' not found.",
            )
            if(reservation.vendorReservationStatus!=changeStatus.vendorReservationPresentStatus):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Server Error",
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
                     
                market=await ReservationService.get_market_by_id(changeStatus.marketId,userInfo.user_id)
                
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
                print("Test1")
                market = await ReservationService.get_market_by_id(changeStatus.marketId,userInfo.user_id)
                print("Test2")
                found = False
                for log in market["logs"]:
                    if log["name"] == changeStatus.logName and log.get("reservationID") == reservationID:
                        print(f"Found matching log: {log}")
                        log["userID"] = ""
                        log["reservationID"] = ""
                        found = True
                        break
                print("Test3")            
                if not found:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Cannot find a log in market '{market['marketName']}' with reservationID '{reservationID}'",
                    )
                print("Test4")    
                updatedMarket = await ReservationService.update_market_logs(market, userInfo.token)
                print("Removed reservation from Market logs successfully")

                response = await ReservationRepository.update_reservation_status(reservationID, changeStatus.vendorReservationNextStatus)
                print("Updated reservation status to RETIRE successfully")
                return response
            elif (changeStatus.vendorReservationNextStatus=="WAITFORPAY" and changeStatus.vendorReservationNextStatus=="VALIDATESLIP"):
                #print("MAY BE USE ANOTHER SERVICE THAT IMPLEMENT WITH CALL BACK")
                print("Update Reservation Status to VALIDATESLIP")
                response = await ReservationRepository.update_reservation_status(reservationID, changeStatus.vendorReservationNextStatus)
                print("Updated reservation status to VALIDATESLIP successfully")
                return response
            elif (changeStatus.vendorReservationPresentStatus=="VALIDATESLIP" and changeStatus.vendorReservationNextStatus=="MERCHANT"):
                print("Update Reservation Status")
                market=await ReservationService.get_market_by_id(changeStatus.marketId,userInfo.user_id)
                response = await ReservationRepository.update_reservation_status(reservationID, changeStatus.vendorReservationNextStatus)
                print("Updated reservation status to MERCHANT successfully")
                return response
            elif (changeStatus.vendorReservationPresentStatus=="MERCHANT" and changeStatus.vendorReservationNextStatus=="WAITFORPAY"):
                print("Update Reservation Status")
                market=await ReservationService.get_market_by_id(changeStatus.marketId,userInfo.user_id)
                response = await ReservationRepository.update_reservation_status(reservationID, changeStatus.vendorReservationNextStatus)
                print("Updated reservation status to WAITFORPAY successfully")
                return response
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unexpected Present or Next Status",
                )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
         