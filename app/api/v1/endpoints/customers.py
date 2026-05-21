from fastapi import APIRouter, HTTPException, status

from app.api.deps import CustomerServiceDep
from app.schemas.customer import (
    CustomerCreate,
    CustomerDeleteResponse,
    CustomerItemResponse,
    CustomerListResponse,
    CustomerUpdate,
    ErrorResponse,
)
from app.services.customer_service import CustomerNotFoundError, CustomerValidationError

router = APIRouter(prefix="/customers", tags=["customers"])


@router.get("", response_model=CustomerListResponse)
def list_customers(service: CustomerServiceDep) -> CustomerListResponse:
    return CustomerListResponse(items=service.list_all())


@router.get(
    "/by-plate/{license_plate}",
    response_model=CustomerItemResponse,
    responses={404: {"model": ErrorResponse}},
)
def get_customer_by_plate(
    license_plate: str,
    service: CustomerServiceDep,
) -> CustomerItemResponse:
    item = service.get_by_license_plate(license_plate)
    if item is None:
        raise HTTPException(status_code=404, detail="No encontrado")
    return CustomerItemResponse(item=item)


@router.post("", response_model=CustomerItemResponse, status_code=status.HTTP_201_CREATED)
def create_customer(body: CustomerCreate, service: CustomerServiceDep) -> CustomerItemResponse:
    try:
        return CustomerItemResponse(item=service.create(body))
    except CustomerValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{customer_id}", response_model=CustomerItemResponse, responses={404: {"model": ErrorResponse}})
def get_customer(customer_id: int, service: CustomerServiceDep) -> CustomerItemResponse:
    try:
        return CustomerItemResponse(item=service.get_by_id(customer_id))
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc


@router.patch("/{customer_id}", response_model=CustomerItemResponse, responses={404: {"model": ErrorResponse}})
def update_customer(
    customer_id: int,
    body: CustomerUpdate,
    service: CustomerServiceDep,
) -> CustomerItemResponse:
    try:
        return CustomerItemResponse(item=service.update(customer_id, body))
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except CustomerValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{customer_id}", response_model=CustomerDeleteResponse, responses={404: {"model": ErrorResponse}})
def delete_customer(customer_id: int, service: CustomerServiceDep) -> CustomerDeleteResponse:
    try:
        service.delete(customer_id)
    except CustomerNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return CustomerDeleteResponse()
