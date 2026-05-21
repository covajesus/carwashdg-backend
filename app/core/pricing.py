TICKET_VAT_PERCENT = 19


def round_amount(value: int | float) -> int:
    return round(value)


def ticket_totals_from_subtotal(subtotal: int) -> dict[str, int]:
    subtotal_int = round_amount(subtotal)
    vat = round(subtotal_int * TICKET_VAT_PERCENT / 100)
    total = subtotal_int + vat
    return {"subtotal": subtotal_int, "iva": vat, "total": total}
