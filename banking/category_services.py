"""
Centralized category rule matching and application.

All code paths that assign categories from rules should go through this module
so matching behavior (longest keyword wins) and manual overrides stay consistent.
"""

from django.db.models import Q

from .models import BankTransaction, CategoryRule

UNCATEGORIZED = "Uncategorized"


def is_uncategorized(category):
    if category is None:
        return True
    return str(category).strip() in ("", UNCATEGORIZED)


def load_rules_sorted():
    """Return rules ordered by keyword length descending (longest match wins)."""
    rules = list(CategoryRule.objects.all())
    rules.sort(key=lambda rule: len((rule.keyword or "").strip()), reverse=True)
    return rules


def match_category_from_description(description, rules=None):
    """
    Pick the category for a description using substring rules (longest keyword wins).
    Returns UNCATEGORIZED when nothing matches.
    """
    if rules is None:
        rules = load_rules_sorted()

    description_upper = (description or "").upper()
    best_category = None
    best_length = 0

    for rule in rules:
        keyword = (rule.keyword or "").strip().upper()
        if not keyword:
            continue
        if keyword in description_upper and len(keyword) > best_length:
            best_category = rule.category
            best_length = len(keyword)

    if best_category:
        return best_category
    return UNCATEGORIZED


def eligible_for_rule_application(queryset=None):
    """Transactions rules may change (not manually locked)."""
    qs = queryset if queryset is not None else BankTransaction.objects.all()
    return qs.filter(category_locked=False)


def preview_rule_reapply(queryset=None):
    """
    Return how many transactions would change category if all rules were re-applied.

    Returns dict with counts and optional sample rows (no personal data in tests).
    """
    rules = load_rules_sorted()
    qs = eligible_for_rule_application(queryset)

    would_change = 0
    unchanged = 0
    samples = []

    for tx in qs.iterator(chunk_size=500):
        new_category = match_category_from_description(tx.description, rules=rules)
        current = tx.category or UNCATEGORIZED
        if current != new_category:
            would_change += 1
            if len(samples) < 5:
                samples.append(
                    {
                        "transaction_id": tx.id,
                        "from_category": current,
                        "to_category": new_category,
                    }
                )
        else:
            unchanged += 1

    return {
        "would_change": would_change,
        "unchanged": unchanged,
        "total_eligible": would_change + unchanged,
        "samples": samples,
    }


def apply_rules_to_queryset(queryset=None, *, only_uncategorized=False):
    """
  Apply category rules to a queryset. Respects category_locked on each row.

  When only_uncategorized is True, limits to rows still uncategorized (import path).

  Returns the number of rows updated.
    """
    rules = load_rules_sorted()
    qs = eligible_for_rule_application(queryset)

    if only_uncategorized:
        qs = qs.filter(
            Q(category__isnull=True)
            | Q(category="")
            | Q(category=UNCATEGORIZED)
        )

    updated = 0
    for tx in qs.iterator(chunk_size=500):
        new_category = match_category_from_description(tx.description, rules=rules)
        current = tx.category or UNCATEGORIZED
        if current != new_category:
            tx.category = new_category
            tx.save(update_fields=["category"])
            updated += 1

    return updated


def apply_rule_to_transaction(transaction, rules=None, *, save=False):
    """Set transaction.category from rules; does not override manual locks."""
    if transaction.category_locked:
        return transaction

    if rules is None:
        rules = load_rules_sorted()

    transaction.category = match_category_from_description(
        transaction.description,
        rules=rules,
    )

    if save:
        transaction.save(update_fields=["category"])

    return transaction


def apply_matching_rule_for_keyword(keyword, category):
    """
    After creating/updating a single rule, update eligible rows whose description
    contains keyword and where the rule engine assigns `category`.
    """
    rules = load_rules_sorted()
    keyword_upper = (keyword or "").strip().upper()
    if not keyword_upper:
        return 0

    qs = eligible_for_rule_application().filter(
        description__icontains=keyword,
    )

    updated = 0
    for tx in qs.iterator(chunk_size=500):
        new_category = match_category_from_description(tx.description, rules=rules)
        if new_category == category and (tx.category or UNCATEGORIZED) != new_category:
            tx.category = new_category
            tx.save(update_fields=["category"])
            updated += 1

    return updated


def rename_category(old_name, new_name):
    """Rename a category everywhere it is referenced."""
    old_name = (old_name or "").strip()
    new_name = (new_name or "").strip()
    if not old_name or not new_name or old_name == new_name:
        return

    BankTransaction.objects.filter(category=old_name).update(category=new_name)
    CategoryRule.objects.filter(category=old_name).update(category=new_name)


def active_category_names():
    from .models import Category

    return list(
        Category.objects.filter(is_active=True).order_by("name").values_list("name", flat=True)
    )