"""Load anonymized sample transactions for local UI demos (optional)."""

from datetime import date
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import connection

from banking.models import BankTransaction, Category, CategoryRule


class Command(BaseCommand):
    help = "Insert sample categories, rules, and transactions for UI demos."

    def handle(self, *args, **options):
        for model in (BankTransaction, CategoryRule):
            model._meta.managed = True
            with connection.schema_editor(atomic=False) as editor:
                try:
                    editor.create_model(model)
                except Exception:
                    pass

        for name in ("Alcohol", "AI tools", "Groceries"):
            Category.objects.get_or_create(name=name, defaults={"is_active": True})

        CategoryRule.objects.get_or_create(keyword="LCBO", category="Alcohol")
        CategoryRule.objects.get_or_create(keyword="BEER STORE", category="Alcohol")
        CategoryRule.objects.get_or_create(keyword="OPENAI", category="AI tools")
        CategoryRule.objects.get_or_create(keyword="ANTHROPIC", category="AI tools")
        CategoryRule.objects.get_or_create(keyword="CURSOR", category="AI tools")

        samples = [
            (date(2025, 3, 10), "LCBO #441 TORONTO", Decimal("62.40"), "Alcohol"),
            (date(2025, 4, 5), "THE BEER STORE 1234", Decimal("28.75"), "Alcohol"),
            (date(2025, 5, 12), "OPENAI CHATGPT SUB", Decimal("33.60"), "AI tools"),
            (date(2025, 6, 1), "ANTHROPIC API", Decimal("45.00"), "AI tools"),
            (date(2025, 6, 18), "CURSOR USAGE MID JUN", Decimal("20.00"), "AI tools"),
            (date(2025, 7, 8), "METRO GROCERY", Decimal("89.12"), "Groceries"),
        ]

        created = 0
        for tx_date, description, amount, category in samples:
            import_hash = "demo-{description}-{tx_date}".format(
                description=description[:12],
                tx_date=tx_date.isoformat(),
            )
            if BankTransaction.objects.filter(import_hash=import_hash, account_name="Personal").exists():
                continue
            BankTransaction.objects.create(
                transaction_date=tx_date,
                description=description,
                dr=amount,
                category=category,
                import_hash=import_hash,
                account_name="Personal",
            )
            created += 1

        self.stdout.write(self.style.SUCCESS("Demo data ready ({created} new rows).".format(created=created)))