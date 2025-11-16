from django import forms
from django.apps import apps


def get_deposit_model():
    return apps.get_model('deposits', 'Deposit')


def get_client_model():
    return apps.get_model('clients', 'Client')


class DepositForm(forms.ModelForm):
    class Meta:
        model = get_deposit_model()
        fields = [
            'client', 'deposit_type', 'amount', 'interest_rate', 'term_months',
            'start_date', 'end_date', 'capitalization', 'status'
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'interest_rate': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'term_months': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'deposit_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'capitalization': forms.Select(attrs={'class': 'form-select'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'deposit_type': 'Тип депозита',
            'amount': 'Сумма вклада',
            'interest_rate': 'Процентная ставка',
            'term_months': 'Срок (месяцев)',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания',
            'capitalization': 'Капитализация',
            'status': 'Статус',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Client = get_client_model()
        self.fields['client'].queryset = Client.objects.filter(is_active=True)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError("Сумма вклада должна быть положительной")
        return amount