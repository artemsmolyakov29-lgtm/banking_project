from django import forms
from django.apps import apps


def get_card_model():
    return apps.get_model('cards', 'Card')


def get_client_model():
    return apps.get_model('clients', 'Client')


def get_account_model():
    return apps.get_model('accounts', 'Account')


class CardForm(forms.ModelForm):
    class Meta:
        model = get_card_model()
        fields = [
            'client', 'account', 'card_type', 'card_number', 'expiry_date',
            'cvv', 'payment_system', 'status', 'daily_limit', 'monthly_limit'
        ]
        widgets = {
            'card_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'cvv': forms.TextInput(attrs={'class': 'form-control', 'maxlength': '3'}),
            'daily_limit': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'monthly_limit': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'card_type': forms.Select(attrs={'class': 'form-select'}),
            'payment_system': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
            'account': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'card_type': 'Тип карты',
            'card_number': 'Номер карты',
            'expiry_date': 'Срок действия',
            'cvv': 'CVV код',
            'payment_system': 'Платежная система',
            'status': 'Статус',
            'daily_limit': 'Дневной лимит',
            'monthly_limit': 'Месячный лимит',
            'account': 'Привязанный счет',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Client = get_client_model()
        Account = get_account_model()
        self.fields['client'].queryset = Client.objects.filter(is_active=True)
        self.fields['account'].queryset = Account.objects.filter(status='active')

    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number')
        if card_number and len(card_number.replace(' ', '')) != 16:
            raise forms.ValidationError("Номер карты должен содержать 16 цифр")
        return card_number

    def clean_cvv(self):
        cvv = self.cleaned_data.get('cvv')
        if cvv and (len(cvv) != 3 or not cvv.isdigit()):
            raise forms.ValidationError("CVV должен содержать 3 цифры")
        return cvv