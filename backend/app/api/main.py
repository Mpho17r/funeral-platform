from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.businesses import router as businesses_router
from app.api.cases import router as cases_router
from app.api.contacts import router as contacts_router
from app.api.documents import router as documents_router
from app.api.families import router as families_router
from app.api.financials import router as financials_router
from app.api.payments import router as payments_router
from app.api.services import router as services_router
from app.api.tasks import router as tasks_router
from app.api.users import router as users_router


api_router = APIRouter()

api_router.include_router(auth_router)
api_router.include_router(businesses_router)
api_router.include_router(cases_router)
api_router.include_router(contacts_router)
api_router.include_router(documents_router)
api_router.include_router(families_router)
api_router.include_router(financials_router)
api_router.include_router(payments_router)
api_router.include_router(services_router)
api_router.include_router(tasks_router)
api_router.include_router(users_router)