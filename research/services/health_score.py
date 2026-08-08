from decimal import Decimal

from django.db import transaction

from research.models import FinancialRatio


ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


def decimal_value(value):
    if value is None:
        return None

    return Decimal(value)


def score_by_thresholds(value, thresholds):
    """
    thresholds must be ordered from highest qualifying value downward.

    Example:
        [
            (Decimal("0.60"), Decimal("10")),
            (Decimal("0.50"), Decimal("9")),
            ...
        ]
    """
    value = decimal_value(value)

    if value is None:
        return ZERO

    for minimum_value, score in thresholds:
        if value >= minimum_value:
            return Decimal(score)

    return ZERO


def score_gross_margin(value):
    return score_by_thresholds(
        value,
        [
            (Decimal("0.60"), Decimal("10")),
            (Decimal("0.50"), Decimal("9")),
            (Decimal("0.40"), Decimal("8")),
            (Decimal("0.30"), Decimal("6")),
            (Decimal("0.20"), Decimal("4")),
            (Decimal("0.10"), Decimal("2")),
        ],
    )


def score_operating_margin(value):
    return score_by_thresholds(
        value,
        [
            (Decimal("0.30"), Decimal("10")),
            (Decimal("0.20"), Decimal("8")),
            (Decimal("0.10"), Decimal("6")),
            (Decimal("0.05"), Decimal("4")),
            (Decimal("0.00"), Decimal("2")),
        ],
    )


def score_net_margin(value):
    return score_by_thresholds(
        value,
        [
            (Decimal("0.25"), Decimal("10")),
            (Decimal("0.20"), Decimal("9")),
            (Decimal("0.15"), Decimal("8")),
            (Decimal("0.10"), Decimal("6")),
            (Decimal("0.05"), Decimal("4")),
            (Decimal("0.00"), Decimal("2")),
        ],
    )


def score_free_cash_flow_margin(value):
    return score_by_thresholds(
        value,
        [
            (Decimal("0.20"), Decimal("10")),
            (Decimal("0.15"), Decimal("8")),
            (Decimal("0.10"), Decimal("6")),
            (Decimal("0.05"), Decimal("4")),
            (Decimal("0.00"), Decimal("2")),
        ],
    )


def score_return_on_assets(value):
    return score_by_thresholds(
        value,
        [
            (Decimal("0.10"), Decimal("10")),
            (Decimal("0.08"), Decimal("8")),
            (Decimal("0.05"), Decimal("6")),
            (Decimal("0.02"), Decimal("4")),
            (Decimal("0.00"), Decimal("2")),
        ],
    )


def score_return_on_equity(value):
    return score_by_thresholds(
        value,
        [
            (Decimal("0.20"), Decimal("10")),
            (Decimal("0.15"), Decimal("9")),
            (Decimal("0.10"), Decimal("7")),
            (Decimal("0.05"), Decimal("5")),
            (Decimal("0.00"), Decimal("2")),
        ],
    )


def score_current_ratio(value):
    value = decimal_value(value)

    if value is None:
        return ZERO

    if Decimal("1.50") <= value <= Decimal("3.00"):
        return Decimal("10")

    if Decimal("1.20") <= value < Decimal("1.50"):
        return Decimal("8")

    if Decimal("1.00") <= value < Decimal("1.20"):
        return Decimal("6")

    if value < Decimal("1.00"):
        return Decimal("2")

    # Extremely high liquidity can indicate idle capital.
    return Decimal("7")


def score_debt_to_equity(value):
    value = decimal_value(value)

    if value is None:
        return ZERO

    if value < Decimal("0"):
        return Decimal("2")

    if value < Decimal("0.20"):
        return Decimal("10")

    if value < Decimal("0.40"):
        return Decimal("9")

    if value < Decimal("0.60"):
        return Decimal("7")

    if value <= Decimal("1.00"):
        return Decimal("5")

    return Decimal("2")


def score_asset_turnover(value):
    value = decimal_value(value)

    if value is None:
        return ZERO

    if value >= Decimal("1.00"):
        return Decimal("5")

    if value >= Decimal("0.75"):
        return Decimal("4")

    if value >= Decimal("0.50"):
        return Decimal("3")

    if value >= Decimal("0.25"):
        return Decimal("2")

    return Decimal("1")


def trend_points(current, previous, reverse=False):
    current = decimal_value(current)
    previous = decimal_value(previous)

    if current is None or previous is None:
        return ZERO

    difference = current - previous

    if reverse:
        difference = -difference

    if difference >= Decimal("0.05"):
        return Decimal("0.75")

    if difference >= Decimal("0.01"):
        return Decimal("0.35")

    if difference <= Decimal("-0.05"):
        return Decimal("-0.75")

    if difference <= Decimal("-0.01"):
        return Decimal("-0.35")

    return ZERO


def health_rating(score):
    if score >= Decimal("90"):
        return "Excellent"

    if score >= Decimal("80"):
        return "Very Good"

    if score >= Decimal("70"):
        return "Good"

    if score >= Decimal("60"):
        return "Fair"

    if score >= Decimal("40"):
        return "Weak"

    return "Poor"


@transaction.atomic
def calculate_health_score(ratio):
    prior_ratio = FinancialRatio.objects.filter(
        company=ratio.company,
        fiscal_period=ratio.fiscal_period,
        fiscal_year=ratio.fiscal_year - 1,
    ).first()

    gross_margin_score = score_gross_margin(
        ratio.gross_margin
    )

    operating_margin_score = score_operating_margin(
        ratio.operating_margin
    )

    net_margin_score = score_net_margin(
        ratio.net_margin
    )

    free_cash_flow_score = score_free_cash_flow_margin(
        ratio.free_cash_flow_margin
    )

    roa_score = score_return_on_assets(
        ratio.return_on_assets
    )

    roe_score = score_return_on_equity(
        ratio.return_on_equity
    )

    current_ratio_score = score_current_ratio(
        ratio.current_ratio
    )

    debt_score = score_debt_to_equity(
        ratio.debt_to_equity
    )

    turnover_score = score_asset_turnover(
        ratio.asset_turnover
    )

    profitability_raw = (
    gross_margin_score
    + operating_margin_score
    + net_margin_score
)

    # Raw maximum 30, scaled to 25.
    profitability_score = (
        profitability_raw
        / Decimal("30")
        * Decimal("25")
    )

    # Raw maximum 10, scaled to 20.
    cash_flow_score = (
        free_cash_flow_score
        / Decimal("10")
        * Decimal("20")
    )

    # Raw maximum 10, remains 10.
    liquidity_score = current_ratio_score

    # Raw maximum 10, scaled to 15.
    leverage_score = (
        debt_score
        / Decimal("10")
        * Decimal("15")
    )

    efficiency_raw = (
        roa_score
        + roe_score
        + turnover_score
    )

    # Raw maximum 25, remains 25.
    efficiency_score = efficiency_raw

    base_score = (
        profitability_score
        + cash_flow_score
        + liquidity_score
        + leverage_score
        + efficiency_score
    )

    trend_adjustment = ZERO

    if prior_ratio:
        trend_adjustment += trend_points(
            ratio.gross_margin,
            prior_ratio.gross_margin,
        )

        trend_adjustment += trend_points(
            ratio.operating_margin,
            prior_ratio.operating_margin,
        )

        trend_adjustment += trend_points(
            ratio.net_margin,
            prior_ratio.net_margin,
        )

        trend_adjustment += trend_points(
            ratio.free_cash_flow_margin,
            prior_ratio.free_cash_flow_margin,
        )

        trend_adjustment += trend_points(
            ratio.return_on_assets,
            prior_ratio.return_on_assets,
        )

        trend_adjustment += trend_points(
            ratio.return_on_equity,
            prior_ratio.return_on_equity,
        )

        trend_adjustment += trend_points(
            ratio.debt_to_equity,
            prior_ratio.debt_to_equity,
            reverse=True,
        )

    # Prevent trend from overwhelming the base score
    trend_adjustment = max(
            Decimal("-5"),
            min(
                Decimal("5"),
                trend_adjustment,
            ),
        )    

    final_score = max(
        ZERO,
        min(
            ONE_HUNDRED,
            base_score + trend_adjustment,
        ),
    )

    ratio.profitability_score = profitability_score
    ratio.cash_flow_score = cash_flow_score
    ratio.liquidity_score = liquidity_score
    ratio.leverage_score = leverage_score
    ratio.efficiency_score = efficiency_score
    ratio.trend_adjustment = trend_adjustment
    ratio.health_score = final_score
    ratio.health_rating = health_rating(final_score)

    ratio.save(
        update_fields=[
            "profitability_score",
            "cash_flow_score",
            "liquidity_score",
            "leverage_score",
            "efficiency_score",
            "trend_adjustment",
            "health_score",
            "health_rating",
            "calculated_at",
        ]
    )

    return ratio


@transaction.atomic
def calculate_company_health_scores(company):
    ratios = FinancialRatio.objects.filter(
        company=company,
    ).order_by(
        "fiscal_year",
        "fiscal_period",
    )

    processed = 0

    for ratio in ratios:
        calculate_health_score(ratio)
        processed += 1

    return {
        "company": company.ticker,
        "processed": processed,
    }