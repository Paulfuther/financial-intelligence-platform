from django.shortcuts import render, redirect, get_object_or_404
from django.db.models import Sum, Count, Avg, Max
from django.db.models.functions import ExtractYear, ExtractMonth
from .models import BankTransaction, CategoryRule, ImportLog
import csv
import hashlib
from decimal import Decimal, InvalidOperation
from datetime import datetime
from django.contrib import messages
import calendar
from django.db.models import Q

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
            account_name = form.cleaned_data["account_name"]
            decoded_file = csv_file.read().decode("utf-8-sig").splitlines()

            first_line = decoded_file[0]
            delimiter = "\t" if "\t" in first_line else ","

            first_line_lower = first_line.lower()

            has_header = (
                first_line_lower.startswith("transaction_date")
                or first_line_lower.startswith("transaction date")
            )

            if has_header:
                reader = csv.DictReader(decoded_file, delimiter=delimiter)
            else:
                reader = csv.DictReader(
                    decoded_file,
                    fieldnames=["date", "description", "dr", "cr", "balance"],
                    delimiter=delimiter,
                )

            imported = 0
            skipped = 0
            errors = 0
            latest_transaction_date = None

            for row_number, row in enumerate(reader, start=1):
                # Standard export format
                date_text = row.get("transaction_date") or row.get("date")
                description = (row.get("description") or "").strip()
                dr = parse_money(row.get("dr"))
                cr = parse_money(row.get("cr"))
                balance = parse_money(row.get("balance"))
                category = row.get("category") or "Uncategorized"
                existing_hash = row.get("import_hash")

                # Canadian Tire format
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

                category_map = {
                    "Grocery": "Groceries",
                    "Grocery Other": "Groceries",
                    "Restaurant": "Eating Out",
                    "Pharmacy": "Medical",
                    "Home stores": "Household",
                    "Business services": "Subscriptions",
                    "Gas": "Gas",

                    # Capital One
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

                # Capital One format
                if row.get("Transaction Date") and row.get("Card No."):
                    date_text = row.get("Transaction Date")
                    description = (row.get("Description") or "").strip()

                    dr = parse_money(row.get("Debit"))
                    cr = parse_money(row.get("Credit"))
                    balance = None

                    capone_category = (row.get("Category") or "").strip()
                    category = capone_category or "Uncategorized"

                    existing_hash = None

                category = category_map.get(category, category)

                transaction_date = parse_date(date_text)

                if transaction_date:
                    if latest_transaction_date is None or transaction_date > latest_transaction_date:
                        latest_transaction_date = transaction_date

                if not transaction_date or not description:
                    errors += 1
                    continue

                import_hash = existing_hash or build_hash(
                    transaction_date,
                    description,
                    dr,
                    cr,
                    balance,
                )

                duplicate_exists = BankTransaction.objects.filter(
                    account_name=account_name,
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
                    category=category,
                    import_hash=import_hash,
                    account_name=account_name,
                )

                imported += 1

            apply_category_rules()

            ImportLog.objects.create(
                file_name=csv_file.name,
                account_name=account_name,
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

def vehicle_summary(request):
    year = request.GET.get("year")

    vehicle_categories = [
        "Gas",
        "Vehicle Repairs",
        "Vehicle Maintenance",
        "Vehicle Insurance",
        "Car Payment",
        
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
    }

    return render(request, "banking/subscription_summary.html", context)