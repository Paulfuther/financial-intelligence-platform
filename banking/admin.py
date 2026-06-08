from django.contrib import admin
from .models import BankTransaction


@admin.register(BankTransaction)
class BankTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "transaction_date",
        "description",
        "category",
        "dr",
        "cr",
    )

    list_filter = (
        "category",
        "transaction_date",
    )

    search_fields = (
        "description",
        "category",
    )

    ordering = ("-transaction_date",)