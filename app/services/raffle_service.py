import random
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso, business_now
from app.models.raffle import Raffle
from app.models.raffle_number import RaffleNumber
from app.schemas.raffle import (
    RaffleAssignmentPublic,
    RaffleCreate,
    RaffleDrawResponse,
    RaffleNumberPublic,
    RafflePublic,
    RaffleUpdate,
)


class RaffleNotFoundError(Exception):
    pass


class RaffleValidationError(Exception):
    pass


class RaffleService:
    DEFAULT_MIN_NUMBER = 1
    DEFAULT_MAX_NUMBER = 9999
    DRAW_MAX_ATTEMPTS = 200

    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def _parse_date_bound(
        value: str | None,
        *,
        field_label: str,
        end_of_day: bool = False,
    ) -> datetime:
        if value is None or not str(value).strip():
            raise RaffleValidationError(f"{field_label} es obligatoria")
        raw = str(value).strip().replace(" ", "T")
        try:
            dt = datetime.fromisoformat(raw)
        except ValueError as exc:
            raise RaffleValidationError(f"{field_label} inválida") from exc
        if end_of_day and (len(raw) == 10 or dt.hour + dt.minute + dt.second == 0):
            return dt.replace(hour=23, minute=59, second=59)
        return dt

    @staticmethod
    def _validate_date_range(start: datetime, end: datetime) -> None:
        if end < start:
            raise RaffleValidationError(
                "La fecha de fin debe ser igual o posterior a la de inicio",
            )

    @staticmethod
    def _raffle_to_public(row: Raffle) -> RafflePublic:
        return RafflePublic(
            id=str(row.id),
            raffle=row.raffle or "",
            start_date=datetime_to_iso(row.start_date),
            end_date=datetime_to_iso(row.end_date),
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    @staticmethod
    def _is_raffle_in_period(row: Raffle, when: datetime) -> bool:
        if row.start_date is not None and when < row.start_date:
            return False
        if row.end_date is not None and when > row.end_date:
            return False
        return True

    @staticmethod
    def _number_to_public(row: RaffleNumber) -> RaffleNumberPublic:
        return RaffleNumberPublic(
            id=str(row.id),
            raffle_id=str(row.raffle_id or ""),
            customer_id=str(row.customer_id) if row.customer_id is not None else None,
            ticket_id=str(row.ticket_id) if row.ticket_id is not None else None,
            number=int(row.number or 0),
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_raffles(self, stmt):
        return stmt.where(Raffle.deleted_date.is_(None))

    def _active_numbers(self, stmt):
        return stmt.where(RaffleNumber.deleted_date.is_(None))

    def _get_active_raffle(self, raffle_id: int) -> Raffle:
        stmt = self._active_raffles(select(Raffle)).where(Raffle.id == raffle_id)
        row = self.db.scalars(stmt).first()
        if row is None:
            raise RaffleNotFoundError()
        return row

    def _find_duplicate_name(self, name: str, except_id: int | None = None) -> Raffle | None:
        normalized = name.strip().lower()
        stmt = self._active_raffles(select(Raffle)).where(
            func.lower(Raffle.raffle) == normalized,
        )
        if except_id is not None:
            stmt = stmt.where(Raffle.id != except_id)
        return self.db.scalars(stmt).first()

    def _used_numbers(self, raffle_id: int) -> set[int]:
        stmt = self._active_numbers(select(RaffleNumber.number)).where(
            RaffleNumber.raffle_id == raffle_id,
            RaffleNumber.number.is_not(None),
        )
        return {int(n) for n in self.db.scalars(stmt).all() if n is not None}

    def get_current_active_public(self) -> RafflePublic | None:
        row = self.get_current_active_raffle()
        if row is None:
            return None
        return self._raffle_to_public(row)

    def get_current_active_raffle(self) -> Raffle | None:
        """Rifa no eliminada y dentro de vigencia (inicio / fin)."""
        now = self._now()
        stmt = self._active_raffles(select(Raffle)).order_by(Raffle.id.desc())
        for row in self.db.scalars(stmt).all():
            if self._is_raffle_in_period(row, now):
                return row
        return None

    def _find_customer_number_row(
        self,
        raffle_id: int,
        customer_id: int,
    ) -> RaffleNumber | None:
        if customer_id <= 0:
            return None
        stmt = self._active_numbers(select(RaffleNumber)).where(
            RaffleNumber.raffle_id == raffle_id,
            RaffleNumber.customer_id == customer_id,
        )
        return self.db.scalars(stmt).first()

    def _pick_unique_number(
        self,
        raffle_id: int,
        *,
        min_number: int = DEFAULT_MIN_NUMBER,
        max_number: int = DEFAULT_MAX_NUMBER,
    ) -> int:
        used = self._used_numbers(raffle_id)
        span = max_number - min_number + 1
        if len(used) >= span:
            raise RaffleValidationError("No hay números disponibles en la rifa activa")

        chosen: int | None = None
        attempts = min(self.DRAW_MAX_ATTEMPTS, span - len(used))
        for _ in range(attempts):
            candidate = random.randint(min_number, max_number)
            if candidate not in used:
                chosen = candidate
                break

        if chosen is None:
            available = [n for n in range(min_number, max_number + 1) if n not in used]
            if not available:
                raise RaffleValidationError("No hay números disponibles en la rifa activa")
            chosen = random.choice(available)
        return chosen

    def assign_number_for_customer(
        self,
        raffle_id: int,
        customer_id: int,
        *,
        ticket_id: int | None = None,
        commit: bool = True,
    ) -> RaffleAssignmentPublic:
        if customer_id <= 0:
            raise RaffleValidationError("El cliente no es válido para la rifa")

        raffle = self._get_active_raffle(raffle_id)
        now = self._now()
        if not self._is_raffle_in_period(raffle, now):
            raise RaffleValidationError("La rifa no está en período de vigencia")

        existing = self._find_customer_number_row(raffle_id, customer_id)
        if existing is not None and existing.number is not None:
            if ticket_id and not existing.ticket_id:
                existing.ticket_id = ticket_id
                existing.updated_date = now
            return RaffleAssignmentPublic(
                raffle_id=str(raffle_id),
                raffle_name=raffle.raffle or "",
                number=int(existing.number),
            )

        chosen = self._pick_unique_number(raffle_id)
        row = RaffleNumber(
            raffle_id=raffle_id,
            customer_id=customer_id,
            ticket_id=ticket_id,
            number=chosen,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        if commit:
            self.db.commit()
            self.db.refresh(row)
        return RaffleAssignmentPublic(
            raffle_id=str(raffle_id),
            raffle_name=raffle.raffle or "",
            number=chosen,
        )

    def list_all(self) -> list[RafflePublic]:
        stmt = self._active_raffles(select(Raffle)).order_by(Raffle.raffle, Raffle.id)
        return [self._raffle_to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, raffle_id: int) -> RafflePublic:
        return self._raffle_to_public(self._get_active_raffle(raffle_id))

    def create(self, data: RaffleCreate) -> RafflePublic:
        name = data.raffle.strip()
        if not name:
            raise RaffleValidationError("El nombre del sorteo es obligatorio")
        if self._find_duplicate_name(name):
            raise RaffleValidationError("Ya existe un sorteo con ese nombre")

        start = self._parse_date_bound(
            data.start_date,
            field_label="La fecha de inicio",
        )
        end = self._parse_date_bound(
            data.end_date,
            field_label="La fecha de fin",
            end_of_day=True,
        )
        self._validate_date_range(start, end)

        now = self._now()
        row = Raffle(
            raffle=name,
            start_date=start,
            end_date=end,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self._raffle_to_public(row)

    def update(self, raffle_id: int, data: RaffleUpdate) -> RafflePublic:
        row = self._get_active_raffle(raffle_id)
        patch = data.model_dump(exclude_unset=True)

        if "raffle" in patch and patch["raffle"] is not None:
            name = patch["raffle"].strip()
            if not name:
                raise RaffleValidationError("El nombre del sorteo no puede quedar vacío")
            if self._find_duplicate_name(name, except_id=raffle_id):
                raise RaffleValidationError("Ya existe un sorteo con ese nombre")
            row.raffle = name

        start = row.start_date
        end = row.end_date
        if "start_date" in patch:
            start = self._parse_date_bound(
                patch["start_date"],
                field_label="La fecha de inicio",
            )
            row.start_date = start
        if "end_date" in patch:
            end = self._parse_date_bound(
                patch["end_date"],
                field_label="La fecha de fin",
                end_of_day=True,
            )
            row.end_date = end
        if start is not None and end is not None:
            self._validate_date_range(start, end)

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self._raffle_to_public(row)

    def delete(self, raffle_id: int) -> None:
        row = self._get_active_raffle(raffle_id)
        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()

    def list_numbers(self, raffle_id: int) -> list[RaffleNumberPublic]:
        self._get_active_raffle(raffle_id)
        stmt = (
            self._active_numbers(select(RaffleNumber))
            .where(RaffleNumber.raffle_id == raffle_id)
            .order_by(RaffleNumber.number, RaffleNumber.id)
        )
        return [self._number_to_public(row) for row in self.db.scalars(stmt).all()]

    def draw_number(
        self,
        raffle_id: int,
        *,
        min_number: int = DEFAULT_MIN_NUMBER,
        max_number: int = DEFAULT_MAX_NUMBER,
    ) -> RaffleDrawResponse:
        if min_number < 0 or max_number < min_number:
            raise RaffleValidationError("Rango de números inválido")

        self._get_active_raffle(raffle_id)
        chosen = self._pick_unique_number(
            raffle_id,
            min_number=min_number,
            max_number=max_number,
        )
        now = self._now()
        row = RaffleNumber(
            raffle_id=raffle_id,
            number=chosen,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return RaffleDrawResponse(item=self._number_to_public(row))
