from django.contrib import admin
from .models import BankTransaction
from .models import DebtAccount

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



@admin.register(DebtAccount)
class DebtAccountAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "debt_type",
        "current_balance",
        "starting_balance",
        "tracking_start_date",
        "target_payoff_date",
        "is_payoff_mode",
        "is_active",
    )

    list_filter = ("debt_type", "is_payoff_mode", "is_active")

    search_fields = ("name", "lender")