from django.db import migrations


def sync_categories_forward(apps, schema_editor):
    table_names = schema_editor.connection.introspection.table_names()
    if "bank_transactions" not in table_names:
        return

    Category = apps.get_model("banking", "Category")
    BankTransaction = apps.get_model("banking", "BankTransaction")

    names = (
        BankTransaction.objects.exclude(category__isnull=True)
        .exclude(category="")
        .exclude(category="Uncategorized")
        .values_list("category", flat=True)
        .distinct()
    )

    for name in names:
        Category.objects.get_or_create(name=name, defaults={"is_active": True})


def sync_categories_backward(apps, schema_editor):
    # No-op: do not delete user-managed categories on rollback.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("banking", "0008_banktransaction_category_locked"),
    ]

    operations = [
        migrations.RunPython(sync_categories_forward, sync_categories_backward),
    ]