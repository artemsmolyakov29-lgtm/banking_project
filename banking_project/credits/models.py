from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from django.apps import apps


class CreditProduct(models.Model):
    """Продукты кредитования"""
    CREDIT_TYPES = (
        ('consumer', 'Потребительский кредит'),
        ('mortgage', 'Ипотека'),
        ('auto_loan', 'Автокредит'),
        ('business', 'Бизнес-кредит'),
        ('credit_card', 'Кредитная карта'),
    )

    PAYMENT_METHODS = (
        ('annuity', 'Аннуитетные платежи'),
        ('differentiated', 'Дифференцированные платежи'),
    )

    name = models.CharField(
        max_length=200,
        verbose_name='Название кредитного продукта'
    )
    credit_type = models.CharField(
        max_length=20,
        choices=CREDIT_TYPES,
        verbose_name='Тип кредита'
    )
    min_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Минимальная сумма'
    )
    max_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Максимальная сумма'
    )
    min_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Минимальная процентная ставка'
    )
    max_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Максимальная процентная ставка'
    )
    min_term_months = models.IntegerField(
        verbose_name='Минимальный срок (месяцев)'
    )
    max_term_months = models.IntegerField(
        verbose_name='Максимальный срок (месяцев)'
    )
    currency = models.ForeignKey(
        'accounts.Currency',
        on_delete=models.PROTECT,
        verbose_name='Валюта кредита'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='annuity',
        verbose_name='Метод платежа'
    )
    early_repayment_allowed = models.BooleanField(
        default=True,
        verbose_name='Досрочное погашение разрешено'
    )
    requires_collateral = models.BooleanField(
        default=False,
        verbose_name='Требуется залог'
    )
    requires_guarantor = models.BooleanField(
        default=False,
        verbose_name='Требуется поручитель'
    )
    min_credit_score = models.IntegerField(
        default=0,
        verbose_name='Минимальный кредитный рейтинг'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание продукта'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный продукт'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Кредитный продукт'
        verbose_name_plural = 'Кредитные продукты'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_credit_type_display()})"


class Credit(models.Model):
    STATUS_CHOICES = (
        ('application', 'Заявка'),
        ('under_review', 'На рассмотрении'),
        ('approved', 'Одобрен'),
        ('rejected', 'Отклонен'),
        ('active', 'Активный'),
        ('closed', 'Закрыт'),
        ('overdue', 'Просрочен'),
        ('default', 'Дефолт'),
    )

    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='credits',
        verbose_name='Клиент'
    )
    account = models.OneToOneField(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='credit_contract',
        verbose_name='Кредитный счет'
    )
    credit_product = models.ForeignKey(
        CreditProduct,
        on_delete=models.PROTECT,
        related_name='credits',
        verbose_name='Кредитный продукт'
    )
    application_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Номер заявки'
    )
    contract_number = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True,
        verbose_name='Номер договора'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Сумма кредита'
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Процентная ставка'
    )
    term_months = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Срок кредита (месяцев)'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='application',
        verbose_name='Статус кредита'
    )
    purpose = models.TextField(
        blank=True,
        verbose_name='Цель кредита'
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата выдачи'
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата окончания'
    )
    next_payment_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата следующего платежа'
    )
    remaining_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Остаток долга'
    )
    total_paid = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Всего выплачено'
    )
    overdue_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Просроченная сумма'
    )
    overdue_days = models.IntegerField(
        default=0,
        verbose_name='Дней просрочки'
    )
    approved_by = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_credits',
        verbose_name='Одобрил'
    )
    approved_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата одобрения'
    )
    rejection_reason = models.TextField(
        blank=True,
        verbose_name='Причина отказа'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Кредитный договор'
        verbose_name_plural = 'Кредитные договоры'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['application_number']),
            models.Index(fields=['contract_number']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['status']),
            models.Index(fields=['next_payment_date']),
        ]

    def __str__(self):
        return f"Кредит {self.contract_number or self.application_number} - {self.client.full_name}"

    def save(self, *args, **kwargs):
        if not self.application_number:
            self.application_number = self.generate_application_number()

        if self.status == 'approved' and not self.contract_number:
            self.contract_number = self.generate_contract_number()

        if self.start_date and self.term_months and not self.end_date:
            self.end_date = self.start_date + timedelta(days=self.term_months * 30)

        # Автоматическое обновление статуса при полном погашении
        if self.remaining_balance <= 0 and self.status == 'active':
            self.status = 'closed'

        super().save(*args, **kwargs)

    def generate_application_number(self):
        """Генерация уникального номера заявки"""
        import uuid
        return f"APP{uuid.uuid4().hex[:8].upper()}"

    def generate_contract_number(self):
        """Генерация уникального номера договора"""
        import uuid
        return f"CRD{uuid.uuid4().hex[:8].upper()}"

    def calculate_monthly_payment(self):
        """Расчет ежемесячного платежа"""
        if self.credit_product.payment_method == 'annuity':
            return self.calculate_annuity_payment()
        else:
            return self.calculate_differentiated_payment(1)  # Первый месяц для примера

    def calculate_annuity_payment(self):
        """Расчет аннуитетного платежа"""
        monthly_rate = self.interest_rate / 100 / 12
        coefficient = (monthly_rate * (1 + monthly_rate) ** self.term_months) / \
                      ((1 + monthly_rate) ** self.term_months - 1)
        payment = self.amount * Decimal(coefficient)
        return round(payment, 2)

    def calculate_differentiated_payment(self, month):
        """Расчет дифференцированного платежа для указанного месяца"""
        principal = self.amount / self.term_months
        remaining_balance = self.amount - (principal * (month - 1))
        interest = remaining_balance * (self.interest_rate / 100 / 12)
        return round(principal + interest, 2)

    def generate_payment_schedule(self):
        """Генерация полного графика платежей"""
        schedule = []
        balance = self.amount
        payment_date = self.start_date

        if self.credit_product.payment_method == 'annuity':
            monthly_payment = self.calculate_annuity_payment()

            for month in range(1, self.term_months + 1):
                interest_amount = balance * (self.interest_rate / 100 / 12)
                principal_amount = monthly_payment - interest_amount
                balance -= principal_amount

                if month == self.term_months:  # Последний платеж
                    principal_amount += balance  # Корректировка округления
                    balance = Decimal('0.00')

                schedule.append({
                    'payment_number': month,
                    'payment_date': payment_date,
                    'principal_amount': round(principal_amount, 2),
                    'interest_amount': round(interest_amount, 2),
                    'total_payment': round(principal_amount + interest_amount, 2),
                    'remaining_balance': max(round(balance, 2), 0)
                })

                payment_date += timedelta(days=30)  # Упрощенный расчет дат
        else:
            # Дифференцированные платежи
            principal = self.amount / self.term_months

            for month in range(1, self.term_months + 1):
                remaining_balance = self.amount - (principal * (month - 1))
                interest_amount = remaining_balance * (self.interest_rate / 100 / 12)
                total_payment = principal + interest_amount
                balance = remaining_balance - principal

                schedule.append({
                    'payment_number': month,
                    'payment_date': payment_date,
                    'principal_amount': round(principal, 2),
                    'interest_amount': round(interest_amount, 2),
                    'total_payment': round(total_payment, 2),
                    'remaining_balance': max(round(balance, 2), 0)
                })

                payment_date += timedelta(days=30)

        return schedule

    def get_next_payment(self):
        """Получение информации о следующем платеже"""
        if not self.next_payment_date:
            return None

        schedule = self.generate_payment_schedule()
        for payment in schedule:
            if payment['payment_date'] >= datetime.now().date():
                return payment
        return None

    # НОВЫЕ МЕТОДЫ ДЛЯ ПЛАТЕЖЕЙ
    def calculate_next_payment(self):
        """Расчет суммы следующего платежа"""
        if not self.next_payment_date:
            return Decimal('0.00')

        # Определяем номер следующего платежа
        paid_payments = self.payments.filter(status='completed').count()
        next_payment_number = paid_payments + 1

        if self.credit_product.payment_method == 'annuity':
            return self.calculate_annuity_payment()
        else:
            return self.calculate_differentiated_payment(next_payment_number)

    def calculate_penalty(self):
        """Расчет штрафов за просрочку"""
        if self.overdue_days <= 0:
            return Decimal('0.00')

        # Простой расчет: 0.1% от просроченной суммы за каждый день
        penalty_rate = Decimal('0.001')  # 0.1% в день
        return self.overdue_amount * penalty_rate * self.overdue_days

    def make_payment(self, amount, payment_method='manual', user=None):
        """Выполнение платежа по кредиту"""
        from django.db import transaction as db_transaction

        try:
            with db_transaction.atomic():
                # Получаем следующий ожидаемый платеж
                expected_payment = self.calculate_next_payment()
                penalty = self.calculate_penalty()
                total_due = expected_payment + penalty

                # Проверяем достаточно ли средств на счете клиента
                client_account = self.client.accounts.filter(
                    currency=self.account.currency,
                    status='active'
                ).first()

                if not client_account or client_account.balance < amount:
                    return False, "Недостаточно средств на счете"

                if amount < total_due:
                    return False, f"Недостаточная сумма платежа. Требуется: {total_due}"

                # Создаем запись о платеже
                paid_payments = self.payments.filter(status='completed').count()
                next_payment_number = paid_payments + 1

                payment = CreditPayment.objects.create(
                    credit=self,
                    payment_number=next_payment_number,
                    payment_date=timezone.now().date(),
                    due_date=self.next_payment_date or timezone.now().date(),
                    amount=amount,
                    principal_amount=min(expected_payment, amount - penalty),
                    interest_amount=max(Decimal('0.00'), expected_payment - min(expected_payment, amount - penalty)),
                    penalty_amount=penalty,
                    status='pending',
                    payment_method=payment_method,
                    processed_by=user
                )

                # Создаем транзакцию
                Transaction = apps.get_model('transactions', 'Transaction')
                transaction = Transaction.objects.create(
                    from_account=client_account,
                    to_account=self.account,
                    amount=amount,
                    currency=self.account.currency,
                    transaction_type='credit_payment',
                    status='completed',
                    description=f"Платеж по кредиту {self.contract_number}",
                    fee=Decimal('0.00'),
                    initiated_by=user
                )

                payment.transaction = transaction
                payment.status = 'completed'
                payment.processed_date = timezone.now()
                payment.save()

                # Обновляем балансы
                client_account.balance -= amount
                client_account.save()

                # Обновляем состояние кредита
                self.remaining_balance -= payment.principal_amount
                self.total_paid += amount

                # Обновляем дату следующего платежа
                if self.next_payment_date:
                    self.next_payment_date += timedelta(days=30)

                # Сбрасываем просрочку если платеж покрыл ее
                if amount >= total_due:
                    self.overdue_amount = Decimal('0.00')
                    self.overdue_days = 0
                    if self.status == 'overdue':
                        self.status = 'active'

                self.save()

                return True, "Платеж успешно выполнен"

        except Exception as e:
            return False, f"Ошибка при выполнении платежа: {str(e)}"

    def can_make_early_repayment(self):
        """Можно ли выполнить досрочное погашение"""
        return (self.credit_product.early_repayment_allowed and
                self.status == 'active' and
                self.remaining_balance > 0)

    def calculate_early_repayment(self):
        """Расчет суммы для досрочного погашения"""
        # Сумма остатка долга плюс проценты до конца периода
        return self.remaining_balance + self.calculate_penalty()


class CreditPayment(models.Model):
    PAYMENT_STATUS = (
        ('pending', 'Ожидает'),
        ('completed', 'Выполнен'),
        ('failed', 'Неуспешен'),
        ('partial', 'Частичный'),
    )

    PAYMENT_METHODS = (
        ('auto', 'Автоматический'),
        ('manual', 'Ручной'),
        ('transfer', 'Перевод'),
        ('cash', 'Наличные'),
    )

    credit = models.ForeignKey(
        Credit,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name='Кредит'
    )
    payment_number = models.IntegerField(
        verbose_name='Номер платежа'
    )
    payment_date = models.DateField(
        verbose_name='Дата платежа'
    )
    due_date = models.DateField(
        verbose_name='Дата выполнения'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Сумма платежа'
    )
    principal_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Сумма основного долга'
    )
    interest_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Сумма процентов'
    )
    penalty_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Сумма пени'
    )
    status = models.CharField(
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending',
        verbose_name='Статус платежа'
    )
    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHODS,
        default='auto',
        verbose_name='Способ оплаты'
    )
    transaction = models.ForeignKey(
        'transactions.Transaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Связанная транзакция'
    )
    processed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Обработал'
    )
    processed_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата обработки'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Платеж по кредиту'
        verbose_name_plural = 'Платежи по кредитам'
        ordering = ['credit', 'payment_number']
        unique_together = ['credit', 'payment_number']
        indexes = [
            models.Index(fields=['credit', 'payment_date']),
            models.Index(fields=['status', 'due_date']),
        ]

    def __str__(self):
        return f"Платеж {self.payment_number} по кредиту {self.credit.contract_number}"

    def is_overdue(self):
        """Проверка, просрочен ли платеж"""
        return self.due_date < timezone.now().date() and self.status != 'completed'

    def process_payment(self):
        """Обработка платежа"""
        if self.status == 'pending':
            try:
                # Списание средств со счета клиента
                account = self.credit.account
                if account.balance >= self.amount:
                    account.balance -= self.amount
                    account.save()

                    # Обновление остатка по кредиту
                    self.credit.remaining_balance -= self.principal_amount
                    self.credit.total_paid += self.amount
                    self.credit.save()

                    self.status = 'completed'
                    self.processed_date = timezone.now()
                    self.save()

                    return True
                else:
                    self.status = 'failed'
                    self.save()
                    return False

            except Exception as e:
                self.status = 'failed'
                self.save()
                return False
        return False


class CreditCollateral(models.Model):
    """Залоговое имущество по кредитам"""
    COLLATERAL_TYPES = (
        ('real_estate', 'Недвижимость'),
        ('vehicle', 'Транспортное средство'),
        ('equipment', 'Оборудование'),
        ('securities', 'Ценные бумаги'),
        ('other', 'Другое'),
    )

    credit = models.ForeignKey(
        Credit,
        on_delete=models.CASCADE,
        related_name='collaterals',
        verbose_name='Кредит'
    )
    collateral_type = models.CharField(
        max_length=20,
        choices=COLLATERAL_TYPES,
        verbose_name='Тип залога'
    )
    description = models.TextField(
        verbose_name='Описание залога'
    )
    estimated_value = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Оценочная стоимость'
    )
    document_number = models.CharField(
        max_length=100,
        verbose_name='Номер документа'
    )
    document_date = models.DateField(
        verbose_name='Дата документа'
    )
    is_insured = models.BooleanField(
        default=False,
        verbose_name='Застрахован'
    )
    insurance_company = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Страховая компания'
    )
    insurance_policy_number = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Номер страхового полиса'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Залог по кредиту'
        verbose_name_plural = 'Залоги по кредитам'

    def __str__(self):
        return f"{self.get_collateral_type_display()} - {self.credit}"