from decimal import Decimal, ROUND_HALF_UP

TICKET_IVA_GROSS_FACTOR = Decimal("1.19")


def round_pesos(value: Decimal | int | float | str) -> int:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ticket_totals_from_subtotal(
    gross_amount: Decimal | int | float,
    *,
    apply_iva: bool = True,
) -> dict[str, int]:
    """Suma de montos de línea en pesos brutos (con IVA incluido si aplica)."""
    gross_int = round_pesos(gross_amount)
    if not apply_iva:
        return {"subtotal": gross_int, "iva": 0, "tax": 0, "total": gross_int}

    net = round_pesos(Decimal(gross_int) / TICKET_IVA_GROSS_FACTOR)
    tax = gross_int - net
    return {"subtotal": net, "iva": tax, "tax": tax, "total": gross_int}
