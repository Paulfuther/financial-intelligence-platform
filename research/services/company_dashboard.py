from decimal import Decimal

from django.db.models import Count

from research.models import FinancialMetric


class CompanyDashboardService:
    KEY_METRICS = (
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
    )

    HISTORY_METRICS = (
        "revenue",
        "operating_income",
        "net_income",
        "eps_diluted",
        "cash",
        "long_term_debt",
        "operating_cash_flow",
        "free_cash_flow",
    )

    COMPARISON_METRICS = (
        "revenue",
        "gross_profit",
        "operating_income",
        "net_income",
        "eps_diluted",
        "cash",
        "long_term_debt",
        "operating_cash_flow",
        "free_cash_flow",
    )

    LOWER_IS_BETTER = {
        "long_term_debt",
    }

    QUARTER_ORDER = {
        "Q1": 1,
        "Q2": 2,
        "Q3": 3,
        "Q4": 4,
    }

    def __init__(self, company, selected_period="annual"):
        self.company = company

        if selected_period not in {
            "annual",
            "quarterly",
        }:
            selected_period = "annual"

        self.selected_period = selected_period

        self.metric_labels = dict(
            FinancialMetric.METRIC_TYPES
        )

    def build(self):
        if self.selected_period == "quarterly":
            financial_data = self._build_quarterly_data()
        else:
            financial_data = self._build_annual_data()

        return {
            "company": self.company,
            "selected_period": self.selected_period,
            "latest_period_label": financial_data[
                "latest_period_label"
            ],
            "latest_metrics": financial_data[
                "latest_metrics"
            ],
            "financial_history": financial_data[
                "financial_history"
            ],
            "changes_since_last_year": financial_data[
                "changes_since_last_year"
            ],
            "recent_filings": self._recent_filings(),
            "filing_count": self.company.filings.count(),
            "financial_fact_count": (
                self.company.financial_facts.count()
            ),
            "financial_metric_count": (
                self.company.financial_metrics.count()
            ),
            "metric_period_counts": (
                self._metric_period_counts()
            ),
        }

    def _recent_filings(self):
        return (
            self.company.filings
            .order_by(
                "-filing_date",
                "-acceptance_datetime",
            )[:10]
        )

    def _metric_period_counts(self):
        return list(
            self.company.financial_metrics
            .values("fiscal_period")
            .annotate(total=Count("id"))
            .order_by("fiscal_period")
        )

    def _build_annual_data(self):
        annual_rows = list(
            self.company.financial_metrics
            .filter(fiscal_period="FY")
            .order_by(
                "-fiscal_year",
                "-end_date",
                "metric",
            )
        )

        available_years = sorted(
            {
                row.fiscal_year
                for row in annual_rows
            },
            reverse=True,
        )

        latest_years = available_years[:5]

        latest_metrics = []
        latest_period_label = None

        if latest_years:
            latest_year = latest_years[0]

            latest_period_label = (
                f"FY {latest_year}"
            )

            latest_lookup = self._metric_lookup(
                rows=annual_rows,
                fiscal_year=latest_year,
                fiscal_period="FY",
            )

            latest_metrics = self._ordered_metrics(
                latest_lookup
            )

        financial_history = []

        for fiscal_year in latest_years:
            metrics = self._metric_lookup(
                rows=annual_rows,
                fiscal_year=fiscal_year,
                fiscal_period="FY",
            )

            financial_history.append(
                {
                    "label": str(fiscal_year),
                    "fiscal_year": fiscal_year,
                    "fiscal_period": "FY",
                    "end_date": self._latest_end_date(
                        metrics
                    ),
                    "metrics": metrics,
                }
            )

        changes = self._annual_changes(
            annual_rows=annual_rows,
            available_years=available_years,
        )

        return {
            "latest_period_label": (
                latest_period_label
            ),
            "latest_metrics": latest_metrics,
            "financial_history": financial_history,
            "changes_since_last_year": changes,
        }

    def _build_quarterly_data(self):
        quarterly_rows = list(
            self.company.financial_metrics
            .filter(
                fiscal_period__in=(
                    "Q1",
                    "Q2",
                    "Q3",
                    "Q4",
                )
            )
            .order_by(
                "-fiscal_year",
                "-end_date",
                "metric",
            )
        )

        /*
         * One reporting period must be represented by
         * only fiscal year and fiscal period.
         *
         * Do not include end_date in this identity.
         * Some facts within one quarter can carry
         * slightly different dates.
         */