# Generated manually for category manual-override support.

from django.db import migrations, models


def add_category_locked_column(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE bank_transactions "
            "ADD COLUMN IF NOT EXISTS category_locked boolean "
            "NOT NULL DEFAULT false"
        )


def drop_category_locked_column(apps, schema_editor):
    if schema_editor.connection.vendor != "postgresql":
        return

    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "ALTER TABLE bank_transactions "
            "DROP COLUMN IF EXISTS category_locked"
        )


class Migration(migrations.Migration):

    dependencies = [
        ("banking", "0007_import_hash_per_account_and_undo_tracking"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name="banktransaction",
                    name="category_locked",
                    field=models.BooleanField(default=False),
                ),
            ],
            database_operations=[
                migrations.RunPython(
                    add_category_locked_column,
                    drop_category_locked_column,
                ),
            ],
        ),
    ]