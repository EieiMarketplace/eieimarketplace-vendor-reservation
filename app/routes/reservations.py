from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from core.auth import verify_token
from schemas.reservations import ReservationResponse,ReservationCreate
from crud.reservations import ReservationRepository
 
router = APIRouter()
security = HTTPBearer()
# Get current user info
@router.post("/reserve", response_model=ReservationResponse)
async def create_reservation(payload: ReservationCreate,credentials: HTTPAuthorizationCredentials = Depends(security)):
    
    #Get Token
    # token = credentials.credentials
    
    # Whether if it need
    # Check if token is blacklisted
    # if crud.is_token_blacklisted(db, token):
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Token has been revoked",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )
    
    #Need!!!
    vendorId ="3"
    
    #Call CRUD
    user = await ReservationRepository.create_reservation(vendorId, payload)
    print(user)
    
    return user