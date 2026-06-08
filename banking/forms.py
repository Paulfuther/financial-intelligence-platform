from django import forms


class BankImportForm(forms.Form):
    csv_file = forms.FileField(label="Bank CSV file")