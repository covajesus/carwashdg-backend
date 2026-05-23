from fastapi import APIRouter, HTTPException, status

from app.api.deps import ExpenseServiceDep
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
from app.services.expense_service import ExpenseNotFoundError, ExpenseValidationError

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.get("/types", response_model=ExpenseTypesResponse)
def list_expense_types(service: ExpenseServiceDep) -> ExpenseTypesResponse:
    return ExpenseTypesResponse(
        items=[ExpenseTypeOption(**row) for row in service.list_type_options()],
    )


@router.get("", response_model=ExpenseListResponse)
def list_expenses(service: ExpenseServiceDep) -> ExpenseListResponse:
    return ExpenseListResponse(items=service.list_all())


@router.post("", response_model=ExpenseItemResponse, status_code=status.HTTP_201_CREATED)
def create_expense(body: ExpenseCreate, service: ExpenseServiceDep) -> ExpenseItemResponse:
    try:
        return ExpenseItemResponse(item=service.create(body))
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get(
    "/{expense_id}",
    response_model=ExpenseItemResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_expense(expense_id: int, service: ExpenseServiceDep) -> ExpenseItemResponse:
    try:
        return ExpenseItemResponse(item=service.get_by_id(expense_id))
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
    service: ExpenseServiceDep,
) -> ExpenseItemResponse:
    try:
        return ExpenseItemResponse(item=service.update(expense_id, body))
    except ExpenseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except ExpenseValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete(
    "/{expense_id}",
    response_model=ExpenseDeleteResponse,
    responses={404: {"model": ErrorResponse}},
)
def delete_expense(expense_id: int, service: ExpenseServiceDep) -> ExpenseDeleteResponse:
    try:
        service.delete(expense_id)
    except ExpenseNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return ExpenseDeleteResponse()
