from datetime import datetime
import re
import unicodedata

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import business_now, datetime_to_iso
from app.models.expense_type import ExpenseType
from app.schemas.expense_type import (
    ExpenseClassification,
    ExpenseTypeCreate,
    ExpenseTypePublic,
    ExpenseTypeUpdate,
)

CLASSIFICATION_LABELS: dict[ExpenseClassification, str] = {
    "cash": "Caja",
    "bank": "Banco",
}


class ExpenseTypeNotFoundError(Exception):
    pass


class ExpenseTypeValidationError(Exception):
    pass


class ExpenseTypeService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def classification_label(value: str) -> str:
        key = value.strip().lower()
        if key == "cash":
            return CLASSIFICATION_LABELS["cash"]
        return CLASSIFICATION_LABELS["bank"]

    @staticmethod
    def _slugify(value: str) -> str:
        normalized = unicodedata.normalize("NFKD", value.strip().lower())
        ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_text).strip("_")
        return slug[:64] or "tipo"

    def to_public(self, row: ExpenseType) -> ExpenseTypePublic:
        classification: ExpenseClassification = (
            "cash" if (row.classification or "").strip().lower() == "cash" else "bank"
        )
        return ExpenseTypePublic(
            id=str(row.id),
            code=(row.code or "").strip(),
            name=(row.name or "").strip(),
            classification=classification,
            classificationLabel=self.classification_label(classification),
            adminOnly=bool(row.admin_only),
            requiresPhoto=bool(row.requires_photo),
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_filter(self, stmt):
        return stmt.where(ExpenseType.deleted_date.is_(None))

    def _find_duplicate_name(self, name: str, except_id: int | None = None) -> ExpenseType | None:
        normalized = name.strip().lower()
        stmt = self._active_filter(select(ExpenseType)).where(
            func.lower(ExpenseType.name) == normalized,
        )
        if except_id is not None:
            stmt = stmt.where(ExpenseType.id != except_id)
        return self.db.scalars(stmt).first()

    def _unique_code(self, base: str, except_id: int | None = None) -> str:
        candidate = self._slugify(base)
        suffix = 2
        while True:
            stmt = self._active_filter(select(ExpenseType)).where(ExpenseType.code == candidate)
            if except_id is not None:
                stmt = stmt.where(ExpenseType.id != except_id)
            existing = self.db.scalars(stmt).first()
            if existing is None:
                return candidate
            candidate = f"{self._slugify(base)[:60]}_{suffix}"
            suffix += 1

    def _normalize_classification(self, value: str | None) -> ExpenseClassification:
        key = (value or "").strip().lower()
        if key not in {"cash", "bank"}:
            raise ExpenseTypeValidationError("Seleccione Caja o Banco")
        return key  # type: ignore[return-value]

    def list_all(self) -> list[ExpenseTypePublic]:
        rows = self.db.scalars(
            self._active_filter(select(ExpenseType)).order_by(
                ExpenseType.name.asc(),
                ExpenseType.id.asc(),
            ),
        ).all()
        return [self.to_public(row) for row in rows]

    def list_options_for_user(self, *, is_admin: bool) -> list[ExpenseTypePublic]:
        items = self.list_all()
        if is_admin:
            return items
        return [row for row in items if not row.adminOnly]

    def get_by_id(self, type_id: int) -> ExpenseTypePublic:
        row = self.db.scalars(
            self._active_filter(select(ExpenseType)).where(ExpenseType.id == type_id),
        ).first()
        if row is None:
            raise ExpenseTypeNotFoundError()
        return self.to_public(row)

    def get_active_row(self, type_id: int) -> ExpenseType:
        row = self.db.scalars(
            self._active_filter(select(ExpenseType)).where(ExpenseType.id == type_id),
        ).first()
        if row is None:
            raise ExpenseTypeNotFoundError()
        return row

    def get_active_row_by_code(self, code: str) -> ExpenseType | None:
        key = code.strip()
        if not key:
            return None
        return self.db.scalars(
            self._active_filter(select(ExpenseType)).where(ExpenseType.code == key),
        ).first()

    def create(self, data: ExpenseTypeCreate) -> ExpenseTypePublic:
        name = data.name.strip()
        if not name:
            raise ExpenseTypeValidationError("El nombre es obligatorio")
        if self._find_duplicate_name(name):
            raise ExpenseTypeValidationError("Ya existe un tipo de gasto con ese nombre")
        classification = self._normalize_classification(data.classification)
        now = self._now()
        row = ExpenseType(
            code=self._unique_code(name),
            name=name,
            classification=classification,
            admin_only=bool(data.adminOnly),
            requires_photo=bool(data.requiresPhoto),
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, type_id: int, data: ExpenseTypeUpdate) -> ExpenseTypePublic:
        row = self.db.get(ExpenseType, type_id)
        if row is None or not row.is_active:
            raise ExpenseTypeNotFoundError()

        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise ExpenseTypeValidationError("El nombre no puede quedar vacío")
            if self._find_duplicate_name(name, except_id=type_id):
                raise ExpenseTypeValidationError("Ya existe un tipo de gasto con ese nombre")
            row.name = name
        if data.classification is not None:
            row.classification = self._normalize_classification(data.classification)
        if data.adminOnly is not None:
            row.admin_only = bool(data.adminOnly)
        if data.requiresPhoto is not None:
            row.requires_photo = bool(data.requiresPhoto)

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, type_id: int) -> None:
        row = self.db.get(ExpenseType, type_id)
        if row is None or not row.is_active:
            raise ExpenseTypeNotFoundError()
        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
