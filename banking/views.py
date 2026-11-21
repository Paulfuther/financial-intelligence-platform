import calendar
import csv
import json
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.db.models import Avg, Count, F, Max, Min, Q, Sum
from django.db.models.functions import ExtractMonth, ExtractYear
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .forms import ACCOUNT_CHOICES, BankImportForm, MirrorCleanupForm
from .import_services import (
    apply_category_rules,
    build_hash,
    find_source_mirrors_of_targets,
    parse_date,
    parse_money,
    persist_csv_import,
    resolve_target_transactions_for_mirror_cleanup,
    transaction_is_duplicate,
    transactions_for_import_log,
)
from .models import BankTransaction, Category, CategoryRule, DebtAccount, ImportLog

MONTHS = [
    (1, "January"),
    (2, "February"),
    (3, "March"),
    (4, "April"),
    (5, "May"),
    (6, "June"),
    (7, "July"),
    (8, "August"),
    (9, "September"),
    (10, "October"),
    (11, "November"),
    (12, "December"),
]


def dashboard(request):
    year = request.GET.get("year")
    month = request.GET.get("month")
    category = request.GET.get("category")
    account = request.GET.get("account")

    # account summary
    account_summary = (
        BankTransaction.objects
        .values("account_name")
        .annotate(
            transaction_count=Count("id"),
            total_spend=Sum("dr"),
        )
        .order_by("account_name")
    )
    #

    transactions = BankTransaction.objects.all()
    if account:
        transactions = transactions.filter(account_name=account)

    if year:
        transactions = transactions.filter(transaction_date__year=year)

    if month:
        transactions = transactions.filter(transaction_date__month=month)

    if category:
        transactions = transactions.filter(category=category)

    years = (
        BankTransaction.objects
        .annotate(year_value=ExtractYear("transaction_date"))
        .values_list("year_value", flat=True)
        .distinct()
        .order_by("-year_value")
    )

    categories = (
        BankTransaction.objects
        .exclude(category__isnull=True)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )

    accounts = (
        BankTransaction.objects
        .exclude(account_name__isnull=True)
        .exclude(account_name="")
        .values_list("account_name", flat=True)
        .distinct()
        .order_by("account_name")
    )

    total_spend = transactions.aggregate(total=Sum("dr"))["total"] or 0
    transaction_count = transactions.count()

    category_summary_qs = (
        transactions
        .values("category")
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    category_labels = []
    category_totals = []

    for row in category_summary_qs:
        category_labels.append(row["category"] or "Uncategorized")
        category_totals.append(float(row["total"] or 0))

    selected_month_name = ""
    if month:
        selected_month_name = dict(MONTHS).get(int(month), "")

    last_import = ImportLog.objects.order_by("-imported_at").first()

    context = {
        "transactions": transactions.order_by("-transaction_date", "description"),
        "years": years,
        "months": MONTHS,
        "categories": categories,
        "selected_year": year,
        "selected_month": month,
        "selected_month_name": selected_month_name,
        "selected_category": category,
        "total_spend": total_spend,
        "transaction_count": transaction_count,
        "category_summary": category_summary_qs,
        "category_labels": category_labels,
        "category_totals": category_totals,
        "last_import": last_import,
        "accounts": accounts,
        "selected_account": account,
        "account_summary": account_summary,
    }

    return render(request, "banking/dashboard.html", context)


@require_GET
def category_transaction_preview(request):
    category = request.GET.get("category", "").strip()
    year = request.GET.get("year", "").strip()
    month = request.GET.get("month", "").strip()
    account = request.GET.get("account", "").strip()

    if not category:
        return JsonResponse(
            {
                "success": False,
                "error": "A category is required.",
            },
            status=400,
        )

    transactions = BankTransaction.objects.filter(
        category=category
    )

    if account:
        transactions = transactions.filter(
            account_name=account
        )

    if year:
        try:
            transactions = transactions.filter(
                transaction_date__year=int(year)
            )
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "success": False,
                    "error": "Invalid year.",
                },
                status=400,
            )

    if month:
        try:
            month_number = int(month)

            if month_number < 1 or month_number > 12:
                raise ValueError

            transactions = transactions.filter(
                transaction_date__month=month_number
            )
        except (TypeError, ValueError):
            return JsonResponse(
                {
                    "success": False,
                    "error": "Invalid month.",
                },
                status=400,
            )

    summary = transactions.aggregate(
        transaction_count=Count("id"),
        total_spend=Sum("dr"),
        average_spend=Avg("dr"),
        largest_spend=Max("dr"),
        first_transaction=Min("transaction_date"),
        last_transaction=Max("transaction_date"),
    )

    transaction_count = summary["transaction_count"] or 0

    transaction_rows = (
        transactions
        .order_by("-transaction_date", "description", "-id")
        .values(
            "id",
            "transaction_date",
            "description",
            "account_name",
            "dr",
            "category",
        )[:100]
    )

    rows = [
        {
            "id": row["id"],
            "date": row["transaction_date"].strftime("%b %d, %Y"),
            "description": row["description"] or "",
            "account": row["account_name"] or "",
            "amount": float(row["dr"] or 0),
            "category": row["category"] or "",
        }
        for row in transaction_rows
    ]

    daily_totals_qs = (
        transactions
        .values(day=F("transaction_date"))
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("day")
    )

    daily_totals = [
        {
            "date": row["day"].strftime("%Y-%m-%d"),
            "date_label": row["day"].strftime("%b %d"),
            "total": float(row["total"] or 0),
            "count": row["count"],
        }
        for row in daily_totals_qs
    ]

    recurring_vendors_qs = (
        transactions
        .exclude(description__isnull=True)
        .exclude(description="")
        .values("description")
        .annotate(
            count=Count("id"),
            total=Sum("dr"),
            average=Avg("dr"),
        )
        .filter(count__gte=2)
        .order_by("-total", "-count", "description")[:8]
    )

    recurring_vendors = [
        {
            "description": row["description"],
            "count": row["count"],
            "total": float(row["total"] or 0),
            "average": float(row["average"] or 0),
        }
        for row in recurring_vendors_qs
    ]

    first_transaction = summary["first_transaction"]
    last_transaction = summary["last_transaction"]

    return JsonResponse(
        {
            "success": True,
            "category": category,
            "year": year,
            "month": month,
            "account": account,
            "transactions": rows,
            "transaction_count": transaction_count,
            "displayed_count": len(rows),
            "total_spend": float(summary["total_spend"] or 0),
            "average_spend": float(summary["average_spend"] or 0),
            "largest_spend": float(summary["largest_spend"] or 0),
            "first_transaction": (
                first_transaction.strftime("%b %d, %Y")
                if first_transaction
                else ""
            ),
            "last_transaction": (
                last_transaction.strftime("%b %d, %Y")
                if last_transaction
                else ""
            ),
            "daily_totals": daily_totals,
            "recurring_vendors": recurring_vendors,
            "is_limited": transaction_count > len(rows),
        }
    )

@require_POST
def update_transaction_category(request, transaction_id):
    try:
        payload = json.loads(request.body or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {
                "success": False,
                "error": "Invalid request data.",
            },
            status=400,
        )

    category = str(payload.get("category", "")).strip()

    if not category:
        return JsonResponse(
            {
                "success": False,
                "error": "A category is required.",
            },
            status=400,
        )

    try:
        transaction = BankTransaction.objects.get(
            id=transaction_id
        )
    except BankTransaction.DoesNotExist:
        return JsonResponse(
            {
                "success": False,
                "error": "Transaction not found.",
            },
            status=404,
        )

    old_category = transaction.category or ""

    transaction.category = category
    transaction.save(update_fields=["category"])

    return JsonResponse(
        {
            "success": True,
            "transaction_id": transaction.id,
            "old_category": old_category,
            "category": transaction.category,
        }
    )

def match_category(description, rules):
    description = description.upper()

    best_match = None
    best_length = 0

    for rule in rules:
        keyword = rule.keyword.upper()

        if keyword in description:
            if len(keyword) > best_length:
                best_match = rule
                best_length = len(keyword)

    if best_match:
        return best_match.category

    return None

def apply_rule_to_transaction(tx):
    rules = CategoryRule.objects.all()
    rules = sorted(rules, key=lambda r: len(r.keyword), reverse=True)

    tx_desc = tx.description.upper()

    for rule in rules:
        if rule.keyword.upper() in tx_desc:
            tx.category = rule.category
            return tx

    return tx

def rules_management(request):
    uncat_q = request.GET.get("uncat_q", "").strip()
    uncat_sort = request.GET.get("uncat_sort", "total")
    if request.method == "POST":
         
        keyword = request.POST.get("keyword", "").strip()
        category = request.POST.get("category", "").strip()

        if keyword and category:
            CategoryRule.objects.get_or_create(
                keyword=keyword,
                category=category,
            )

            transactions = BankTransaction.objects.filter(
                Q(category="Uncategorized") |
                Q(category="") |
                Q(category__isnull=True)
            )

            for tx in transactions:
                apply_rule_to_transaction(tx)
                tx.save()

        return redirect("banking:rules_management")

    rules = CategoryRule.objects.all().order_by("-keyword")

    categories = Category.objects.filter(
        is_active=True
    ).order_by("name")

    uncategorized = (
        BankTransaction.objects
        .filter(
            Q(category="Uncategorized") |
            Q(category="") |
            Q(category__isnull=True)
        )
    )

    if uncat_q:
        uncategorized = uncategorized.filter(description__icontains=uncat_q)

    uncategorized = (
        uncategorized
        .values("description")
        .annotate(
            rows=Count("id"),
            total_dr=Sum("dr"),
        )
    )

    if uncat_sort == "description":
        uncategorized = uncategorized.order_by("description")
    elif uncat_sort == "rows":
        uncategorized = uncategorized.order_by("-rows")
    else:
        uncategorized = uncategorized.order_by("-total_dr")

    uncategorized = uncategorized[:200]

    category_rollup = (
        BankTransaction.objects
        .values("category")
        .annotate(
            transaction_count=Count("id"),
            total_spend=Sum("dr"),
        )
        .order_by("-total_spend")
    )

    rule_counts = (
        CategoryRule.objects
        .values("category")
        .annotate(rule_count=Count("id"))
    )

    rule_count_map = {
        row["category"]: row["rule_count"]
        for row in rule_counts
    }

    for row in category_rollup:
        row["rule_count"] = rule_count_map.get(row["category"], 0)

    context = {
        "rules": rules,
        "categories": categories,
        "uncategorized": uncategorized,
        "category_rollup": category_rollup,
        "uncat_q": uncat_q,
        "uncat_sort": uncat_sort,
    }

    return render(request, "banking/rules_management.html", context)

def edit_rule(request, rule_id):
    rule = get_object_or_404(CategoryRule, id=rule_id)

    categories = Category.objects.filter(
        is_active=True
    ).order_by("name")

    if request.method == "POST":
        keyword = request.POST.get("keyword", "").strip()
        category = request.POST.get("category", "").strip()
        apply_to_existing = request.POST.get("apply_to_existing")

        if keyword and category:
            rule.keyword = keyword
            rule.category = category
            rule.save()

            if apply_to_existing:
                BankTransaction.objects.filter(
                    description__icontains=keyword
                ).update(category=category)

        return redirect("banking:rules_management")

    return render(request, "banking/edit_rule.html", {
        "rule": rule,
        "categories": categories,
    })

def rule_detail(request, rule_id):
    rule = get_object_or_404(CategoryRule, id=rule_id)

    transactions = (
        BankTransaction.objects
        .filter(description__icontains=rule.keyword)
        .order_by("-transaction_date")
    )

    vendor_summary = (
        transactions
        .values("description")
        .annotate(
            rows=Count("id"),
            total_spend=Sum("dr"),
        )
        .order_by("-total_spend")
    )

    total_spend = transactions.aggregate(total=Sum("dr"))["total"] or 0

    return render(request, "banking/rule_detail.html", {
        "rule": rule,
        "transactions": transactions,
        "vendor_summary": vendor_summary,
        "total_spend": total_spend,
    })

def category_detail(request, category):
    start_date = request.GET.get("start_date")
    end_date = request.GET.get("end_date")

    transactions = (
        BankTransaction.objects
        .filter(category=category)
        .order_by("-transaction_date")
    )

    if start_date:
        transactions = transactions.filter(transaction_date__gte=start_date)

    if end_date:
        transactions = transactions.filter(transaction_date__lte=end_date)

    summary = transactions.aggregate(
        total_spend=Sum("dr"),
        transaction_count=Count("id"),
        average_spend=Avg("dr"),
        largest_spend=Max("dr"),
        first_payment=Min("transaction_date"),
        last_payment=Max("transaction_date"),
    )

    vendor_summary = (
        transactions
        .values("description")
        .annotate(
            transaction_count=Count("id"),
            total_spend=Sum("dr"),
        )
        .order_by("-total_spend")[:10]
    )

    rules = (
        CategoryRule.objects
        .filter(category=category)
        .order_by("-keyword")
    )

    monthly_trend = (
        transactions
        .annotate(
            year=ExtractYear("transaction_date"),
            month=ExtractMonth("transaction_date"),
        )
        .values("year", "month")
        .annotate(total_spend=Sum("dr"))
        .order_by("year", "month")
    )

    monthly_labels = []
    monthly_totals = []

    for row in monthly_trend:
        monthly_labels.append(f"{row['year']}-{row['month']:02d}")
        monthly_totals.append(float(row["total_spend"] or 0))

    context = {
        "category": category,
        "transactions": transactions,
        "vendor_summary": vendor_summary,
        "rules": rules,
        "summary": summary,
        "monthly_labels": monthly_labels,
        "monthly_totals": monthly_totals,
        "start_date": start_date,
        "end_date": end_date,
    }

    return render(request, "banking/category_detail.html", context)

def import_log_list(request):
    logs = (
        ImportLog.objects
        .all()
        .order_by("-imported_at")
    )

    total_imported = sum(log.imported_count for log in logs)
    total_skipped = sum(log.skipped_count for log in logs)
    total_errors = sum(log.error_count for log in logs)

    context = {
        "logs": logs,
        "total_imported": total_imported,
        "total_skipped": total_skipped,
        "total_errors": total_errors,
    }

    return render(
        request,
        "banking/import_log_list.html",
        context,
    )


@require_POST
def undo_import_log(request, import_log_id):
    import_log = get_object_or_404(ImportLog, pk=import_log_id)
    transactions = list(transactions_for_import_log(import_log))

    if not transactions:
        messages.warning(request, "No transactions matched this import.")
        return redirect("banking:import_log_list")

    ids = [tx.pk for tx in transactions]
    deleted_count, _ = BankTransaction.objects.filter(pk__in=ids).delete()

    import_log.imported_count = 0
    import_log.transaction_hashes = []
    import_log.save(update_fields=["imported_count", "transaction_hashes"])

    messages.success(
        request,
        f"Removed {deleted_count} transaction(s) from import #{import_log.id} ({import_log.file_name}).",
    )
    return redirect("banking:import_log_list")


def undo_import_preview(request, import_log_id):
    import_log = get_object_or_404(ImportLog, pk=import_log_id)
    tracked_hashes = import_log.transaction_hashes or []
    transactions = list(transactions_for_import_log(import_log))

    return render(
        request,
        "banking/undo_import.html",
        {
            "import_log": import_log,
            "transactions": transactions,
            "using_heuristic": not tracked_hashes,
        },
    )


def vehicle_summary(request):
    year = request.GET.get("year")

    vehicle_categories = [
        "Gas",
        "Vehicle Repairs",
        "Vehicle Maintenance",
        "Vehicle Insurance",
        "Car Payment",
        'Vehicle Loan Payment',
        
    ]

    transactions = BankTransaction.objects.filter(
        category__in=vehicle_categories
    )

    if year:
        transactions = transactions.filter(transaction_date__year=year)

    years = (
        BankTransaction.objects
        .annotate(year_value=ExtractYear("transaction_date"))
        .values_list("year_value", flat=True)
        .distinct()
        .order_by("-year_value")
    )

    category_summary = (
        transactions
        .values("category")
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    monthly_summary = (
        transactions
        .annotate(
            year_value=ExtractYear("transaction_date"),
            month_value=ExtractMonth("transaction_date"),
        )
        .values("year_value", "month_value")
        .annotate(total=Sum("dr"))
        .order_by("year_value", "month_value")
    )

    largest_expense = (
        transactions
        .exclude(dr__isnull=True)
        .order_by("-dr")
        .first()
    )

    top_transactions = (
        transactions
        .exclude(dr__isnull=True)
        .order_by("-dr")[:10]
    )

    account_summary = (
        transactions
        .values("account_name")
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    for row in monthly_summary:
        month_name = calendar.month_abbr[row["month_value"]]

        row["month_name"] = month_name

        row["chart_label"] = (
            f"{month_name} "
            f"{str(row['year_value'])[-2:]}"
        )

    highest_month = None

    if monthly_summary:
        highest_month = max(
            monthly_summary,
            key=lambda x: x["total"] or 0
        )


    total_cost = transactions.aggregate(total=Sum("dr"))["total"] or 0

    for row in category_summary:
        if total_cost:
            row["percent"] = (row["total"] or 0) / total_cost * 100
        else:
            row["percent"] = 0

    transaction_count = transactions.count()

    months_count = monthly_summary.count() or 1
    monthly_average = total_cost / months_count

    context = {
        "selected_year": year,
        "years": years,
        "vehicle_categories": vehicle_categories,
        "category_summary": category_summary,
        "monthly_summary": monthly_summary,
        "total_cost": total_cost,
        "transaction_count": transaction_count,
        "monthly_average": monthly_average,
        "largest_expense": largest_expense,
        "top_transactions": top_transactions,
        "account_summary": account_summary,
        "highest_month": highest_month,
    }

    return render(request, "banking/vehicle_summary.html", context)


# Helper Funciton for food summary

def normalize_food_vendor(description):
    desc = (description or "").upper()

    if "STARBUCKS" in desc:
        return "Starbucks"

    if "DOORDASH" in desc or "DD/" in desc:
        return "DoorDash"

    if "TIM HORTONS" in desc:
        return "Tim Hortons"

    if "MCDONALD" in desc:
        return "McDonald's"

    if "LCBO" in desc:
        return "LCBO"

    if "BEER STORE" in desc:
        return "Beer Store"

    if "PIZZA" in desc:
        return "Pizza"

    if "HARVEY" in desc:
        return "Harvey's"

    if "WENDY" in desc:
        return "Wendy's"
    
    if "SHELB" in desc:
        return "Shelby's"

    if "MR SUB" in desc:
        return "Mr. Sub"
    
    if "ANGELO" in desc:
        return "Angelo's"
    
    if "LITTLE CAESAR" in desc:
        return "Little Ceasar's"

    if "OSMO" in desc:
        return "Osmow's"
    
    if "A W STORE" in desc:
        return "A and W"

    return description[:35]

# ------------------------------ #

def food_summary(request):
    year = request.GET.get("year")

    food_categories = [
        "Eating Out",
        "Coffee",
    ]

    transactions = BankTransaction.objects.filter(
        category__in=food_categories
    )

    if year:
        transactions = transactions.filter(transaction_date__year=year)

    years = (
        BankTransaction.objects
        .annotate(year_value=ExtractYear("transaction_date"))
        .values_list("year_value", flat=True)
        .distinct()
        .order_by("-year_value")
    )

    category_summary = (
        transactions
        .values("category")
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    total_cost = transactions.aggregate(total=Sum("dr"))["total"] or 0
    transaction_count = transactions.count()

    for row in category_summary:
        row["percent"] = ((row["total"] or 0) / total_cost * 100) if total_cost else 0

    monthly_summary = (
        transactions
        .annotate(
            year_value=ExtractYear("transaction_date"),
            month_value=ExtractMonth("transaction_date"),
        )
        .values("year_value", "month_value")
        .annotate(total=Sum("dr"))
        .order_by("year_value", "month_value")
    )


    for row in monthly_summary:
        month_name = calendar.month_abbr[row["month_value"]]
        row["month_name"] = month_name
        row["chart_label"] = f"{month_name} {str(row['year_value'])[-2:]}"

    months_count = monthly_summary.count() or 1
    monthly_average = total_cost / months_count

    largest_expense = (
        transactions
        .exclude(dr__isnull=True)
        .order_by("-dr")
        .first()
    )

    top_transactions = (
        transactions
        .exclude(dr__isnull=True)
        .order_by("-dr")[:10]
    )

    account_summary = (
        transactions
        .values("account_name")
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    highest_month = None

    if monthly_summary:
        highest_month = max(
            monthly_summary,
            key=lambda x: x["total"] or 0
        )

    vendor_totals = {}

    for tx in transactions:
        vendor = normalize_food_vendor(tx.description)

        if vendor not in vendor_totals:
            vendor_totals[vendor] = {
                "count": 0,
                "total": 0,
            }

        vendor_totals[vendor]["count"] += 1
        vendor_totals[vendor]["total"] += float(tx.dr or 0)

    vendor_summary = sorted(
        [
            {
                "vendor": vendor,
                "count": data["count"],
                "total": data["total"],
            }
            for vendor, data in vendor_totals.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )[:15]


    context = {
        "selected_year": year,
        "years": years,
        "category_summary": category_summary,
        "monthly_summary": monthly_summary,
        "total_cost": total_cost,
        "transaction_count": transaction_count,
        "monthly_average": monthly_average,
        "largest_expense": largest_expense,
        "top_transactions": top_transactions,
        "account_summary": account_summary,
        "highest_month": highest_month,
        "vendor_summary": vendor_summary,
    }

    return render(request, "banking/food_summary.html", context)

# ----- Vendors -------

def normalize_subscription_vendor(description):
    desc = (description or "").upper()

    if "DOCUSIGN" in desc:
        return "DocuSign"

    if "INTUIT" in desc or "QBOOK" in desc:
        return "QuickBooks"

    if "LINODE" in desc or "AKAMAI" in desc:
        return "Linode"

    if "MICROSOFT" in desc:
        return "Microsoft"

    if "OPENAI" in desc or "CHATGPT" in desc:
        return "OpenAI"

    if "TWILIO" in desc:
        return "Twilio"

    if "SENDGRID" in desc:
        return "SendGrid"

    if "AMAZON.CA PRIME" in desc or "AMAZON PRIME" in desc:
        return "Amazon Prime"

    if "APPLE.COM/BILL" in desc:
        return "Apple Services"

    if "GOOGLE" in desc:
        return "Google"

    if "GODADDY" in desc:
        return "GoDaddy"

    if "ROGERS" in desc:
        return "Rogers"
    
    if "RGRS" in desc:
        return "Rogers"
    
    if "ADOBE" in desc:
        return "Adobe"
    
    if "MEDIUM" in desc:
        return "Medium"
    
    if "NETFLIX" in desc:
        return "Netflix"

    return description[:35]

# ------------------------------- 

def subscription_summary(request):
    year = request.GET.get("year")
    month = request.GET.get("month", "")

    subscription_categories = [
        "Software",
        "Subscriptions",
        "Cloud Services",
        "Domain Hosting",
        "AI Services",
        "Telecommunications",
        "Apple Services",
    ]

    transactions = BankTransaction.objects.filter(
        category__in=subscription_categories
    )

    if year:
        transactions = transactions.filter(transaction_date__year=year)

    if month:
        transactions = transactions.filter(transaction_date__month=month)

    years = (
        BankTransaction.objects
        .annotate(year_value=ExtractYear("transaction_date"))
        .values_list("year_value", flat=True)
        .distinct()
        .order_by("-year_value")
    )

    month_transactions = transactions.order_by(
        "-transaction_date",
        "description"
    )


    category_summary = (
        transactions
        .values("category")
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    total_cost = transactions.aggregate(total=Sum("dr"))["total"] or 0
    transaction_count = transactions.count()

    for row in category_summary:
        row["percent"] = ((row["total"] or 0) / total_cost * 100) if total_cost else 0

    monthly_summary = (
        transactions
        .annotate(
            year_value=ExtractYear("transaction_date"),
            month_value=ExtractMonth("transaction_date"),
        )
        .values("year_value", "month_value")
        .annotate(total=Sum("dr"))
        .order_by("year_value", "month_value")
    )


    for row in monthly_summary:
        month_name = calendar.month_abbr[row["month_value"]]
        row["month_name"] = month_name
        row["chart_label"] = f"{month_name} {str(row['year_value'])[-2:]}"

    months_count = monthly_summary.count() or 1
    monthly_average = total_cost / months_count

    largest_expense = (
        transactions
        .exclude(dr__isnull=True)
        .order_by("-dr")
        .first()
    )

    top_transactions = (
        transactions
        .exclude(dr__isnull=True)
        .order_by("-dr")[:15]
    )

    account_summary = (
        transactions
        .values("account_name")
        .annotate(
            total=Sum("dr"),
            count=Count("id"),
        )
        .order_by("-total")
    )

    vendor_totals = {}

    for tx in transactions:
        vendor = normalize_subscription_vendor(tx.description)

        if vendor not in vendor_totals:
            vendor_totals[vendor] = {
                "count": 0,
                "total": 0,
            }

        vendor_totals[vendor]["count"] += 1
        vendor_totals[vendor]["total"] += float(tx.dr or 0)

    vendor_summary = sorted(
        [
            {
                "vendor": vendor,
                "count": data["count"],
                "total": data["total"],
            }
            for vendor, data in vendor_totals.items()
        ],
        key=lambda x: x["total"],
        reverse=True,
    )[:15]

    context = {
        "selected_year": year,
        "years": years,
        "category_summary": category_summary,
        "monthly_summary": monthly_summary,
        "total_cost": total_cost,
        "transaction_count": transaction_count,
        "monthly_average": monthly_average,
        "largest_expense": largest_expense,
        "top_transactions": top_transactions,
        "account_summary": account_summary,
        "vendor_summary": vendor_summary,
        "months": MONTHS,

        "selected_month": month,

        "month_transactions": month_transactions,
    }

    return render(request, "banking/subscription_summary.html", context)

# ------ helper funciton for imports -----

def parse_import_rows(csv_file, account_name):
    decoded_file = csv_file.read().decode("utf-8-sig").splitlines()
    # Look for a recognized header row.
    # Some exports (Canadian Tire) include account metadata above the transactions.
    header_index = None
    for i, line in enumerate(decoded_file):
        line_lower = line.strip().lower()
        if (
            line_lower.startswith("ref,transaction date")
            or line_lower.startswith("transaction_date")
            or line_lower.startswith("transaction date")
        ):
            header_index = i
            break
    if header_index is not None:
        header_line = decoded_file[header_index]
        delimiter = "\t" if "\t" in header_line else ","
        reader = csv.DictReader(
            decoded_file[header_index:],
            delimiter=delimiter,
        )

    else:
        # Fallback for older/simple bank exports with no header
        first_line = decoded_file[0]
        delimiter = "\t" if "\t" in first_line else ","
        reader = csv.DictReader(
            decoded_file,
            fieldnames=["date", "description", "dr", "cr", "balance"],
            delimiter=delimiter,
        )

    valid_rows = []
    duplicate_rows = []
    error_rows = []

    accounts_requiring_balance = [
        "Personal Account",
        "Corporate Bank Account",
        "Corporate Credit Card",
    ]

    category_map = {
        "Grocery": "Groceries",
        "Grocery Other": "Groceries",
        "Restaurant": "Eating Out",
        "Pharmacy": "Medical",
        "Home stores": "Household",
        "Business services": "Subscriptions",
        "Gas": "Gas",
        "Dining": "Eating Out",
        "Gas/Automotive": "Gas",
        "Fee/Interest Charge": "Interest",
        "Payment/Credit": "Credit Card Payment",
        "Merchandise": "Shopping",
        "Internet": "Online Shopping",
        "Other Services": "Subscriptions",
        "Other Travel": "Travel",
        "Car Rental": "Travel",
        "Insurance": "Insurance",
    }

    for row_number, row in enumerate(reader, start=1):
        date_text = row.get("transaction_date") or row.get("date")
        description = (row.get("description") or "").strip()
        dr = parse_money(row.get("dr"))
        cr = parse_money(row.get("cr"))
        balance = parse_money(row.get("balance"))
        category = row.get("category") or "Uncategorized"
        existing_hash = row.get("import_hash")

        # Canadian Tire
        if row.get("TRANSACTION DATE"):
            date_text = row.get("TRANSACTION DATE")
            description = (row.get("DESCRIPTION") or "").strip()
            amount = parse_money(row.get("AMOUNT"))
            card_category = (row.get("Category") or "").strip()

            if amount is not None and amount > 0:
                dr = amount
                cr = None
            elif amount is not None and amount < 0:
                dr = None
                cr = abs(amount)

            balance = None
            category = card_category or "Uncategorized"
            existing_hash = None

        # Capital One
        if row.get("Transaction Date") and row.get("Card No."):
            date_text = row.get("Transaction Date")
            description = (row.get("Description") or "").strip()
            dr = parse_money(row.get("Debit"))
            cr = parse_money(row.get("Credit"))
            balance = None
            category = (row.get("Category") or "").strip() or "Uncategorized"
            existing_hash = None

        category = category_map.get(category, category)
        transaction_date = parse_date(date_text)

        row_errors = []

        if not transaction_date:
            row_errors.append("Missing or invalid date")

        if not description:
            row_errors.append("Missing description")

        if account_name in accounts_requiring_balance and balance is None:
            row_errors.append("Missing balance")

        if row_errors:
            error_rows.append({
                "row_number": row_number,
                "errors": row_errors,
                "row": row,
            })
            continue

        import_hash = existing_hash or build_hash(
            transaction_date,
            description,
            dr,
            cr,
            balance,
            account_name,
        )

        clean_row = {
            "transaction_date": str(transaction_date),
            "description": description,
            "dr": str(dr) if dr is not None else "",
            "cr": str(cr) if cr is not None else "",
            "balance": str(balance) if balance is not None else "",
            "category": category,
            "import_hash": import_hash,
            "account_name": account_name,
        }

        if transaction_is_duplicate(
            account_name,
            transaction_date,
            description,
            dr,
            cr,
            balance,
            import_hash,
        ):
            duplicate_rows.append(clean_row)
        else:
            valid_rows.append(clean_row)

    return valid_rows, duplicate_rows, error_rows

# ------ End of Import Helper ---------

def import_bank_csv(request):
    if request.method == "POST":
        form = BankImportForm(request.POST, request.FILES)

        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            account_name = form.cleaned_data["account_name"]

            valid_rows, duplicate_rows, error_rows = parse_import_rows(
                csv_file,
                account_name,
            )

            request.session["pending_import_rows"] = valid_rows
            request.session["pending_import_account"] = account_name
            request.session["pending_import_file"] = csv_file.name


            return render(request, "banking/import_preview.html", {
                "valid_rows": valid_rows,
                "duplicate_rows": duplicate_rows,
                "error_rows": error_rows,
                "account_name": account_name,
                "file_name": csv_file.name,
            })

    else:
        form = BankImportForm()

    return render(request, "banking/import_bank_csv.html", {"form": form})


def confirm_bank_csv_import(request):
    if request.method != "POST":
        return redirect("banking:import_bank_csv")

    rows = request.session.get("pending_import_rows", [])
    account_name = request.session.get("pending_import_account")
    file_name = request.session.get("pending_import_file")

    import_log, counts = persist_csv_import(rows, account_name, file_name)

    request.session.pop("pending_import_rows", None)
    request.session.pop("pending_import_account", None)
    request.session.pop("pending_import_file", None)

    messages.success(
        request,
        (
            f"Import complete (log #{import_log.id}). "
            f"Imported: {counts['imported']}, skipped duplicates: {counts['skipped']}, "
            f"errors: {counts['errors']}."
        ),
    )

    return redirect("banking:dashboard")


def mirror_cleanup(request):
    mirrors = []
    error = None
    summary = {}
    preview_form = None

    if request.method == "POST" and request.POST.get("confirm") == "1":
        source = request.POST.get("source_account")
        target = request.POST.get("target_account")
        log_id = request.POST.get("match_import_log_id")
        log_id = int(log_id) if log_id else None
        date_from = parse_date(request.POST.get("transaction_date_from"))
        date_to = parse_date(request.POST.get("transaction_date_to"))

        try:
            targets = resolve_target_transactions_for_mirror_cleanup(
                target,
                match_import_log_id=log_id,
                transaction_date_from=date_from,
                transaction_date_to=date_to,
            )
            mirrors = list(find_source_mirrors_of_targets(source, targets))
        except ValueError as exc:
            messages.error(request, str(exc))
            return redirect("banking:mirror_cleanup")
        except ImportLog.DoesNotExist:
            messages.error(request, "Import log not found.")
            return redirect("banking:mirror_cleanup")

        if not mirrors:
            messages.warning(request, "No mirror transactions to delete.")
            return redirect("banking:mirror_cleanup")

        ids = [tx.pk for tx in mirrors]
        deleted_count, _ = BankTransaction.objects.filter(pk__in=ids).delete()
        messages.success(
            request,
            f"Removed {deleted_count} duplicate transaction(s) from {source}.",
        )
        return redirect("banking:import_log_list")

    form = MirrorCleanupForm(request.GET or None)
    if form.is_valid():
        preview_form = form
        source = form.cleaned_data["source_account"]
        target = form.cleaned_data["target_account"]
        log_id = form.cleaned_data.get("match_import_log_id")
        try:
            if log_id and not ImportLog.objects.filter(pk=log_id).exists():
                raise ImportLog.DoesNotExist
            targets = resolve_target_transactions_for_mirror_cleanup(
                target,
                match_import_log_id=log_id,
                transaction_date_from=form.cleaned_data.get("transaction_date_from"),
                transaction_date_to=form.cleaned_data.get("transaction_date_to"),
            )
            mirrors = list(find_source_mirrors_of_targets(source, targets))
            summary = {
                "source": source,
                "target": target,
                "target_count": targets.count(),
                "mirror_count": len(mirrors),
            }
        except ValueError as exc:
            error = str(exc)
        except ImportLog.DoesNotExist:
            error = "Import log not found."

    return render(
        request,
        "banking/mirror_cleanup.html",
        {
            "form": form,
            "preview_form": preview_form,
            "mirrors": mirrors,
            "summary": summary,
            "error": error,
        },
    )

def debt_dashboard(request):
    debts = DebtAccount.objects.filter(is_active=True)

    total_debt = sum(d.current_balance for d in debts)

    credit_card_debt = sum(
        d.current_balance for d in debts if d.debt_type == "credit_card"
    )

    loan_debt = sum(
        d.current_balance for d in debts if d.debt_type != "credit_card"
    )

    total_limit = sum(
        d.credit_limit or 0 for d in debts if d.debt_type == "credit_card"
    )

    utilization = (
        (credit_card_debt / total_limit) * 100
        if total_limit > 0
        else 0
    )

    available_credit = total_limit - credit_card_debt

    payoff_accounts = []

    today = date.today()

    for debt in debts:
        paid_down = 0
        progress_percent = 0
        months_remaining = None
        required_monthly_payment = None

        if debt.is_payoff_mode and debt.starting_balance:
            paid_down = debt.starting_balance - debt.current_balance

            if debt.starting_balance > 0:
                progress_percent = (paid_down / debt.starting_balance) * 100

        if debt.target_payoff_date and debt.current_balance > 0:
            months_remaining = (
                (debt.target_payoff_date.year - today.year) * 12
                + (debt.target_payoff_date.month - today.month)
            )

            if months_remaining <= 0:
                months_remaining = 1

            balance = debt.current_balance
            annual_rate = debt.interest_rate or 0
            monthly_rate = (annual_rate / 100) / 12

            if months_remaining > 0:
                if monthly_rate > 0:
                    required_monthly_payment = (
                        balance * monthly_rate
                    ) / (
                        1 - (1 + monthly_rate) ** (-months_remaining)
                    )
                else:
                    required_monthly_payment = balance / months_remaining
            else:
                required_monthly_payment = None

        payoff_accounts.append({
            "debt": debt,
            "paid_down": paid_down,
            "progress_percent": progress_percent,
            "months_remaining": months_remaining,
            "required_monthly_payment": required_monthly_payment,
        })

    context = {
        "debts": debts,
        "payoff_accounts": payoff_accounts,
        "total_debt": total_debt,
        "credit_card_debt": credit_card_debt,
        "loan_debt": loan_debt,
        "total_limit": total_limit,
        "available_credit": available_credit,
        "utilization": utilization,
    }

    return render(request, "banking/debt_dashboard.html", context)

def category_summary(request):
    summary = (
        BankTransaction.objects
        .exclude(category__isnull=True)
        .exclude(category="")
        .exclude(category="Uncategorized")
        .values("category")
        .annotate(
            transaction_count=Count("id"),
            total_spend=Sum("dr"),
            average_spend=Avg("dr"),
            largest_spend=Max("dr"),
        )
        .order_by("category")
    )

    totals = (
        BankTransaction.objects
        .exclude(category__isnull=True)
        .exclude(category="")
        .exclude(category="Uncategorized")
        .aggregate(
            total_transactions=Count("id"),
            grand_total=Sum("dr"),
        )
    )

    return render(request, "banking/category_summary.html", {
        "summary": summary,
        "total_transactions": totals["total_transactions"] or 0,
        "grand_total": totals["grand_total"] or 0,
    })


