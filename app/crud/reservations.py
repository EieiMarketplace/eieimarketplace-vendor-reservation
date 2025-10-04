from typing import Optional, List

from fastapi import HTTPException,status
from db.mongo import get_database
from schemas.reservations import ReservationCreate, ReservationInfo, ReservationResponse, ReservationVenderResponse, MarketInfo, LogInfo, UserInfo
from core.config import settings
from bson import ObjectId

class ReservationRepository:
    @staticmethod
    def _collection():
        return get_database()[settings.MONGO_DB_RESERVATION]
    def _market_collection():
        return get_database()[settings.MONGO_DB_MARKET]

    @staticmethod
    async def create_reservation(vendor_id: str, data: ReservationCreate) -> ReservationResponse:
        doc = {
            "product": data.product,
            "detail": data.detail,
            "vendorId": vendor_id,
            "vendorReservationStatus": data.vendorReservationStatus,
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
        return ReservationResponse(
            id=str(result.inserted_id),
            product=doc["product"],
            detail=doc["detail"],
            vendorId=doc["vendorId"],
            vendorReservationStatus=doc["vendorReservationStatus"],
        )
    
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
            if userInfo.role == "organizer":
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
                vendorName=doc.get("vendorName", ),
                vendorReservationStatus=doc.get("vendorReservationStatus", ""),
                marketID=doc.get("marketId", ""),
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