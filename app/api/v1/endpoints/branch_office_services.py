from fastapi import APIRouter, HTTPException, status

from app.api.deps import BranchOfficeServiceServiceDep
from app.schemas.branch_office_service import (
    BranchOfficeServiceCreate,
    BranchOfficeServiceDeleteResponse,
    BranchOfficeServiceItemResponse,
    BranchOfficeServiceListResponse,
    BranchOfficeServiceUpdate,
    ErrorResponse,
)
from app.services.branch_office_service_service import (
    BranchOfficeServiceNotFoundError,
    BranchOfficeServiceValidationError,
)

router = APIRouter(prefix="/branch-office-services", tags=["branch_office_services"])


@router.get("", response_model=BranchOfficeServiceListResponse)
def list_branch_office_services(
    service: BranchOfficeServiceServiceDep,
) -> BranchOfficeServiceListResponse:
    return BranchOfficeServiceListResponse(items=service.list_all())


@router.get(
    "/sucursal/{branch_office_id}",
    response_model=BranchOfficeServiceListResponse,
)
def list_branch_office_services_by_branch(
    branch_office_id: int,
    service: BranchOfficeServiceServiceDep,
) -> BranchOfficeServiceListResponse:
    if branch_office_id < 1:
        raise HTTPException(status_code=400, detail="Sucursal no válida")
    return BranchOfficeServiceListResponse(
        items=service.list_all(branch_office_id=branch_office_id),
    )


@router.get(
    "/servicio/{service_id}",
    response_model=BranchOfficeServiceListResponse,
)
def list_branch_office_services_by_service(
    service_id: int,
    service: BranchOfficeServiceServiceDep,
) -> BranchOfficeServiceListResponse:
    if service_id < 1:
        raise HTTPException(status_code=400, detail="Servicio no válido")
    return BranchOfficeServiceListResponse(
        items=service.list_all(service_id=service_id),
    )


@router.post("", response_model=BranchOfficeServiceItemResponse, status_code=status.HTTP_201_CREATED)
def create_branch_office_service(
    body: BranchOfficeServiceCreate,
    service: BranchOfficeServiceServiceDep,
) -> BranchOfficeServiceItemResponse:
    try:
        return BranchOfficeServiceItemResponse(item=service.create(body))
    except BranchOfficeServiceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{row_id}", response_model=BranchOfficeServiceItemResponse, responses={404: {"model": ErrorResponse}})
def get_branch_office_service(
    row_id: int,
    service: BranchOfficeServiceServiceDep,
) -> BranchOfficeServiceItemResponse:
    try:
        return BranchOfficeServiceItemResponse(item=service.get_by_id(row_id))
    except BranchOfficeServiceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc


@router.patch("/{row_id}", response_model=BranchOfficeServiceItemResponse, responses={404: {"model": ErrorResponse}})
def update_branch_office_service(
    row_id: int,
    body: BranchOfficeServiceUpdate,
    service: BranchOfficeServiceServiceDep,
) -> BranchOfficeServiceItemResponse:
    try:
        return BranchOfficeServiceItemResponse(item=service.update(row_id, body))
    except BranchOfficeServiceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    except BranchOfficeServiceValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/{row_id}", response_model=BranchOfficeServiceDeleteResponse, responses={404: {"model": ErrorResponse}})
def delete_branch_office_service(
    row_id: int,
    service: BranchOfficeServiceServiceDep,
) -> BranchOfficeServiceDeleteResponse:
    try:
        service.delete(row_id)
    except BranchOfficeServiceNotFoundError as exc:
        raise HTTPException(status_code=404, detail="No encontrado") from exc
    return BranchOfficeServiceDeleteResponse()
