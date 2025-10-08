import datetime
from typing import Optional, List

from fastapi import HTTPException,status
 
from dependencies.constant import Status
from models.reservations import VendorReservation
from schemas.markets import Log
from db.mongo import get_database
from schemas.reservations import ChangeReservationResponse, ReservationByMarketIdModelResponse, ReservationByMarketIdResponse, ReservationCreate, ReservationInfo, ReservationResponse, ReservationVenderResponse, MarketInfo, LogInfo, UserInfo
from core.config import settings
from bson import ObjectId
from core.auth import get_user_from_id

class ReservationRepository:
    @staticmethod
    def _collection():
        return get_database()[settings.MONGO_DB_RESERVATION]
    def _market_collection():
        return get_database()[settings.MONGO_DB_MARKET]

    @staticmethod
    async def create_reservation(vendor_id: str, data: ReservationCreate) -> dict:
        doc:VendorReservation = {
            "product": data.product,
            "detail": data.detail,
            "vendorId": vendor_id,
            "marketId":data.marketId,
            "createdTime": datetime.datetime.now(),
            "updatedTime": datetime.datetime.now(),
            "vendorReservationStatus": "APPLICATION",
        }

        try:
            result = await ReservationRepository._collection().insert_one(doc)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database insert failed: {str(e)}"
            )

        # Convert MongoDB _id to string
        print("result",result)
        doc["id"] = str(result.inserted_id)
        return doc
    
    @staticmethod
    async def get_reservations_by_vendor(vendor_id: str) -> List[ReservationVenderResponse]:
        try:
            cursor = ReservationRepository._collection().find({"vendorId": vendor_id})
            reservations = []
            async for doc in cursor:
                markets = await ReservationRepository._market_collection().find_one({"_id": ObjectId(doc["marketId"])})
                # if market not found, skip this reservation
                if not markets:
                    continue
                
                # if Log
                logs = markets.get("logs", [])
                venderlog = None
                if logs:
                    for log in logs:
                        if log.get("user_id") == vendor_id and log.get("reservation_id") == str(doc.get("_id", "")):
                            venderlog = LogInfo(
                                name=log.get("name", ""),
                                size=log.get("size", ""),
                                price=log.get("price", 0),
                                user_id=log.get("user_id", ""),
                                reservation_id=log.get("reservation_id", "")
                            )
                            break


                reservations.append(ReservationVenderResponse(
                    id=str(doc.get("_id", "")),
                    vendorId=doc.get("vendorId", ""),
                    vendorReservationStatus=doc.get("vendorReservationStatus", ""),
                    product=doc.get("product", ""),
                    markets=MarketInfo(
                        market_name=markets.get("market_name", ""),
                        isOpen=markets.get("isOpen", ""),
                        marketType=markets.get("marketType", "")
                    ),
                    log = venderlog
                ))

            return reservations
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database query failed: {str(e)}"
            )
    
    @staticmethod
    async def get_reservation_by_id(reservation_id: str, role: str) -> Optional[ReservationInfo]:
        try:
            doc = await ReservationRepository._collection().find_one({"_id": ObjectId(reservation_id)})
            print(ReservationRepository._collection())
            if not doc:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Reservation not found"
                )
            
            # Fetch market details
            market = await ReservationRepository._market_collection().find_one({"_id": ObjectId(doc["marketId"])})
            if not market:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Market not found"
                )
            
            # Fetch logs related to this reservation
            logs = []
            if role == "organizer":
                logs = market.get("logs", [])
            else:
                for log in market.get("logs", []):
                    if log.get("reservation_id") == reservation_id:
                        logs.append(LogInfo(
                            name=log.get("name", ""),
                            size=log.get("size", ""),
                            price=log.get("price", 0),
                            user_id=log.get("user_id", ""),
                            reservation_id=log.get("reservation_id", "")
                        ))

            return ReservationInfo(
                vendorName=doc.get("vendorName", ""),
                vendorReservationStatus=doc.get("vendorReservationStatus", ""),
                marketID=doc.get("marketId", ""),
                vendorId=doc.get("vendorId", ""),
                marketInfo = MarketInfo(
                    market_name=market.get("market_name", ""),
                    isOpen=market.get("isOpen", ""),
                    marketType=market.get("marketType", "")
                ),
                reservationProduct=doc.get("product", ""),
                reservationDetail=doc.get("detail", ""),
                Log=logs
            )
        except HTTPException as he:
            raise he
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Database query failed: {str(e)}"
            )

    @staticmethod
    async def get_user_info(user_id: str, token: str) -> UserInfo:
        userInfo = await get_user_from_id(user_id, token)
        return userInfo

    @staticmethod
    async def search_reservation_by_marketid(market_id:str,vendor_reservation_status:str)-> List[ReservationByMarketIdModelResponse]:
        pipeline = [
                      {
                "$match": {
                    "marketId": market_id
                } if vendor_reservation_status == Status.ALL.name else {
                    "marketId": market_id,
                    "vendorReservationStatus": vendor_reservation_status
                }
            },
 
            {
                "$addFields": {
                    "marketObjId": {"$toObjectId": "$marketId"}
                }
            },
            {
                "$lookup": {
                    "from": settings.MONGO_DB_MARKET,
                    "localField": "marketObjId",
                    "foreignField": "_id",
                    "as": "market_info"
                }
            },
            {"$unwind": "$market_info"},
                    {
                        "$addFields": {
                            "filtered_logs": {
                                "$filter": {
                                    "input": "$market_info.logs",
                                    "as": "log",
                                    "cond": {"$eq": ["$$log.reservation_id", {"$toString": "$_id"}]}
                                }
                            }
                        }
                    },
                    {
                        "$project": {
                            "_id": {"$toString": "$_id"},
                            "vendorId": 1,
                            # "vendorName": 1,
                             "product":1,
                            "vendorReservationStatus": 1,
                            "marketId": 1,
                            "filtered_logs": 1,
                            "createdTime": 1,
                            "updatedTime": 1
                        }
                    }
                ]

        try:
                    cursor = ReservationRepository._collection().aggregate(pipeline)
                    results = await cursor.to_list(length=None)
                    print("Results ",results)
                    reservations = []
                    for doc in results:
                        log_data = None
                        logs = doc.get("filtered_logs", [])
                        if logs:
                            log_data = LogInfo(
                                name=logs[0].get("name", ""),
                                size=logs[0].get("size", ""),
                                price=logs[0].get("price", 0),
                                user_id=logs[0].get("user_id", ""),
                                reservation_id=logs[0].get("reservation_id", "")
                            )

                        reservations.append(
                            ReservationByMarketIdModelResponse(
                                id=doc["_id"],
                                product= doc.get("product", ""),
                                vendorId= doc.get("vendorId", ""),
                                vendorName= doc.get("vendorName", ""),
                                vendorReservationStatus=doc.get("vendorReservationStatus", ""),
                                log=log_data,
                                marketId=doc.get("marketId", ""),
                                createdTime=doc.get("createdTime",datetime.datetime.now()),
                                updatedTime=doc.get("updatedTime",datetime.datetime.now()),
                            )
                        )

                    return reservations
        except Exception as e:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=f"Database aggregation failed: {str(e)}"
                    )
                    
    @staticmethod
    async def update_reservation_status(reservation_id: str, new_status: str)->ChangeReservationResponse:
        try:
            result = await ReservationRepository._collection().update_one(
                {"_id": ObjectId(reservation_id)},
                {
                    "$set": {
                        "vendorReservationStatus": new_status,
                        "updatedTime": datetime.datetime.now()
                    }
                }
            )

            if result.matched_count == 0:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Reservation ID '{reservation_id}' not found."
                )
            response = ChangeReservationResponse(message= "Reservation status updated successfully", status= new_status,reservation_id=reservation_id)
            return response

        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update reservation status: {str(e)}"
            )