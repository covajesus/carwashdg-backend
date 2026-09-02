from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, ExpenseTypeServiceDep
from app.core.branch_scope import branch_scope_for_user
from app.schemas.expense_type import (
    ExpenseTypeCreate,
    ExpenseTypeDeleteResponse,
    ExpenseTypeItemResponse,
    ExpenseTypeListResponse,
    ExpenseTypeUpdate,
)
from app.schemas.ticket import ErrorResponse
from app.services.expense_type_service import (
    ExpenseTypeNotFoundError,
    ExpenseTypeValidationError,
)

router = APIRouter(prefix="/expense-types", tags=["expense-types"])


def _require_admin(user) -> None:
    if branch_scope_for_user(user) is not None:
        raise HTTPException(status_code=403, detail="No autorizado")


@router.get("", response_model=ExpenseTypeListResponse)
def list_expense_types(
    current_user: CurrentUserDep,
    service: ExpenseTypeServiceDep,
) -> ExpenseTypeListResponse:
    is_admin = branch_scope_for_user(current_user) is None
    return ExpenseTypeListResponse(items=service.list_options_for_user(is_admin=is_admin))


@router.post(
    "",
    response_model=ExpenseTypeItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}, 403: {"model": ErrorResponse}},
)
def create_expense_type(
    body: ExpenseTypeCreate,
    current_user: CurrentUserDep,
    service: ExpenseTypeServiceDep,
) -> ExpenseTypeItemResponse:
    _require_admin(current_user)
    try:
        return ExpenseTypeItemResponse(item=service.create(body))
    except ExpenseTypeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{type_id}",
    response_model=ExpenseTypeItemResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_expense_type(
    type_id: int,
    current_user: CurrentUserDep,
    service: ExpenseTypeServiceDep,
) -> ExpenseTypeItemResponse:
    del current_user
    try:
        return ExpenseTypeItemResponse(item=service.get_by_id(type_id))
    except ExpenseTypeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc


@router.patch(
    "/{type_id}",
    response_model=ExpenseTypeItemResponse,
    responses={
        400: {"model": ErrorResponse},
        403: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
    },
)
def update_expense_type(
    type_id: int,
    body: ExpenseTypeUpdate,
    current_user: CurrentUserDep,
    service: ExpenseTypeServiceDep,
) -> ExpenseTypeItemResponse:
    _require_admin(current_user)
    try:
        return ExpenseTypeItemResponse(item=service.update(type_id, body))
    except ExpenseTypeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except ExpenseTypeValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{type_id}",
    response_model=ExpenseTypeDeleteResponse,
    responses={403: {"model": ErrorResponse}, 404: {"model": ErrorResponse}},
)
def delete_expense_type(
    type_id: int,
    current_user: CurrentUserDep,
    service: ExpenseTypeServiceDep,
) -> ExpenseTypeDeleteResponse:
    _require_admin(current_user)
    try:
        service.delete(type_id)
    except ExpenseTypeNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return ExpenseTypeDeleteResponse()
