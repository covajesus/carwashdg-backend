import calendar
from datetime import date, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.branch_scope import branch_scope_for_user
from app.core.datetime_utils import business_now
from app.models.branch_office import BranchOffice
from app.models.expense import Expense
from app.models.expense_type import ExpenseType
from app.schemas.expense import ExpenseCreate, ExpensePublic, ExpenseUpdate
from app.schemas.user import UserPublic
from app.services.expense_type_service import ExpenseTypeService


class ExpenseNotFoundError(Exception):
    pass


class ExpenseValidationError(Exception):
    pass


class ExpenseForbiddenError(Exception):
    pass


class ExpenseService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._types = ExpenseTypeService(db)

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def _user_is_admin(user: UserPublic) -> bool:
        return branch_scope_for_user(user) is None

    def list_type_options_for_user(self, user: UserPublic) -> list[dict[str, object]]:
        items = self._types.list_options_for_user(is_admin=self._user_is_admin(user))
        return [
            {
                "id": row.id,
                "label": row.name,
                "classification": row.classification,
                "classificationLabel": row.classificationLabel,
                "requiresPhoto": row.requiresPhoto,
                "adminOnly": row.adminOnly,
            }
            for row in items
        ]

    def _resolve_type_row(self, expense_type_id: int | None) -> ExpenseType:
        if expense_type_id is None or expense_type_id < 1:
            raise ExpenseValidationError("Seleccione el tipo de gasto")
        try:
            return self._types.get_active_row(expense_type_id)
        except Exception as exc:
            raise ExpenseValidationError("Tipo de gasto no válido") from exc

    def _type_row_for_expense(self, row: Expense) -> ExpenseType | None:
        if row.expense_type_id is not None and row.expense_type_id >= 1:
            try:
                return self._types.get_active_row(int(row.expense_type_id))
            except Exception:
                pass
        if row.expense_type:
            return self._types.get_active_row_by_code(row.expense_type)
        return None

    def _assert_expense_visible_to_user(self, user: UserPublic, row: Expense) -> None:
        if self._user_is_admin(user):
            return
        type_row = self._type_row_for_expense(row)
        if type_row is not None and bool(type_row.admin_only):
            raise ExpenseNotFoundError()

    def _reject_admin_only_type_for_user(self, user: UserPublic, type_row: ExpenseType) -> None:
        if self._user_is_admin(user):
            return
        if bool(type_row.admin_only):
            raise ExpenseValidationError("Tipo de gasto no válido")

    def _branch_name(self, branch_office_id: int | None) -> str | None:
        if branch_office_id is None or branch_office_id < 1:
            return None
        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            return None
        return branch.branch_office.strip() or None

    def to_public(self, row: Expense) -> ExpensePublic:
        type_row = self._type_row_for_expense(row)
        classification = None
        classification_label = None
        type_id = row.expense_type_id
        type_code = (row.expense_type or "").strip()
        type_label = type_code or "—"
        if type_row is not None:
            type_id = int(type_row.id) if type_row.id is not None else type_id
            type_code = (type_row.code or "").strip() or type_code
            type_label = (type_row.name or "").strip() or type_label
            classification = (
                "cash" if (type_row.classification or "").strip().lower() == "cash" else "bank"
            )
            classification_label = self._types.classification_label(classification)
        return ExpensePublic(
            id=str(row.id),
            expenseTypeId=type_id,
            expense_type=type_code,
            expense_type_label=type_label,
            classification=classification,
            classificationLabel=classification_label,
            amount=int(row.amount or 0),
            expense_date=row.expense_date,
            branchOfficeId=row.branch_office_id,
            branchOfficeName=self._branch_name(row.branch_office_id),
            photo_url=row.photo_url,
            added_date=row.added_date,
            updated_date=row.updated_date,
            deleted_date=row.deleted_date,
        )

    def _active_filter(self, stmt):
        return stmt.where(Expense.deleted_date.is_(None))

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

    def _admin_only_type_ids(self) -> list[int]:
        rows = self.db.scalars(
            select(ExpenseType.id).where(
                ExpenseType.deleted_date.is_(None),
                ExpenseType.admin_only.is_(True),
            ),
        ).all()
        return [int(row) for row in rows if row is not None]

    def month_total_for_user(self, user: UserPublic, *, year: int, month: int) -> int:
        if month < 1 or month > 12:
            raise ExpenseValidationError("Mes no válido")
        if year < 2000 or year > 2100:
            raise ExpenseValidationError("Año no válido")

        scope = branch_scope_for_user(user)
        if scope == 0:
            return 0

        first_day = date(year, month, 1)
        last_day = date(year, month, calendar.monthrange(year, month)[1])

        stmt = select(func.coalesce(func.sum(Expense.amount), 0)).where(
            Expense.deleted_date.is_(None),
            Expense.expense_date >= first_day,
            Expense.expense_date <= last_day,
        )
        if scope is not None:
            stmt = stmt.where(Expense.branch_office_id == scope)
        if not self._user_is_admin(user):
            admin_only_ids = self._admin_only_type_ids()
            if admin_only_ids:
                stmt = stmt.where(
                    (Expense.expense_type_id.is_(None))
                    | (Expense.expense_type_id.notin_(tuple(admin_only_ids))),
                )

        return int(self.db.scalar(stmt) or 0)

    def list_for_user(
        self,
        user: UserPublic,
        *,
        branch_office_id: int | None = None,
        expense_date: date | None = None,
    ) -> list[ExpensePublic]:
        scope = branch_scope_for_user(user)
        if scope == 0:
            return []

        stmt = self._active_filter(select(Expense)).order_by(
            Expense.expense_date.desc(),
            Expense.added_date.desc(),
        )
        if scope is not None:
            stmt = stmt.where(Expense.branch_office_id == scope)
        elif branch_office_id is not None and branch_office_id >= 1:
            self._validate_branch_exists(branch_office_id)
            stmt = stmt.where(Expense.branch_office_id == branch_office_id)

        if expense_date is not None:
            stmt = stmt.where(Expense.expense_date == expense_date)

        rows = list(self.db.scalars(stmt).all())
        if not self._user_is_admin(user):
            visible: list[Expense] = []
            for row in rows:
                type_row = self._type_row_for_expense(row)
                if type_row is not None and bool(type_row.admin_only):
                    continue
                visible.append(row)
            rows = visible
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
        type_row = self._resolve_type_row(data.expenseTypeId)
        self._reject_admin_only_type_for_user(user, type_row)
        photo_url = self._normalize_photo(data.photo_url)
        if bool(type_row.requires_photo) and not photo_url:
            raise ExpenseValidationError("Suba una foto del comprobante")
        branch_office_id = self._resolve_branch_for_create(user, data.branchOfficeId)
        now = self._now()
        row = Expense(
            expense_type=(type_row.code or "").strip(),
            expense_type_id=int(type_row.id),
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

        type_row = self._type_row_for_expense(row)
        if data.expenseTypeId is not None:
            type_row = self._resolve_type_row(data.expenseTypeId)
            self._reject_admin_only_type_for_user(user, type_row)
            row.expense_type_id = int(type_row.id)
            row.expense_type = (type_row.code or "").strip()

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
