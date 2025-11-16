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
            'account', 'card_number', 'cardholder_name', 'expiry_date',
            'card_type', 'card_system', 'status', 'daily_limit', 'is_virtual'
        ]
        widgets = {
            'card_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': '0000 0000 0000 0000'
            }),
            'expiry_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control'
            }),
            'cardholder_name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'IVAN IVANOV'
            }),
            'daily_limit': forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'form-control'
            }),
            'card_type': forms.Select(attrs={'class': 'form-select'}),
            'card_system': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'account': forms.Select(attrs={'class': 'form-select'}),
            'is_virtual': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'card_type': 'Тип карты',
            'card_number': 'Номер карты',
            'cardholder_name': 'Имя держателя карты',
            'expiry_date': 'Срок действия',
            'card_system': 'Платежная система',
            'status': 'Статус',
            'daily_limit': 'Дневной лимит',
            'account': 'Привязанный счет',
            'is_virtual': 'Виртуальная карта',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Account = get_account_model()
        self.fields['account'].queryset = Account.objects.filter(status='active')

    def clean_card_number(self):
        card_number = self.cleaned_data.get('card_number')
        if card_number:
            # Удаляем пробелы и проверяем длину
            clean_number = card_number.replace(' ', '')
            if len(clean_number) != 16 or not clean_number.isdigit():
                raise forms.ValidationError("Номер карты должен содержать 16 цифр")
            return clean_number
        return card_number

    def clean_expiry_date(self):
        expiry_date = self.cleaned_data.get('expiry_date')
        if expiry_date:
            from datetime import date
            if expiry_date < date.today():
                raise forms.ValidationError("Срок действия карты не может быть в прошлом")
        return expiry_date

    def clean_daily_limit(self):
        daily_limit = self.cleaned_data.get('daily_limit')
        if daily_limit and daily_limit <= 0:
            raise forms.ValidationError("Дневной лимит должен быть положительным числом")
        return daily_limit


class CardBlockForm(forms.Form):
    """
    Форма для блокировки карты
    """
    block_reason = forms.ChoiceField(
        choices=get_card_model().BLOCK_REASONS,
        label='Причина блокировки',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    block_description = forms.CharField(
        required=False,
        label='Дополнительное описание',
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Дополнительная информация о причине блокировки...'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Динамически получаем выбор причин из модели
        self.fields['block_reason'].choices = get_card_model().BLOCK_REASONS


class CardLimitForm(forms.ModelForm):
    """
    Форма для изменения лимитов карты
    """
    class Meta:
        model = get_card_model()
        fields = ['daily_limit']
        widgets = {
            'daily_limit': forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'form-control',
                'min': '0'
            })
        }
        labels = {
            'daily_limit': 'Дневной лимит'
        }

    def clean_daily_limit(self):
        daily_limit = self.cleaned_data.get('daily_limit')
        if daily_limit and daily_limit < 0:
            raise forms.ValidationError("Лимит не может быть отрицательным")
        return daily_limit