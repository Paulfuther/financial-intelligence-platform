from django.db import models

# Create your models hefrom django.db import models


class Company(models.Model):
    ticker = models.CharField(
        max_length=20,
        db_index=True,
    )

    cik = models.CharField(
        max_length=10,
        unique=True,
    )

    name = models.CharField(
        max_length=255,
    )

    sic = models.CharField(
        max_length=10,
        blank=True,
    )

    sic_description = models.CharField(
        max_length=255,
        blank=True,
    )

    exchange = models.CharField(
        max_length=50,
        blank=True,
    )

    fiscal_year_end = models.CharField(
        max_length=4,
        blank=True,
    )

    state_of_incorporation = models.CharField(
        max_length=20,
        blank=True,
    )


    last_sec_sync = models.DateTimeField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["ticker"]
        verbose_name = "Research company"
        verbose_name_plural = "Research companies"

    def save(self, *args, **kwargs):
        self.ticker = self.ticker.strip().upper()
        self.cik = self.cik.strip().zfill(10)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.ticker} — {self.name}"

class Filing(models.Model):

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="filings",
    )

    accession_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )

    form = models.CharField(
        max_length=20,
        db_index=True,
    )

    filing_date = models.DateField(
        db_index=True,
    )

    report_date = models.DateField(
        null=True,
        blank=True,
    )

    acceptance_datetime = models.DateTimeField(
        null=True,
        blank=True,
    )

    primary_document = models.CharField(
        max_length=255,
        blank=True,
    )

    primary_document_description = models.CharField(
        max_length=255,
        blank=True,
    )

    filing_url = models.URLField(
        max_length=500,
        blank=True,
    )

    is_xbrl = models.BooleanField(
        default=False,
    )

    is_inline_xbrl = models.BooleanField(
        default=False,
    )

    file_number = models.CharField(
        max_length=50,
        blank=True,
    )

    film_number = models.CharField(
        max_length=50,
        blank=True,
    )

    items = models.CharField(
        max_length=255,
        blank=True,
    )

    size = models.PositiveBigIntegerField(
        null=True,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = [
            "-filing_date",
            "-acceptance_datetime",
        ]

        indexes = [
            models.Index(
                fields=["company", "form", "filing_date"],
            ),
        ]

    def __str__(self):
        return (
            f"{self.company.ticker} "
            f"{self.form} "
            f"{self.filing_date}"
        )
    
class FinancialFact(models.Model):
    STATEMENT_TYPES = (
        ("income", "Income Statement"),
        ("balance", "Balance Sheet"),
        ("cash_flow", "Cash Flow Statement"),
        ("equity", "Statement of Equity"),
        ("other", "Other"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_facts",
    )

    filing = models.ForeignKey(
        Filing,
        on_delete=models.SET_NULL,
        related_name="financial_facts",
        null=True,
        blank=True,
    )

    taxonomy = models.CharField(
        max_length=50,
        default="us-gaap",
    )

    concept = models.CharField(
        max_length=150,
        db_index=True,
    )

    label = models.CharField(
        max_length=255,
        blank=True,
    )

    description = models.TextField(
        blank=True,
    )

    statement_type = models.CharField(
        max_length=20,
        choices=STATEMENT_TYPES,
        default="other",
        db_index=True,
    )

    unit = models.CharField(
        max_length=30,
    )

    value = models.DecimalField(
        max_digits=30,
        decimal_places=4,
    )

    start_date = models.DateField(
        null=True,
        blank=True,
    )

    end_date = models.DateField(
        db_index=True,
    )

    filed_date = models.DateField(
        null=True,
        blank=True,
    )

    fiscal_year = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
    )

    fiscal_period = models.CharField(
        max_length=10,
        blank=True,
    )

    form = models.CharField(
        max_length=20,
        blank=True,
        db_index=True,
    )

    accession_number = models.CharField(
        max_length=30,
        blank=True,
        db_index=True,
    )

    frame = models.CharField(
        max_length=30,
        blank=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "-end_date",
            "statement_type",
            "concept",
        )

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "company",
                    "taxonomy",
                    "concept",
                    "unit",
                    "accession_number",
                    "start_date",
                    "end_date",
                ),
                name="unique_company_financial_fact",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "statement_type",
                    "fiscal_year",
                ),
            ),
            models.Index(
                fields=(
                    "company",
                    "concept",
                    "end_date",
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.company.ticker} — "
            f"{self.label or self.concept} — "
            f"{self.end_date}"
        )

class FinancialMetric(models.Model):
    PERIOD_TYPES = (
        ("FY", "Full Year"),
        ("Q1", "First Quarter"),
        ("Q2", "Second Quarter"),
        ("Q3", "Third Quarter"),
        ("Q4", "Fourth Quarter"),
        ("TTM", "Trailing Twelve Months"),
    )

    METRIC_TYPES = (
        ("revenue", "Revenue"),
        ("cost_of_revenue", "Cost of Revenue"),
        ("gross_profit", "Gross Profit"),
        ("operating_income", "Operating Income"),
        ("net_income", "Net Income"),
        ("eps_basic", "Basic EPS"),
        ("eps_diluted", "Diluted EPS"),
        ("cash", "Cash and Equivalents"),
        ("current_assets", "Current Assets"),
        ("total_assets", "Total Assets"),
        ("current_liabilities", "Current Liabilities"),
        ("total_liabilities", "Total Liabilities"),
        ("long_term_debt", "Long-Term Debt"),
        ("shareholders_equity", "Shareholders’ Equity"),
        ("operating_cash_flow", "Operating Cash Flow"),
        ("capital_expenditures", "Capital Expenditures"),
        ("free_cash_flow", "Free Cash Flow"),
        ("dividends_paid", "Dividends Paid"),
        ("share_repurchases", "Share Repurchases"),
        ("shares_outstanding", "Shares Outstanding"),
    )

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_metrics",
    )

    metric = models.CharField(
        max_length=50,
        choices=METRIC_TYPES,
        db_index=True,
    )

    fiscal_year = models.PositiveIntegerField(
        db_index=True,
    )

    fiscal_period = models.CharField(
        max_length=10,
        choices=PERIOD_TYPES,
        default="FY",
        db_index=True,
    )

    start_date = models.DateField(
        null=True,
        blank=True,
    )

    end_date = models.DateField(
        db_index=True,
    )

    value = models.DecimalField(
        max_digits=30,
        decimal_places=4,
    )

    unit = models.CharField(
        max_length=30,
        default="USD",
    )

    source_fact = models.ForeignKey(
        FinancialFact,
        on_delete=models.SET_NULL,
        related_name="normalized_metrics",
        null=True,
        blank=True,
    )

    source_concept = models.CharField(
        max_length=150,
        blank=True,
    )

    accession_number = models.CharField(
        max_length=30,
        blank=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = (
            "company",
            "-fiscal_year",
            "fiscal_period",
            "metric",
        )

        constraints = [
            models.UniqueConstraint(
                fields=(
                    "company",
                    "metric",
                    "fiscal_year",
                    "fiscal_period",
                ),
                name="unique_company_financial_metric",
            ),
        ]

        indexes = [
            models.Index(
                fields=(
                    "company",
                    "metric",
                    "fiscal_year",
                ),
            ),
            models.Index(
                fields=(
                    "company",
                    "fiscal_year",
                    "fiscal_period",
                ),
            ),
        ]

    def __str__(self):
        return (
            f"{self.company.ticker} — "
            f"{self.get_metric_display()} — "
            f"{self.fiscal_year} {self.fiscal_period}"
        )
    
class FinancialRatio(models.Model):
    PERIOD_TYPES = [
        ("FY", "Fiscal Year"),
        ("Q1", "Quarter 1"),
        ("Q2", "Quarter 2"),
        ("Q3", "Quarter 3"),
        ("Q4", "Quarter 4"),
        ("TTM", "Trailing Twelve Months"),
    ]

    company = models.ForeignKey(
        Company,
        on_delete=models.CASCADE,
        related_name="financial_ratios",
    )

    fiscal_year = models.PositiveIntegerField(
        db_index=True,
    )

    fiscal_period = models.CharField(
        max_length=3,
        choices=PERIOD_TYPES,
        default="FY",
        db_index=True,
    )

    # Profitability
    gross_margin = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    operating_margin = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    net_margin = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    free_cash_flow_margin = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Liquidity
    current_ratio = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Leverage
    debt_to_equity = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    debt_to_assets = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Returns
    return_on_assets = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    return_on_equity = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    # Efficiency
    asset_turnover = models.DecimalField(
        max_digits=12,
        decimal_places=6,
        null=True,
        blank=True,
    )

    calculated_at = models.DateTimeField(
        auto_now=True,
    )

    # Overall score
    health_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    health_rating = models.CharField(
        max_length=20,
        blank=True,
    )

    # Component scores
    profitability_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    cash_flow_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    liquidity_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    leverage_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    efficiency_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )

    trend_adjustment = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    class Meta:
        ordering = [
            "-fiscal_year",
            "-fiscal_period",
        ]

        constraints = [
            models.UniqueConstraint(
                fields=[
                    "company",
                    "fiscal_year",
                    "fiscal_period",
                ],
                name="unique_company_financial_ratio_period",
            )
        ]

        indexes = [
            models.Index(
                fields=[
                    "company",
                    "fiscal_year",
                    "fiscal_period",
                ],
                name="ratio_company_period_idx",
            )
        ]

    def __str__(self):
        return (
            f"{self.company.ticker} "
            f"{self.fiscal_year} "
            f"{self.fiscal_period}"
        )