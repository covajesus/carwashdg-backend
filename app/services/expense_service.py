from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.branch_scope import branch_scope_for_user
from app.core.datetime_utils import business_now
from app.models.branch_office import BranchOffice
from app.models.expense import Expense
from app.schemas.expense import ExpenseCreate, ExpensePublic, ExpenseUpdate
from app.schemas.user import UserPublic

EXPENSE_TYPE_LABELS: dict[str, str] = {
    "insumos": "Insumos y químicos",
    "servicios_basicos": "Servicios básicos (luz, agua, gas)",
    "mantenimiento": "Mantenimiento y equipos",
    "nomina": "Nómina y sueldos",
    "arriendo": "Arriendo",
    "marketing": "Marketing y publicidad",
    "transporte": "Transporte y combustible",
    "prestamo": "Préstamo",
    "otros": "Otros",
}

# Solo administradores pueden ver, crear o editar estos tipos.
ADMIN_ONLY_EXPENSE_TYPES = frozenset({"arriendo"})

class ExpenseNotFoundError(Exception):
    pass


class ExpenseValidationError(Exception):
    pass


class ExpenseForbiddenError(Exception):
    pass


class ExpenseService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def type_label(expense_type: str) -> str:
        key = expense_type.strip()
        return EXPENSE_TYPE_LABELS.get(key, key or "—")

    @staticmethod
    def list_type_options() -> list[dict[str, str]]:
        return [{"id": key, "label": label} for key, label in EXPENSE_TYPE_LABELS.items()]

    @staticmethod
    def _user_is_admin(user: UserPublic) -> bool:
        return branch_scope_for_user(user) is None

    def list_type_options_for_user(self, user: UserPublic) -> list[dict[str, str]]:
        options = self.list_type_options()
        if self._user_is_admin(user):
            return options
        return [row for row in options if row["id"] not in ADMIN_ONLY_EXPENSE_TYPES]

    def _assert_expense_visible_to_user(self, user: UserPublic, row: Expense) -> None:
        if self._user_is_admin(user):
            return
        if row.expense_type.strip() in ADMIN_ONLY_EXPENSE_TYPES:
            raise ExpenseNotFoundError()

    def _reject_admin_only_type_for_user(self, user: UserPublic, expense_type: str) -> None:
        if self._user_is_admin(user):
            return
        if expense_type in ADMIN_ONLY_EXPENSE_TYPES:
            raise ExpenseValidationError("Tipo de gasto no válido")

    def _branch_name(self, branch_office_id: int | None) -> str | None:
        if branch_office_id is None or branch_office_id < 1:
            return None
        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            return None
        return branch.branch_office.strip() or None

    def to_public(self, row: Expense) -> ExpensePublic:
        branch_id = row.branch_office_id
        return ExpensePublic(
            id=str(row.id),
            expense_type=row.expense_type,
            expense_type_label=self.type_label(row.expense_type),
            amount=int(row.amount or 0),
            expense_date=row.expense_date,
            branchOfficeId=branch_id,
            branchOfficeName=self._branch_name(branch_id),
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
        return text

    def _validate_branch_exists(self, branch_office_id: int) -> None:
        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            raise ExpenseValidationError("La sucursal no existe")

    def _resolve_branch_for_create(self, user: UserPublic, requested: int | None) -> int:
        scope = branch_scope_for_user(user)
        if scope is None:
            if requested is None or requested < 1:
                raise ExpenseValidationError("Seleccione la sucursal")
            self._validate_branch_exists(requested)
            return requested
        if scope == 0:
            raise ExpenseValidationError("Su cuenta no tiene sucursal asignada")
        self._validate_branch_exists(scope)
        return scope

    def _resolve_branch_for_update(
        self,
        user: UserPublic,
        row: Expense,
        requested: int | None,
    ) -> int | None:
        if requested is None:
            return None
        scope = branch_scope_for_user(user)
        if scope is not None:
            if scope == 0 or requested != scope:
                raise ExpenseForbiddenError()
            return None
        self._validate_branch_exists(requested)
        return requested

    def _assert_can_access(self, user: UserPublic, row: Expense) -> None:
        scope = branch_scope_for_user(user)
        if scope is None:
            return
        if scope == 0 or row.branch_office_id != scope:
            raise ExpenseNotFoundError()

    def list_for_user(self, user: UserPublic) -> list[ExpensePublic]:
        scope = branch_scope_for_user(user)
        if scope == 0:
            return []

        stmt = self._active_filter(select(Expense)).order_by(
            Expense.expense_date.desc(),
            Expense.added_date.desc(),
        )
        if scope is not None:
            stmt = stmt.where(Expense.branch_office_id == scope)

        rows = list(self.db.scalars(stmt).all())
        if not self._user_is_admin(user):
            rows = [row for row in rows if row.expense_type.strip() not in ADMIN_ONLY_EXPENSE_TYPES]
        return [self.to_public(row) for row in rows]

    def get_by_id_for_user(self, user: UserPublic, expense_id: int) -> ExpensePublic:
        row = self.db.scalars(
            self._active_filter(select(Expense)).where(Expense.id == expense_id),
        ).first()
        if row is None:
            raise ExpenseNotFoundError()
        self._assert_can_access(user, row)
        self._assert_expense_visible_to_user(user, row)
        return self.to_public(row)

    def create(self, user: UserPublic, data: ExpenseCreate) -> ExpensePublic:
        expense_type = self._normalize_type(data.expense_type)
        self._reject_admin_only_type_for_user(user, expense_type)
        photo_url = self._normalize_photo(data.photo_url)
        branch_office_id = self._resolve_branch_for_create(user, data.branchOfficeId)
        now = self._now()
        row = Expense(
            expense_type=expense_type,
            amount=int(data.amount),
            expense_date=data.expense_date,
            branch_office_id=branch_office_id,
            photo_url=photo_url,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, user: UserPublic, expense_id: int, data: ExpenseUpdate) -> ExpensePublic:
        row = self.db.get(Expense, expense_id)
        if row is None or not row.is_active:
            raise ExpenseNotFoundError()
        self._assert_can_access(user, row)
        self._assert_expense_visible_to_user(user, row)

        if data.expense_type is not None:
            expense_type = self._normalize_type(data.expense_type)
            self._reject_admin_only_type_for_user(user, expense_type)
            row.expense_type = expense_type
        if data.amount is not None:
            if data.amount < 1:
                raise ExpenseValidationError("Indique un monto mayor a cero")
            row.amount = int(data.amount)
        if data.expense_date is not None:
            row.expense_date = data.expense_date
        if data.photo_url is not None:
            row.photo_url = self._normalize_photo(data.photo_url)

        branch_id = self._resolve_branch_for_update(user, row, data.branchOfficeId)
        if branch_id is not None:
            row.branch_office_id = branch_id

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, user: UserPublic, expense_id: int) -> None:
        row = self.db.get(Expense, expense_id)
        if row is None or not row.is_active:
            raise ExpenseNotFoundError()
        self._assert_can_access(user, row)
        self._assert_expense_visible_to_user(user, row)
        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
