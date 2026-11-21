from django.core.management.base import BaseCommand

from banking.category_services import apply_rules_to_queryset, preview_rule_reapply


class Command(BaseCommand):
    help = (
        "Re-apply all category rules to existing transactions. "
        "Manual category edits (locked) are never changed."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would change without updating.",
        )

    def handle(self, *args, **options):
        if options["dry_run"]:
            preview = preview_rule_reapply()
            self.stdout.write(
                "Eligible transactions: {total}".format(total=preview["total_eligible"])
            )
            self.stdout.write(
                "Would change category: {count}".format(count=preview["would_change"])
            )
            self.stdout.write(
                "Would stay the same: {count}".format(count=preview["unchanged"])
            )
            return

        updated = apply_rules_to_queryset()
        self.stdout.write(
            self.style.SUCCESS(
                "Updated {count} transaction(s).".format(count=updated)
            )
        )