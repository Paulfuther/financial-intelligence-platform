# Generated manually for import deduplication and undo support.

from django.db import migrations, models

from banking.import_hash_migration_ops import (
    apply_bank_transaction_unique_index,
    reverse_bank_transaction_unique_index,
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