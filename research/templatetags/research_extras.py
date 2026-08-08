from decimal import Decimal, InvalidOperation

from django import template


register = template.Library()

@register.filter
def percentage_points(value, decimal_places=1):
    if value is None:
        return "—"

    try:
        places = int(decimal_places)
        number = float(value) * 100

        return f"{number:+.{places}f} pts"
    except (TypeError, ValueError):
        return "—"

@register.filter
def ratio_change(current, previous):
    if current is None or previous is None:
        return None

    try:
        return Decimal(current) - Decimal(previous)
    except (InvalidOperation, TypeError, ValueError):
        return None


@register.filter
def relative_change(current, previous):
    if current is None or previous in (None, 0):
        return None

    try:
        current = Decimal(current)
        previous = Decimal(previous)

        return ((current - previous) / abs(previous)) * Decimal("100")
    except (InvalidOperation, ZeroDivisionError, TypeError, ValueError):
        return None


@register.filter
def compact_number(value, decimals=1):
    """
    Convert large values into readable forms:

    416161000000 -> 416.2B
    35934000000  -> 35.9B
    982000000    -> 982.0M
    7.46         -> 7.46
    """
    if value is None:
        return "—"

    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return value

    absolute_number = abs(number)

    units = (
        (Decimal("1000000000000"), "T"),
        (Decimal("1000000000"), "B"),
        (Decimal("1000000"), "M"),
        (Decimal("1000"), "K"),
    )

    try:
        decimal_places = int(decimals)
    except (TypeError, ValueError):
        decimal_places = 1

    for divisor, suffix in units:
        if absolute_number >= divisor:
            shortened = number / divisor

            return (
                f"{shortened:,.{decimal_places}f}"
                f"{suffix}"
            )

    if number == number.to_integral_value():
        return f"{number:,.0f}"

    return f"{number:,.2f}"


@register.filter
def compact_currency(value, decimals=1):
    if value is None:
        return "—"

    return f"${compact_number(value, decimals)}"

@register.filter
def percentage(value, decimal_places=1):
    if value is None:
        return "—"

    try:
        return f"{float(value) * 100:.{int(decimal_places)}f}%"
    except (TypeError, ValueError):
        return "—"