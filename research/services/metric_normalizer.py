from django.db import transaction

from research.models import FinancialFact, FinancialMetric

METRIC_CONCEPTS = {
    "revenue": [
        "RevenueFromContractWithCustomerExcludingAssessedTax",
        "SalesRevenueNet",
        "Revenues",
    ],
    "cost_of_revenue": [
        "CostOfRevenue",
        "CostOfGoodsAndServicesSold",
    ],
    "gross_profit": [
        "GrossProfit",
    ],
    "operating_income": [
        "OperatingIncomeLoss",
    ],
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
    ],
    "eps_basic": [
        "EarningsPerShareBasic",
    ],
    "eps_diluted": [
        "EarningsPerShareDiluted",
    ],
    "cash": [
        "CashAndCashEquivalentsAtCarryingValue",
        "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents",
    ],
    "current_assets": [
        "AssetsCurrent",
    ],
    "total_assets": [
        "Assets",
    ],
    "current_liabilities": [
        "LiabilitiesCurrent",
    ],
    "total_liabilities": [
        "Liabilities",
    ],
    "long_term_debt": [
        "LongTermDebtNoncurrent",
        "LongTermDebt",
        "LongTermDebtAndFinanceLeaseObligationsNoncurrent",
    ],
    "shareholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "operating_cash_flow": [
        "NetCashProvidedByUsedInOperatingActivities",
    ],
    "capital_expenditures": [
        "PaymentsToAcquirePropertyPlantAndEquipment",
        "PaymentsForAdditionsToPropertyPlantAndEquipment",
    ],
    "dividends_paid": [
        "PaymentsOfDividends",
        "PaymentsOfDividendsCommonStock",
    ],
    "share_repurchases": [
        "PaymentsForRepurchaseOfCommonStock",
    ],
    "shares_outstanding": [
        "EntityCommonStockSharesOutstanding",
        "CommonStockSharesOutstanding",
    ],
}


EXPECTED_UNITS = {
    "revenue": ("USD",),
    "cost_of_revenue": ("USD",),
    "gross_profit": ("USD",),
    "operating_income": ("USD",),
    "net_income": ("USD",),
    "eps_basic": (
        "USD/shares",
        "USD / shares",
    ),
    "eps_diluted": (
        "USD/shares",
        "USD / shares",
    ),
    "cash": ("USD",),
    "current_assets": ("USD",),
    "total_assets": ("USD",),
    "current_liabilities": ("USD",),
    "total_liabilities": ("USD",),
    "long_term_debt": ("USD",),
    "shareholders_equity": ("USD",),
    "operating_cash_flow": ("USD",),
    "capital_expenditures": ("USD",),
    "dividends_paid": ("USD",),
    "share_repurchases": ("USD",),
    "shares_outstanding": ("shares",),
}


DURATION_METRICS = {
    "revenue",
    "cost_of_revenue",
    "gross_profit",
    "operating_income",
    "net_income",
    "eps_basic",
    "eps_diluted",
    "operating_cash_flow",
    "capital_expenditures",
    "dividends_paid",
    "share_repurchases",
}


INSTANT_METRICS = {
    "cash",
    "current_assets",
    "total_assets",
    "current_liabilities",
    "total_liabilities",
    "long_term_debt",
    "shareholders_equity",
    "shares_outstanding",
}


def normalize_unit(unit):
    cleaned_unit = (unit or "").strip()

    aliases = {
        "USD / shares": "USD/shares",
        "USD/share": "USD/shares",
        "share": "shares",
    }

    return aliases.get(cleaned_unit, cleaned_unit)


def is_full_year_fact(fact):
    if fact.fiscal_period == "FY":
        return True

    if not fact.start_date or not fact.end_date:
        return False

    duration_days = (fact.end_date - fact.start_date).days

    return 330 <= duration_days <= 385


def find_best_fact(
    company,
    metric_name,
    fiscal_year,
    fiscal_period,
):
    concepts = METRIC_CONCEPTS.get(metric_name, [])

    if not concepts:
        return None

    allowed_forms = ("10-K", "10-K/A") if fiscal_period == "FY" else ("10-Q", "10-Q/A")

    expected_units = {
        normalize_unit(unit) for unit in EXPECTED_UNITS.get(metric_name, ())
    }

    all_candidates = list(
        FinancialFact.objects.filter(
            company=company,
            concept__in=concepts,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
            form__in=allowed_forms,
        )
        .exclude(value__isnull=True)
        .order_by(
            "-filed_date",
            "-end_date",
            "-id",
        )
    )

    if not all_candidates:
        return None

    candidates = []

    for fact in all_candidates:
        normalized_fact_unit = normalize_unit(fact.unit)

        if expected_units and normalized_fact_unit not in expected_units:
            continue

        candidates.append(fact)

    if not candidates:
        return None

    # Annual SEC filings contain comparative values from earlier years.
    # Only use the fact whose reporting end date matches the fiscal year
    # currently being normalized.
    if fiscal_period == "FY":
        matching_year_candidates = [
            fact
            for fact in candidates
            if fact.end_date and fact.end_date.year == fiscal_year
        ]

        if not matching_year_candidates:
            return None

        candidates = matching_year_candidates

    def concept_rank(fact):
        try:
            return concepts.index(fact.concept)
        except ValueError:
            return len(concepts)

    def form_rank(fact):
        # Prefer the original filing when all other qualities are equal.
        return 1 if fact.form.endswith("/A") else 0

    def filed_rank(fact):
        if not fact.filed_date:
            return 0

        return -fact.filed_date.toordinal()

    def end_date_rank(fact):
        if not fact.end_date:
            return 0

        return -fact.end_date.toordinal()

    if metric_name in INSTANT_METRICS:
        instant_candidates = [
            fact
            for fact in candidates
            if fact.start_date is None and fact.end_date is not None
        ]

        if not instant_candidates:
            instant_candidates = candidates

        return min(
            instant_candidates,
            key=lambda fact: (
                concept_rank(fact),
                form_rank(fact),
                filed_rank(fact),
                end_date_rank(fact),
                -fact.id,
            ),
        )

    duration_candidates = [
        fact
        for fact in candidates
        if fact.start_date is not None and fact.end_date is not None
    ]

    if not duration_candidates:
        return None

    if fiscal_period == "FY":
        target_days = 365
        minimum_days = 300
        maximum_days = 400
    else:
        target_days = 91
        minimum_days = 70
        maximum_days = 120

    appropriate_candidates = []

    for fact in duration_candidates:
        duration_days = (fact.end_date - fact.start_date).days

        if minimum_days <= duration_days <= maximum_days:
            appropriate_candidates.append(fact)

    if not appropriate_candidates:
        return None

    return min(
        appropriate_candidates,
        key=lambda fact: (
            concept_rank(fact),
            abs((fact.end_date - fact.start_date).days - target_days),
            form_rank(fact),
            filed_rank(fact),
            end_date_rank(fact),
            -fact.id,
        ),
    )


def save_metric(
    company,
    metric_name,
    fiscal_year,
    fiscal_period,
    fact,
):
    metric, created = FinancialMetric.objects.update_or_create(
        company=company,
        metric=metric_name,
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        defaults={
            "start_date": fact.start_date,
            "end_date": fact.end_date,
            "value": fact.value,
            "unit": normalize_unit(fact.unit),
            "source_fact": fact,
            "source_concept": fact.concept,
            "accession_number": (fact.accession_number or ""),
        },
    )

    return metric, created


def create_free_cash_flow(
    company,
    fiscal_year,
    fiscal_period,
):
    operating_cash_flow = FinancialMetric.objects.filter(
        company=company,
        metric="operating_cash_flow",
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    ).first()

    capital_expenditures = FinancialMetric.objects.filter(
        company=company,
        metric="capital_expenditures",
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
    ).first()

    if not operating_cash_flow or not capital_expenditures:
        return None, False

    capex_value = abs(capital_expenditures.value)

    free_cash_flow_value = operating_cash_flow.value - capex_value

    end_date = max(
        operating_cash_flow.end_date,
        capital_expenditures.end_date,
    )

    start_dates = [
        value
        for value in (
            operating_cash_flow.start_date,
            capital_expenditures.start_date,
        )
        if value is not None
    ]

    start_date = min(start_dates) if start_dates else None

    metric, created = FinancialMetric.objects.update_or_create(
        company=company,
        metric="free_cash_flow",
        fiscal_year=fiscal_year,
        fiscal_period=fiscal_period,
        defaults={
            "start_date": start_date,
            "end_date": end_date,
            "value": free_cash_flow_value,
            "unit": operating_cash_flow.unit or "USD",
            "source_fact": None,
            "source_concept": (
                "Calculated: operating_cash_flow - abs(capital_expenditures)"
            ),
            "accession_number": (
                operating_cash_flow.accession_number
                or capital_expenditures.accession_number
                or ""
            ),
        },
    )

    return metric, created


@transaction.atomic
def normalize_company_metrics(company):
    reporting_periods = (
        FinancialFact.objects.filter(
            company=company,
            fiscal_year__isnull=False,
            fiscal_period__in=(
                "FY",
                "Q1",
                "Q2",
                "Q3",
            ),
            form__in=(
                "10-K",
                "10-K/A",
                "10-Q",
                "10-Q/A",
            ),
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
    missing_metrics = []

    for fiscal_year, fiscal_period in reporting_periods:
        for metric_name in METRIC_CONCEPTS:
            fact = find_best_fact(
                company=company,
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
            )

            if not fact:
                FinancialMetric.objects.filter(
                    company=company,
                    metric=metric_name,
                    fiscal_year=fiscal_year,
                    fiscal_period=fiscal_period,
                ).delete()

                missing_metrics.append(
                    {
                        "fiscal_year": fiscal_year,
                        "fiscal_period": fiscal_period,
                        "metric": metric_name,
                    }
                )
                continue

            _, created = save_metric(
                company=company,
                metric_name=metric_name,
                fiscal_year=fiscal_year,
                fiscal_period=fiscal_period,
                fact=fact,
            )

            if created:
                created_count += 1
            else:
                updated_count += 1

        free_cash_flow, created = create_free_cash_flow(
            company=company,
            fiscal_year=fiscal_year,
            fiscal_period=fiscal_period,
        )

        if free_cash_flow:
            if created:
                created_count += 1
            else:
                updated_count += 1

    return {
        "company": company.ticker,
        "created": created_count,
        "updated": updated_count,
        "missing": missing_metrics,
    }
