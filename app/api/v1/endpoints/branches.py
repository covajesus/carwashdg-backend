from fastapi import APIRouter, HTTPException, status

from app.api.deps import BranchOfficeServiceDep
from app.schemas.branch_office import (
    BranchOfficeCreate,
    BranchOfficeDeleteResponse,
    BranchOfficeItemResponse,
    BranchOfficeListResponse,
    BranchOfficeUpdate,
    ErrorResponse,
)
from app.services.branch_office_service import (
    BranchOfficeNotFoundError,
    BranchOfficeValidationError,
)

router = APIRouter(prefix="/branches", tags=["branch_offices"])


@router.get(
    "",
    response_model=BranchOfficeListResponse,
    responses={401: {"model": ErrorResponse}},
)
def list_branches(service: BranchOfficeServiceDep) -> BranchOfficeListResponse:
    return BranchOfficeListResponse(items=service.list_all())


@router.post(
    "",
    response_model=BranchOfficeItemResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def create_branch(
    body: BranchOfficeCreate,
    service: BranchOfficeServiceDep,
) -> BranchOfficeItemResponse:
    try:
        item = service.create(body)
    except BranchOfficeValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BranchOfficeItemResponse(item=item)


@router.get(
    "/{branch_id}",
    response_model=BranchOfficeItemResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def get_branch(
    branch_id: int,
    service: BranchOfficeServiceDep,
) -> BranchOfficeItemResponse:
    try:
        item = service.get_by_id(branch_id)
    except BranchOfficeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return BranchOfficeItemResponse(item=item)


@router.patch(
    "/{branch_id}",
    response_model=BranchOfficeItemResponse,
    responses={
        400: {"model": ErrorResponse},
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def update_branch(
    branch_id: int,
    body: BranchOfficeUpdate,
    service: BranchOfficeServiceDep,
) -> BranchOfficeItemResponse:
    try:
        item = service.update(branch_id, body)
    except BranchOfficeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    except BranchOfficeValidationError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return BranchOfficeItemResponse(item=item)


@router.delete(
    "/{branch_id}",
    response_model=BranchOfficeDeleteResponse,
    responses={
        404: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
    },
)
def delete_branch(
    branch_id: int,
    service: BranchOfficeServiceDep,
) -> BranchOfficeDeleteResponse:
    try:
        service.delete(branch_id)
    except BranchOfficeNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No encontrado",
        ) from exc
    return BranchOfficeDeleteResponse()
