from django import forms

ACCOUNT_CHOICES = [
    ("Personal", "Personal"),
    ("Corporate Bank", "Corporate Bank"),
    ("Corporate Credit Card", "Corporate Credit Card"),
    ("Capital One Card", "Capital One Card"),
    ("Canadian Tire Mastercard", "Canadian Tire Mastercard"),
]


class MirrorCleanupForm(forms.Form):
    source_account = forms.ChoiceField(
        choices=ACCOUNT_CHOICES,
        label="Remove copies from",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    target_account = forms.ChoiceField(
        choices=ACCOUNT_CHOICES,
        label="Keep rows on",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    match_import_log_id = forms.IntegerField(
        required=False,
        label="Reference import log ID",
        help_text="Optional. Limit matching to rows from this import (e.g. 99).",
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    transaction_date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    transaction_date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )


class BankImportForm(forms.Form):
    account_name = forms.ChoiceField(
        choices=ACCOUNT_CHOICES,
        label="Account",
    )

    csv_file = forms.FileField(
    widget=forms.ClearableFileInput(attrs={
        "class": "form-control",
        "accept": ".csv,.txt",
    })
)