# Generated manually for import deduplication and undo support.

from django.db import migrations, models


def apply_bank_transaction_unique_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        """
        ALTER TABLE bank_transactions
        DROP CONSTRAINT IF EXISTS bank_transactions_import_hash_key;

        ALTER TABLE bank_transactions
        DROP CONSTRAINT IF EXISTS bank_transactions_import_hash_uniq;

        DROP INDEX IF EXISTS bank_transactions_import_hash_key;
        DROP INDEX IF EXISTS bank_transactions_import_hash_uniq;
        DROP INDEX IF EXISTS bank_transactions_account_import_hash_uniq;

        CREATE UNIQUE INDEX bank_transactions_account_import_hash_uniq
        ON bank_transactions (account_name, import_hash);
        """
    )


def reverse_bank_transaction_unique_index(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    schema_editor.execute(
        """
        DROP INDEX IF EXISTS bank_transactions_account_import_hash_uniq;

        CREATE UNIQUE INDEX IF NOT EXISTS bank_transactions_import_hash_key
        ON bank_transactions (import_hash);
        """
    )


class Migration(migrations.Migration):

    dependencies = [
        ("banking", "0006_category"),
    ]

    operations = [
        migrations.AddField(
            model_name="importlog",
            name="transaction_hashes",
            field=models.JSONField(blank=True, default=list),
        ),
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AlterField(
                    model_name="banktransaction",
                    name="import_hash",
                    field=models.TextField(),
                ),
                migrations.AddConstraint(
                    model_name="banktransaction",
                    constraint=models.UniqueConstraint(
                        fields=("account_name", "import_hash"),
                        name="bank_transactions_account_import_hash_uniq",
                    ),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    apply_bank_transaction_unique_index,
                    reverse_bank_transaction_unique_index,
                ),
            ],
        ),
    ]