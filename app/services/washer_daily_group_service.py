from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.datetime_utils import business_now, business_today
from app.core.roles import WASHER_ROL_ID
from app.models.branch_office import BranchOffice
from app.models.user import User
from app.models.washer_daily_group import WasherDailyGroup, WasherDailyGroupMember
from app.schemas.user import UserPublic
from app.schemas.washer_daily_group import (
    TicketWasherOptionGroup,
    TicketWasherOptionWasher,
    TicketWasherOptionsResponse,
    WasherDailyGroupCreate,
    WasherDailyGroupListResponse,
    WasherDailyGroupMemberPublic,
    WasherDailyGroupPublic,
    WasherDailyGroupUpdate,
)
from app.core.branch_scope import branch_scope_for_user
from app.core.user_status import active_from_status_id
from app.services.branch_office_washer_service import BranchOfficeWasherService


class WasherDailyGroupNotFoundError(Exception):
    pass


class WasherDailyGroupValidationError(Exception):
    pass


class WasherDailyGroupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self._branch_washers = BranchOfficeWasherService(db)

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def _today() -> date:
        return business_today()

    def _ensure_branch_access(self, user: UserPublic, branch_office_id: int) -> BranchOffice:
        scope = branch_scope_for_user(user)
        if scope == 0:
            raise WasherDailyGroupValidationError("No tiene permiso para consultar grupos")
        if scope is not None and scope != branch_office_id:
            raise WasherDailyGroupValidationError("No puede consultar otra sucursal")
        branch = self.db.get(BranchOffice, branch_office_id)
        if branch is None or not branch.is_active:
            raise WasherDailyGroupValidationError("La sucursal no existe")
        return branch

    def _resolve_branch_for_user(self, user: UserPublic) -> int:
        scope = branch_scope_for_user(user)
        if scope is None or scope == 0:
            raise WasherDailyGroupValidationError("No tiene sucursal asignada")
        return scope

    def _washer_full_name(self, washer_id: int) -> str:
        row = self.db.get(User, washer_id)
        if row is None or not row.is_active:
            return f"Lavador #{washer_id}"
        return row.full_name.strip() or f"Lavador #{washer_id}"

    def _active_groups_query(self, *, branch_office_id: int, group_date: date):
        return select(WasherDailyGroup).where(
            WasherDailyGroup.branch_office_id == branch_office_id,
            WasherDailyGroup.group_date == group_date,
            WasherDailyGroup.deleted_date.is_(None),
        )

    def _active_members_for_group(self, group_id: int) -> list[WasherDailyGroupMember]:
        return self.db.scalars(
            select(WasherDailyGroupMember)
            .where(
                WasherDailyGroupMember.group_id == group_id,
                WasherDailyGroupMember.deleted_date.is_(None),
            )
            .order_by(WasherDailyGroupMember.id.asc()),
        ).all()

    def _member_washer_ids(self, group_id: int) -> list[int]:
        return [row.washer_id for row in self._active_members_for_group(group_id)]

    def _washer_ids_in_groups(
        self,
        *,
        branch_office_id: int,
        group_date: date,
        exclude_group_id: int | None = None,
    ) -> set[int]:
        groups = self.db.scalars(
            self._active_groups_query(
                branch_office_id=branch_office_id,
                group_date=group_date,
            ).order_by(WasherDailyGroup.id.asc()),
        ).all()
        assigned: set[int] = set()
        for group in groups:
            if group.id is None:
                continue
            if exclude_group_id is not None and group.id == exclude_group_id:
                continue
            assigned.update(self._member_washer_ids(group.id))
        return assigned

    def _validate_washer_ids_for_branch(
        self,
        *,
        branch_office_id: int,
        washer_ids: list[int],
        group_date: date,
        exclude_group_id: int | None = None,
    ) -> None:
        branch_washer_ids = set(
            self._branch_washers.list_washer_ids_for_branch(branch_office_id),
        )
        already_grouped = self._washer_ids_in_groups(
            branch_office_id=branch_office_id,
            group_date=group_date,
            exclude_group_id=exclude_group_id,
        )
        for washer_id in washer_ids:
            if washer_id not in branch_washer_ids:
                raise WasherDailyGroupValidationError(
                    f"El lavador #{washer_id} no pertenece a esta sucursal",
                )
            user = self.db.get(User, washer_id)
            if user is None or not user.is_active or user.rol_id != WASHER_ROL_ID:
                raise WasherDailyGroupValidationError("Lavador no válido")
            if washer_id in already_grouped:
                raise WasherDailyGroupValidationError(
                    f"{self._washer_full_name(washer_id)} ya está en otro grupo del día",
                )

    def _to_public(self, group: WasherDailyGroup) -> WasherDailyGroupPublic:
        members = [
            WasherDailyGroupMemberPublic(
                washer_id=str(row.washer_id),
                full_name=self._washer_full_name(row.washer_id),
            )
            for row in self._active_members_for_group(group.id or 0)
        ]
        return WasherDailyGroupPublic(
            id=str(group.id),
            branch_office_id=str(group.branch_office_id),
            group_date=group.group_date.isoformat(),
            name=group.name.strip(),
            members=members,
        )

    def list_for_branch_and_date(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        group_date: date | None = None,
    ) -> WasherDailyGroupListResponse:
        day = group_date or self._today()
        self._ensure_branch_access(user, branch_office_id)
        rows = self.db.scalars(
            self._active_groups_query(branch_office_id=branch_office_id, group_date=day)
            .order_by(WasherDailyGroup.name.asc(), WasherDailyGroup.id.asc()),
        ).all()
        return WasherDailyGroupListResponse(
            branch_office_id=str(branch_office_id),
            group_date=day.isoformat(),
            items=[self._to_public(row) for row in rows],
        )

    def get_by_id(self, user: UserPublic, group_id: int) -> WasherDailyGroupPublic:
        row = self.db.get(WasherDailyGroup, group_id)
        if row is None or not row.is_active:
            raise WasherDailyGroupNotFoundError("Grupo no encontrado")
        self._ensure_branch_access(user, row.branch_office_id)
        if row.group_date != self._today():
            raise WasherDailyGroupValidationError("Solo puede editar grupos del día actual")
        return self._to_public(row)

    def create_for_manager(
        self,
        user: UserPublic,
        *,
        data: WasherDailyGroupCreate,
    ) -> WasherDailyGroupPublic:
        branch_office_id = self._resolve_branch_for_user(user)
        day = self._today()
        name = data.name.strip()
        if not name:
            raise WasherDailyGroupValidationError("Indique el nombre del grupo")
        self._validate_washer_ids_for_branch(
            branch_office_id=branch_office_id,
            washer_ids=data.washer_ids,
            group_date=day,
        )
        now = self._now()
        row = WasherDailyGroup(
            branch_office_id=branch_office_id,
            group_date=day,
            name=name[:255],
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.flush()
        if row.id is None:
            raise WasherDailyGroupValidationError("No se pudo crear el grupo")
        for washer_id in data.washer_ids:
            self.db.add(
                WasherDailyGroupMember(
                    group_id=row.id,
                    washer_id=washer_id,
                    added_date=now,
                    deleted_date=None,
                ),
            )
        self.db.commit()
        self.db.refresh(row)
        return self._to_public(row)

    def update(
        self,
        user: UserPublic,
        group_id: int,
        data: WasherDailyGroupUpdate,
    ) -> WasherDailyGroupPublic:
        row = self.db.get(WasherDailyGroup, group_id)
        if row is None or not row.is_active:
            raise WasherDailyGroupNotFoundError("Grupo no encontrado")
        self._ensure_branch_access(user, row.branch_office_id)
        if row.group_date != self._today():
            raise WasherDailyGroupValidationError("Solo puede editar grupos del día actual")

        now = self._now()
        if data.name is not None:
            name = data.name.strip()
            if not name:
                raise WasherDailyGroupValidationError("Indique el nombre del grupo")
            row.name = name[:255]
        if data.washer_ids is not None:
            self._validate_washer_ids_for_branch(
                branch_office_id=row.branch_office_id,
                washer_ids=data.washer_ids,
                group_date=row.group_date,
                exclude_group_id=row.id,
            )
            existing = self._active_members_for_group(row.id or 0)
            for member in existing:
                member.deleted_date = now
            for washer_id in data.washer_ids:
                self.db.add(
                    WasherDailyGroupMember(
                        group_id=row.id,
                        washer_id=washer_id,
                        added_date=now,
                        deleted_date=None,
                    ),
                )
        row.updated_date = now
        self.db.commit()
        self.db.refresh(row)
        return self._to_public(row)

    def delete(self, user: UserPublic, group_id: int) -> None:
        row = self.db.get(WasherDailyGroup, group_id)
        if row is None or not row.is_active:
            raise WasherDailyGroupNotFoundError("Grupo no encontrado")
        self._ensure_branch_access(user, row.branch_office_id)
        if row.group_date != self._today():
            raise WasherDailyGroupValidationError("Solo puede eliminar grupos del día actual")
        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        for member in self._active_members_for_group(row.id or 0):
            member.deleted_date = now
        self.db.commit()

    def _active_washer_ids_for_branch(self, branch_office_id: int) -> list[int]:
        branch_washer_ids = self._branch_washers.list_washer_ids_for_branch(branch_office_id)
        if not branch_washer_ids:
            return []
        rows = self.db.scalars(
            select(User)
            .where(
                User.id.in_(branch_washer_ids),
                User.rol_id == WASHER_ROL_ID,
                User.deleted_date.is_(None),
            )
            .order_by(User.full_name.asc(), User.id.asc()),
        ).all()
        return [
            row.id
            for row in rows
            if row.id is not None and active_from_status_id(row.status_id)
        ]

    def ticket_washer_options(
        self,
        user: UserPublic,
        *,
        branch_office_id: int,
        group_date: date | None = None,
    ) -> TicketWasherOptionsResponse:
        day = group_date or self._today()
        self._ensure_branch_access(user, branch_office_id)
        groups = self.db.scalars(
            self._active_groups_query(branch_office_id=branch_office_id, group_date=day)
            .order_by(WasherDailyGroup.name.asc(), WasherDailyGroup.id.asc()),
        ).all()
        grouped_ids = self._washer_ids_in_groups(
            branch_office_id=branch_office_id,
            group_date=day,
        )
        active_washer_ids = self._active_washer_ids_for_branch(branch_office_id)
        washers = [
            TicketWasherOptionWasher(
                id=str(washer_id),
                full_name=self._washer_full_name(washer_id),
            )
            for washer_id in active_washer_ids
            if washer_id not in grouped_ids
        ]
        group_items = [
            TicketWasherOptionGroup(
                id=str(group.id),
                name=group.name.strip(),
                member_names=[
                    self._washer_full_name(member.washer_id)
                    for member in self._active_members_for_group(group.id or 0)
                ],
            )
            for group in groups
            if group.id is not None
        ]
        return TicketWasherOptionsResponse(
            branch_office_id=str(branch_office_id),
            group_date=day.isoformat(),
            washers=washers,
            groups=group_items,
        )

    def get_active_group(self, group_id: int, *, group_date: date) -> WasherDailyGroup | None:
        row = self.db.get(WasherDailyGroup, group_id)
        if row is None or not row.is_active:
            return None
        if row.group_date != group_date:
            return None
        return row

    def member_ids_for_group(self, group_id: int) -> list[int]:
        return self._member_washer_ids(group_id)

    def member_ids_for_group_on_date(self, group_id: int, *, day: date) -> list[int]:
        """
        Miembros que reciben crédito en compensación del día `day`.
        Vacío si el grupo no existe o su group_date no coincide (evita repartir
        con la lista actual de un grupo de otro día o editada después).
        """
        row = self.db.get(WasherDailyGroup, group_id)
        if row is None or row.deleted_date is not None:
            return []
        if row.group_date != day:
            return []
        return self._member_washer_ids(group_id)
