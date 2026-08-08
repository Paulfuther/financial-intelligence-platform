from decimal import Decimal, InvalidOperation

from django.db import transaction

from research.models import FinancialMetric, FinancialRatio


def safe_divide(numerator, denominator):
    if numerator is None or denominator in (None, 0):
        return None

    try:
        return Decimal(numerator) / Decimal(denominator)
    except (InvalidOperation, ZeroDivisionError, TypeError):
        return None


def get_metric_value(metrics, metric_name):
    metric = metrics.get(metric_name)

    if not metric:
        return None

    return metric.value


@transaction.atomic
def calculate_company_ratios(company):
    reporting_periods = (
        FinancialMetric.objects.filter(
            company=company,
        )
        .values_list(
            "fiscal_year",
            "fiscal_period",
        )
        .distinct()
        .order_by(
            "fiscal_year",
            "fiscal_period",
        )
    )

    created_count = 0
    updated_count = 0

    for fiscal_year, fiscal_period in reporting_periods:
        period_metrics = {
            metric.metric: metric
            for metric in FinancialMetric.objects.filter(
                company=company,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
            )
        }

        revenue = get_metric_value(
            period_metrics,
            "revenue",
        )

        gross_profit = get_metric_value(
            period_metrics,
            "gross_profit",
        )

        operating_income = get_metric_value(
            period_metrics,
            "operating_income",
        )

        net_income = get_metric_value(
            period_metrics,
            "net_income",
        )

        free_cash_flow = get_metric_value(
            period_metrics,
            "free_cash_flow",
        )

        current_assets = get_metric_value(
            period_metrics,
            "current_assets",
        )

        current_liabilities = get_metric_value(
            period_metrics,
            "current_liabilities",
        )

        long_term_debt = get_metric_value(
            period_metrics,
            "long_term_debt",
        )

        total_assets = get_metric_value(
            period_metrics,
            "total_assets",
        )

        shareholders_equity = get_metric_value(
            period_metrics,
            "shareholders_equity",
        )

        defaults = {
            "gross_margin": safe_divide(
                gross_profit,
                revenue,
            ),
            "operating_margin": safe_divide(
                operating_income,
                revenue,
            ),
            "net_margin": safe_divide(
                net_income,
                revenue,
            ),
            "free_cash_flow_margin": safe_divide(
                free_cash_flow,
                revenue,
            ),
            "current_ratio": safe_divide(
                current_assets,
                current_liabilities,
            ),
            "debt_to_equity": safe_divide(
                long_term_debt,
                shareholders_equity,
            ),
            "debt_to_assets": safe_divide(
                long_term_debt,
                total_assets,
            ),
            "return_on_assets": safe_divide(
                net_income,
                total_assets,
            ),
            "return_on_equity": safe_divide(
                net_income,
                shareholders_equity,
            ),
            "asset_turnover": safe_divide(
                revenue,
                total_assets,
            ),
        }

        _, created = FinancialRatio.objects.update_or_create(
            company=company,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            defaults=defaults,
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    return {
        "company": company.ticker,
        "created": created_count,
        "updated": updated_count,
    }