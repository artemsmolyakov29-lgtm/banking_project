from django.db import models
from django.conf import settings
from django.core.validators import MinLengthValidator
import datetime


class Card(models.Model):
    CARD_TYPES = (
        ('debit', 'Дебетовая'),
        ('credit', 'Кредитная'),
        ('prepaid', 'Предоплаченная'),
    )

    CARD_SYSTEMS = (
        ('visa', 'Visa'),
        ('mastercard', 'MasterCard'),
        ('mir', 'Мир'),
    )

    STATUS_CHOICES = (
        ('active', 'Активна'),
        ('blocked', 'Заблокирована'),
        ('expired', 'Истек срок'),
        ('lost', 'Утеряна'),
        ('stolen', 'Украдена'),
        ('closed', 'Закрыта'),
    )

    account = models.ForeignKey(
        'accounts.Account',
        on_delete=models.CASCADE,
        related_name='cards',
        verbose_name='Счет'
    )
    card_number = models.CharField(
        max_length=16,
        unique=True,
        validators=[MinLengthValidator(16)],
        verbose_name='Номер карты'
    )
    cardholder_name = models.CharField(
        max_length=100,
        verbose_name='Имя держателя карты'
    )
    expiry_date = models.DateField(
        verbose_name='Срок действия'
    )
    cvv = models.CharField(
        max_length=3,
        editable=False,  # Не храним CVV в БД - это нарушение PCI DSS
        verbose_name='CVV код'
    )
    card_type = models.CharField(
        max_length=20,
        choices=CARD_TYPES,
        default='debit',
        verbose_name='Тип карты'
    )
    card_system = models.CharField(
        max_length=20,
        choices=CARD_SYSTEMS,
        default='visa',
        verbose_name='Платежная система'
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='active',
        verbose_name='Статус'
    )
    daily_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        default=100000.00,  # 100 000 рублей по умолчанию
        verbose_name='Дневной лимит'
    )
    issue_date = models.DateField(
        auto_now_add=True,
        verbose_name='Дата выпуска'
    )
    pin_code = models.CharField(
        max_length=4,
        editable=False,  # PIN не храним в открытом виде
        verbose_name='PIN код'
    )
    is_virtual = models.BooleanField(
        default=False,
        verbose_name='Виртуальная карта'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Банковская карта'
        verbose_name_plural = 'Банковские карты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['card_number']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['expiry_date']),
        ]

    def __str__(self):
        return f"Карта {self.card_number} - {self.cardholder_name}"

    def is_expired(self):
        """Проверка, истек ли срок действия карты"""
        return datetime.date.today() > self.expiry_date

    def get_masked_number(self):
        """Возвращает маскированный номер карты"""
        return f"**** **** **** {self.card_number[-4:]}"

    def block_card(self, reason='blocked'):
        """Блокировка карты"""
        if self.status == 'active':
            self.status = reason
            self.save()
            return True
        return False

    def unblock_card(self):
        """Разблокировка карты"""
        if self.status in ['blocked', 'lost', 'stolen']:
            self.status = 'active'
            self.save()
            return True
        return False

    def can_be_used(self):
        """Можно ли использовать карту"""
        return self.status == 'active' and not self.is_expired()

    def get_remaining_daily_limit(self, used_today=None):
        """
        Оставшийся дневной лимит
        used_today - сумма, уже использованная сегодня
        """
        if used_today is None:
            # Здесь можно добавить логику подсчета использованной сегодня суммы
            used_today = 0
        return max(self.daily_limit - used_today, 0)


class CardTransaction(models.Model):
    """
    История операций по карте
    """
    TRANSACTION_TYPES = (
        ('purchase', 'Покупка'),
        ('withdrawal', 'Снятие наличных'),
        ('refund', 'Возврат'),
        ('online_payment', 'Онлайн платеж'),
    )

    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name='transactions',
        verbose_name='Карта'
    )
    transaction_type = models.CharField(
        max_length=20,
        choices=TRANSACTION_TYPES,
        verbose_name='Тип операции'
    )
    amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        verbose_name='Сумма'
    )
    currency = models.ForeignKey(
        'accounts.Currency',
        on_delete=models.PROTECT,
        verbose_name='Валюта'
    )
    merchant_name = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Название магазина/мерчанта'
    )
    merchant_location = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Местоположение'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    transaction_date = models.DateTimeField(
        verbose_name='Дата и время операции'
    )
    authorization_code = models.CharField(
        max_length=10,
        blank=True,
        verbose_name='Код авторизации'
    )
    is_successful = models.BooleanField(
        default=True,
        verbose_name='Успешная операция'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания записи'
    )

    class Meta:
        verbose_name = 'Операция по карте'
        verbose_name_plural = 'Операции по картам'
        ordering = ['-transaction_date']
        indexes = [
            models.Index(fields=['card', 'transaction_date']),
            models.Index(fields=['transaction_date']),
        ]

    def __str__(self):
        return f"Операция {self.id} по карте {self.card.get_masked_number()}"