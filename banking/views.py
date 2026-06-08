from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Avg, Max
from django.db.models.functions import ExtractYear, ExtractMonth
from .models import BankTransaction, CategoryRule, ImportLog
import csv
import hashlib
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.contrib import messages


from .forms import BankImportForm




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

    transactions = BankTransaction.objects.all()

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
    }

    return render(request, "banking/dashboard.html", context)


def rules_management(request):
    if request.method == "POST":
        keyword = request.POST.get("keyword", "").strip()
        category = request.POST.get("category", "").strip()

        if keyword and category:
            CategoryRule.objects.get_or_create(
                keyword=keyword,
                category=category,
            )

            BankTransaction.objects.filter(
                description__icontains=keyword
            ).update(category=category)

        return redirect("banking:rules_management")

    rules = CategoryRule.objects.all().order_by("keyword")

    categories = (
        BankTransaction.objects
        .exclude(category__isnull=True)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )

    uncategorized = (
        BankTransaction.objects
        .filter(category="Uncategorized")
        .values("description")
        .annotate(
            rows=Count("id"),
            total_dr=Sum("dr"),
        )
        .order_by("-total_dr")[:100]
    )

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
    }

    return render(request, "banking/rules_management.html", context)


def edit_rule(request, rule_id):
    rule = get_object_or_404(CategoryRule, id=rule_id)

    categories = (
        BankTransaction.objects
        .exclude(category__isnull=True)
        .exclude(category="")
        .values_list("category", flat=True)
        .distinct()
        .order_by("category")
    )

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

    transactions = (
        BankTransaction.objects
        .filter(category=category)
        .order_by("-transaction_date")
    )

    summary = transactions.aggregate(
        total_spend=Sum("dr"),
        transaction_count=Count("id"),
        average_spend=Avg("dr"),
        largest_spend=Max("dr"),
    )

    vendor_summary = (
        transactions
        .values("description")
        .annotate(
            transaction_count=Count("id"),
            total_spend=Sum("dr"),
        )
        .order_by("-total_spend")
    )

    rules = (
        CategoryRule.objects
        .filter(category=category)
        .order_by("keyword")
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
    }

    return render(
        request,
        "banking/category_detail.html",
        context,
    )


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


def build_hash(transaction_date, description, dr, cr, balance):
    raw = (
        f"{transaction_date}|"
        f"{description.strip()}|"
        f"{dr or 0}|"
        f"{cr or 0}|"
        f"{balance or 0}|"
        
    )

    return hashlib.md5(raw.encode("utf-8")).hexdigest()


def apply_category_rules():
    for rule in CategoryRule.objects.all():
        BankTransaction.objects.filter(
            description__icontains=rule.keyword,
            category="Uncategorized",
        ).update(category=rule.category)


def import_bank_csv(request):
    if request.method == "POST":
        form = BankImportForm(request.POST, request.FILES)

        if form.is_valid():
            csv_file = request.FILES["csv_file"]
            decoded_file = csv_file.read().decode("utf-8-sig").splitlines()

            reader = csv.DictReader(
                decoded_file,
                fieldnames=["date", "description", "dr", "cr", "balance"],
            )

            imported = 0
            skipped = 0
            errors = 0
            latest_transaction_date = None

            for row_number, row in enumerate(reader, start=1):
                date_text = row.get("date")
                description = (row.get("description") or "").strip()
                dr = parse_money(row.get("dr"))
                cr = parse_money(row.get("cr"))
                balance = parse_money(row.get("balance"))

                transaction_date = parse_date(date_text)

                if transaction_date:
                    if latest_transaction_date is None or transaction_date > latest_transaction_date:
                        latest_transaction_date = transaction_date

                if not transaction_date or not description:
                    errors += 1
                    continue

                import_hash = build_hash(
                    transaction_date,
                    description,
                    dr,
                    cr,
                    balance,
                )

                duplicate_exists = BankTransaction.objects.filter(
                    transaction_date=transaction_date,
                    description=description,
                    dr=dr,
                    cr=cr,
                    balance=balance,
                ).exists()

                if duplicate_exists:
                    skipped += 1
                    continue

                BankTransaction.objects.create(
                    transaction_date=transaction_date,
                    description=description,
                    dr=dr,
                    cr=cr,
                    balance=balance,
                    category="Uncategorized",
                    import_hash=import_hash,
                )

                imported += 1

            apply_category_rules()

            ImportLog.objects.create(
                file_name=csv_file.name,
                imported_count=imported,
                skipped_count=skipped,
                error_count=errors,
                latest_transaction_date=latest_transaction_date,
            )

            messages.success(
                request,
                f"Import complete. Imported: {imported}, skipped duplicates: {skipped}, errors: {errors}."
            )

            return redirect("banking:dashboard")

    else:
        form = BankImportForm()

    return render(request, "banking/import_bank_csv.html", {"form": form})

def import_log_list(request):
    logs = ImportLog.objects.all().order_by("-imported_at")

    return render(request, "banking/import_log_list.html", {
        "logs": logs,
    })


