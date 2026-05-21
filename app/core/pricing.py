from decimal import Decimal, ROUND_HALF_UP

TICKET_IVA_RATE = Decimal("0.19")


def round_pesos(value: Decimal | int | float | str) -> int:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ticket_totals_from_subtotal(
    subtotal: Decimal | int | float,
    *,
    apply_iva: bool = True,
) -> dict[str, int]:
    subtotal_int = round_pesos(subtotal)
    tax = round_pesos(subtotal_int * TICKET_IVA_RATE) if apply_iva else 0
    total = subtotal_int + tax
    return {"subtotal": subtotal_int, "iva": tax, "tax": tax, "total": total}
