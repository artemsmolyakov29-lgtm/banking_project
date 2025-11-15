from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('transfer', 'Перевод между счетами'),
        ('deposit', 'Пополнение'),
        ('withdrawal', 'Снятие'),
        ('payment', 'Платеж'),
        ('fee', 'Комиссия'),
        ('interest', 'Начисление процентов'),
        ('refund', 'Возврат'),
    )

    STATUS_CHOICES = (
        ('pending', 'В обработке'),
        ('completed', 'Завершена'),
        ('failed', 'Неуспешна'),
        ('cancelled', 'Отменена'),
    )

    from_account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='sent_transactions',
        null=True,
        blank=True,
        verbose_name='Со счета'
    )
    to_account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='received_transactions',
        verbose_name='На счет'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        verbose_name='Сумма'
    )
    currency = models.ForeignKey(
        'accounts.Currency',
        on_delete=models.PROTECT,
        verbose_name='Валюта'
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        verbose_name='Тип транзакции'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        verbose_name='Статус'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    reference_number = models.CharField(
        max_length=50,
        unique=True,
        verbose_name='Номер транзакции'
    )
    fee = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Комиссия'
    )
    exchange_rate = models.DecimalField(
        max_digits=10,
        decimal_places=6,
        default=1.0,
        verbose_name='Курс обмена'
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Инициатор'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    executed_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата выполнения'
    )

    class Meta:
        verbose_name = 'Транзакция'
        verbose_name_plural = 'Транзакции'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['from_account', 'created_at']),
            models.Index(fields=['to_account', 'created_at']),
            models.Index(fields=['reference_number']),
            models.Index(fields=['created_at']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Транзакция {self.reference_number} - {self.amount} {self.currency.code}"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Генерация уникального номера транзакции
            import uuid
            self.reference_number = f"TXN{uuid.uuid4().hex[:12].upper()}"

        if self.status == 'completed' and not self.executed_at:
            from django.utils import timezone
            self.executed_at = timezone.now()

        super().save(*args, **kwargs)

    def get_absolute_amount(self):
        """Абсолютная сумма с учетом комиссии"""
        return self.amount + self.fee

    def is_internal_transfer(self):
        """Является ли транзакция внутренним переводом"""
        return (self.from_account is not None and
                self.to_account is not None and
                self.transaction_type == 'transfer')

    def can_be_cancelled(self):
        """Можно ли отменить транзакцию"""
        return self.status in ['pending']

    def execute_transaction(self):
        """
        Выполнение транзакции - основная бизнес-логика
        """
        if self.status != 'pending':
            return False

        try:
            with models.transaction.atomic():
                if self.from_account:
                    # Списание со счета отправителя
                    if self.from_account.balance >= self.get_absolute_amount():
                        self.from_account.balance -= self.get_absolute_amount()
                        self.from_account.save()
                    else:
                        self.status = 'failed'
                        self.save()
                        return False

                # Зачисление на счет получателя
                self.to_account.balance += self.amount
                self.to_account.save()

                self.status = 'completed'
                self.save()
                return True

        except Exception as e:
            self.status = 'failed'
            self.save()
            return False


class TransactionFee(models.Model):
    """
    Тарифы комиссий за транзакции
    """
    FEE_TYPES = (
        ('percentage', 'Процент от суммы'),
        ('fixed', 'Фиксированная'),
        ('tiered', 'Ступенчатая'),
    )

    name = models.CharField(
        max_length=100,
        verbose_name='Название тарифа'
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=Transaction.TRANSACTION_TYPES,
        verbose_name='Тип транзакции'
    )
    fee_type = models.CharField(
        max_length=20,
        choices=FEE_TYPES,
        verbose_name='Тип комиссии'
    )
    amount = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        verbose_name='Размер комиссии'
    )
    min_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=0.00,
        verbose_name='Минимальная сумма'
    )
    max_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Максимальная сумма'
    )
    currency = models.ForeignKey(
        'accounts.Currency',
        on_delete=models.CASCADE,
        verbose_name='Валюта'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Тариф комиссии'
        verbose_name_plural = 'Тарифы комиссий'

    def __str__(self):
        return f"{self.name} - {self.get_fee_type_display()}"

    def calculate_fee(self, transaction_amount):
        """Расчет комиссии для указанной суммы"""
        if self.fee_type == 'percentage':
            fee = transaction_amount * (self.amount / 100)
        elif self.fee_type == 'fixed':
            fee = self.amount
        else:  # tiered - упрощенная реализация
            fee = self.amount  # Можно расширить логику

        return max(fee, self.min_amount)