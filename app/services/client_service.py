from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.datetime_utils import datetime_to_iso, business_now
from app.models.client import Client
from app.schemas.client import ClientCreate, ClientPublic, ClientUpdate


class ClientNotFoundError(Exception):
    pass


class ClientValidationError(Exception):
    pass


class ClientService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def _now() -> datetime:
        return business_now()

    @staticmethod
    def to_public(row: Client) -> ClientPublic:
        return ClientPublic(
            id=str(row.id),
            clients=row.clients,
            added_date=datetime_to_iso(row.added_date),
            updated_date=datetime_to_iso(row.updated_date),
            deleted_date=datetime_to_iso(row.deleted_date),
        )

    def _active_filter(self, stmt):
        return stmt.where(Client.deleted_date.is_(None))

    def _find_duplicate(self, name: str, except_id: int | None = None) -> Client | None:
        normalized = name.strip().lower()
        stmt = self._active_filter(select(Client)).where(
            func.lower(Client.clients) == normalized,
        )
        if except_id is not None:
            stmt = stmt.where(Client.id != except_id)
        return self.db.scalars(stmt).first()

    def list_all(self) -> list[ClientPublic]:
        stmt = self._active_filter(select(Client)).order_by(Client.clients)
        return [self.to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, client_id: int) -> ClientPublic:
        stmt = self._active_filter(select(Client)).where(Client.id == client_id)
        row = self.db.scalars(stmt).first()
        if row is None:
            raise ClientNotFoundError()
        return self.to_public(row)

    def create(self, data: ClientCreate) -> ClientPublic:
        name = data.clients.strip()
        if not name:
            raise ClientValidationError("El cliente es obligatorio")
        if self._find_duplicate(name):
            raise ClientValidationError("Ya existe un cliente con ese nombre")

        now = self._now()
        row = Client(
            clients=name,
            added_date=now,
            updated_date=now,
            deleted_date=None,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def update(self, client_id: int, data: ClientUpdate) -> ClientPublic:
        row = self.db.get(Client, client_id)
        if row is None or not row.is_active:
            raise ClientNotFoundError()

        if data.clients is not None:
            name = data.clients.strip()
            if not name:
                raise ClientValidationError("El cliente no puede quedar vacío")
            if self._find_duplicate(name, except_id=client_id):
                raise ClientValidationError("Ya existe un cliente con ese nombre")
            row.clients = name

        row.updated_date = self._now()
        self.db.commit()
        self.db.refresh(row)
        return self.to_public(row)

    def delete(self, client_id: int) -> None:
        row = self.db.get(Client, client_id)
        if row is None or not row.is_active:
            raise ClientNotFoundError()

        now = self._now()
        row.deleted_date = now
        row.updated_date = now
        self.db.commit()
