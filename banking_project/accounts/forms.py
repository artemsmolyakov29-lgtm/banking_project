from django import forms
from .models import Account


class AccountForm(forms.ModelForm):
    class Meta:
        model = Account
        fields = ['account_type', 'currency', 'balance', 'status', 'interest_rate']
        widgets = {
            'balance': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'interest_rate': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'account_type': forms.Select(attrs={'class': 'form-select'}),
            'currency': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
        }

    def clean_balance(self):
        balance = self.cleaned_data.get('balance')
        if balance and balance < 0:
            raise forms.ValidationError("Баланс не может быть отрицательным")
        return balance