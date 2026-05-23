from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.washer_group_member import WasherGroupMember

GROUP_NAME_SEPARATOR = " · "
MIN_GROUP_MEMBERS = 2
MAX_GROUP_MEMBERS = 20


class WasherGroupMemberValidationError(Exception):
    pass


class WasherGroupMemberService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return datetime.now()

    @staticmethod
    def normalize_names(raw_names: list[str]) -> list[str]:
        seen: set[str] = set()
        names: list[str] = []
        for raw in raw_names:
            name = (raw or "").strip()
            if not name:
                continue
            if len(name) > 255:
                raise WasherGroupMemberValidationError("Cada nombre es demasiado largo")
            key = name.casefold()
            if key in seen:
                continue
            seen.add(key)
            names.append(name)
        return names

    @staticmethod
    def format_display_name(names: list[str]) -> str:
        joined = GROUP_NAME_SEPARATOR.join(names)
        if len(joined) <= 255:
            return joined
        return joined[:252] + "..."

    def _active_filter(self, stmt):
        return stmt.where(WasherGroupMember.deleted_date.is_(None))

    def list_names_for_washer(self, washer_id: int) -> list[str]:
        if washer_id <= 0:
            return []
        rows = self.db.scalars(
            self._active_filter(select(WasherGroupMember))
            .where(WasherGroupMember.washer_id == washer_id)
            .order_by(WasherGroupMember.sort_order, WasherGroupMember.id),
        ).all()
        return [row.name for row in rows]

    def is_group_washer(self, washer_id: int) -> bool:
        return len(self.list_names_for_washer(washer_id)) >= MIN_GROUP_MEMBERS

    def replace_members(
        self,
        washer_id: int,
        raw_names: list[str],
        *,
        commit: bool = True,
    ) -> list[str]:
        if washer_id <= 0:
            raise WasherGroupMemberValidationError("Lavador no válido")

        names = self.normalize_names(raw_names)
        if len(names) < MIN_GROUP_MEMBERS:
            raise WasherGroupMemberValidationError(
                "Indique al menos 2 nombres para el lavador grupal",
            )
        if len(names) > MAX_GROUP_MEMBERS:
            raise WasherGroupMemberValidationError("Demasiados nombres en el grupo")

        now = self._now()
        active_rows = self.db.scalars(
            self._active_filter(select(WasherGroupMember)).where(
                WasherGroupMember.washer_id == washer_id,
            ),
        ).all()
        for row in active_rows:
            row.deleted_date = now
            row.updated_date = now

        for index, name in enumerate(names):
            self.db.add(
                WasherGroupMember(
                    washer_id=washer_id,
                    name=name,
                    sort_order=index,
                    added_date=now,
                    updated_date=now,
                    deleted_date=None,
                ),
            )

        if commit:
            self.db.commit()
        return names

    def soft_delete_for_washer(self, washer_id: int, *, commit: bool = True) -> None:
        if washer_id <= 0:
            return
        now = self._now()
        rows = self.db.scalars(
            self._active_filter(select(WasherGroupMember)).where(
                WasherGroupMember.washer_id == washer_id,
            ),
        ).all()
        for row in rows:
            row.deleted_date = now
            row.updated_date = now
        if commit and rows:
            self.db.commit()
