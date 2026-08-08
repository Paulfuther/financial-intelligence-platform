from django.core.management.base import BaseCommand, CommandError

from research.models import Company
from research.services.metric_normalizer import (
    normalize_company_metrics,
)


class Command(BaseCommand):
    help = "Normalize raw SEC financial facts into financial metrics."

    def add_arguments(self, parser):
        parser.add_argument(
            "--ticker",
            type=str,
            help="Normalize one company by ticker.",
        )

    def handle(self, *args, **options):
        ticker = options.get("ticker")

        companies = Company.objects.all()

        if ticker:
            companies = companies.filter(
                ticker__iexact=ticker.strip(),
            )

            if not companies.exists():
                raise CommandError(
                    f"No company found with ticker {ticker}."
                )

        if not companies.exists():
            self.stdout.write(
                self.style.WARNING(
                    "No companies are available to normalize."
                )
            )
            return

        for company in companies:
            self.stdout.write(
                f"Normalizing {company.ticker}..."
            )

            result = normalize_company_metrics(company)

            self.stdout.write(
                self.style.SUCCESS(
                    (
                        f"{company.ticker}: "
                        f"{result['created']} created, "
                        f"{result['updated']} updated, "
                        f"{len(result['missing'])} missing."
                    )
                )
            )