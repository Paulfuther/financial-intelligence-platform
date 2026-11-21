import os
import unittest

import django
from django.db import connection
from django.db.backends.postgresql.schema import DatabaseSchemaEditor

from banking.import_hash_migration_ops import (
    POSTGRES_APPLY_SQL,
    apply_bank_transaction_unique_index,
)


def postgres_integration_enabled():
    return os.environ.get("RUN_POSTGRES_MIGRATION_TESTS", "").lower() in (
        "1",
        "true",
        "yes",
    )


def setup_django():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "banksite.postgres_test_settings")
    os.environ.setdefault("SECRET_KEY", "test")
    os.environ.setdefault("SEC_USER_AGENT", "test-agent")
    django.setup()


@unittest.skipUnless(
    postgres_integration_enabled(),
    "Set RUN_POSTGRES_MIGRATION_TESTS=1 to run PostgreSQL migration integration tests.",
)
class Migration0007PostgresIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        setup_django()
        connection.ensure_connection()
        if connection.vendor != "postgresql":
            raise unittest.SkipTest("PostgreSQL only")

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DROP TABLE IF EXISTS bank_transactions_bad_backup CASCADE;
                DROP TABLE IF EXISTS bank_transactions CASCADE;
                """
            )
            cursor.execute(
                """
                CREATE TABLE bank_transactions (
                    id BIGSERIAL PRIMARY KEY,
                    transaction_date DATE NOT NULL,
                    description TEXT NOT NULL,
                    dr NUMERIC(12, 2),
                    cr NUMERIC(12, 2),
                    balance NUMERIC(12, 2),
                    category TEXT NOT NULL DEFAULT 'Uncategorized',
                    import_hash TEXT NOT NULL,
                    account_name VARCHAR(100) NOT NULL DEFAULT 'Personal'
                );
                ALTER TABLE bank_transactions
                ADD CONSTRAINT bank_transactions_import_hash_key UNIQUE (import_hash);
                """
            )
            cursor.execute(
                """
                CREATE TABLE bank_transactions_bad_backup (
                    LIKE bank_transactions INCLUDING ALL
                );
                """
            )
            cursor.execute(
                """
                INSERT INTO bank_transactions (transaction_date, description, import_hash)
                VALUES ('2025-01-01', 'main row', 'abc123');
                INSERT INTO bank_transactions_bad_backup (transaction_date, description, import_hash)
                VALUES ('2025-01-01', 'backup row', 'def456');
                """
            )

    def tearDown(self):
        with connection.cursor() as cursor:
            cursor.execute(
                """
                DROP TABLE IF EXISTS bank_transactions_bad_backup CASCADE;
                DROP TABLE IF EXISTS bank_transactions CASCADE;
                """
            )

    def test_schema_editor_execute_breaks_on_percent_in_sql(self):
        broken_sql = (
            "DO $x$ BEGIN EXECUTE format('SELECT %I', 'bank_transactions'); END $x$;"
        )
        editor = DatabaseSchemaEditor(connection)
        with self.assertRaises(IndexError):
            editor.execute(broken_sql)

    def test_apply_sql_with_backup_table_present(self):
        editor = DatabaseSchemaEditor(connection)
        apply_bank_transaction_unique_index(None, editor)

        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname FROM pg_indexes
                WHERE tablename = 'bank_transactions'
                  AND indexname = 'bank_transactions_account_import_hash_uniq'
                """
            )
            self.assertIsNotNone(cursor.fetchone())

            cursor.execute("SELECT COUNT(*) FROM bank_transactions_bad_backup")
            self.assertEqual(cursor.fetchone()[0], 1)

        self.assertNotIn("%I", POSTGRES_APPLY_SQL)


if __name__ == "__main__":
    unittest.main()