import random
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso
from app.models.raffle import Raffle
from app.models.raffle_number import RaffleNumber
from app.models.status import Status
from app.schemas.raffle import (
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
        return datetime.now()

    @staticmethod
    def _raffle_to_public(row: Raffle) -> RafflePublic:
        return RafflePublic(
            id=str(row.id),
            status_id=str(row.status_id) if row.status_id is not None else None,
            raffle=row.raffle or "",
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    @staticmethod
    def _number_to_public(row: RaffleNumber) -> RaffleNumberPublic:
        return RaffleNumberPublic(
            id=str(row.id),
            raffle_id=str(row.raffle_id or ""),
            number=int(row.number or 0),
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_raffles(self, stmt):
        return stmt.where(Raffle.deleted_date.is_(None))

    def _active_numbers(self, stmt):
        return stmt.where(RaffleNumber.deleted_date.is_(None))

    def _validate_status_id(self, status_id: int | None) -> None:
        if status_id is None:
            return
        row = self.db.get(Status, status_id)
        if row is None or not row.is_active:
            raise RaffleValidationError("El estatus no existe")

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

    def list_all(self) -> list[RafflePublic]:
        stmt = self._active_raffles(select(Raffle)).order_by(Raffle.raffle, Raffle.id)
        return [self._raffle_to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, raffle_id: int) -> RafflePublic:
        return self._raffle_to_public(self._get_active_raffle(raffle_id))

    def create(self, data: RaffleCreate) -> RafflePublic:
        name = data.raffle.strip()
        if not name:
            raise RaffleValidationError("El nombre del sorteo es obligatorio")
        self._validate_status_id(data.status_id)
        if self._find_duplicate_name(name):
            raise RaffleValidationError("Ya existe un sorteo con ese nombre")

        now = self._now()
        row = Raffle(
            status_id=data.status_id,
            raffle=name,
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

        if "status_id" in patch:
            self._validate_status_id(patch["status_id"])
            row.status_id = patch["status_id"]

        if "raffle" in patch and patch["raffle"] is not None:
            name = patch["raffle"].strip()
            if not name:
                raise RaffleValidationError("El nombre del sorteo no puede quedar vacío")
            if self._find_duplicate_name(name, except_id=raffle_id):
                raise RaffleValidationError("Ya existe un sorteo con ese nombre")
            row.raffle = name

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
        used = self._used_numbers(raffle_id)
        span = max_number - min_number + 1
        if len(used) >= span:
            raise RaffleValidationError("No hay números disponibles en el rango indicado")

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
                raise RaffleValidationError("No hay números disponibles")
            chosen = random.choice(available)

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
