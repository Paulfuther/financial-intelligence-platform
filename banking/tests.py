import io
from datetime import date
from decimal import Decimal

from django.db import connection
from django.test import SimpleTestCase, TransactionTestCase

from banking.import_services import (
    build_hash,
    find_source_mirrors_of_targets,
    persist_csv_import,
    resolve_target_transactions_for_mirror_cleanup,
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


class Migration0007SqlTests(SimpleTestCase):
    def test_apply_sql_only_targets_bank_transactions(self):
        from banking.import_hash_migration_ops import (
            POSTGRES_APPLY_SQL,
            migration_sql_targets_only_bank_transactions,
            postgres_sql_has_no_format_placeholders,
        )

        self.assertTrue(migration_sql_targets_only_bank_transactions())
        self.assertTrue(postgres_sql_has_no_format_placeholders(POSTGRES_APPLY_SQL))
        self.assertIn("t.relname = table_name", POSTGRES_APPLY_SQL)
        self.assertNotIn(
            "DROP INDEX IF EXISTS bank_transactions_import_hash_key;",
            POSTGRES_APPLY_SQL,
        )
        self.assertNotIn("bank_transactions_bad_backup", POSTGRES_APPLY_SQL)

    def test_compose_sql_mogrify_on_percent(self):
        """Guardrail: migration SQL must stay free of mogrify placeholders."""
        from django.db import connection

        from banking.import_hash_migration_ops import (
            POSTGRES_APPLY_SQL,
            postgres_sql_has_no_format_placeholders,
        )

        self.assertTrue(postgres_sql_has_no_format_placeholders(POSTGRES_APPLY_SQL))
        if connection.vendor != "postgresql":
            return
        with self.assertRaises(IndexError):
            connection.ops.compose_sql(
                "SELECT format('%I', 'bank_transactions')",
                (),
            )


class MirrorTransactionCleanupTests(TransactionTestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        enable_banking_tables()

    @classmethod
    def tearDownClass(cls):
        disable_banking_tables()
        super().tearDownClass()

    def test_removes_only_exact_mirrors(self):
        target_account = "Capital One Card"
        source_account = "Canadian Tire Mastercard"
        shared = {
            "transaction_date": date(2025, 11, 18),
            "description": "FINCH NISSAN",
            "dr": Decimal("1410.57"),
            "cr": None,
            "balance": None,
        }
        BankTransaction.objects.create(
            **shared,
            category="Vehicle",
            import_hash=build_hash(
                shared["transaction_date"],
                shared["description"],
                shared["dr"],
                shared["cr"],
                shared["balance"],
                target_account,
            ),
            account_name=target_account,
        )
        BankTransaction.objects.create(
            **shared,
            category="Vehicle",
            import_hash=build_hash(
                shared["transaction_date"],
                shared["description"],
                shared["dr"],
                shared["cr"],
                shared["balance"],
                source_account,
            ),
            account_name=source_account,
        )
        BankTransaction.objects.create(
            transaction_date=date(2025, 11, 19),
            description="CANADIAN TIRE STORE #123",
            dr=Decimal("45.00"),
            category="Shopping",
            import_hash=build_hash(
                date(2025, 11, 19),
                "CANADIAN TIRE STORE #123",
                Decimal("45.00"),
                None,
                None,
                source_account,
            ),
            account_name=source_account,
        )

        targets = resolve_target_transactions_for_mirror_cleanup(target_account)
        mirrors = find_source_mirrors_of_targets(source_account, targets)
        self.assertEqual(mirrors.count(), 1)
        self.assertEqual(mirrors.first().description, "FINCH NISSAN")

    def test_match_import_log_limits_targets(self):
        target_account = "Capital One Card"
        source_account = "Canadian Tire Mastercard"
        row = {
            "transaction_date": date(2025, 11, 19),
            "description": "PETRO-CANADA 33485",
            "dr": Decimal("30.00"),
            "cr": None,
            "balance": None,
        }
        target_hash = build_hash(
            row["transaction_date"],
            row["description"],
            row["dr"],
            row["cr"],
            row["balance"],
            target_account,
        )
        BankTransaction.objects.create(
            **row,
            category="Gas",
            import_hash=target_hash,
            account_name=target_account,
        )
        BankTransaction.objects.create(
            **row,
            category="Gas",
            import_hash=build_hash(
                row["transaction_date"],
                row["description"],
                row["dr"],
                row["cr"],
                row["balance"],
                source_account,
            ),
            account_name=source_account,
        )
        BankTransaction.objects.create(
            transaction_date=date(2025, 10, 1),
            description="OLD CAPITAL ONE",
            dr=Decimal("5.00"),
            category="Misc",
            import_hash=build_hash(
                date(2025, 10, 1),
                "OLD CAPITAL ONE",
                Decimal("5.00"),
                None,
                None,
                target_account,
            ),
            account_name=target_account,
        )

        import_log = ImportLog.objects.create(
            file_name="statement.csv",
            account_name=target_account,
            imported_count=1,
            latest_transaction_date=row["transaction_date"],
            transaction_hashes=[target_hash],
        )

        targets = resolve_target_transactions_for_mirror_cleanup(
            target_account,
            match_import_log_id=import_log.id,
        )
        self.assertEqual(list(targets.values_list("pk", flat=True)), [BankTransaction.objects.get(import_hash=target_hash).pk])
        mirrors = find_source_mirrors_of_targets(source_account, targets)
        self.assertEqual(mirrors.count(), 1)

    def test_persist_csv_import_writes_import_log_with_hashes(self):
        rows = [
            {
                "transaction_date": "2025-11-19",
                "description": "TEST MERCHANT",
                "dr": "12.50",
                "cr": "",
                "balance": "",
                "category": "Shopping",
                "import_hash": build_hash(
                    date(2025, 11, 19),
                    "TEST MERCHANT",
                    Decimal("12.50"),
                    None,
                    None,
                    "Capital One Card",
                ),
                "account_name": "Capital One Card",
            }
        ]
        import_log, counts = persist_csv_import(rows, "Capital One Card", "t.csv")
        self.assertEqual(counts["imported"], 1)
        self.assertEqual(len(import_log.transaction_hashes), 1)
        self.assertEqual(import_log.account_name, "Capital One Card")
