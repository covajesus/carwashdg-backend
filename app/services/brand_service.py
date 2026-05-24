from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso, business_now
from app.models.brand import Brand
from app.schemas.brand import BrandCreate, BrandPublic, BrandUpdate


class BrandNotFoundError(Exception):
    pass


class BrandValidationError(Exception):
    pass


class BrandService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def to_public(row: Brand) -> BrandPublic:
        return BrandPublic(
            id=str(row.id),
            brand=row.brand,
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_filter(self, stmt):
        return stmt.where(Brand.deleted_date.is_(None))

    def _find_duplicate(self, name: str, except_id: int | None = None) -> Brand | None:
        normalized = name.strip().lower()
        stmt = self._active_filter(select(Brand)).where(
            func.lower(Brand.brand) == normalized,
        )
        if except_id is not None:
            stmt = stmt.where(Brand.id != except_id)
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[BrandPublic]:
        stmt = self._active_filter(select(Brand)).order_by(Brand.brand)
        return [self.to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, brand_id: int) -> BrandPublic:
        stmt = self._active_filter(select(Brand)).where(Brand.id == brand_id)
        row = self.db.scalars(stmt).first()
        if row is None:
            raise BrandNotFoundError()
        return self.to_public(row)

    def create(self, data: BrandCreate) -> BrandPublic:
        name = data.brand.strip()
        if not name:
            raise BrandValidationError("La marca es obligatoria")
        if self._find_duplicate(name):
            raise BrandValidationError("Ya existe una marca con ese nombre")

        now = self._now()
        row = Brand(
            brand=name,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, brand_id: int, data: BrandUpdate) -> BrandPublic:
        row = self.db.get(Brand, brand_id)
        if row is None or not row.is_active:
            raise BrandNotFoundError()

        if data.brand is not None:
            name = data.brand.strip()
            if not name:
                raise BrandValidationError("La marca no puede quedar vacía")
            if self._find_duplicate(name, except_id=brand_id):
                raise BrandValidationError("Ya existe una marca con ese nombre")
            row.brand = name

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, brand_id: int) -> None:
        row = self.db.get(Brand, brand_id)
        if row is None or not row.is_active:
            raise BrandNotFoundError()

        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
