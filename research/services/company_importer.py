from datetime import datetime, timezone as datetime_timezone

from django.utils import timezone

from research.models import Filing, FinancialFact

from .sec_client import SECClient

client = SECClient()


def parse_date(value):
    if not value:
        return None

    return datetime.strptime(value, "%Y-%m-%d").date()


def parse_datetime(value):
    if not value:
        return None

    parsed = datetime.strptime(
        value,
        "%Y-%m-%dT%H:%M:%S.%fZ",
    )

    return timezone.make_aware(
        parsed,
        timezone=datetime_timezone.utc,
    )


def sync_company(company):
    data = client.get_company_submissions(company.cik)

    company.name = data.get("name", company.name)

    exchanges = data.get("exchanges", [])
    company.exchange = exchanges[0] if exchanges else ""

    company.sic = data.get("sic", "")
    company.sic_description = data.get("sicDescription", "")
    company.fiscal_year_end = data.get("fiscalYearEnd", "")
    company.state_of_incorporation = data.get(
        "stateOfIncorporation",
        "",
    )

    company.last_sec_sync = timezone.now()
    company.save()

    imported_filings = sync_recent_filings(
        company=company,
        submissions_data=data,
    )

    facts_data = client.get_company_facts(company.cik)

    financial_fact_results = sync_financial_facts(
        company=company,
        company_facts_data=facts_data,
    )

    return {
        "company": company,
        "filings_imported": imported_filings,
        "financial_facts_created": financial_fact_results["created"],
        "financial_facts_updated": financial_fact_results["updated"],
        "financial_facts_skipped": financial_fact_results["skipped"],
    }


def sync_recent_filings(company, submissions_data):
    recent = (
        submissions_data
        .get("filings", {})
        .get("recent", {})
    )

    accession_numbers = recent.get("accessionNumber", [])

    imported_count = 0

    for index, accession_number in enumerate(accession_numbers):
        form = get_list_value(recent, "form", index)
        filing_date = get_list_value(
            recent,
            "filingDate",
            index,
        )

        if not accession_number or not form or not filing_date:
            continue

        primary_document = get_list_value(
            recent,
            "primaryDocument",
            index,
        )

        filing_url = build_filing_url(
            company.cik,
            accession_number,
            primary_document,
        )

        Filing.objects.update_or_create(
            accession_number=accession_number,
            defaults={
                "company": company,
                "form": form,
                "filing_date": parse_date(filing_date),
                "report_date": parse_date(
                    get_list_value(
                        recent,
                        "reportDate",
                        index,
                    )
                ),
                "acceptance_datetime": parse_datetime(
                    get_list_value(
                        recent,
                        "acceptanceDateTime",
                        index,
                    )
                ),
                "primary_document": primary_document,
                "primary_document_description": get_list_value(
                    recent,
                    "primaryDocDescription",
                    index,
                ),
                "filing_url": filing_url,
                "is_xbrl": bool(
                    get_list_value(
                        recent,
                        "isXBRL",
                        index,
                    )
                ),
                "is_inline_xbrl": bool(
                    get_list_value(
                        recent,
                        "isInlineXBRL",
                        index,
                    )
                ),
                "file_number": get_list_value(
                    recent,
                    "fileNumber",
                    index,
                ),
                "film_number": get_list_value(
                    recent,
                    "filmNumber",
                    index,
                ),
                "items": get_list_value(
                    recent,
                    "items",
                    index,
                ),
                "size": get_list_value(
                    recent,
                    "size",
                    index,
                ) or None,
            },
        )

        imported_count += 1

    return imported_count

def sync_financial_facts(company, company_facts_data):
    facts = company_facts_data.get("facts", {})

    created_count = 0
    updated_count = 0
    skipped_count = 0

    for taxonomy, taxonomy_facts in facts.items():
        for concept, concept_data in taxonomy_facts.items():
            label = concept_data.get("label", "")
            description = concept_data.get("description", "")
            units = concept_data.get("units", {})

            statement_type = determine_statement_type(
                concept=concept,
                label=label,
            )

            for unit, fact_rows in units.items():
                for fact_row in fact_rows:
                    accession_number = fact_row.get("accn", "")
                    end_date = parse_date(fact_row.get("end"))

                    if not accession_number or not end_date:
                        skipped_count += 1
                        continue

                    value = fact_row.get("val")

                    if value is None:
                        skipped_count += 1
                        continue

                    filing = Filing.objects.filter(
                        accession_number=accession_number,
                    ).first()

                    _, created = FinancialFact.objects.update_or_create(
                        company=company,
                        taxonomy=taxonomy,
                        concept=concept,
                        unit=unit,
                        accession_number=accession_number,
                        start_date=parse_date(
                            fact_row.get("start")
                        ),
                        end_date=end_date,
                        defaults={
                            "filing": filing,
                            "label": label,
                            "description": description,
                            "statement_type": statement_type,
                            "value": value,
                            "filed_date": parse_date(
                                fact_row.get("filed")
                            ),
                            "fiscal_year": parse_fiscal_year(
                                fact_row.get("fy")
                            ),
                            "fiscal_period": (
                                fact_row.get("fp") or ""
                            ),
                            "form": fact_row.get("form") or "",
                            "frame": fact_row.get("frame") or "",
                        },
                    )

                    if created:
                        created_count += 1
                    else:
                        updated_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "skipped": skipped_count,
    }

def get_list_value(data, key, index, default=""):
    values = data.get(key, [])

    if index >= len(values):
        return default

    return values[index]


def build_filing_url(cik, accession_number, primary_document):
    if not primary_document:
        return ""

    cik_number = str(int(cik))
    accession_without_dashes = accession_number.replace("-", "")

    return (
        "https://www.sec.gov/Archives/edgar/data/"
        f"{cik_number}/"
        f"{accession_without_dashes}/"
        f"{primary_document}"
    )

def parse_fiscal_year(value):
    if value in (None, ""):
        return None

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def determine_statement_type(concept, label):
    text = f"{concept} {label}".lower()

    cash_flow_terms = (
        "cashflow",
        "cash flow",
        "netcash",
        "payments",
        "proceeds",
    )

    balance_terms = (
        "assets",
        "liabilities",
        "equity",
        "cashandcash",
        "debt",
        "inventory",
        "receivable",
        "payable",
    )

    income_terms = (
        "revenue",
        "sales",
        "income",
        "earnings",
        "expense",
        "profit",
        "loss",
        "costof",
    )

    equity_terms = (
        "stockholder",
        "shareholder",
        "commonstock",
        "retainedearnings",
        "dividend",
    )

    if any(term in text for term in cash_flow_terms):
        return "cash_flow"

    if any(term in text for term in equity_terms):
        return "equity"

    if any(term in text for term in balance_terms):
        return "balance"

    if any(term in text for term in income_terms):
        return "income"

    return "other"