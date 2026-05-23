from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpensePublic, ExpenseUpdate

EXPENSE_TYPE_LABELS: dict[str, str] = {
    "insumos": "Insumos y químicos",
    "servicios_basicos": "Servicios básicos (luz, agua, gas)",
    "mantenimiento": "Mantenimiento y equipos",
    "nomina": "Nómina y sueldos",
    "arriendo": "Arriendo",
    "marketing": "Marketing y publicidad",
    "transporte": "Transporte y combustible",
    "otros": "Otros",
}

MAX_PHOTO_URL_LENGTH = 4_000_000


class ExpenseNotFoundError(Exception):
    pass


class ExpenseValidationError(Exception):
    pass


class ExpenseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    @staticmethod
    def type_label(expense_type: str) -> str:
        key = expense_type.strip()
        return EXPENSE_TYPE_LABELS.get(key, key or "—")

    @staticmethod
    def list_type_options() -> list[dict[str, str]]:
        return [{"id": key, "label": label} for key, label in EXPENSE_TYPE_LABELS.items()]

    def to_public(self, row: Expense) -> ExpensePublic:
        return ExpensePublic(
            id=str(row.id),
            expense_type=row.expense_type,
            expense_type_label=self.type_label(row.expense_type),
            amount=int(row.amount or 0),
            expense_date=row.expense_date,
            photo_url=row.photo_url,
            added_date=row.added_date,
            updated_date=row.updated_date,
            deleted_date=row.deleted_date,
        )

    def _active_filter(self, stmt):
        return stmt.where(Expense.deleted_date.is_(None))

    @staticmethod
    def _normalize_type(value: str) -> str:
        key = value.strip()
        if not key:
            raise ExpenseValidationError("Seleccione el tipo de gasto")
        if key not in EXPENSE_TYPE_LABELS:
            raise ExpenseValidationError("Tipo de gasto no válido")
        return key

    @staticmethod
    def _normalize_photo(value: str | None) -> str | None:
        if value is None:
            return None
        text = value.strip()
        if not text:
            return None
        if len(text) > MAX_PHOTO_URL_LENGTH:
            raise ExpenseValidationError("La foto es demasiado grande")
        return text

    def list_all(self) -> list[ExpensePublic]:
        stmt = self._active_filter(select(Expense)).order_by(
            Expense.expense_date.desc(),
            Expense.added_date.desc(),
        )
        return [self.to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, expense_id: int) -> ExpensePublic:
        row = self.db.scalars(
            self._active_filter(select(Expense)).where(Expense.id == expense_id),
        ).first()
        if row is None:
            raise ExpenseNotFoundError()
        return self.to_public(row)

    def create(self, data: ExpenseCreate) -> ExpensePublic:
        expense_type = self._normalize_type(data.expense_type)
        photo_url = self._normalize_photo(data.photo_url)
        now = self._now()
        row = Expense(
            expense_type=expense_type,
            amount=int(data.amount),
            expense_date=data.expense_date,
            photo_url=photo_url,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, expense_id: int, data: ExpenseUpdate) -> ExpensePublic:
        row = self.db.get(Expense, expense_id)
        if row is None or not row.is_active:
            raise ExpenseNotFoundError()

        if data.expense_type is not None:
            row.expense_type = self._normalize_type(data.expense_type)
        if data.amount is not None:
            if data.amount < 1:
                raise ExpenseValidationError("Indique un monto mayor a cero")
            row.amount = int(data.amount)
        if data.expense_date is not None:
            row.expense_date = data.expense_date
        if data.photo_url is not None:
            row.photo_url = self._normalize_photo(data.photo_url)

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, expense_id: int) -> None:
        row = self.db.get(Expense, expense_id)
        if row is None or not row.is_active:
            raise ExpenseNotFoundError()
        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
