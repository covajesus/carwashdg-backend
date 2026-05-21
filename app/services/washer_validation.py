from sqlalchemy.orm import Session

from app.core.roles import WASHER_ROL_ID
from app.core.user_status import active_from_status_id
from app.models.user import User


class WasherValidationError(Exception):
    pass


def resolve_washer_id(db: Session, washer_id: int | None) -> int | None:
    """washer_id debe ser users.id con rol Lavador (rol_id = 3)."""
    if washer_id is None:
        return None
    row = db.get(User, washer_id)
    if row is None or row.deleted_date is not None:
        raise WasherValidationError("El lavador no existe")
    if row.rol_id != WASHER_ROL_ID:
        raise WasherValidationError("El usuario seleccionado no es un lavador")
    if not active_from_status_id(row.status_id):
        raise WasherValidationError("El lavador no está activo")
    return washer_id
