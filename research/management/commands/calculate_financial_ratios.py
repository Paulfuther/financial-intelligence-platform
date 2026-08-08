from django.core.management.base import BaseCommand, CommandError

from research.models import Company
from research.services.ratio_calculator import calculate_company_ratios
from research.services.health_score import calculate_company_health_scores


class Command(BaseCommand):
    help = "Calculate financial ratios and health scores for a company."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            type=str,
            help="Calculate ratios for one ticker, such as AAPL.",
        )

        parser.add_argument(
            "--all",
            action="store_true",
            help="Calculate ratios for every company.",
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
            raise CommandError("No matching companies were found.")

        for company in companies:
            self.stdout.write(
                f"Calculating ratios for {company.ticker}..."
            )

            ratio_result = calculate_company_ratios(company)
            health_result = calculate_company_health_scores(company)

            self.stdout.write(
                self.style.SUCCESS(
                    f"{company.ticker}: "
                    f"ratios={ratio_result}, "
                    f"health={health_result}"
                )
            )