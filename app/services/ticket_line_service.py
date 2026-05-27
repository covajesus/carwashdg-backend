from datetime import datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import business_now, datetime_to_iso
from app.core.pricing import round_money
from app.models.service import Service
from app.models.ticket_branch_office_service import TicketBranchOfficeService
from app.models.user import User
from app.models.washer_daily_group import WasherDailyGroup
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
        return business_now()

    @staticmethod
    def _timestamp_str() -> str:
        return datetime_to_iso(business_now()) or ""

    @staticmethod
    def _resolved_line_total(row: TicketBranchOfficeService) -> int:
        if row.total is not None:
            return round_money(row.total)
        return 0

    def to_public(self, row: TicketBranchOfficeService) -> TicketBranchOfficeServicePublic:
        svc_id = row.service_id
        return TicketBranchOfficeServicePublic(
            id=str(row.id),
            ticket_id=str(row.ticket_id or ""),
            service_id=str(svc_id) if svc_id is not None else None,
            additional_service=(row.additional_service or "").strip() or None,
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
        additional = (row.additional_service or "").strip()
        svc_id = row.service_id

        if svc_id == 0 or (svc_id is None and additional):
            if not additional:
                return None
            return TicketServiceLine(
                id=str(row.id),
                ticket_id=str(row.ticket_id or ""),
                service_id="0",
                service_name=additional,
                additional_service=additional,
                price=self._resolved_line_total(row),
                washer_id=str(row.washer_id) if row.washer_id is not None else None,
                added_date=datetime_to_iso(row.added_date),
            )

        if svc_id is None:
            return None

        svc = self.db.get(Service, svc_id)
        if svc is None or not svc.is_active:
            return None
        return TicketServiceLine(
            id=str(row.id),
            ticket_id=str(row.ticket_id or ""),
            service_id=str(svc_id),
            service_name=svc.service,
            additional_service=None,
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

    def assignee_labels_for_ticket_ids(
        self,
        ticket_ids: list[int],
    ) -> dict[int, tuple[str, str, int | None, int | None]]:
        """ticket_id → (kind, label, washer_id, group_id)."""
        if not ticket_ids:
            return {}

        stmt = (
            self._active_filter(select(TicketBranchOfficeService))
            .where(
                TicketBranchOfficeService.ticket_id.in_(ticket_ids),
                or_(
                    TicketBranchOfficeService.washer_id.isnot(None),
                    TicketBranchOfficeService.washer_daily_group_id.isnot(None),
                ),
            )
            .order_by(
                TicketBranchOfficeService.ticket_id,
                TicketBranchOfficeService.added_date,
                TicketBranchOfficeService.id,
            )
        )

        assignment_by_ticket: dict[int, TicketBranchOfficeService] = {}
        for row in self.db.scalars(stmt).all():
            tid = row.ticket_id
            if tid is None or tid in assignment_by_ticket:
                continue
            assignment_by_ticket[tid] = row

        washer_ids = {
            row.washer_id
            for row in assignment_by_ticket.values()
            if row.washer_id is not None and row.washer_daily_group_id is None
        }
        group_ids = {
            row.washer_daily_group_id
            for row in assignment_by_ticket.values()
            if row.washer_daily_group_id is not None
        }

        washer_names: dict[int, str] = {}
        if washer_ids:
            for user in self.db.scalars(select(User).where(User.id.in_(washer_ids))).all():
                if user.id is not None:
                    washer_names[int(user.id)] = (
                        user.full_name.strip() or f"Lavador #{user.id}"
                    )

        group_names: dict[int, str] = {}
        if group_ids:
            for group in self.db.scalars(
                select(WasherDailyGroup).where(WasherDailyGroup.id.in_(group_ids)),
            ).all():
                if group.id is not None:
                    group_names[int(group.id)] = group.name.strip() or f"Grupo #{group.id}"

        result: dict[int, tuple[str, str, int | None, int | None]] = {}
        for tid, row in assignment_by_ticket.items():
            if row.washer_daily_group_id is not None:
                gid = int(row.washer_daily_group_id)
                result[tid] = ("group", group_names.get(gid, f"Grupo #{gid}"), None, gid)
            elif row.washer_id is not None:
                wid = int(row.washer_id)
                result[tid] = ("washer", washer_names.get(wid, f"Lavador #{wid}"), wid, None)
        return result

    def reassign_ticket_assignee(
        self,
        ticket_id: int,
        *,
        washer_id: int | None,
        washer_daily_group_id: int | None,
    ) -> tuple[str, str]:
        """Actualiza lavador o grupo en todas las líneas activas del ticket."""
        if ticket_id <= 0:
            raise TicketLineValidationError("El ticket no es válido")
        if washer_id is not None and washer_daily_group_id is not None:
            raise TicketLineValidationError("Seleccione un lavador o un grupo, no ambos")
        if washer_id is None and washer_daily_group_id is None:
            raise TicketLineValidationError("Seleccione un lavador o un grupo")

        resolved: int | None = None
        if washer_daily_group_id is None:
            resolved = self._resolve_washer(ticket_id=ticket_id, washer_id=washer_id)
            if resolved is None:
                raise TicketLineValidationError("Lavador no válido")

        ts = self._timestamp_str()
        lines = list(
            self.db.scalars(
                self._active_filter(select(TicketBranchOfficeService)).where(
                    TicketBranchOfficeService.ticket_id == ticket_id,
                ),
            ).all(),
        )
        service_lines = [
            line
            for line in lines
            if line.service_id is not None or (line.additional_service or "").strip()
        ]

        if service_lines:
            for line in service_lines:
                line.washer_id = resolved
                line.washer_daily_group_id = washer_daily_group_id
                line.updated_date = ts
        else:
            self.assign_washer_to_ticket(
                ticket_id,
                washer_id,
                washer_daily_group_id=washer_daily_group_id,
                commit=False,
            )

        if washer_daily_group_id is not None:
            gid = int(washer_daily_group_id)
            group = self.db.get(WasherDailyGroup, gid)
            label = group.name.strip() if group and group.name else f"Grupo #{gid}"
            return ("group", label)
        assert resolved is not None
        user = self.db.get(User, resolved)
        label = user.full_name.strip() if user and user.full_name else f"Lavador #{resolved}"
        return ("washer", label)

    def assign_washer_to_ticket(
        self,
        ticket_id: int,
        washer_id: int | None,
        *,
        washer_daily_group_id: int | None = None,
        commit: bool = True,
    ) -> None:
        """Asigna lavador o grupo al ticket (línea placeholder o actualización de líneas existentes)."""
        if ticket_id <= 0:
            raise TicketLineValidationError("El ticket no es válido")
        if washer_id is not None and washer_daily_group_id is not None:
            raise TicketLineValidationError("Seleccione un lavador o un grupo, no ambos")

        resolved: int | None = None
        if washer_daily_group_id is None:
            resolved = self._resolve_washer(ticket_id=ticket_id, washer_id=washer_id)
        now = self._now()
        ts = self._timestamp_str()

        placeholder = self.db.scalars(
            self._active_filter(select(TicketBranchOfficeService)).where(
                TicketBranchOfficeService.ticket_id == ticket_id,
                TicketBranchOfficeService.service_id.is_(None),
                TicketBranchOfficeService.additional_service.is_(None),
            ),
        ).first()

        if resolved is None and washer_daily_group_id is None:
            if placeholder is not None:
                placeholder.deleted_date = now
                placeholder.updated_date = ts
        elif placeholder is not None:
            placeholder.washer_id = resolved
            placeholder.washer_daily_group_id = washer_daily_group_id
            placeholder.updated_date = ts
        else:
            self.db.add(
                TicketBranchOfficeService(
                    ticket_id=ticket_id,
                    service_id=None,
                    washer_id=resolved,
                    washer_daily_group_id=washer_daily_group_id,
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
        lines: list[tuple[int, int, str | None]] | None = None,
        washer_id: int | None,
        washer_daily_group_id: int | None = None,
    ) -> None:
        """Inserta líneas en tickets_branch_offices_services (sin commit)."""
        if ticket_id <= 0:
            raise TicketLineValidationError("El ticket no es válido")
        if washer_id is not None and washer_daily_group_id is not None:
            raise TicketLineValidationError("Seleccione un lavador o un grupo, no ambos")

        items: list[tuple[int, int | None, str | None]] = []
        if lines:
            items = [(service_id, line_total, extra) for service_id, line_total, extra in lines]
        if not items:
            return

        resolved_washer: int | None = None
        if washer_daily_group_id is None:
            resolved_washer = self._resolve_washer(
                ticket_id=ticket_id,
                washer_id=washer_id,
            )

        for service_id, line_total, additional_name in items:
            additional = (additional_name or "").strip() or None
            if line_total is None:
                raise TicketLineValidationError(
                    "Indique el monto de cada servicio al crear el ticket",
                )
            stored_total = round_money(line_total)

            if service_id == 0:
                if not additional:
                    raise TicketLineValidationError(
                        "Indique el nombre del servicio adicional",
                    )
                self.db.add(
                    TicketBranchOfficeService(
                        ticket_id=ticket_id,
                        service_id=0,
                        additional_service=additional[:255],
                        washer_id=resolved_washer,
                        washer_daily_group_id=washer_daily_group_id,
                        total=stored_total,
                        added_date=self._now(),
                        updated_date=self._timestamp_str(),
                        deleted_date=None,
                    ),
                )
                continue

            if service_id < 0:
                raise TicketLineValidationError("Servicio no válido")

            svc = self.db.get(Service, service_id)
            if svc is None or not svc.is_active:
                raise TicketLineValidationError("El servicio no existe")

            self.db.add(
                TicketBranchOfficeService(
                    ticket_id=ticket_id,
                    service_id=service_id,
                    additional_service=None,
                    washer_id=resolved_washer,
                    washer_daily_group_id=washer_daily_group_id,
                    total=stored_total,
                    added_date=self._now(),
                    updated_date=self._timestamp_str(),
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
        if data.service_id is None:
            raise TicketLineValidationError("El servicio es obligatorio")

        svc = self.db.get(Service, data.service_id)
        if svc is None or not svc.is_active:
            raise TicketLineValidationError("El servicio no existe")

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
        stored_total = round_money(data.total)
        row = TicketBranchOfficeService(
            ticket_id=data.ticket_id,
            service_id=data.service_id,
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

        if data.service_id is not None:
            svc = self.db.get(Service, data.service_id)
            if svc is None or not svc.is_active:
                raise TicketLineValidationError("El servicio no existe")
            row.service_id = data.service_id

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
            row.total = round_money(data.total)

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
