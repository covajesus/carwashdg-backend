from decimal import Decimal, ROUND_HALF_UP

TICKET_IVA_RATE = Decimal("0.19")


def round_pesos(value: Decimal | int | float | str) -> int:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ticket_totals_from_subtotal(subtotal: Decimal | int | float) -> dict[str, int]:
    subtotal_int = round_pesos(subtotal)
    iva = round_pesos(subtotal_int * TICKET_IVA_RATE)
    total = subtotal_int + iva
    return {"subtotal": subtotal_int, "iva": iva, "total": total}
