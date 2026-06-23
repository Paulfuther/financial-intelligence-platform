from django.db import models


class BankTransaction(models.Model):
    transaction_date = models.DateField()
    description = models.TextField()
    dr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    cr = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    balance = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    category = models.TextField(default="Uncategorized")
    import_hash = models.TextField(unique=True)
    account_name = models.CharField(max_length=100, default="Personal")
    
    class Meta:
        managed = False
        db_table = "bank_transactions"

    def __str__(self):
        return f"{self.transaction_date} - {self.description}"
    
class CategoryRule(models.Model):
    keyword = models.TextField()
    category = models.TextField()

    class Meta:
        managed = False
        db_table = "category_rules"
        unique_together = ("keyword", "category")

    def __str__(self):
        return f"{self.keyword} → {self.category}"
    
class ImportLog(models.Model):

    imported_at = models.DateTimeField(auto_now_add=True)

    file_name = models.CharField(max_length=255)

    account_name = models.CharField(
        max_length=100,
        default="Personal"
    )

    imported_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)

    latest_transaction_date = models.DateField(
        null=True,
        blank=True
    )


class DebtAccount(models.Model):
    DEBT_TYPES = [
        ("credit_card", "Credit Card"),
        ("loan", "Loan"),
        ("line_of_credit", "Line of Credit"),
        ("mortgage", "Mortgage"),
        ("vehicle", "Vehicle Loan"),
    ]

    name = models.CharField(max_length=100)
    debt_type = models.CharField(max_length=30, choices=DEBT_TYPES)
    lender = models.CharField(max_length=100, blank=True)
    current_balance = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    credit_limit = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    interest_rate = models.DecimalField(max_digits=6, decimal_places=3, null=True, blank=True)
    minimum_payment = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    due_day = models.PositiveSmallIntegerField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    starting_balance = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    tracking_start_date = models.DateField(
        null=True,
        blank=True
    )

    target_payoff_date = models.DateField(
        null=True,
        blank=True
    )

    is_payoff_mode = models.BooleanField(
        default=False
)
    

def apply_rule_to_transaction(transaction):
    rules = CategoryRule.objects.all()

    description = (transaction.description or "").upper()

    best_match = None
    best_length = 0

    for rule in rules:
        keyword = rule.keyword.upper()

        if keyword in description:
            if len(keyword) > best_length:
                best_match = rule
                best_length = len(keyword)

    if best_match:
        transaction.category = best_match.category
    else:
        transaction.category = "Uncategorized"


def recategorize_all_transactions():
    rules = CategoryRule.objects.all()

    transactions = BankTransaction.objects.all()

    for tx in transactions:
        apply_rule_to_transaction(tx)
        tx.save()