from datetime import datetime

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from banking.forms import ACCOUNT_CHOICES
from banking.import_services import (
    find_source_mirrors_of_targets,
    resolve_target_transactions_for_mirror_cleanup,
)
from banking.models import BankTransaction, ImportLog


class Command(BaseCommand):
    help = (
        "Delete rows on a SOURCE account that exactly mirror rows on a TARGET account "
        "(same date, description, dr, cr, balance). Use for wrong-card imports with no ImportLog."
    )

    def add_arguments(self, parser):
        account_help = ", ".join(choice[0] for choice in ACCOUNT_CHOICES)
        parser.add_argument("--source", required=True, help=f"Wrong account. Choices: {account_help}")
        parser.add_argument("--target", required=True, help=f"Correct account. Choices: {account_help}")
        parser.add_argument(
            "--match-import-log-id",
            type=int,
            help="Only mirror against transactions from this import log (recommended).",
        )
        parser.add_argument(
            "--transaction-date-from",
            help="Optional lower bound on transaction_date (YYYY-MM-DD).",
        )
        parser.add_argument(
            "--transaction-date-to",
            help="Optional upper bound on transaction_date (YYYY-MM-DD).",
        )
        parser.add_argument("--dry-run", action="store_true", help="List matches only.")
        parser.add_argument("--yes", action="store_true", help="Skip confirmation.")

    def handle(self, *args, **options):
        source = options["source"]
        target = options["target"]
        dry_run = options["dry_run"]
        skip_confirm = options["yes"]
        log_id = options.get("match_import_log_id")

        valid_accounts = {c[0] for c in ACCOUNT_CHOICES}
        if source not in valid_accounts:
            raise CommandError(f"Unknown source account '{source}'.")
        if target not in valid_accounts:
            raise CommandError(f"Unknown target account '{target}'.")
        if source == target:
            raise CommandError("Source and target must differ.")

        date_from = options.get("transaction_date_from")
        date_to = options.get("transaction_date_to")
        if date_from:
            date_from = datetime.strptime(date_from, "%Y-%m-%d").date()
        if date_to:
            date_to = datetime.strptime(date_to, "%Y-%m-%d").date()

        if log_id:
            if not ImportLog.objects.filter(pk=log_id).exists():
                raise CommandError(f"Import log {log_id} does not exist.")

        try:
            target_qs = resolve_target_transactions_for_mirror_cleanup(
                target,
                match_import_log_id=log_id,
                transaction_date_from=date_from,
                transaction_date_to=date_to,
            )
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        target_count = target_qs.count()
        mirrors = list(find_source_mirrors_of_targets(source, target_qs))

        self.stdout.write(
            f"Target account: {target} ({target_count} reference row(s))"
        )
        self.stdout.write(f"Source account: {source}")
        if log_id:
            log = ImportLog.objects.get(pk=log_id)
            self.stdout.write(
                f"Reference import #{log_id}: {log.file_name} ({log.imported_at:%Y-%m-%d %H:%M})"
            )
        self.stdout.write(f"Mirror rows on source to delete: {len(mirrors)}")

        if not mirrors:
            self.stdout.write(self.style.WARNING("Nothing to delete."))
            return

        for tx in mirrors:
            self.stdout.write(
                f"  {tx.transaction_date} | {tx.description[:70]} | dr={tx.dr} cr={tx.cr}"
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run only; no rows deleted."))
            return

        if not skip_confirm:
            confirm = input(
                f"Delete {len(mirrors)} transaction(s) on '{source}'? Type 'yes': "
            )
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("Cancelled."))
                return

        ids = [tx.pk for tx in mirrors]
        with transaction.atomic():
            deleted_count, _ = BankTransaction.objects.filter(pk__in=ids).delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} mirror transaction(s) from '{source}'."
            )
        )