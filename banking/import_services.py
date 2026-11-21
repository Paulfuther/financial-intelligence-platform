import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation

from .models import BankTransaction


def parse_money(value):
    if value is None:
        return None

    value = str(value).strip().replace("$", "").replace(",", "")

    if value == "":
        return None

    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def parse_date(value):
    value = str(value).strip()

    for fmt in ("%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            pass

    return None


def build_hash(transaction_date, description, dr, cr, balance, account_name):
    raw = (
        f"{account_name}|"
        f"{transaction_date}|"
        f"{description.strip()}|"
        f"{dr or 0}|"
        f"{cr or 0}|"
        f"{balance or 0}|"
    )

    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def transaction_is_duplicate(account_name, transaction_date, description, dr, cr, balance, import_hash):
    if BankTransaction.objects.filter(
        account_name=account_name,
        import_hash=import_hash,
    ).exists():
        return True

    return BankTransaction.objects.filter(
        account_name=account_name,
        transaction_date=transaction_date,
        description=description,
        dr=dr,
        cr=cr,
        balance=balance,
    ).exists()


def transactions_for_import_log(import_log):
    """Return transactions that belong to this import log, newest tracking first."""
    tracked_hashes = import_log.transaction_hashes or []
    if tracked_hashes:
        return BankTransaction.objects.filter(
            account_name=import_log.account_name,
            import_hash__in=tracked_hashes,
        ).order_by("transaction_date", "id")

    if not import_log.imported_count:
        return BankTransaction.objects.none()

    candidates = BankTransaction.objects.filter(
        account_name=import_log.account_name,
    )
    if import_log.latest_transaction_date:
        candidates = candidates.filter(
            transaction_date__lte=import_log.latest_transaction_date,
        )

    return candidates.order_by("-transaction_date", "-id")[: import_log.imported_count]