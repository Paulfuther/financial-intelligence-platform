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