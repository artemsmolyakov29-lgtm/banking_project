from django.db import models
from django.conf import settings
from django.core.validators import MinLengthValidator
from django.apps import apps
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

    BLOCK_REASONS = (
        ('suspicious_activity', 'Подозрительная активность'),
        ('lost_card', 'Карта утеряна'),
        ('stolen_card', 'Карта украдена'),
        ('client_request', 'Запрос клиента'),
        ('overdraft', 'Просрочка по кредиту'),
        ('fraud', 'Мошенничество'),
        ('other', 'Другая причина'),
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
        editable=False,
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
        default=100000.00,
        verbose_name='Дневной лимит'
    )
    issue_date = models.DateField(
        auto_now_add=True,
        verbose_name='Дата выпуска'
    )
    pin_code = models.CharField(
        max_length=4,
        editable=False,
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
    status_changed_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата изменения статуса'
    )
    block_reason = models.CharField(
        max_length=50,
        choices=BLOCK_REASONS,
        blank=True,
        null=True,
        verbose_name='Причина блокировки'
    )
    block_description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание причины блокировки'
    )

    class Meta:
        verbose_name = 'Банковская карта'
        verbose_name_plural = 'Банковские карты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['card_number']),
            models.Index(fields=['account', 'status']),
            models.Index(fields=['expiry_date']),
            models.Index(fields=['status']),
        ]

    def __str__(self):
        return f"Карта {self.card_number} - {self.cardholder_name}"

    def is_expired(self):
        """Проверка, истек ли срок действия карты"""
        return datetime.date.today() > self.expiry_date

    def get_masked_number(self):
        """Возвращает маскированный номер карты"""
        return f"**** **** **** {self.card_number[-4:]}"

    def _log_card_status_change(self, user, old_status, new_status, reason=None, block_reason=None):
        """Внутренний метод для логирования изменения статуса карты"""
        try:
            # Ленивая загрузка функции логирования
            audit_utils = apps.get_app_config('audit')
            log_card_status_change = getattr(audit_utils, 'log_card_status_change', None)

            if log_card_status_change:
                log_card_status_change(
                    user=user,
                    card=self,
                    old_status=old_status,
                    new_status=new_status,
                    reason=reason,
                    block_reason=block_reason
                )
        except (ImportError, LookupError, AttributeError):
            # Если модуль аудита недоступен, просто игнорируем логирование
            pass

    def block_card(self, reason='blocked', block_reason=None, block_description=None, user=None):
        """Блокировка карты с записью в аудит"""
        if self.status == 'active':
            old_status = self.status
            self.status = reason
            self.block_reason = block_reason
            self.block_description = block_description
            self.save()

            # Запись в аудит
            if user:
                self._log_card_status_change(
                    user=user,
                    old_status=old_status,
                    new_status=self.status,
                    reason=block_description,
                    block_reason=block_reason
                )
            return True
        return False

    def unblock_card(self, user=None):
        """Разблокировка карты с записью в аудит"""
        if self.status in ['blocked', 'lost', 'stolen']:
            old_status = self.status
            self.status = 'active'
            self.block_reason = None
            self.block_description = None
            self.save()

            # Запись в аудит
            if user:
                self._log_card_status_change(
                    user=user,
                    old_status=old_status,
                    new_status=self.status,
                    reason="Карта разблокирована"
                )
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

    def get_status_display_with_color(self):
        """Возвращает статус с цветом для отображения в интерфейсе"""
        status_colors = {
            'active': 'success',
            'blocked': 'danger',
            'expired': 'warning',
            'lost': 'danger',
            'stolen': 'danger',
            'closed': 'secondary'
        }
        color = status_colors.get(self.status, 'secondary')
        return f'<span class="badge bg-{color}">{self.get_status_display()}</span>'


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


class CardStatusHistory(models.Model):
    """
    История изменения статусов карты
    """
    card = models.ForeignKey(
        Card,
        on_delete=models.CASCADE,
        related_name='status_history',
        verbose_name='Карта'
    )
    old_status = models.CharField(
        max_length=20,
        choices=Card.STATUS_CHOICES,
        verbose_name='Предыдущий статус'
    )
    new_status = models.CharField(
        max_length=20,
        choices=Card.STATUS_CHOICES,
        verbose_name='Новый статус'
    )
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        verbose_name='Изменено пользователем'
    )
    change_reason = models.TextField(
        blank=True,
        null=True,
        verbose_name='Причина изменения'
    )
    block_reason = models.CharField(
        max_length=50,
        choices=Card.BLOCK_REASONS,
        blank=True,
        null=True,
        verbose_name='Причина блокировки'
    )
    changed_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата и время изменения'
    )

    class Meta:
        verbose_name = 'История статуса карты'
        verbose_name_plural = 'История статусов карт'
        ordering = ['-changed_at']
        indexes = [
            models.Index(fields=['card', 'changed_at']),
        ]

    def __str__(self):
        return f"Изменение статуса карты {self.card.get_masked_number()}"