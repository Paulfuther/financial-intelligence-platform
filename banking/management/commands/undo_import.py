from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from banking.import_services import transactions_for_import_log
from banking.models import BankTransaction, ImportLog


class Command(BaseCommand):
    help = (
        "Remove transactions created by a single import log entry. "
        "Use --dry-run first to review what would be deleted."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--import-log-id",
            type=int,
            required=True,
            help="ID of the import log row to undo (see /banking/imports/).",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="List matching transactions without deleting them.",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Skip interactive confirmation when applying the undo.",
        )

    def handle(self, *args, **options):
        import_log_id = options["import_log_id"]
        dry_run = options["dry_run"]
        skip_confirm = options["yes"]

        try:
            import_log = ImportLog.objects.get(pk=import_log_id)
        except ImportLog.DoesNotExist as exc:
            raise CommandError(f"Import log {import_log_id} does not exist.") from exc

        tracked_hashes = import_log.transaction_hashes or []
        using_heuristic = not tracked_hashes

        transactions = list(transactions_for_import_log(import_log))
        count = len(transactions)

        self.stdout.write(
            f"Import log #{import_log.id}: {import_log.file_name} "
            f"({import_log.account_name}) on {import_log.imported_at:%Y-%m-%d %H:%M}"
        )
        self.stdout.write(f"Recorded imported_count: {import_log.imported_count}")
        self.stdout.write(f"Matched transactions: {count}")

        if using_heuristic:
            self.stdout.write(
                self.style.WARNING(
                    "This import has no stored transaction hashes (older import). "
                    "Matches use a best-effort heuristic; verify the list carefully."
                )
            )

        if not transactions:
            self.stdout.write(self.style.WARNING("Nothing to delete."))
            return

        for tx in transactions:
            self.stdout.write(
                f"  {tx.transaction_date} | {tx.description[:60]} | "
                f"dr={tx.dr} cr={tx.cr} | hash={tx.import_hash[:12]}..."
            )

        if dry_run:
            self.stdout.write(self.style.SUCCESS("Dry run only; no rows deleted."))
            return

        if not skip_confirm:
            confirm = input(f"Delete {count} transaction(s)? Type 'yes' to continue: ")
            if confirm.strip().lower() != "yes":
                self.stdout.write(self.style.WARNING("Cancelled."))
                return

        with transaction.atomic():
            ids = [tx.pk for tx in transactions]
            deleted_count, _ = BankTransaction.objects.filter(pk__in=ids).delete()
            import_log.imported_count = 0
            import_log.transaction_hashes = []
            import_log.save(update_fields=["imported_count", "transaction_hashes"])

        self.stdout.write(
            self.style.SUCCESS(
                f"Deleted {deleted_count} transaction(s). Import log #{import_log.id} counts cleared."
            )
        )