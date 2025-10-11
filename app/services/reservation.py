 
 
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
                
                # Dictionary to store responses and asyncio.Event for each vendor
                vendor_data = {v_id: {"name": None, "event": asyncio.Event()} for v_id in vendor_ids}
                
                # Background task to consume messages
                async def consume_responses():
                    async with response_queue.iterator() as queue_iter:
                        async for message in queue_iter:
                            async with message.process():
                                try:
                                    data = json.loads(message.body)
                                    correlation_id = message.correlation_id
                                    
                                    # Extract vendor_id from correlation_id
                                    if correlation_id and correlation_id.startswith("req-"):
                                        vendor_id = correlation_id[4:]  # Remove "req-" prefix
                                        
                                        if vendor_id in vendor_data:
                                            # Store the name
                                            vendor_data[vendor_id]["name"] = data.get("first_name", "Unknown")
                                            # Signal that this vendor's data is ready
                                            vendor_data[vendor_id]["event"].set()
                                            print(f"✅ Received data for vendor {vendor_id}: {vendor_data[vendor_id]['name']}")
                                            
                                            # Check if all vendors received
                                            if all(v["event"].is_set() for v in vendor_data.values()):
                                                break  # Exit consumer loop
                                except Exception as e:
                                    print(f"❌ Error processing message: {e}")
                
                # Start consumer task
                consumer_task = asyncio.create_task(consume_responses()) #run the background process wait to read
                
                # Send all requests
                print(f"📤 Sending requests for {len(vendor_ids)} vendors...")
                for vendor_id in vendor_ids:
                    correlation_id = f"req-{vendor_id}"
                    payload = {
                        "event": "user_info_request", #ไม่ได้ใช้ทำอะไรหรอก5555
                        "userId": vendor_id,
                        "token": userInfo.token,
                    }
                    
                    await exchange.publish(
                        aio_pika.Message(
                            body=json.dumps(payload).encode(),
                            correlation_id=correlation_id,
                            reply_to=response_queue.name
                        ),
                        routing_key=settings.USER_STATUS
                    )
                
                print("⏳ Waiting for all responses...")
                
                # Wait for all vendors to respond with timeout
                try:
                    await asyncio.wait_for(
                        asyncio.gather(*[v["event"].wait() for v in vendor_data.values()]),
                        timeout=10.0  # 10 seconds timeout
                    )
                    print("✅ All vendor data received!")
                except asyncio.TimeoutError:
                    print("⚠️ Timeout waiting for some vendor responses")
                    # Mark missing vendors as "Unknown"
                    for vendor_id, data in vendor_data.items():
                        if not data["event"].is_set():
                            data["name"] = "Unknown"
                            print(f"⚠️ No response for vendor {vendor_id}, setting to Unknown")
                
                # Cancel consumer task
                consumer_task.cancel()
                try:
                    await consumer_task
                except asyncio.CancelledError:
                    pass
                
                # Merge vendor names into reservations
                for reservation in reservations_cursor:
                    reservation.vendorName = vendor_data.get(
                        reservation.vendorId, 
                        {"name": "Unknown"}
                    )["name"]
                
                print(f"✅ Successfully merged {len(vendor_ids)} vendor names")
                
            finally:
                await connection.close()
            
            return reservations_cursor
            
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Unexpected error: {e}")
            raise HTTPException(status_code=500, detail=str(e))
    
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
                     
                market = await ReservationService.get_market_by_id(changeStatus.marketId,userInfo.user_id)

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
         