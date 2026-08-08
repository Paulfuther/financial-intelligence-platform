from decimal import Decimal
from django.shortcuts import get_object_or_404, render
from .models import Company
from research.models import FinancialRatio

def company_list(request):
    companies = Company.objects.prefetch_related("filings").order_by("ticker")

    context = {
        "companies": companies,
    }

    return render(
        request,
        "research/company_list.html",
        context,
    )


def company_dashboard(request, company_id):
    company = get_object_or_404(
        Company,
        pk=company_id,
    )

    selected_period = request.GET.get(
        "period",
        "annual",
    )

    ratio_periods = (
        ["FY"]
        if selected_period == "annual"
        else ["Q1", "Q2", "Q3", "Q4"]
    )

    financial_ratios = (
        FinancialRatio.objects.filter(
            company=company,
            fiscal_period__in=ratio_periods,
        )
        .order_by(
            "-fiscal_year",
            "-fiscal_period",
        )
    )

    latest_ratio = financial_ratios.first()
    prior_ratio = None

    if latest_ratio:
        if selected_period == "annual":
            prior_ratio = FinancialRatio.objects.filter(
                company=company,
                fiscal_period="FY",
                fiscal_year=latest_ratio.fiscal_year - 1,
            ).first()
        else:
            prior_ratio = FinancialRatio.objects.filter(
                company=company,
                fiscal_period=latest_ratio.fiscal_period,
                fiscal_year=latest_ratio.fiscal_year - 1,
            ).first()

    selected_tab = request.GET.get(
        "tab",
        "overview",
    )

    allowed_tabs = {
        "overview",
        "financials",
        "charts",
        "ratios",
        "filings",
        "ai",
    }

    if selected_tab not in allowed_tabs:
        selected_tab = "overview"

    if selected_period not in (
        "annual",
        "quarterly",
    ):
        selected_period = "annual"

    recent_filings = company.filings.order_by(
        "-filing_date",
        "-acceptance_datetime",
    )[:10]

    key_metric_names = [
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "eps_diluted",
        "cash",
        "total_assets",
        "total_liabilities",
        "long_term_debt",
        "shareholders_equity",
        "operating_cash_flow",
        "capital_expenditures",
        "free_cash_flow",
    ]

    history_metric_names = [
        "revenue",
        "operating_income",
        "net_income",
        "eps_diluted",
        "cash",
        "long_term_debt",
        "operating_cash_flow",
        "free_cash_flow",
    ]

    metric_labels = dict(
        company.financial_metrics.model.METRIC_TYPES
    )

    latest_metrics = []
    financial_history = []
    changes_since_last_year = []
    latest_period_label = None

    # These feed the Financials tab.
    statement_periods = []
    statement_metric_lookup = {}

    if selected_period == "quarterly":
        period_order = {
            "Q1": 1,
            "Q2": 2,
            "Q3": 3,
            "Q4": 4,
        }

        financial_rows = list(
            company.financial_metrics.filter(
                fiscal_period__in=[
                    "Q1",
                    "Q2",
                    "Q3",
                    "Q4",
                ],
            ).order_by(
                "-fiscal_year",
                "-end_date",
                "metric",
            )
        )

        available_periods = sorted(
            {
                (
                    row.fiscal_year,
                    row.fiscal_period,
                )
                for row in financial_rows
            },
            key=lambda item: (
                item[0],
                period_order.get(item[1], 0),
            ),
            reverse=True,
        )

        latest_periods = available_periods[:8]

        if latest_periods:
            latest_year, latest_quarter = latest_periods[0]

            latest_period_label = (
                f"{latest_quarter} {latest_year}"
            )

            latest_lookup = {
                row.metric: row
                for row in financial_rows
                if (
                    row.fiscal_year == latest_year
                    and row.fiscal_period == latest_quarter
                )
            }

            latest_metrics = [
                latest_lookup[metric_name]
                for metric_name in key_metric_names
                if metric_name in latest_lookup
            ]

        for fiscal_year, fiscal_period in latest_periods:
            period_key = (
                fiscal_year,
                fiscal_period,
            )

            row_lookup = {
                row.metric: row
                for row in financial_rows
                if (
                    row.fiscal_year == fiscal_year
                    and row.fiscal_period == fiscal_period
                )
            }

            statement_metric_lookup[period_key] = row_lookup

            period_data = {
                "key": period_key,
                "label": f"{fiscal_period} {fiscal_year}",
                "fiscal_year": fiscal_year,
                "fiscal_period": fiscal_period,
                "metrics": row_lookup,
            }

            statement_periods.append(period_data)
            financial_history.append(period_data)

    else:
        financial_rows = list(
            company.financial_metrics.filter(
                fiscal_period="FY",
            ).order_by(
                "-fiscal_year",
                "metric",
            )
        )

        available_years = sorted(
            {
                row.fiscal_year
                for row in financial_rows
            },
            reverse=True,
        )

        latest_years = available_years[:5]

        if latest_years:
            latest_year = latest_years[0]
            latest_period_label = f"FY {latest_year}"

            latest_lookup = {
                row.metric: row
                for row in financial_rows
                if row.fiscal_year == latest_year
            }

            latest_metrics = [
                latest_lookup[metric_name]
                for metric_name in key_metric_names
                if metric_name in latest_lookup
            ]

        for fiscal_year in latest_years:
            period_key = (
                fiscal_year,
                "FY",
            )

            row_lookup = {
                row.metric: row
                for row in financial_rows
                if row.fiscal_year == fiscal_year
            }

            statement_metric_lookup[period_key] = row_lookup

            period_data = {
                "key": period_key,
                "label": str(fiscal_year),
                "fiscal_year": fiscal_year,
                "fiscal_period": "FY",
                "metrics": row_lookup,
            }

            statement_periods.append(period_data)
            financial_history.append(period_data)

        if len(available_years) >= 2:
            current_year = available_years[0]
            prior_year = available_years[1]

            current_lookup = {
                row.metric: row
                for row in financial_rows
                if row.fiscal_year == current_year
            }

            prior_lookup = {
                row.metric: row
                for row in financial_rows
                if row.fiscal_year == prior_year
            }

            comparison_metrics = [
                "revenue",
                "gross_profit",
                "operating_income",
                "net_income",
                "eps_diluted",
                "cash",
                "long_term_debt",
                "operating_cash_flow",
                "free_cash_flow",
            ]

            lower_is_better = {
                "long_term_debt",
            }

            for metric_name in comparison_metrics:
                current_row = current_lookup.get(
                    metric_name
                )

                prior_row = prior_lookup.get(
                    metric_name
                )

                if not current_row or not prior_row:
                    continue

                current_value = current_row.value
                prior_value = prior_row.value

                if prior_value == 0:
                    percentage_change = None
                else:
                    percentage_change = (
                        (
                            current_value
                            - prior_value
                        )
                        / abs(prior_value)
                        * Decimal("100")
                    )

                if percentage_change is None:
                    direction = "neutral"
                    is_positive = None

                elif percentage_change > 0:
                    direction = "up"
                    is_positive = (
                        metric_name
                        not in lower_is_better
                    )

                elif percentage_change < 0:
                    direction = "down"
                    is_positive = (
                        metric_name
                        in lower_is_better
                    )

                else:
                    direction = "flat"
                    is_positive = None

                changes_since_last_year.append(
                    {
                        "metric": metric_name,
                        "label": metric_labels.get(
                            metric_name,
                            metric_name,
                        ),
                        "current": current_row,
                        "prior": prior_row,
                        "percentage_change": (
                            percentage_change
                        ),
                        "direction": direction,
                        "is_positive": is_positive,
                    }
                )

    def build_statement(statement_definition):
        statement_rows = []

        for metric_name, fallback_label in statement_definition:
            values = []

            for period in statement_periods:
                metric_row = period["metrics"].get(
                    metric_name
                )

                values.append(metric_row)

            statement_rows.append(
                {
                    "metric": metric_name,
                    "label": metric_labels.get(
                        metric_name,
                        fallback_label,
                    ),
                    "values": values,
                    "is_eps": metric_name in {
                        "eps_basic",
                        "eps_diluted",
                    },
                    "is_shares": (
                        metric_name
                        == "shares_outstanding"
                    ),
                }
            )

        return statement_rows

    income_statement_definition = [
        (
            "revenue",
            "Revenue",
        ),
        (
            "cost_of_revenue",
            "Cost of Revenue",
        ),
        (
            "gross_profit",
            "Gross Profit",
        ),
        (
            "operating_expenses",
            "Operating Expenses",
        ),
        (
            "research_and_development",
            "Research and Development",
        ),
        (
            "selling_general_admin",
            "Selling, General and Administrative",
        ),
        (
            "operating_income",
            "Operating Income",
        ),
        (
            "pretax_income",
            "Income Before Tax",
        ),
        (
            "income_tax_expense",
            "Income Tax Expense",
        ),
        (
            "net_income",
            "Net Income",
        ),
        (
            "eps_basic",
            "Basic EPS",
        ),
        (
            "eps_diluted",
            "Diluted EPS",
        ),
        (
            "shares_outstanding",
            "Shares Outstanding",
        ),
    ]

    balance_sheet_definition = [
        (
            "cash",
            "Cash and Cash Equivalents",
        ),
        (
            "accounts_receivable",
            "Accounts Receivable",
        ),
        (
            "inventory",
            "Inventory",
        ),
        (
            "current_assets",
            "Current Assets",
        ),
        (
            "total_assets",
            "Total Assets",
        ),
        (
            "accounts_payable",
            "Accounts Payable",
        ),
        (
            "current_liabilities",
            "Current Liabilities",
        ),
        (
            "short_term_debt",
            "Short-Term Debt",
        ),
        (
            "long_term_debt",
            "Long-Term Debt",
        ),
        (
            "total_liabilities",
            "Total Liabilities",
        ),
        (
            "shareholders_equity",
            "Shareholders’ Equity",
        ),
    ]

    cash_flow_definition = [
        (
            "operating_cash_flow",
            "Operating Cash Flow",
        ),
        (
            "capital_expenditures",
            "Capital Expenditures",
        ),
        (
            "free_cash_flow",
            "Free Cash Flow",
        ),
        (
            "dividends_paid",
            "Dividends Paid",
        ),
        (
            "share_repurchases",
            "Share Repurchases",
        ),
        (
            "investing_cash_flow",
            "Investing Cash Flow",
        ),
        (
            "financing_cash_flow",
            "Financing Cash Flow",
        ),
    ]

    income_statement = build_statement(
        income_statement_definition
    )

    balance_sheet = build_statement(
        balance_sheet_definition
    )

    cash_flow_statement = build_statement(
        cash_flow_definition
    )

    chart_periods = list(reversed(statement_periods)
    )

    chart_labels = [
        period["label"]
        for period in chart_periods
    ]

    def chart_values(metric_name):
        values = []

        for period in chart_periods:
            metric_row = period["metrics"].get(
                metric_name
            )

            if metric_row:
                values.append(
                    float(metric_row.value)
                )
            else:
                values.append(None)

        return values

    chart_definitions = [
        {
            "category": "Performance",
            "metrics": [
                {
                    "metric": "revenue",
                    "label": "Revenue",
                    "description": (
                        "Total revenue recognized during "
                        "the reporting period."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "gross_profit",
                    "label": "Gross Profit",
                    "description": (
                        "Revenue remaining after direct "
                        "costs of revenue."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "operating_income",
                    "label": "Operating Income",
                    "description": (
                        "Profit generated from core "
                        "business operations."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "net_income",
                    "label": "Net Income",
                    "description": (
                        "Profit remaining after all "
                        "expenses and taxes."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "eps_diluted",
                    "label": "Diluted EPS",
                    "description": (
                        "Net income attributable to each "
                        "diluted common share."
                    ),
                    "format": "per_share",
                },
            ],
        },
        {
            "category": "Cash Flow",
            "metrics": [
                {
                    "metric": "operating_cash_flow",
                    "label": "Operating Cash Flow",
                    "description": (
                        "Cash generated by normal "
                        "business operations."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "capital_expenditures",
                    "label": "Capital Expenditures",
                    "description": (
                        "Cash invested in property, "
                        "equipment and long-term assets."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "free_cash_flow",
                    "label": "Free Cash Flow",
                    "description": (
                        "Operating cash flow remaining "
                        "after capital expenditures."
                    ),
                    "format": "currency",
                },
            ],
        },
        {
            "category": "Balance Sheet",
            "metrics": [
                {
                    "metric": "cash",
                    "label": "Cash",
                    "description": (
                        "Cash and cash equivalents held "
                        "at the reporting date."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "total_assets",
                    "label": "Total Assets",
                    "description": (
                        "Total economic resources "
                        "reported by the company."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "total_liabilities",
                    "label": "Total Liabilities",
                    "description": (
                        "Total financial obligations "
                        "reported by the company."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "long_term_debt",
                    "label": "Long-Term Debt",
                    "description": (
                        "Debt obligations due beyond "
                        "the next twelve months."
                    ),
                    "format": "currency",
                },
                {
                    "metric": "shareholders_equity",
                    "label": "Shareholders’ Equity",
                    "description": (
                        "Residual value attributable "
                        "to shareholders."
                    ),
                    "format": "currency",
                },
            ],
        },
    ]

    chart_groups = []
    chart_metrics = {}
    default_chart_metric = None

    for group in chart_definitions:
        available_metrics = []

        for metric_definition in group["metrics"]:
            metric_name = metric_definition["metric"]
            values = chart_values(metric_name)

            # Do not show a selector for a metric that has
            # no values in the selected reporting periods.
            if not any(
                value is not None
                for value in values
            ):
                continue

            metric_data = {
                **metric_definition,
                "values": values,
            }

            available_metrics.append(
                metric_definition
            )

            chart_metrics[metric_name] = metric_data

            if default_chart_metric is None:
                default_chart_metric = metric_name

        if available_metrics:
            chart_groups.append(
                {
                    "category": group["category"],
                    "metrics": available_metrics,
                }
            )

    chart_data = {
        "labels": chart_labels,
        "metrics": chart_metrics,
        "default_metric": default_chart_metric,
        "period_type": selected_period,
    }

    context = {
        "company": company,
        "selected_period": selected_period,
        "selected_tab": selected_tab,
        "latest_period_label": latest_period_label,
        "recent_filings": recent_filings,
        "latest_metrics": latest_metrics,
        "financial_history": financial_history,
        "changes_since_last_year": (
            changes_since_last_year
        ),
        "statement_periods": statement_periods,
        "income_statement": income_statement,
        "balance_sheet": balance_sheet,
        "cash_flow_statement": cash_flow_statement,
        "filing_count": company.filings.count(),
        "financial_fact_count": (
            company.financial_facts.count()
        ),
        "financial_metric_count": (
            company.financial_metrics.count()
        ),
        "chart_data": chart_data,
        "chart_groups": chart_groups,
        "default_chart_metric": default_chart_metric,
        "financial_ratios": financial_ratios,

        "latest_ratio": latest_ratio,
        "prior_ratio": prior_ratio,
    }

    return render(
        request,
        "research/company_dashboard.html",
        context,
    )