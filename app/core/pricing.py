from decimal import Decimal, ROUND_HALF_UP

TICKET_IVA_GROSS_FACTOR = Decimal("1.19")
COIN_ROUND_UNIT = 1000


def round_money(value: Decimal | int | float | str) -> int:
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    return int(value.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def round_coins_to_nearest_thousand(amount: int) -> int:
    """Redondea al mil de pesos más cercano (44300→44000, 44500→45000)."""
    if amount <= 0:
        return 0
    thousands = Decimal(amount) / Decimal(COIN_ROUND_UNIT)
    rounded = int(thousands.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return rounded * COIN_ROUND_UNIT


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
    cash: Decimal | int | float,
    card_gross: Decimal | int | float,
) -> dict[str, int]:
    """Mixed payment: cash without VAT; only card gross includes VAT."""
    cash_int = round_money(cash)
    card_int = round_money(card_gross)
    if card_int <= 0:
        total_mixed = cash_int + card_int
        return {"subtotal": total_mixed, "iva": 0, "tax": 0, "total": total_mixed}

    card_net = round_money(Decimal(card_int) / TICKET_IVA_GROSS_FACTOR)
    tax = card_int - card_net
    subtotal = cash_int + card_net
    total_out = cash_int + card_int
    return {"subtotal": subtotal, "iva": tax, "tax": tax, "total": total_out}
