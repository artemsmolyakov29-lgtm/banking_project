from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import datetime


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

    class Meta:
        verbose_name = 'Депозит'
        verbose_name_plural = 'Депозиты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['client', 'status']),
            models.Index(fields=['end_date']),
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

        # Расчет дней с начала депозита
        days_passed = (as_of_date - self.start_date).days

        # Годовые проценты пересчитываем в дневные
        daily_rate = self.interest_rate / 100 / 365
        interest = self.amount * Decimal(daily_rate) * days_passed

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

    def __str__(self):
        return f"Проценты по депозиту {self.deposit.id} за период {self.period_start} - {self.period_end}"