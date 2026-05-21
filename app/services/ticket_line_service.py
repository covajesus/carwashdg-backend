from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso
from app.core.pricing import round_pesos
from app.models.branch_office_service import BranchOfficeService
from app.models.service import Service
from app.models.ticket_branch_office_service import TicketBranchOfficeService
from app.schemas.ticket import TicketServiceLine
from app.schemas.ticket_branch_office_service import (
    TicketBranchOfficeServiceCreate,
    TicketBranchOfficeServicePublic,
    TicketBranchOfficeServiceUpdate,
)
from app.services.washer_validation import WasherValidationError, resolve_washer_id


class TicketLineNotFoundError(Exception):
    pass


class TicketLineValidationError(Exception):
    pass


class TicketLineService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    @staticmethod
    def _timestamp_str() -> str:
        return datetime.now().isoformat()

    @staticmethod
    def _resolved_line_total(row: TicketBranchOfficeService) -> int:
        if row.total is not None:
            return round_pesos(row.total)
        return 0

    def to_public(self, row: TicketBranchOfficeService) -> TicketBranchOfficeServicePublic:
        return TicketBranchOfficeServicePublic(
            id=str(row.id),
            ticket_id=str(row.ticket_id or ""),
            branch_office_service_id=(
                str(row.branch_office_service_id)
                if row.branch_office_service_id is not None
                else None
            ),
            washer_id=str(row.washer_id) if row.washer_id is not None else None,
            total=self._resolved_line_total(row),
            added_date=datetime_to_iso(row.added_date),
            updated_date=row.updated_date,
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_filter(self, stmt):
        return stmt.where(TicketBranchOfficeService.deleted_date.is_(None))

    def _default_washer_for_ticket(self, ticket_id: int) -> int | None:
        stmt = (
            self._active_filter(select(TicketBranchOfficeService))
            .where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.washer_id.isnot(None),
            )
            .limit(1)
        )
        row = self.db.scalars(stmt).first()
        return row.washer_id if row else None

    def _resolve_washer(self, *, ticket_id: int, washer_id: int | None) -> int | None:
        try:
            resolved = resolve_washer_id(
                self.db,
                washer_id if washer_id is not None else self._default_washer_for_ticket(ticket_id),
            )
        except WasherValidationError as exc:
            raise TicketLineValidationError(str(exc)) from exc
        return resolved

    def _to_line(self, row: TicketBranchOfficeService) -> TicketServiceLine | None:
        if row.branch_office_service_id is None:
            return None
        bos = self.db.get(BranchOfficeService, row.branch_office_service_id)
        if bos is None or not bos.is_active:
            return None
        svc = self.db.get(Service, bos.service_id)
        if svc is None:
            return None
        return TicketServiceLine(
            id=str(row.id),
            ticket_id=str(row.ticket_id or ""),
            branch_office_service_id=str(row.branch_office_service_id or ""),
            service_id=str(bos.service_id or ""),
            service_name=svc.service,
            price=self._resolved_line_total(row),
            washer_id=str(row.washer_id) if row.washer_id is not None else None,
            added_date=datetime_to_iso(row.added_date),
        )

    def list_lines_for_ticket(self, ticket_id: int) -> list[TicketServiceLine]:
        stmt = (
            self._active_filter(select(TicketBranchOfficeService))
            .where(TicketBranchOfficeService.ticket_id == ticket_id)
            .order_by(TicketBranchOfficeService.added_date, TicketBranchOfficeService.id)
        )
        lines: list[TicketServiceLine] = []
        for row in self.db.scalars(stmt).all():
            line = self._to_line(row)
            if line is not None:
                lines.append(line)
        return lines

    def washer_id_for_ticket(self, ticket_id: int) -> int | None:
        return self._default_washer_for_ticket(ticket_id)

    def assign_washer_to_ticket(
        self,
        ticket_id: int,
        washer_id: int | None,
        *,
        commit: bool = True,
    ) -> None:
        """Asigna lavador al ticket (línea placeholder o actualización de líneas existentes)."""
        if ticket_id <= 0:
            raise TicketLineValidationError("El ticket no es válido")

        resolved = self._resolve_washer(ticket_id=ticket_id, washer_id=washer_id)
        now = self._now()
        ts = self._timestamp_str()

        placeholder = self.db.scalars(
            self._active_filter(select(TicketBranchOfficeService)).where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.branch_office_service_id.is_(None),
            ),
        ).first()

        if resolved is None:
            if placeholder is not None:
                placeholder.deleted_date = now
                placeholder.updated_date = ts
        elif placeholder is not None:
            placeholder.washer_id = resolved
            placeholder.updated_date = ts
        else:
            self.db.add(
                TicketBranchOfficeService(
                    ticket_id=ticket_id,
                    branch_office_service_id=None,
                    washer_id=resolved,
                    added_date=now,
                    updated_date=ts,
                    deleted_date=None,
                ),
            )

        if commit:
            self.db.commit()

    def create_lines_for_ticket(
        self,
        *,
        ticket_id: int,
        branch_office_service_ids: list[int] | None = None,
        lines: list[tuple[int, int]] | None = None,
        washer_id: int | None,
    ) -> None:
        """Inserta líneas en tickets_branch_offices_services (sin commit)."""
        if ticket_id <= 0:
            raise TicketLineValidationError("El ticket no es válido")

        items: list[tuple[int, int | None]] = []
        if lines:
            items = [(bos_id, line_total) for bos_id, line_total in lines]
        elif branch_office_service_ids:
            items = [(bos_id, None) for bos_id in branch_office_service_ids]
        if not items:
            return

        now = self._now()
        ts = self._timestamp_str()

        for bos_id, line_total in items:
            if bos_id <= 0:
                raise TicketLineValidationError("Servicio no válido")

            bos = self.db.get(BranchOfficeService, bos_id)
            if bos is None or not bos.is_active:
                raise TicketLineValidationError("El servicio de sucursal no existe")

            resolved_washer = self._resolve_washer(
                ticket_id=ticket_id,
                washer_id=washer_id,
            )
            if line_total is None:
                raise TicketLineValidationError(
                    "Indique el monto de cada servicio al crear el ticket",
                )
            stored_total = round_pesos(line_total)

            self.db.add(
                TicketBranchOfficeService(
                    ticket_id=ticket_id,
                    branch_office_service_id=bos_id,
                    washer_id=resolved_washer,
                    total=stored_total,
                    added_date=now,
                    updated_date=ts,
                    deleted_date=None,
                ),
            )

    def list_all(self, *, ticket_id: int | None = None) -> list[TicketBranchOfficeServicePublic]:
        stmt = self._active_filter(select(TicketBranchOfficeService))
        if ticket_id is not None:
            stmt = stmt.where(TicketBranchOfficeService.ticket_id == ticket_id)
        return [self.to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, line_id: int) -> TicketBranchOfficeServicePublic:
        stmt = self._active_filter(select(TicketBranchOfficeService)).where(
            TicketBranchOfficeService.id == line_id,
        )
        row = self.db.scalars(stmt).first()
        if row is None:
            raise TicketLineNotFoundError()
        return self.to_public(row)

    def create(self, data: TicketBranchOfficeServiceCreate) -> TicketBranchOfficeServicePublic:
        if data.branch_office_service_id is None:
            raise TicketLineValidationError("El servicio de sucursal es obligatorio")

        bos = self.db.get(BranchOfficeService, data.branch_office_service_id)
        if bos is None or not bos.is_active:
            raise TicketLineValidationError("El servicio de sucursal no existe")

        washer_id = self._resolve_washer(
            ticket_id=data.ticket_id,
            washer_id=data.washer_id,
        )

        now = self._now()
        ts = self._timestamp_str()
        if data.ticket_id <= 0:
            raise TicketLineValidationError("El ticket no es válido")

        if data.total is None:
            raise TicketLineValidationError("El monto del servicio es obligatorio")
        stored_total = round_pesos(data.total)
        row = TicketBranchOfficeService(
            ticket_id=data.ticket_id,
            branch_office_service_id=data.branch_office_service_id,
            washer_id=washer_id,
            total=stored_total,
            added_date=now,
            updated_date=ts,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(
        self,
        line_id: int,
        data: TicketBranchOfficeServiceUpdate,
    ) -> TicketBranchOfficeServicePublic:
        row = self.db.get(TicketBranchOfficeService, line_id)
        if row is None or not row.is_active:
            raise TicketLineNotFoundError()

        if data.branch_office_service_id is not None:
            bos = self.db.get(BranchOfficeService, data.branch_office_service_id)
            if bos is None or not bos.is_active:
                raise TicketLineValidationError("El servicio de sucursal no existe")
            row.branch_office_service_id = data.branch_office_service_id

        if data.ticket_id is not None:
            row.ticket_id = data.ticket_id

        if data.washer_id is not None:
            ticket_id = row.ticket_id or data.ticket_id
            if ticket_id is None:
                raise TicketLineValidationError("El ticket es obligatorio")
            row.washer_id = self._resolve_washer(
                ticket_id=ticket_id,
                washer_id=data.washer_id,
            )

        if data.total is not None:
            row.total = round_pesos(data.total)

        row.updated_date = self._timestamp_str()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def soft_delete_for_ticket(self, ticket_id: int, *, deleted_at: datetime | None = None) -> None:
        """Marca como eliminadas todas las líneas activas del ticket (sin commit)."""
        if ticket_id <= 0:
            return
        when = deleted_at or self._now()
        ts = when.isoformat()
        stmt = self._active_filter(select(TicketBranchOfficeService)).where(
            TicketBranchOfficeService.ticket_id == ticket_id,
        )
        for row in self.db.scalars(stmt).all():
            row.deleted_date = when
            row.updated_date = ts

    def delete(self, line_id: int) -> None:
        row = self.db.get(TicketBranchOfficeService, line_id)
        if row is None or not row.is_active:
            raise TicketLineNotFoundError()
        now = self._now()
        row.deleted_date = now
        row.updated_date = self._timestamp_str()
        self.db.commit()
