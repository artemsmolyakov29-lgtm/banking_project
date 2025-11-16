from django import forms
from django.core.exceptions import ValidationError
from decimal import Decimal
from django.apps import apps
from .models import Transaction


def get_account_model():
    """Ленивая загрузка модели Account"""
    return apps.get_model('accounts', 'Account')


class TransferForm(forms.ModelForm):
    from_account_number = forms.CharField(
        label='Номер счета отправителя',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    to_account_number = forms.CharField(
        label='Номер счета получателя',
        max_length=20,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})
    )
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        label='Описание перевода'
    )

    class Meta:
        model = Transaction
        fields = ['amount', 'description']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

    def clean(self):
        cleaned_data = super().clean()
        from_account_number = cleaned_data.get('from_account_number')
        to_account_number = cleaned_data.get('to_account_number')
        amount = cleaned_data.get('amount')

        if from_account_number and to_account_number:
            if from_account_number == to_account_number:
                raise ValidationError("Нельзя переводить средства на тот же счет")

            try:
                Account = get_account_model()
                # Получаем счета
                from_account = Account.objects.get(account_number=from_account_number, status='active')
                to_account = Account.objects.get(account_number=to_account_number, status='active')

                # Проверяем права доступа для клиентов
                if self.user and self.user.role == 'client':
                    client_accounts = self.user.client.accounts.all()
                    if from_account not in client_accounts:
                        raise ValidationError("У вас нет доступа к этому счету отправителя")

                # Проверяем валюту счетов
                if from_account.currency != to_account.currency:
                    raise ValidationError("Переводы между счетами в разных валютах временно не поддерживаются")

                # Проверяем достаточно ли средств (учитывая возможную комиссию)
                fee = self.calculate_fee(amount)
                total_amount = amount + fee

                if from_account.balance < total_amount:
                    raise ValidationError(
                        f"Недостаточно средств на счете. Доступно: {from_account.balance}, требуется: {total_amount}")

                # Сохраняем объекты счетов для использования в save
                self.from_account = from_account
                self.to_account = to_account
                self.fee = fee
                self.currency = from_account.currency

            except Account.DoesNotExist:
                raise ValidationError("Один из счетов не найден или неактивен")

        return cleaned_data

    def calculate_fee(self, amount):
        """Расчет комиссии (1% от суммы, но не менее 10 и не более 1000)"""
        fee = amount * Decimal('0.01')
        return max(Decimal('10'), min(fee, Decimal('1000')))

    def save(self, commit=True):
        transaction = super().save(commit=False)
        transaction.from_account = self.from_account
        transaction.to_account = self.to_account
        transaction.transaction_type = 'transfer'
        transaction.fee = self.fee
        transaction.currency = self.currency
        transaction.description = self.cleaned_data['description']
        transaction.initiated_by = self.user

        if commit:
            transaction.save()
            # Выполняем перевод
            if transaction.execute_transfer():
                return transaction
            else:
                raise ValidationError("Ошибка при выполнении перевода")

        return transaction