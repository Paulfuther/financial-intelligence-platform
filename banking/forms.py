from django import forms

ACCOUNT_CHOICES = [
    ("Personal", "Personal"),
    ("Corporate Bank", "Corporate Bank"),
    ("Corporate Credit Card", "Corporate Credit Card"),
]


class BankImportForm(forms.Form):
    account_name = forms.ChoiceField(
        choices=ACCOUNT_CHOICES,
        label="Account",
    )

    csv_file = forms.FileField(
        label="Bank CSV file",
    )