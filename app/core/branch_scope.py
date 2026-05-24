from app.schemas.user import UserPublic


def branch_scope_for_user(user: UserPublic) -> int | None:
    """
    None: administrador, sin filtro de sucursal.
    int >= 1: gerente, solo esa sucursal.
    0: gerente sin sucursal u otro rol → sin acceso por sucursal.
    """
    if user.role == "admin":
        return None
    if user.role == "manager":
        bid = user.branchOfficeId
        return bid if bid is not None and bid >= 1 else 0
    return 0
