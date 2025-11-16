from django import forms
from django.apps import apps


def get_credit_model():
    return apps.get_model('credits', 'Credit')


def get_client_model():
    return apps.get_model('clients', 'Client')


class CreditForm(forms.ModelForm):
    class Meta:
        model = get_credit_model()
        fields = [
            'client', 'credit_type', 'amount', 'interest_rate', 'term_months',
            'start_date', 'end_date', 'purpose', 'status', 'payment_schedule'
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'interest_rate': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'term_months': forms.NumberInput(attrs={'class': 'form-control'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'credit_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'payment_schedule': forms.Select(attrs={'class': 'form-select'}),
            'purpose': forms.TextInput(attrs={'class': 'form-control'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'credit_type': 'Тип кредита',
            'amount': 'Сумма кредита',
            'interest_rate': 'Процентная ставка',
            'term_months': 'Срок (месяцев)',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания',
            'purpose': 'Цель кредита',
            'status': 'Статус',
            'payment_schedule': 'График платежей',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Client = get_client_model()
        self.fields['client'].queryset = Client.objects.filter(is_active=True)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount <= 0:
            raise forms.ValidationError("Сумма кредита должна быть положительной")
        return amount

    def clean_interest_rate(self):
        interest_rate = self.cleaned_data.get('interest_rate')
        if interest_rate and interest_rate <= 0:
            raise forms.ValidationError("Процентная ставка должна быть положительной")
        return interest_rate