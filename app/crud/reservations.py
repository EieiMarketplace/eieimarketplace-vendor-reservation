from typing import Optional, List

from fastapi import HTTPException,status
from db.mongo import get_database
from schemas.reservations import ReservationCreate, ReservationResponse
from core.config import settings

class ReservationRepository:
    @staticmethod
    def _collection():
        return get_database()[settings.MONGO_DB]

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
        return ReservationResponse(
            id=str(result["_id"]),
            product=result.get("product", ""),
            detail=result.get("detail", ""),
            vendorId=result.get("vendorId", ""),
            vendorReservationStatus=result.get("vendorReservationStatus", ""),
        )