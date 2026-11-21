from django.contrib import admin

from .models import BankTransaction, Category, DebtAccount, ImportLog

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




@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "imported_at",
        "account_name",
        "file_name",
        "imported_count",
        "skipped_count",
    )
    list_filter = ("account_name",)
    search_fields = ("file_name", "account_name")
    readonly_fields = (
        "imported_at",
        "transaction_hashes",
    )
    ordering = ("-imported_at",)