from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.rol import Rol
from app.schemas.rol import RolPublic


class RolNotFoundError(Exception):
    pass


class RolService:
    def __init__(self, db: Session) -> None:
        self.db = db

    @staticmethod
    def to_public(row: Rol) -> RolPublic:
        return RolPublic(
            id=str(row.id),
            rol=row.rol,
            added_date=row.added_date,
            updated_date=row.updated_date,
        )

    def list_all(self) -> list[RolPublic]:
        stmt = select(Rol).order_by(Rol.id)
        return [self.to_public(row) for row in self.db.scalars(stmt).all()]

    def get_by_id(self, rol_id: int) -> RolPublic:
        row = self.db.get(Rol, rol_id)
        if row is None:
            raise RolNotFoundError()
        return self.to_public(row)
