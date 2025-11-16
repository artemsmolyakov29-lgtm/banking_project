from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from decimal import Decimal


def get_credit_model():
    return apps.get_model('credits', 'Credit')


def get_client_model():
    return apps.get_model('clients', 'Client')


def get_account_model():
    return apps.get_model('accounts', 'Account')


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


# НОВЫЕ ФОРМЫ ДЛЯ ПЛАТЕЖЕЙ ПО КРЕДИТАМ

class CreditPaymentForm(forms.Form):
    """Форма для внесения платежа по кредиту"""
    amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Введите сумму платежа'
        }),
        label='Сумма платежа'
    )
    payment_method = forms.ChoiceField(
        choices=[
            ('manual', 'Ручной платеж'),
            ('transfer', 'Банковский перевод'),
        ],
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Способ оплаты',
        initial='manual'
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Дополнительные примечания'
        }),
        label='Примечания'
    )

    def __init__(self, *args, **kwargs):
        self.credit = kwargs.pop('credit', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.credit:
            # Устанавливаем минимальную сумму платежа
            min_amount = self.credit.calculate_next_payment() + self.credit.calculate_penalty()
            self.fields['amount'].min_value = min_amount
            self.fields['amount'].widget.attrs['min'] = str(min_amount)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if not self.credit:
            return amount

        # Проверяем минимальную сумму платежа
        min_amount = self.credit.calculate_next_payment() + self.credit.calculate_penalty()
        if amount < min_amount:
            raise ValidationError(
                f"Минимальная сумма платежа: {min_amount}. "
                f"Включает основной платеж и штрафы за просрочку."
            )

        # Проверяем максимальную сумму (не больше остатка долга + 10%)
        max_amount = self.credit.remaining_balance * Decimal('1.1')
        if amount > max_amount:
            raise ValidationError(
                f"Сумма платежа не может превышать {max_amount} "
                f"(остаток долга + 10% на возможные проценты)"
            )

        return amount

    def save(self):
        """Сохранение платежа"""
        if not self.credit or not self.user:
            raise ValueError("Не указан кредит или пользователь")

        amount = self.cleaned_data['amount']
        payment_method = self.cleaned_data['payment_method']
        notes = self.cleaned_data.get('notes', '')

        success, message = self.credit.make_payment(amount, payment_method, self.user)

        if success:
            # Добавляем примечания к последнему платежу
            last_payment = self.credit.payments.last()
            if last_payment and notes:
                last_payment.notes = notes
                last_payment.save()

        return success, message


class EarlyRepaymentForm(forms.Form):
    """Форма для досрочного погашения кредита"""
    repayment_amount = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'readonly': 'readonly'
        }),
        label='Сумма досрочного погашения'
    )
    confirmation = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='Я подтверждаю досрочное погашение кредита'
    )

    def __init__(self, *args, **kwargs):
        self.credit = kwargs.pop('credit', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.credit:
            # Устанавливаем сумму досрочного погашения
            repayment_amount = self.credit.calculate_early_repayment()
            self.fields['repayment_amount'].initial = repayment_amount

    def clean(self):
        cleaned_data = super().clean()

        if not self.credit:
            raise ValidationError("Кредит не указан")

        if not self.credit.can_make_early_repayment():
            raise ValidationError("Досрочное погашение для этого кредита не разрешено")

        confirmation = cleaned_data.get('confirmation')
        if not confirmation:
            raise ValidationError("Необходимо подтвердить досрочное погашение")

        return cleaned_data

    def save(self):
        """Выполнение досрочного погашения"""
        if not self.credit or not self.user:
            raise ValueError("Не указан кредит или пользователь")

        repayment_amount = self.cleaned_data['repayment_amount']

        success, message = self.credit.make_payment(
            repayment_amount,
            'early_repayment',
            self.user
        )

        return success, message


class PaymentScheduleFilterForm(forms.Form):
    """Форма для фильтрации графика платежей"""
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='С даты'
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        }),
        label='По дату'
    )
    status = forms.ChoiceField(
        choices=[
            ('', 'Все статусы'),
            ('pending', 'Ожидающие'),
            ('completed', 'Выполненные'),
            ('failed', 'Неуспешные'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        label='Статус платежа'
    )

    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise ValidationError("Дата 'С' не может быть позже даты 'По'")

        return cleaned_data