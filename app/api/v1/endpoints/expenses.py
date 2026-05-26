from fastapi import APIRouter, HTTPException, status

from app.api.deps import CurrentUserDep, ExpenseServiceDep
from app.schemas.expense import (
    ExpenseCreate,
    ExpenseDeleteResponse,
    ExpenseItemResponse,
    ExpenseListResponse,
    ExpenseTypeOption,
    ExpenseTypesResponse,
    ExpenseUpdate,
)
from app.schemas.ticket import ErrorResponse
from app.services.expense_service import (
    ExpenseForbiddenError,
    ExpenseNotFoundError,
    ExpenseValidationError,
)

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/types", response_model=ExpenseTypesResponse)
def list_expense_types(
    current_user: CurrentUserDep,
    service: ExpenseServiceDep,
) -> ExpenseTypesResponse:
    return ExpenseTypesResponse(
        items=[
            ExpenseTypeOption(**row) for row in service.list_type_options_for_user(current_user)
        ],
    )


@router.get("", response_model=ExpenseListResponse)
def list_expenses(
    current_user: CurrentUserDep,
    service: ExpenseServiceDep,
) -> ExpenseListResponse:
    return ExpenseListResponse(items=service.list_for_user(current_user))


@router.post("", response_model=ExpenseItemResponse, status_code=status.HTTP_201_CREATED)
def create_expense(
    body: ExpenseCreate,
    current_user: CurrentUserDep,
    service: ExpenseServiceDep,
) -> ExpenseItemResponse:
    try:
        return ExpenseItemResponse(item=service.create(current_user, body))
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{expense_id}",
    response_model=ExpenseItemResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_expense(
    expense_id: int,
    current_user: CurrentUserDep,
    service: ExpenseServiceDep,
) -> ExpenseItemResponse:
    try:
        return ExpenseItemResponse(item=service.get_by_id_for_user(current_user, expense_id))
    except ExpenseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc


@router.patch(
    "/{expense_id}",
    response_model=ExpenseItemResponse,
    responses={404: {"model": ErrorResponse}},
)
def update_expense(
    expense_id: int,
    body: ExpenseUpdate,
    current_user: CurrentUserDep,
    service: ExpenseServiceDep,
) -> ExpenseItemResponse:
    try:
        return ExpenseItemResponse(item=service.update(current_user, expense_id, body))
    except ExpenseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except ExpenseForbiddenError as exc:
        raise HTTPException(status_code=403, detail="No autorizado") from exc
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{expense_id}",
    response_model=ExpenseDeleteResponse,
    responses={404: {"model": ErrorResponse}},
)
def delete_expense(
    expense_id: int,
    current_user: CurrentUserDep,
    service: ExpenseServiceDep,
) -> ExpenseDeleteResponse:
    try:
        service.delete(current_user, expense_id)
    except ExpenseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return ExpenseDeleteResponse()
