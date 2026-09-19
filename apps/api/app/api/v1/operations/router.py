from fastapi import APIRouter

from app.api.v1.operations.bookings import router as bookings_router
from app.api.v1.operations.credentials import router as credentials_router
from app.api.v1.operations.dispatch import router as dispatch_router
from app.api.v1.operations.dispatcher import router as dispatcher_router
from app.api.v1.operations.workforce import router as workforce_router

router = APIRouter()
router.include_router(bookings_router)
router.include_router(credentials_router)
router.include_router(dispatcher_router)
router.include_router(workforce_router)
router.include_router(dispatch_router)
