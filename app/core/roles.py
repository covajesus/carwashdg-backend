from typing import Literal

UserRole = Literal["admin", "manager", "washer"]

ROLE_FROM_ID: dict[int, UserRole] = {
    1: "admin",
    2: "manager",
    3: "washer",
}

ID_FROM_ROLE: dict[UserRole, int] = {
    "admin": 1,
    "manager": 2,
    "washer": 3,
}

WASHER_ROL_ID: int = ID_FROM_ROLE["washer"]
MANAGER_ROL_ID: int = ID_FROM_ROLE["manager"]


def role_from_id(rol_id: int | None) -> UserRole:
    if rol_id is None:
        return "washer"
    return ROLE_FROM_ID.get(rol_id, "washer")


def role_id_from_role(role: str) -> int | None:
    if role not in ID_FROM_ROLE:
        return None
    return ID_FROM_ROLE[role]  # type: ignore[index]
