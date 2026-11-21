import io
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import TransactionTestCase

from banking.import_services import (
    build_hash,
    transaction_is_duplicate,
    transactions_for_import_log,
)
from banking.models import BankTransaction, CategoryRule, ImportLog


def enable_banking_tables():
    for model in (BankTransaction, CategoryRule):
        model._meta.managed = True
        with connection.schema_editor(atomic=False) as editor:
            editor.create_model(model)


def disable_banking_tables():
    for model in (BankTransaction, CategoryRule):
        with connection.schema_editor(atomic=False) as editor:
            editor.delete_model(model)
        model._meta.managed = False


def parse_import_rows(csv_file, account_name):
    from banking.views import parse_import_rows as view_parse

    return view_parse(csv_file, account_name)


class ImportDeduplicationTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        enable_banking_tables()

    @classmethod
    def tearDownClass(cls):
        disable_banking_tables()
        super().tearDownClass()

    def test_build_hash_scopes_to_account(self):
        args = (
            date(2025, 3, 1),
            "COFFEE SHOP",
            Decimal("4.50"),
            None,
            None,
        )
        wrong_hash = build_hash(*args, "Capital One Card")
        right_hash = build_hash(*args, "Canadian Tire Mastercard")
        self.assertNotEqual(wrong_hash, right_hash)

    def test_same_account_duplicate_still_detected(self):
        import_hash = build_hash(
            date(2025, 3, 1),
            "GROCERY",
            Decimal("25.00"),
            None,
            None,
            "Capital One Card",
        )
        BankTransaction.objects.create(
            transaction_date=date(2025, 3, 1),
            description="GROCERY",
            dr=Decimal("25.00"),
            category="Groceries",
            import_hash=import_hash,
            account_name="Capital One Card",
        )
        self.assertTrue(
            transaction_is_duplicate(
                "Capital One Card",
                date(2025, 3, 1),
                "GROCERY",
                Decimal("25.00"),
                None,
                None,
                import_hash,
            )
        )

    def test_wrong_card_undo_then_correct_card_import(self):
        csv_body = (
            "2025-03-01,COFFEE SHOP,4.50,,\n"
            "2025-03-02,GROCERY STORE,32.10,,\n"
        )
        wrong_account = "Capital One Card"
        right_account = "Canadian Tire Mastercard"

        for pass_account in (wrong_account, right_account):
            csv_file = io.BytesIO(csv_body.encode("utf-8"))
            csv_file.name = "statement.csv"
            valid_rows, duplicate_rows, error_rows = parse_import_rows(csv_file, pass_account)
            self.assertEqual(error_rows, [])
            if pass_account == wrong_account:
                self.assertEqual(len(duplicate_rows), 0)
                self.assertEqual(len(valid_rows), 2)
            else:
                self.assertEqual(len(duplicate_rows), 0)
                self.assertEqual(len(valid_rows), 2)

        wrong_hashes = []
        for row in parse_import_rows(
            io.BytesIO(csv_body.encode("utf-8")),
            wrong_account,
        )[0]:
            BankTransaction.objects.create(
                transaction_date=date.fromisoformat(row["transaction_date"]),
                description=row["description"],
                dr=Decimal(row["dr"]) if row["dr"] else None,
                cr=Decimal(row["cr"]) if row["cr"] else None,
                balance=None,
                category=row["category"],
                import_hash=row["import_hash"],
                account_name=wrong_account,
            )
            wrong_hashes.append(row["import_hash"])

        import_log = ImportLog.objects.create(
            file_name="statement.csv",
            account_name=wrong_account,
            imported_count=2,
            latest_transaction_date=date(2025, 3, 2),
            transaction_hashes=wrong_hashes,
        )

        matched = list(transactions_for_import_log(import_log))
        self.assertEqual(len(matched), 2)
        BankTransaction.objects.filter(pk__in=[tx.pk for tx in matched]).delete()
        import_log.imported_count = 0
        import_log.transaction_hashes = []
        import_log.save()

        valid_rows, duplicate_rows, _ = parse_import_rows(
            io.BytesIO(csv_body.encode("utf-8")),
            right_account,
        )
        self.assertEqual(duplicate_rows, [])
        self.assertEqual(len(valid_rows), 2)

        for row in valid_rows:
            self.assertFalse(
                transaction_is_duplicate(
                    right_account,
                    date.fromisoformat(row["transaction_date"]),
                    row["description"],
                    Decimal(row["dr"]) if row["dr"] else None,
                    Decimal(row["cr"]) if row["cr"] else None,
                    None,
                    row["import_hash"],
                )
            )
            BankTransaction.objects.create(
                transaction_date=date.fromisoformat(row["transaction_date"]),
                description=row["description"],
                dr=Decimal(row["dr"]) if row["dr"] else None,
                category=row["category"],
                import_hash=row["import_hash"],
                account_name=right_account,
            )

        wrong_card_count = BankTransaction.objects.filter(account_name=wrong_account).count()
        right_card_count = BankTransaction.objects.filter(account_name=right_account).count()
        self.assertEqual(wrong_card_count, 0)
        self.assertEqual(right_card_count, 2)

    def test_global_import_hash_collision_avoided_across_accounts(self):
        legacy_hash = build_hash(
            date(2025, 3, 1),
            "LEGACY ROW",
            Decimal("10.00"),
            None,
            None,
            "Capital One Card",
        )
        BankTransaction.objects.create(
            transaction_date=date(2025, 3, 1),
            description="LEGACY ROW",
            dr=Decimal("10.00"),
            category="Shopping",
            import_hash=legacy_hash,
            account_name="Capital One Card",
        )

        other_account_hash = build_hash(
            date(2025, 3, 1),
            "LEGACY ROW",
            Decimal("10.00"),
            None,
            None,
            "Canadian Tire Mastercard",
        )
        self.assertNotEqual(legacy_hash, other_account_hash)

        BankTransaction.objects.create(
            transaction_date=date(2025, 3, 1),
            description="LEGACY ROW",
            dr=Decimal("10.00"),
            category="Shopping",
            import_hash=other_account_hash,
            account_name="Canadian Tire Mastercard",
        )

        self.assertEqual(BankTransaction.objects.count(), 2)