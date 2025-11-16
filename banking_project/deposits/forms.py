from django import forms
from django.apps import apps
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
import datetime


def get_deposit_model():
    return apps.get_model('deposits', 'Deposit')


def get_client_model():
    return apps.get_model('clients', 'Client')


def get_account_model():
    return apps.get_model('accounts', 'Account')


def get_currency_model():
    return apps.get_model('accounts', 'Currency')


class DepositForm(forms.ModelForm):
    # НОВОЕ ПОЛЕ: Выбор счета клиента
    account = forms.ModelChoiceField(
        queryset=get_account_model().objects.none(),
        required=True,
        label="Счет для депозита",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = get_deposit_model()
        fields = [
            'client', 'account', 'deposit_type', 'amount', 'interest_rate', 'term_months',
            'start_date', 'end_date', 'capitalization', 'status'
        ]
        widgets = {
            'amount': forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'form-control',
                'min': '1000',
                'max': '100000000'
            }),
            'interest_rate': forms.NumberInput(attrs={
                'step': '0.01',
                'class': 'form-control',
                'min': '0.01',
                'max': '25.00'
            }),
            'term_months': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '60'
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'min': datetime.date.today().isoformat()
            }),
            'end_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'form-control',
                'readonly': 'readonly'  # Будет вычисляться автоматически
            }),
            'deposit_type': forms.Select(attrs={'class': 'form-select'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'capitalization': forms.Select(attrs={'class': 'form-select'}),
            'client': forms.Select(attrs={'class': 'form-select'}),
        }
        labels = {
            'deposit_type': 'Тип депозита',
            'amount': 'Сумма вклада',
            'interest_rate': 'Процентная ставка (%)',
            'term_months': 'Срок (месяцев)',
            'start_date': 'Дата начала',
            'end_date': 'Дата окончания',
            'capitalization': 'Капитализация процентов',
            'status': 'Статус депозита',
        }
        help_texts = {
            'amount': 'Минимальная сумма: 1 000 руб., максимальная: 100 000 000 руб.',
            'interest_rate': 'Процентная ставка годовых от 0.01% до 25.00%',
            'term_months': 'Срок депозита от 1 до 60 месяцев',
            'capitalization': 'Частота начисления и капитализации процентов',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        Client = get_client_model()
        Account = get_account_model()

        # Ограничиваем выбор активными клиентами
        self.fields['client'].queryset = Client.objects.filter(is_active=True)

        # Динамически заполняем счета в зависимости от выбранного клиента
        if 'client' in self.data:
            try:
                client_id = int(self.data.get('client'))
                self.fields['account'].queryset = Account.objects.filter(
                    client_id=client_id,
                    status='active'
                )
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            # Если форма редактирует существующий депозит
            self.fields['account'].queryset = Account.objects.filter(
                client=self.instance.client,
                status='active'
            )
        else:
            self.fields['account'].queryset = Account.objects.none()

        # НОВОЕ: Добавляем CSS классы для улучшенного UI
        for field_name, field in self.fields.items():
            if 'class' not in field.widget.attrs:
                field.widget.attrs['class'] = 'form-control'

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            raise ValidationError("Сумма вклада обязательна для заполнения")

        if amount <= 0:
            raise ValidationError("Сумма вклада должна быть положительной")

        min_amount = Decimal('1000')
        max_amount = Decimal('100000000')

        if amount < min_amount:
            raise ValidationError(f"Минимальная сумма вклада: {min_amount:,} руб.")

        if amount > max_amount:
            raise ValidationError(f"Максимальная сумма вклада: {max_amount:,} руб.")

        return amount

    def clean_interest_rate(self):
        interest_rate = self.cleaned_data.get('interest_rate')
        if interest_rate is None:
            raise ValidationError("Процентная ставка обязательна для заполнения")

        if interest_rate <= 0:
            raise ValidationError("Процентная ставка должна быть положительной")

        if interest_rate > Decimal('25.00'):
            raise ValidationError("Максимальная процентная ставка: 25.00%")

        return interest_rate

    def clean_term_months(self):
        term_months = self.cleaned_data.get('term_months')
        if term_months is None:
            raise ValidationError("Срок депозита обязателен для заполнения")

        if term_months < 1:
            raise ValidationError("Срок депозита должен быть не менее 1 месяца")

        if term_months > 60:
            raise ValidationError("Максимальный срок депозита: 60 месяцев")

        return term_months

    def clean_start_date(self):
        start_date = self.cleaned_data.get('start_date')
        if start_date and start_date < datetime.date.today():
            raise ValidationError("Дата начала не может быть в прошлом")
        return start_date

    def clean_end_date(self):
        end_date = self.cleaned_data.get('end_date')
        start_date = self.cleaned_data.get('start_date')

        if start_date and end_date:
            if end_date <= start_date:
                raise ValidationError("Дата окончания должна быть позже даты начала")

            # Проверяем, что срок соответствует term_months
            term_months = self.cleaned_data.get('term_months')
            if term_months:
                expected_end_date = start_date + datetime.timedelta(days=term_months * 30)
                if abs((end_date - expected_end_date).days) > 5:  # Допуск 5 дней
                    raise ValidationError(
                        f"Дата окончания должна соответствовать сроку депозита "
                        f"({term_months} месяцев)"
                    )

        return end_date

    def clean(self):
        cleaned_data = super().clean()

        # НОВАЯ ПРОВЕРКА: Проверяем, что на счете достаточно средств
        account = cleaned_data.get('account')
        amount = cleaned_data.get('amount')

        if account and amount:
            if account.balance < amount:
                raise ValidationError({
                    'amount': f"Недостаточно средств на счете. Доступно: {account.balance:,} руб."
                })

        # Автоматически вычисляем дату окончания, если не указана
        start_date = cleaned_data.get('start_date')
        term_months = cleaned_data.get('term_months')

        if start_date and term_months and not cleaned_data.get('end_date'):
            end_date = start_date + datetime.timedelta(days=term_months * 30)
            cleaned_data['end_date'] = end_date

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)

        # НОВАЯ ЛОГИКА: При создании нового депозита списываем средства со счета
        if not instance.pk and commit:
            account = self.cleaned_data.get('account')
            amount = self.cleaned_data.get('amount')

            if account and amount:
                # Списываем средства со счета
                account.balance -= amount
                account.save()

                # Создаем транзакцию для аудита
                Transaction = apps.get_model('transactions', 'Transaction')
                Transaction.objects.create(
                    from_account=account,
                    to_account=account,  # В реальной системе это был бы специальный счет депозитов
                    amount=amount,
                    currency=account.currency,
                    transaction_type='deposit_opening',
                    description=f'Открытие депозита #{instance.id}',
                    status='completed'
                )

        if commit:
            instance.save()

        return instance


# НОВАЯ ФОРМА: Форма для начисления процентов
class InterestAccrualForm(forms.Form):
    accrual_date = forms.DateField(
        label="Дата начисления",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control',
            'max': datetime.date.today().isoformat()
        }),
        initial=datetime.date.today
    )

    deposit = forms.ModelChoiceField(
        queryset=get_deposit_model().objects.none(),
        required=False,
        label="Конкретный депозит (опционально)",
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Оставьте пустым для начисления по всем активным депозитам"
    )

    dry_run = forms.BooleanField(
        required=False,
        initial=True,
        label="Тестовый режим",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Показать какие проценты будут начислены без реального начисления"
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        Deposit = get_deposit_model()

        # Ограничиваем выбор только активными депозитами
        self.fields['deposit'].queryset = Deposit.objects.filter(
            status='active',
            start_date__lte=datetime.date.today(),
            end_date__gte=datetime.date.today()
        ).select_related('client', 'account')

    def clean_accrual_date(self):
        accrual_date = self.cleaned_data.get('accrual_date')
        if accrual_date > datetime.date.today():
            raise ValidationError("Дата начисления не может быть в будущем")
        return accrual_date


# НОВАЯ ФОРМА: Форма для фильтрации депозитов в отчетах
class DepositFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('', 'Все статусы'),
        ('active', 'Активные'),
        ('closed', 'Закрытые'),
        ('matured', 'Срок истек'),
    ]

    DEPOSIT_TYPE_CHOICES = [
        ('', 'Все типы'),
        ('demand', 'До востребования'),
        ('term', 'Срочный'),
        ('savings', 'Сберегательный'),
    ]

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        label="Статус депозита",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    deposit_type = forms.ChoiceField(
        choices=DEPOSIT_TYPE_CHOICES,
        required=False,
        label="Тип депозита",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    min_amount = forms.DecimalField(
        required=False,
        label="Минимальная сумма",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Минимальная сумма'
        })
    )

    max_amount = forms.DecimalField(
        required=False,
        label="Максимальная сумма",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': 'Максимальная сумма'
        })
    )

    date_from = forms.DateField(
        required=False,
        label="С даты",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    date_to = forms.DateField(
        required=False,
        label="По дату",
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'form-control'
        })
    )

    def clean(self):
        cleaned_data = super().clean()
        min_amount = cleaned_data.get('min_amount')
        max_amount = cleaned_data.get('max_amount')

        if min_amount and max_amount and min_amount > max_amount:
            raise ValidationError("Минимальная сумма не может быть больше максимальной")

        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise ValidationError("Дата 'с' не может быть позже даты 'по'")

        return cleaned_data


# НОВАЯ ФОРМА: Форма для закрытия депозита
class DepositCloseForm(forms.Form):
    early_close = forms.BooleanField(
        required=False,
        label="Досрочное закрытие",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Отметьте, если закрываете депозит досрочно"
    )

    reason = forms.CharField(
        required=False,
        label="Причина закрытия",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Укажите причину закрытия депозита...'
        }),
        help_text="Обязательно для досрочного закрытия"
    )

    def clean(self):
        cleaned_data = super().clean()
        early_close = cleaned_data.get('early_close')
        reason = cleaned_data.get('reason')

        if early_close and not reason:
            raise ValidationError({
                'reason': "При досрочном закрытии необходимо указать причину"
            })

        return cleaned_data