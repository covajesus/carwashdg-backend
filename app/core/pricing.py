from decimal import Decimal, ROUND_HALF_UP

TICKET_IVA_GROSS_FACTOR = Decimal("1.19")


def round_money(value: Decimal | int | float | str) -> int:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def ticket_totals_from_subtotal(
    gross_amount: Decimal | int | float,
    *,
    apply_iva: bool = True,
) -> dict[str, int]:
    """Suma de montos de línea en pesos brutos (con IVA incluido si aplica)."""
    gross_int = round_money(gross_amount)
    if not apply_iva:
        return {"subtotal": gross_int, "iva": 0, "tax": 0, "total": gross_int}

    net = round_money(Decimal(gross_int) / TICKET_IVA_GROSS_FACTOR)
    tax = gross_int - net
    return {"subtotal": net, "iva": tax, "tax": tax, "total": gross_int}


def split_mixed_payment_totals(
    efectivo: Decimal | int | float,
    transbank_gross: Decimal | int | float,
) -> dict[str, int]:
    """Efectivo sin IVA en el desglose; solo Transbank como bruto con IVA incluido."""
    efectivo_int = round_money(efectivo)
    tb = round_money(transbank_gross)
    if tb <= 0:
        total_mixed = efectivo_int + tb
        return {"subtotal": total_mixed, "iva": 0, "tax": 0, "total": total_mixed}

    net_tb = round_money(Decimal(tb) / TICKET_IVA_GROSS_FACTOR)
    tax = tb - net_tb
    subtotal = efectivo_int + net_tb
    total_out = efectivo_int + tb
    return {"subtotal": subtotal, "iva": tax, "tax": tax, "total": total_out}
