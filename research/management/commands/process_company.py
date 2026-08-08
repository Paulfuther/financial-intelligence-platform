from django.core.management.base import BaseCommand, CommandError

from research.models import Company
from research.services.company_pipeline import (
    process_company_financials,
)


class Command(BaseCommand):
    help = (
        "Normalize metrics, calculate ratios, "
        "and calculate health scores for a company."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            type=str,
            help="Ticker symbol, such as AAPL or NVDA.",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Process all companies.",
        )

    def handle(self, *args, **options):
        ticker = options.get("ticker")
        process_all = options.get("all")

        if not ticker and not process_all:
            raise CommandError(
                "Provide either --ticker SYMBOL or --all."
            )

        if ticker and process_all:
            raise CommandError(
                "Use either --ticker or --all, not both."
            )

        if ticker:
            companies = Company.objects.filter(
                ticker__iexact=ticker.strip()
            )
        else:
            companies = Company.objects.all().order_by("ticker")

        if not companies.exists():
            raise CommandError(
                "No matching companies were found."
            )

        for company in companies:
            self.stdout.write(
                f"Processing {company.ticker}..."
            )

            try:
                result = process_company_financials(company)
            except Exception as exc:
                self.stdout.write(
                    self.style.ERROR(
                        f"{company.ticker} failed: {exc}"
                    )
                )
                continue

            for step in result.steps:
                self.stdout.write(f"  ✓ {step}")

            self.stdout.write(
                self.style.SUCCESS(
                    f"{company.ticker} completed successfully."
                )
            )