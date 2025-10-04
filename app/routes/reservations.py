from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from core.auth import get_user_from_token, verify_token
from schemas.reservations import ReservationResponse,ReservationCreate
from crud.reservations import ReservationRepository
from services.reservation import ReservationService
 
 
router = APIRouter()
security = HTTPBearer()
# Get current user info
@router.post("/reserve", response_model=ReservationResponse)
async def create_reservation(payload: ReservationCreate,credentials: HTTPAuthorizationCredentials = Depends(security)):
    
    userInfo = await get_user_from_token(credentials.credentials)
 
    #Call CRUD
    user = await ReservationService.create_reservation(userInfo, payload)
    return user

@router.get("/vendor/{vendorID}")
async def get_reservations_by_vendor(vendorID: str,credentials: HTTPAuthorizationCredentials = Depends(security)):
    venderReservations = await ReservationRepository.get_reservations_by_vendor(vendorID)    
    return venderReservations

@router.get("/{ReservationID}")
async def get_reservation_by_id(ReservationID: str,credentials: HTTPAuthorizationCredentials = Depends(security)):
    userInfo = await get_user_from_token(credentials.credentials)
    reservation = await ReservationRepository.get_reservation_by_id(ReservationID, userInfo.role)    
    return reservation