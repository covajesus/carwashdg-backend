from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.session import get_db
from app.schemas.user import UserPublic
from app.services.user_service import UserNotFoundError, UserService
from app.services.brand_service import BrandService
from app.services.client_service import ClientService
from app.services.branch_office_service import BranchOfficeService
from app.services.car_type_service import CarTypeService
from app.services.catalog_service import CatalogService
from app.services.configuration_service import ConfigurationService
from app.services.customer_service import CustomerService
from app.services.expense_service import ExpenseService
from app.services.eerr_service import EerrService
from app.services.collection_service import CollectionService
from app.services.raffle_service import RaffleService
from app.services.rol_service import RolService
from app.services.slider_service import SliderService
from app.services.status_service import StatusService
from app.services.ticket_line_service import TicketLineService
from app.services.ticket_service import TicketService
from app.services.cash_closure_service import CashClosureService
from app.services.washer_pay_service import WasherPayService
from app.services.washer_daily_group_service import WasherDailyGroupService

DbSession = Annotated[Session, Depends(get_db)]


def get_brand_service(db: DbSession) -> BrandService:
    return BrandService(db)


def get_client_service(db: DbSession) -> ClientService:
    return ClientService(db)


def get_branch_office_service(db: DbSession) -> BranchOfficeService:
    return BranchOfficeService(db)


def get_car_type_service(db: DbSession) -> CarTypeService:
    return CarTypeService(db)


def get_status_service(db: DbSession) -> StatusService:
    return StatusService(db)


def get_slider_service(db: DbSession) -> SliderService:
    return SliderService(db)


def get_configuration_service(db: DbSession) -> ConfigurationService:
    return ConfigurationService(db)


def get_customer_service(db: DbSession) -> CustomerService:
    return CustomerService(db)


def get_catalog_service(db: DbSession) -> CatalogService:
    return CatalogService(db)


def get_raffle_service(db: DbSession) -> RaffleService:
    return RaffleService(db)


def get_rol_service(db: DbSession) -> RolService:
    return RolService(db)


def get_ticket_service(db: DbSession) -> TicketService:
    return TicketService(db)


def get_ticket_line_service(db: DbSession) -> TicketLineService:
    return TicketLineService(db)


def get_washer_pay_service(db: DbSession) -> WasherPayService:
    return WasherPayService(db)


def get_washer_daily_group_service(db: DbSession) -> WasherDailyGroupService:
    return WasherDailyGroupService(db)


def get_expense_service(db: DbSession) -> ExpenseService:
    return ExpenseService(db)


def get_eerr_service(db: DbSession) -> EerrService:
    return EerrService(db)


def get_collection_service(db: DbSession) -> CollectionService:
    return CollectionService(db)


def get_cash_closure_service(db: DbSession) -> CashClosureService:
    return CashClosureService(db)


def get_user_service(db: DbSession) -> UserService:
    return UserService(db)


_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
    service: Annotated[UserService, Depends(get_user_service)],
) -> UserPublic:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No autorizado",
        )
    payload = decode_access_token(credentials.credentials)
    if payload is None or "sub" not in payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado",
        )
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        ) from exc
    try:
        return service.get_by_id(user_id)
    except UserNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado",
        ) from exc


BrandServiceDep = Annotated[BrandService, Depends(get_brand_service)]
ClientServiceDep = Annotated[ClientService, Depends(get_client_service)]
BranchOfficeServiceDep = Annotated[BranchOfficeService, Depends(get_branch_office_service)]
CarTypeServiceDep = Annotated[CarTypeService, Depends(get_car_type_service)]
StatusServiceDep = Annotated[StatusService, Depends(get_status_service)]
SliderServiceDep = Annotated[SliderService, Depends(get_slider_service)]
ConfigurationServiceDep = Annotated[ConfigurationService, Depends(get_configuration_service)]
CustomerServiceDep = Annotated[CustomerService, Depends(get_customer_service)]
CatalogServiceDep = Annotated[CatalogService, Depends(get_catalog_service)]
RaffleServiceDep = Annotated[RaffleService, Depends(get_raffle_service)]
RolServiceDep = Annotated[RolService, Depends(get_rol_service)]
TicketServiceDep = Annotated[TicketService, Depends(get_ticket_service)]
TicketLineServiceDep = Annotated[TicketLineService, Depends(get_ticket_line_service)]
WasherPayServiceDep = Annotated[WasherPayService, Depends(get_washer_pay_service)]
WasherDailyGroupServiceDep = Annotated[
    WasherDailyGroupService,
    Depends(get_washer_daily_group_service),
]
ExpenseServiceDep = Annotated[ExpenseService, Depends(get_expense_service)]
CollectionServiceDep = Annotated[CollectionService, Depends(get_collection_service)]
EerrServiceDep = Annotated[EerrService, Depends(get_eerr_service)]
CashClosureServiceDep = Annotated[CashClosureService, Depends(get_cash_closure_service)]
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
CurrentUserDep = Annotated[UserPublic, Depends(get_current_user)]
