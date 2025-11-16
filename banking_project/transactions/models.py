from django.db import models
from django.conf import settings
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from django.apps import apps


class Transaction(models.Model):
    TRANSACTION_TYPES = (
        ('transfer', 'Перевод между счетами'),
        ('deposit', 'Пополнение'),
        ('withdrawal', 'Снятие'),
        ('payment', 'Платеж'),
        ('fee', 'Комиссия'),
        ('interest', 'Начисление процентов'),
        ('refund', 'Возврат'),
        ('credit_payment', 'Платеж по кредиту'),
        ('deposit_interest', 'Начисление процентов по депозиту'),
        ('loan_issuance', 'Выдача кредита'),
        ('early_repayment', 'Досрочное погашение'),
        ('interest_accrual', 'Начисление процентов'),
        ('card_payment', 'Оплата картой'),  # НОВЫЙ ТИП
        ('card_withdrawal', 'Снятие наличных с карты'),  # НОВЫЙ ТИП
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
    deposit = models.ForeignKey(
        'deposits.Deposit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='interest_transactions',
        verbose_name='Связанный депозит'
    )
    credit = models.ForeignKey(
        'credits.Credit',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions',
        verbose_name='Связанный кредит'
    )
    credit_payment = models.OneToOneField(
        'credits.CreditPayment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transaction_link',
        verbose_name='Связанный платеж по кредиту'
    )
    deposit_interest_payment = models.OneToOneField(
        'deposits.DepositInterestPayment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transaction',
        verbose_name='Связанное начисление процентов'
    )
    # НОВОЕ ПОЛЕ ДЛЯ СВЯЗИ С КАРТАМИ
    card = models.ForeignKey(
        'cards.Card',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='card_transactions',
        verbose_name='Связанная карта'
    )
    card_transaction = models.OneToOneField(
        'cards.CardTransaction',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transaction_link',
        verbose_name='Связанная операция по карте'
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
            models.Index(fields=['credit', 'created_at']),
            models.Index(fields=['transaction_type', 'created_at']),
            models.Index(fields=['deposit', 'created_at']),
            models.Index(fields=['card', 'created_at']),  # НОВЫЙ ИНДЕКС
        ]

    def __str__(self):
        return f"Транзакция {self.reference_number} - {self.amount} {self.currency.code}"

    def save(self, *args, **kwargs):
        if not self.reference_number:
            # Генерация уникального номера транзакции
            import uuid
            self.reference_number = f"TXN{uuid.uuid4().hex[:12].upper()}"

        if self.status == 'completed' and not self.executed_at:
            self.executed_at = timezone.now()

        # Автоматическое определение валюты из счетов
        if not self.currency_id and self.to_account:
            self.currency = self.to_account.currency
        elif not self.currency_id and self.from_account:
            self.currency = self.from_account.currency

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

    def _check_card_status(self):
        """Проверка статуса карты для карточных операций"""
        if self.card and self.transaction_type in ['card_payment', 'card_withdrawal']:
            if not self.card.can_be_used():
                return False, "Карта заблокирована или просрочена"

            # Проверка дневного лимита
            daily_used = self.card.transactions.filter(
                transaction_date__date=timezone.now().date(),
                is_successful=True
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')

            remaining_limit = self.card.get_remaining_daily_limit(daily_used)
            if self.amount > remaining_limit:
                return False, "Превышен дневной лимит по карте"

        return True, ""

    def execute_transaction(self):
        """
        Выполнение транзакции - основная бизнес-логика
        """
        if self.status != 'pending':
            return False

        # Проверка статуса карты для карточных операций
        if self.transaction_type in ['card_payment', 'card_withdrawal']:
            card_valid, error_message = self._check_card_status()
            if not card_valid:
                self.status = 'failed'
                self.description = f"{self.description}. {error_message}" if self.description else error_message
                self.save()
                return False

        try:
            with db_transaction.atomic():
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

    def execute_transfer(self):
        """Выполнение перевода между счетами с блокировкой для избежания гонки условий"""
        if self.status != 'pending':
            return False

        try:
            with db_transaction.atomic():
                # Блокируем счета для избежания гонки условий
                if self.from_account:
                    from_account = self.from_account.__class__.objects.select_for_update().get(id=self.from_account.id)
                    # Проверяем достаточно ли средств (учитывая комиссию)
                    total_amount = self.amount + self.fee
                    if from_account.balance < total_amount:
                        self.status = 'failed'
                        self.save()
                        return False

                    # Списание со счета отправителя
                    from_account.balance -= total_amount
                    from_account.save()

                # Зачисление на счет получателя
                to_account = self.to_account.__class__.objects.select_for_update().get(id=self.to_account.id)
                to_account.balance += self.amount
                to_account.save()

                # Обновляем статус транзакции
                self.status = 'completed'
                self.executed_at = timezone.now()
                self.save()

                return True

        except Exception as e:
            self.status = 'failed'
            self.save()
            return False

    def cancel_transaction(self):
        """Отмена транзакции (только для завершенных)"""
        if self.status != 'completed':
            return False

        try:
            with db_transaction.atomic():
                # Возвращаем средства
                if self.from_account:
                    from_account = self.from_account.__class__.objects.select_for_update().get(id=self.from_account.id)
                    to_account = self.to_account.__class__.objects.select_for_update().get(id=self.to_account.id)

                    from_account.balance += self.amount + self.fee
                    to_account.balance -= self.amount

                    from_account.save()
                    to_account.save()

                self.status = 'cancelled'
                self.save()
                return True

        except Exception as e:
            return False

    # НОВЫЕ МЕТОДЫ ДЛЯ РАБОТЫ С КРЕДИТАМИ И ДЕПОЗИТАМИ
    def is_credit_related(self):
        """Является ли транзакция связанной с кредитом"""
        return self.transaction_type in ['credit_payment', 'loan_issuance', 'early_repayment']

    def is_deposit_related(self):
        """Является ли транзакция связанной с депозитом"""
        return self.transaction_type in ['deposit_interest', 'interest_accrual']

    def is_card_related(self):
        """Является ли транзакция связанной с картой"""
        return self.transaction_type in ['card_payment', 'card_withdrawal']

    def get_credit_info(self):
        """Получение информации о связанном кредите"""
        if self.credit:
            return {
                'contract_number': self.credit.contract_number,
                'client': self.credit.client.get_full_name(),
                'amount': self.credit.amount,
                'remaining_balance': self.credit.remaining_balance
            }
        return None

    def get_deposit_info(self):
        """Получение информации о связанном депозите"""
        if self.deposit:
            return {
                'deposit_id': self.deposit.id,
                'client': self.deposit.client.get_full_name(),
                'amount': self.deposit.amount,
                'interest_rate': self.deposit.interest_rate
            }
        return None

    def get_card_info(self):
        """Получение информации о связанной карте"""
        if self.card:
            return {
                'card_number': self.card.get_masked_number(),
                'cardholder': self.card.cardholder_name,
                'card_type': self.card.get_card_type_display(),
                'status': self.card.get_status_display()
            }
        return None

    def process_credit_payment(self):
        """Специальная обработка для кредитных платежей"""
        if self.transaction_type != 'credit_payment' or not self.credit_payment:
            return False

        try:
            # Используем метод make_payment из модели Credit
            success, message = self.credit.make_payment(
                self.amount,
                self.credit_payment.payment_method,
                self.initiated_by
            )

            if success:
                self.status = 'completed'
                self.executed_at = timezone.now()
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

    def process_deposit_interest(self):
        """Специальная обработка для начисления процентов по депозитам"""
        if self.transaction_type not in ['deposit_interest', 'interest_accrual'] or not self.deposit:
            return False

        try:
            # Проверяем, что депозит активен
            if self.deposit.status != 'active':
                self.status = 'failed'
                self.save()
                return False

            # Выполняем транзакцию
            success = self.execute_transaction()

            if success and self.deposit_interest_payment:
                # Обновляем связь с начислением процентов
                self.deposit_interest_payment.transaction = self
                self.deposit_interest_payment.save()

            return success

        except Exception as e:
            self.status = 'failed'
            self.save()
            return False

    def process_card_transaction(self):
        """Специальная обработка для карточных операций"""
        if not self.is_card_related() or not self.card:
            return False

        try:
            # Проверяем статус карты
            if not self.card.can_be_used():
                self.status = 'failed'
                self.description = f"{self.description}. Карта недоступна для операций" if self.description else "Карта недоступна для операций"
                self.save()
                return False

            # Выполняем транзакцию
            success = self.execute_transaction()

            if success and self.card_transaction:
                # Обновляем связь с операцией по карте
                self.card_transaction.transaction_link = self
                self.card_transaction.save()

            return success

        except Exception as e:
            self.status = 'failed'
            self.save()
            return False

    @classmethod
    def create_deposit_interest_transaction(cls, deposit, interest_amount, description, interest_payment=None):
        """
        Создание транзакции для начисления процентов по депозиту
        """
        transaction = cls(
            from_account=None,  # Проценты начисляются от банка
            to_account=deposit.account,
            amount=interest_amount,
            currency=deposit.account.currency,
            transaction_type='interest_accrual',
            description=description,
            status='completed',
            deposit=deposit,
            deposit_interest_payment=interest_payment
        )
        transaction.save()
        return transaction

    @classmethod
    def create_card_transaction(cls, card, amount, transaction_type, description, merchant_name="", currency=None):
        """
        Создание транзакции для операции по карте
        """
        if not currency:
            currency = card.account.currency

        transaction = cls(
            from_account=card.account,
            to_account=None,  # Для платежей получатель будет указан отдельно
            amount=amount,
            currency=currency,
            transaction_type=transaction_type,
            description=description,
            status='pending',
            card=card
        )
        transaction.save()
        return transaction


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

        if self.max_amount:
            fee = min(fee, self.max_amount)

        return max(fee, self.min_amount)