from django.contrib import admin, messages
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils.html import format_html, format_html_join

from .models import Company, Filing, FinancialFact, FinancialMetric
from .services.company_importer import sync_company


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    change_form_template = "admin/research/company/change_form.html"

    list_display = (
        "ticker",
        "name",
        "exchange",
        "sic_description",
        "filing_count",
        "financial_fact_count",
        "last_sec_sync",
    )

    search_fields = (
        "ticker",
        "name",
        "cik",
    )

    ordering = ("ticker",)

    readonly_fields = (
        "filing_count_display",
        "latest_filing_display",
        "recent_filings_display",
        "last_sec_sync",
        "created_at",
        "updated_at",
    )

    actions = ("refresh_from_sec",)

    fieldsets = (
        (
            "Company",
            {
                "fields": (
                    ("ticker", "cik"),
                    "name",
                    "exchange",
                ),
            },
        ),
        (
            "SEC Information",
            {
                "fields": (
                    ("sic", "sic_description"),
                    (
                        "fiscal_year_end",
                        "state_of_incorporation",
                    ),
                    "last_sec_sync",
                ),
            },
        ),
        (
            "Filing Summary",
            {
                "fields": (
                    "filing_count_display",
                    "latest_filing_display",
                    "recent_filings_display",
                ),
            },
        ),
        (
            "System Information",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    def get_urls(self):
        default_urls = super().get_urls()

        custom_urls = [
            path(
                "<path:object_id>/refresh-sec/",
                self.admin_site.admin_view(self.refresh_company_view),
                name="research_company_refresh",
            ),
        ]

        return custom_urls + default_urls

    def refresh_company_view(
        self,
        request,
        object_id,
    ):
        company = get_object_or_404(
            Company,
            pk=object_id,
        )

        if request.method != "POST":
            self.message_user(
                request,
                "SEC refresh must be submitted from the company page.",
                level=messages.WARNING,
            )

            return redirect(
                reverse(
                    "admin:research_company_change",
                    args=[company.pk],
                )
            )

        try:
            result = sync_company(company)

            filing_count = result.get(
                "filings_imported",
                0,
            )

            facts_created = result.get(
                "financial_facts_created",
                0,
            )

            facts_updated = result.get(
                "financial_facts_updated",
                0,
            )

            self.message_user(
                request,
                (
                    f"{company.ticker} refreshed successfully. "
                    f"{filing_count} filing(s), "
                    f"{facts_created} financial fact(s) created, "
                    f"{facts_updated} updated."
                ),
                level=messages.SUCCESS,
            )

        except Exception as error:
            self.message_user(
                request,
                (f"SEC refresh failed for {company.ticker}: {error}"),
                level=messages.ERROR,
            )

        return redirect(
            reverse(
                "admin:research_company_change",
                args=[company.pk],
            )
        )

    @admin.action(description="Refresh selected companies from SEC")
    def refresh_from_sec(
        self,
        request,
        queryset,
    ):
        updated_count = 0
        filing_count = 0
        failed_companies = []

        for company in queryset:
            try:
                result = sync_company(company)

                updated_count += 1
                filing_count += result.get(
                    "filings_imported",
                    0,
                )

            except Exception as error:
                failed_companies.append(f"{company.ticker}: {error}")

        if updated_count:
            self.message_user(
                request,
                (
                    f"{updated_count} company record(s) refreshed. "
                    f"{filing_count} filing record(s) processed."
                ),
                level=messages.SUCCESS,
            )

        if failed_companies:
            self.message_user(
                request,
                "SEC refresh failed for: " + "; ".join(failed_companies),
                level=messages.ERROR,
            )

    @admin.display(description="Filings")
    def filing_count(self, company):
        return company.filings.count()

    @admin.display(description="Financial facts")
    def financial_fact_count(self, company):

        count = company.financial_facts.count()

        facts_url = (
            reverse("admin:research_financialfact_changelist")
            + f"?company__id__exact={company.pk}"
        )

        return format_html(
            '<a href="{}">{} fact(s)</a>',
            facts_url,
            count,
        )

    @admin.display(description="Total filing records")
    def filing_count_display(self, company):
        count = company.filings.count()

        filings_url = (
            reverse("admin:research_filing_changelist")
            + f"?company__id__exact={company.pk}"
        )

        return format_html(
            '<a href="{}">{} filing record(s)</a>',
            filings_url,
            count,
        )

    @admin.display(description="Latest filing")
    def latest_filing_display(self, company):
        filing = company.filings.order_by(
            "-filing_date",
            "-acceptance_datetime",
        ).first()

        if not filing:
            return "No filings imported."

        if filing.filing_url:
            return format_html(
                '<a href="{}" target="_blank">{} — filed {}</a>',
                filing.filing_url,
                filing.form,
                filing.filing_date,
            )

        return f"{filing.form} — filed {filing.filing_date}"

    @admin.display(description="Recent filings")
    def recent_filings_display(self, company):
        filings = company.filings.order_by(
            "-filing_date",
            "-acceptance_datetime",
        )[:15]

        if not filings:
            return "No filings imported."

        rows = []

        for filing in filings:
            admin_url = reverse(
                "admin:research_filing_change",
                args=[filing.pk],
            )

            sec_link = ""

            if filing.filing_url:
                sec_link = format_html(
                    ' · <a href="{}" target="_blank">Open SEC filing</a>',
                    filing.filing_url,
                )

            rows.append(
                (
                    admin_url,
                    filing.form,
                    filing.filing_date,
                    filing.report_date or "—",
                    sec_link,
                )
            )

        return format_html(
            '<table style="width:100%; '
            'border-collapse:collapse;">'
            "<thead>"
            "<tr>"
            '<th style="text-align:left; padding:8px;">Form</th>'
            '<th style="text-align:left; padding:8px;">Filed</th>'
            '<th style="text-align:left; padding:8px;">Report date</th>'
            '<th style="text-align:left; padding:8px;">Links</th>'
            "</tr>"
            "</thead>"
            "<tbody>{}</tbody>"
            "</table>",
            format_html_join(
                "",
                (
                    "<tr>"
                    '<td style="padding:8px; '
                    'border-top:1px solid #ddd;">'
                    '<a href="{}"><strong>{}</strong></a>'
                    "</td>"
                    '<td style="padding:8px; '
                    'border-top:1px solid #ddd;">{}</td>'
                    '<td style="padding:8px; '
                    'border-top:1px solid #ddd;">{}</td>'
                    '<td style="padding:8px; '
                    'border-top:1px solid #ddd;">{}</td>'
                    "</tr>"
                ),
                rows,
            ),
        )


@admin.register(Filing)
class FilingAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "form",
        "filing_date",
        "report_date",
        "is_xbrl",
        "is_inline_xbrl",
    )

    list_filter = (
        "company",
        "form",
        "is_xbrl",
        "is_inline_xbrl",
        "filing_date",
    )

    search_fields = (
        "company__ticker",
        "company__name",
        "accession_number",
        "form",
        "primary_document",
    )

    ordering = (
        "-filing_date",
        "-acceptance_datetime",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )


@admin.register(FinancialFact)
class FinancialFactAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "statement_type",
        "concept_display",
        "fiscal_year",
        "fiscal_period",
        "end_date",
        "formatted_value",
        "unit",
        "form",
    )

    list_filter = (
        "company",
        "statement_type",
        "fiscal_year",
        "fiscal_period",
        "form",
        "unit",
        "taxonomy",
    )

    search_fields = (
        "company__ticker",
        "company__name",
        "concept",
        "label",
        "description",
        "accession_number",
    )

    ordering = (
        "company__ticker",
        "-end_date",
        "statement_type",
        "concept",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    list_select_related = (
        "company",
        "filing",
    )

    date_hierarchy = "end_date"

    list_per_page = 100

    fieldsets = (
        (
            "Company and filing",
            {
                "fields": (
                    "company",
                    "filing",
                    "accession_number",
                    "form",
                ),
            },
        ),
        (
            "Financial concept",
            {
                "fields": (
                    ("taxonomy", "concept"),
                    "label",
                    "description",
                    "statement_type",
                ),
            },
        ),
        (
            "Value",
            {
                "fields": (
                    ("value", "unit"),
                    ("start_date", "end_date"),
                    ("fiscal_year", "fiscal_period"),
                    ("filed_date", "frame"),
                ),
            },
        ),
        (
            "System Information",
            {
                "classes": ("collapse",),
                "fields": (
                    "created_at",
                    "updated_at",
                ),
            },
        ),
    )

    @admin.display(description="Concept")
    def concept_display(self, fact):
        return fact.label or fact.concept

    @admin.display(
        description="Value",
        ordering="value",
    )
    def formatted_value(self, fact):
        value = fact.value

        if fact.unit == "USD":
            return f"${value:,.0f}"

        if fact.unit == "USD/shares":
            return f"${value:,.2f}"

        if fact.unit == "shares":
            return f"{value:,.0f}"

        return f"{value:,.4f}"

@admin.register(FinancialMetric)
class FinancialMetricAdmin(admin.ModelAdmin):
    list_display = (
        "company",
        "metric",
        "fiscal_year",
        "fiscal_period",
        "formatted_value",
        "unit",
        "end_date",
    )

    list_filter = (
        "company",
        "metric",
        "fiscal_year",
        "fiscal_period",
        "unit",
    )

    search_fields = (
        "company__ticker",
        "company__name",
        "metric",
        "source_concept",
        "accession_number",
    )

    ordering = (
        "company__ticker",
        "-fiscal_year",
        "fiscal_period",
        "metric",
    )

    list_select_related = (
        "company",
        "source_fact",
    )

    list_per_page = 100

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    @admin.display(
        description="Value",
        ordering="value",
    )
    def formatted_value(self, metric):
        if metric.unit == "USD":
            return f"${metric.value:,.0f}"

        if metric.unit == "USD/shares":
            return f"${metric.value:,.2f}"

        if metric.unit == "shares":
            return f"{metric.value:,.0f}"

        return f"{metric.value:,.4f}"
