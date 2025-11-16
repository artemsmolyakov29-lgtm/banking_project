from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import datetime
from django.utils import timezone


class Deposit(models.Model):
    DEPOSIT_TYPES = (
        ('demand', 'До востребования'),
        ('term', 'Срочный'),
        ('savings', 'Сберегательный'),
    )

    STATUS_CHOICES = (
        ('active', 'Активный'),
        ('closed', 'Закрыт'),
        ('matured', 'Срок истек'),
    )

    CAPITALIZATION_CHOICES = (
        ('monthly', 'Ежемесячная'),
        ('quarterly', 'Ежеквартальная'),
        ('end_of_term', 'В конце срока'),
        ('none', 'Без капитализации'),
    )

    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='deposits',
        verbose_name='Клиент'
    )
    account = models.OneToOneField(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='deposit',
        verbose_name='Счет'
    )
    deposit_type = models.CharField(
        max_length=20,
        choices=DEPOSIT_TYPES,
        default='term',
        verbose_name='Тип депозита'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Сумма депозита'
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Процентная ставка'
    )
    term_months = models.IntegerField(
        validators=[MinValueValidator(1)],
        verbose_name='Срок (месяцев)'
    )
    capitalization = models.CharField(
        max_length=20,
        choices=CAPITALIZATION_CHOICES,
        default='monthly',
        verbose_name='Капитализация'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус'
    )
    start_date = models.DateField(
        verbose_name='Дата открытия'
    )
    end_date = models.DateField(
        verbose_name='Дата закрытия'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    # Новое поле для отслеживания даты последнего начисления
    last_interest_accrual = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата последнего начисления процентов'
    )

    class Meta:
        verbose_name = 'Депозит'
        verbose_name_plural = 'Депозиты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['end_date']),
            models.Index(fields=['last_interest_accrual']),
        ]

    def __str__(self):
        return f"Депозит {self.id} - {self.client.full_name} ({self.amount} {self.account.currency.code})"

    def calculate_interest(self, as_of_date=None):
        """
        Расчет начисленных процентов на указанную дату
        """
        if as_of_date is None:
            as_of_date = datetime.date.today()

        if as_of_date < self.start_date:
            return Decimal('0.00')

        # Расчет дней с начала депозита или последнего начисления
        if self.last_interest_accrual and self.last_interest_accrual > self.start_date:
            start_date = self.last_interest_accrual
        else:
            start_date = self.start_date

        days_passed = (as_of_date - start_date).days

        if days_passed <= 0:
            return Decimal('0.00')

        # Годовые проценты пересчитываем в дневные
        daily_rate = self.interest_rate / Decimal('100') / Decimal('365')
        interest = self.amount * daily_rate * Decimal(days_passed)

        return round(interest, 2)

    def get_total_amount(self, as_of_date=None):
        """
        Полная сумма с учетом начисленных процентов
        """
        interest = self.calculate_interest(as_of_date)
        return self.amount + interest

    def is_mature(self):
        """Проверка, истек ли срок депозита"""
        return datetime.date.today() >= self.end_date

    def can_close_early(self):
        """Можно ли закрыть досрочно"""
        return self.deposit_type != 'demand' and not self.is_mature()

    def close_deposit(self):
        """Закрытие депозита"""
        if self.status == 'active':
            self.status = 'closed'
            self.save()
            return True
        return False

    def get_expected_interest(self, as_of_date=None):
        """
        Расчет ожидаемых процентов на указанную дату
        """
        if as_of_date is None:
            as_of_date = datetime.date.today()

        if as_of_date < self.start_date:
            return Decimal('0.00')

        # Используем улучшенный расчет с учетом капитализации
        return self.calculate_interest(as_of_date)

    def get_next_accrual_date(self):
        """
        Дата следующего начисления процентов
        """
        today = datetime.date.today()

        if self.capitalization == 'monthly':
            # Следующее начисление в конце текущего месяца
            next_month = today.replace(day=28) + datetime.timedelta(days=4)
            return next_month - datetime.timedelta(days=next_month.day)

        elif self.capitalization == 'quarterly':
            # Следующее начисление в конце текущего квартала
            quarter = (today.month - 1) // 3 + 1
            quarter_end_month = quarter * 3
            quarter_end_year = today.year
            if quarter_end_month > 12:
                quarter_end_month = 12
            return datetime.date(quarter_end_year, quarter_end_month, 1) + datetime.timedelta(days=-1)

        elif self.capitalization == 'end_of_term':
            # Начисление только в конце срока
            return self.end_date

        else:  # 'none'
            # Для депозитов без капитализации - начисление в конце месяца
            next_month = today.replace(day=28) + datetime.timedelta(days=4)
            return next_month - datetime.timedelta(days=next_month.day)

    def get_interest_history(self):
        """История начисленных процентов"""
        return self.interest_payments.all().order_by('-payment_date')

    def get_total_accrued_interest(self):
        """Сумма всех начисленных процентов"""
        total = self.interest_payments.aggregate(total=models.Sum('amount'))['total']
        return total or Decimal('0.00')

    def can_accrue_interest(self):
        """Можно ли начислять проценты"""
        today = datetime.date.today()
        return (
                self.status == 'active' and
                self.start_date <= today <= self.end_date and
                (self.last_interest_accrual is None or self.last_interest_accrual < today)
        )


class DepositInterestPayment(models.Model):
    """
    История начисления процентов по депозиту
    """
    deposit = models.ForeignKey(
        Deposit,
        on_delete=models.CASCADE,
        related_name='interest_payments',
        verbose_name='Депозит'
    )
    period_start = models.DateField(
        verbose_name='Начало периода'
    )
    period_end = models.DateField(
        verbose_name='Конец периода'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Сумма процентов'
    )
    payment_date = models.DateField(
        verbose_name='Дата начисления'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания записи'
    )

    class Meta:
        verbose_name = 'Начисление процентов по депозиту'
        verbose_name_plural = 'Начисления процентов по депозитам'
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['deposit', 'payment_date']),
        ]

    def __str__(self):
        return f"Проценты по депозиту {self.deposit.id} за период {self.period_start} - {self.period_end}"