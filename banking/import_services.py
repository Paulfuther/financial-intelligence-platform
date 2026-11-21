import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation

from django.db.models import Q

from .category_services import apply_rules_to_queryset
from .models import BankTransaction, ImportLog


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


def amount_filter_q(dr, cr, balance):
    q = Q()
    if dr is None:
        q &= Q(dr__isnull=True)
    else:
        q &= Q(dr=dr)
    if cr is None:
        q &= Q(cr__isnull=True)
    else:
        q &= Q(cr=cr)
    if balance is None:
        q &= Q(balance__isnull=True)
    else:
        q &= Q(balance=balance)
    return q


def find_source_mirrors_of_targets(source_account, target_transactions):
    """
    Return source-account transactions that exactly match a target row on
    date, description, and amounts (not import_hash — cross-account copies).
    """
    if source_account is None:
        return BankTransaction.objects.none()

    target_list = list(target_transactions)
    if not target_list:
        return BankTransaction.objects.none()

    matched_ids = set()
    for target in target_list:
        mirrors = BankTransaction.objects.filter(
            account_name=source_account,
            transaction_date=target.transaction_date,
            description=target.description,
        ).filter(amount_filter_q(target.dr, target.cr, target.balance))
        for mirror in mirrors:
            matched_ids.add(mirror.pk)

    if not matched_ids:
        return BankTransaction.objects.none()

    return BankTransaction.objects.filter(pk__in=matched_ids).order_by(
        "transaction_date",
        "id",
    )


def resolve_target_transactions_for_mirror_cleanup(
    target_account,
    match_import_log_id=None,
    transaction_date_from=None,
    transaction_date_to=None,
):
    targets = BankTransaction.objects.filter(account_name=target_account)

    if match_import_log_id:
        import_log = ImportLog.objects.get(pk=match_import_log_id)
        if import_log.account_name != target_account:
            raise ValueError(
                "Import log account "
                f"'{import_log.account_name}' does not match target '{target_account}'."
            )
        targets = targets.filter(
            pk__in=transactions_for_import_log(import_log).values_list("pk", flat=True),
        )
    if transaction_date_from:
        targets = targets.filter(transaction_date__gte=transaction_date_from)
    if transaction_date_to:
        targets = targets.filter(transaction_date__lte=transaction_date_to)

    return targets.order_by("transaction_date", "id")


def apply_category_rules():
    apply_rules_to_queryset(only_uncategorized=True)


def persist_csv_import(rows, account_name, file_name):
    """
    Create bank transactions and a single ImportLog row (with hashes).
    Wrapped in atomic so a failure does not leave orphan transactions.
    """
    from django.db import transaction

    imported = 0
    skipped = 0
    error_count = 0
    latest_transaction_date = None
    transaction_hashes = []
    errors = []

    with transaction.atomic():
        for row in rows:
            transaction_date = parse_date(row["transaction_date"])
            dr = parse_money(row["dr"])
            cr = parse_money(row["cr"])
            balance = parse_money(row["balance"])

            if transaction_is_duplicate(
                row["account_name"],
                transaction_date,
                row["description"],
                dr,
                cr,
                balance,
                row["import_hash"],
            ):
                skipped += 1
                continue

            BankTransaction.objects.create(
                transaction_date=transaction_date,
                description=row["description"],
                dr=dr,
                cr=cr,
                balance=balance,
                category=row["category"],
                import_hash=row["import_hash"],
                account_name=row["account_name"],
            )
            imported += 1
            transaction_hashes.append(row["import_hash"])

            if latest_transaction_date is None or transaction_date > latest_transaction_date:
                latest_transaction_date = transaction_date

        import_log = ImportLog.objects.create(
            file_name=file_name or "",
            account_name=account_name or "",
            imported_count=imported,
            skipped_count=skipped,
            error_count=error_count,
            latest_transaction_date=latest_transaction_date,
            transaction_hashes=transaction_hashes,
        )

    if imported:
        apply_category_rules()

    return import_log, {"imported": imported, "skipped": skipped, "errors": errors}