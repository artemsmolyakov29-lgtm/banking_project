from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
import random
import string


class Currency(models.Model):
    code = models.CharField(
        max_length=3,
        unique=True,
        verbose_name='Код валюты'
    )
    name = models.CharField(
        max_length=50,
        verbose_name='Название валюты'
    )
    symbol = models.CharField(
        max_length=5,
        verbose_name='Символ'
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=1.0,
        verbose_name='Курс к базовой валюте'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активная валюта'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Валюта'
        verbose_name_plural = 'Валюты'
        ordering = ['code']

    def __str__(self):
        return f"{self.code} - {self.name}"


class Account(models.Model):
    ACCOUNT_TYPES = (
        ('checking', 'Расчетный счет'),
        ('savings', 'Сберегательный счет'),
        ('credit', 'Кредитный счет'),
        ('deposit', 'Депозитный счет'),
        ('corporate', 'Корпоративный счет'),
    )

    STATUS_CHOICES = (
        ('active', 'Активный'),
        ('blocked', 'Заблокирован'),
        ('closed', 'Закрыт'),
        ('dormant', 'Неактивный'),
    )

    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.CASCADE,
        related_name='accounts',
        verbose_name='Клиент'
    )
    account_number = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Номер счета'
    )
    account_type = models.CharField(
        max_length=20,
        choices=ACCOUNT_TYPES,
        verbose_name='Тип счета'
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.PROTECT,
        verbose_name='Валюта счета'
    )
    balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        validators=[MinValueValidator(Decimal('0.00'))],
        verbose_name='Текущий баланс'
    )
    available_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Доступный баланс'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус счета'
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.00,
        verbose_name='Процентная ставка'
    )
    overdraft_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Лимит овердрафта'
    )
    opening_date = models.DateField(
        auto_now_add=True,
        verbose_name='Дата открытия'
    )
    closing_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата закрытия'
    )
    last_activity_date = models.DateField(
        auto_now=True,
        verbose_name='Дата последней активности'
    )
    is_default = models.BooleanField(
        default=False,
        verbose_name='Счет по умолчанию'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание счета'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Создал'
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
        verbose_name = 'Банковский счет'
        verbose_name_plural = 'Банковские счета'
        ordering = ['-opening_date']
        indexes = [
            models.Index(fields=['account_number']),
            models.Index(fields=['client', 'status']),
            models.Index(fields=['account_type', 'status']),
            models.Index(fields=['opening_date']),
        ]

    def __str__(self):
        return f"{self.account_number} - {self.client.full_name} ({self.balance} {self.currency.code})"

    def save(self, *args, **kwargs):
        if not self.account_number:
            self.account_number = self.generate_account_number()

        # Автоматический расчет доступного баланса
        self.available_balance = self.balance + self.overdraft_limit

        # Если счет закрывается, устанавливаем дату закрытия
        if self.status == 'closed' and not self.closing_date:
            from django.utils import timezone
            self.closing_date = timezone.now().date()

        super().save(*args, **kwargs)

    def generate_account_number(self):
        """Генерация уникального номера счета"""
        while True:
            # Формат: 40702810XXXXXXXXXXXXX (20 цифр)
            # 407 - счет, 02 - рубль, 810 - код рубля, остальные - случайные
            base = "40702810"
            random_part = ''.join(random.choices(string.digits, k=12))
            account_number = base + random_part

            if not Account.objects.filter(account_number=account_number).exists():
                return account_number

    def can_withdraw(self, amount):
        """Можно ли снять указанную сумму"""
        return self.available_balance >= amount and self.status == 'active'

    def withdraw(self, amount):
        """Снятие средств со счета"""
        if self.can_withdraw(amount):
            self.balance -= amount
            self.save()
            return True
        return False

    def deposit(self, amount):
        """Пополнение счета"""
        if self.status == 'active':
            self.balance += amount
            self.save()
            return True
        return False

    def transfer(self, to_account, amount):
        """Перевод на другой счет"""
        if self.can_withdraw(amount):
            self.balance -= amount
            to_account.balance += amount
            self.save()
            to_account.save()
            return True
        return False

    def get_transaction_history(self, days=30):
        """История транзакций за указанный период"""
        from django.utils import timezone
        from datetime import timedelta

        start_date = timezone.now() - timedelta(days=days)

        # Используем related_name, определенные в модели Transaction
        sent_transactions = self.sent_transactions.filter(
            created_at__gte=start_date
        )
        received_transactions = self.received_transactions.filter(
            created_at__gte=start_date
        )

        return {
            'sent': sent_transactions,
            'received': received_transactions
        }


class AccountBalanceHistory(models.Model):
    """История изменений баланса счета"""
    account = models.ForeignKey(
        Account,
        on_delete=models.CASCADE,
        related_name='balance_history',
        verbose_name='Счет'
    )
    date = models.DateField(
        verbose_name='Дата'
    )
    opening_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Начальный баланс'
    )
    closing_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Конечный баланс'
    )
    total_deposits = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Общие поступления'
    )
    total_withdrawals = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Общие списания'
    )
    interest_accrued = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Начисленные проценты'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания записи'
    )

    class Meta:
        verbose_name = 'История баланса счета'
        verbose_name_plural = 'История балансов счетов'
        unique_together = ['account', 'date']
        ordering = ['-date']

    def __str__(self):
        return f"{self.account.account_number} - {self.date}"


class AccountInterestRate(models.Model):
    """Процентные ставки по типам счетов"""
    account_type = models.CharField(
        max_length=20,
        choices=Account.ACCOUNT_TYPES,
        verbose_name='Тип счета'
    )
    currency = models.ForeignKey(
        Currency,
        on_delete=models.CASCADE,
        verbose_name='Валюта'
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        verbose_name='Процентная ставка'
    )
    min_balance = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Минимальный баланс'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активная ставка'
    )
    effective_date = models.DateField(
        verbose_name='Дата вступления в силу'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Процентная ставка'
        verbose_name_plural = 'Процентные ставки'
        unique_together = ['account_type', 'currency', 'effective_date']
        ordering = ['-effective_date']

    def __str__(self):
        return f"{self.get_account_type_display()} - {self.currency.code}: {self.interest_rate}%"