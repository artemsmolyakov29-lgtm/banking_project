from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db import transaction, models
from django.apps import apps
from decimal import Decimal
import datetime
import logging

logger = logging.getLogger(__name__)


def get_deposit_model():
    """Ленивая загрузка модели Deposit"""
    return apps.get_model('deposits', 'Deposit')


def get_deposit_interest_payment_model():
    """Ленивая загрузка модели DepositInterestPayment"""
    return apps.get_model('deposits', 'DepositInterestPayment')


def get_transaction_model():
    """Ленивая загрузка модели Transaction"""
    return apps.get_model('transactions', 'Transaction')


def get_audit_log_model():
    """Ленивая загрузка модели AuditLog"""
    return apps.get_model('audit', 'AuditLog')


class Command(BaseCommand):
    help = 'Начисление процентов по депозитам'

    def add_arguments(self, parser):
        parser.add_argument(
            '--date',
            type=str,
            help='Дата для начисления процентов (формат: YYYY-MM-DD). По умолчанию - текущая дата'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать какие депозиты будут обработаны без реального начисления'
        )
        parser.add_argument(
            '--deposit-id',
            type=int,
            help='ID конкретного депозита для начисления процентов'
        )

    def handle(self, *args, **options):
        Deposit = get_deposit_model()
        DepositInterestPayment = get_deposit_interest_payment_model()
        Transaction = get_transaction_model()
        AuditLog = get_audit_log_model()

        # Определяем дату начисления
        if options['date']:
            try:
                accrual_date = datetime.datetime.strptime(options['date'], '%Y-%m-%d').date()
            except ValueError:
                self.stderr.write(self.style.ERROR('Неверный формат даты. Используйте YYYY-MM-DD'))
                return
        else:
            accrual_date = timezone.now().date()

        dry_run = options['dry_run']
        deposit_id = options.get('deposit_id')

        self.stdout.write(
            self.style.SUCCESS(
                f'{"ТЕСТОВЫЙ РЕЖИМ" if dry_run else "НАЧИСЛЕНИЕ"} процентов на дату: {accrual_date}'
            )
        )

        # Получаем активные депозиты для начисления
        deposits_query = Deposit.objects.filter(
            status='active',
            start_date__lte=accrual_date,
            end_date__gte=accrual_date
        ).select_related('account', 'client', 'client__user')

        if deposit_id:
            deposits_query = deposits_query.filter(id=deposit_id)
            if not deposits_query.exists():
                self.stderr.write(self.style.ERROR(f'Депозит с ID {deposit_id} не найден или не активен'))
                return

        deposits = list(deposits_query)

        if not deposits:
            self.stdout.write(self.style.WARNING('Нет активных депозитов для начисления процентов'))
            return

        total_accrued = Decimal('0.00')
        processed_count = 0
        errors = []

        for deposit in deposits:
            try:
                self.stdout.write(f'Обработка депозита {deposit.id} - {deposit.client.full_name}')

                # Проверяем, нужно ли начислять проценты в эту дату
                if not self.should_accrue_interest(deposit, accrual_date):
                    self.stdout.write(f'  Пропуск - не время для начисления')
                    continue

                # Рассчитываем проценты
                interest_amount = self.calculate_interest_amount(deposit, accrual_date)

                if interest_amount <= 0:
                    self.stdout.write(f'  Пропуск - сумма процентов 0 или отрицательная')
                    continue

                if dry_run:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Будет начислено: {interest_amount} {deposit.account.currency.code}'
                        )
                    )
                    total_accrued += interest_amount
                    processed_count += 1
                    continue

                # Реальное начисление процентов
                success = self.accrue_interest_for_deposit(
                    deposit, interest_amount, accrual_date,
                    DepositInterestPayment, Transaction, AuditLog
                )

                if success:
                    total_accrued += interest_amount
                    processed_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Успешно начислено: {interest_amount} {deposit.account.currency.code}'
                        )
                    )
                else:
                    errors.append(f'Депозит {deposit.id}: ошибка при начислении')

            except Exception as e:
                error_msg = f'Депозит {deposit.id}: {str(e)}'
                self.stderr.write(self.style.ERROR(f'  Ошибка: {error_msg}'))
                errors.append(error_msg)
                logger.error(f'Ошибка начисления процентов для депозита {deposit.id}: {str(e)}')

        # Вывод итогов
        self.stdout.write('\n' + '=' * 50)
        if dry_run:
            self.stdout.write(
                self.style.WARNING(
                    f'ТЕСТОВЫЙ РЕЖИМ: Было бы обработано {processed_count} депозитов, '
                    f'сумма начислений: {total_accrued}'
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f'УСПЕШНО: Обработано {processed_count} депозитов, '
                    f'начислено: {total_accrued}'
                )
            )

            if errors:
                self.stdout.write(
                    self.style.ERROR(
                        f'ОШИБКИ ({len(errors)}):'
                    )
                )
                for error in errors:
                    self.stdout.write(self.style.ERROR(f'  - {error}'))

    def should_accrue_interest(self, deposit, accrual_date):
        """
        Проверяет, нужно ли начислять проценты для депозита в указанную дату
        """
        # Не начисляем в день открытия
        if accrual_date == deposit.start_date:
            return False

        # Проверяем периодичность начисления в зависимости от типа капитализации
        if deposit.capitalization == 'monthly':
            # Начисляем в последний день месяца
            next_month = accrual_date.replace(day=28) + datetime.timedelta(days=4)
            last_day_of_month = next_month - datetime.timedelta(days=next_month.day)
            return accrual_date == last_day_of_month

        elif deposit.capitalization == 'quarterly':
            # Начисляем в последний день квартала
            quarter = (accrual_date.month - 1) // 3 + 1
            quarter_end_month = quarter * 3
            quarter_end_year = accrual_date.year
            if quarter_end_month > 12:
                quarter_end_month = 12
            last_day_of_quarter = datetime.date(
                quarter_end_year, quarter_end_month, 1
            ) + datetime.timedelta(days=-1)
            return accrual_date == last_day_of_quarter

        elif deposit.capitalization == 'end_of_term':
            # Начисляем только в конце срока
            return accrual_date == deposit.end_date

        else:  # 'none' - без капитализации
            # Начисляем ежемесячно, но без капитализации
            next_month = accrual_date.replace(day=28) + datetime.timedelta(days=4)
            last_day_of_month = next_month - datetime.timedelta(days=next_month.day)
            return accrual_date == last_day_of_month

    def calculate_interest_amount(self, deposit, accrual_date):
        """
        Рассчитывает сумму процентов для начисления
        """
        # Определяем период начисления
        if deposit.capitalization in ['monthly', 'quarterly', 'none']:
            # Для периодических начислений - рассчитываем за прошедший период
            period_start = self.get_previous_accrual_date(deposit, accrual_date)
            if not period_start:
                period_start = deposit.start_date
        else:  # 'end_of_term'
            # В конце срока - за весь период
            period_start = deposit.start_date

        # Количество дней в периоде
        days_in_period = (accrual_date - period_start).days
        if days_in_period <= 0:
            return Decimal('0.00')

        # База для расчета (сумма депозита + капитализированные проценты)
        base_amount = deposit.amount

        # Если есть капитализация, добавляем ранее начисленные проценты
        if deposit.capitalization != 'none':
            previous_interest = deposit.interest_payments.filter(
                payment_date__lt=accrual_date
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
            base_amount += previous_interest

        # Расчет процентов: (база * ставка * дни) / (100 * 365)
        interest_amount = (base_amount * deposit.interest_rate * Decimal(days_in_period)) / (
                Decimal('100') * Decimal('365')
        )

        return round(interest_amount, 2)

    def get_previous_accrual_date(self, deposit, current_date):
        """
        Получает дату предыдущего начисления процентов
        """
        last_payment = deposit.interest_payments.filter(
            payment_date__lt=current_date
        ).order_by('-payment_date').first()

        if last_payment:
            return last_payment.payment_date

        # Если начислений не было, возвращаем дату начала депозита
        return deposit.start_date

    @transaction.atomic
    def accrue_interest_for_deposit(self, deposit, interest_amount, accrual_date,
                                    DepositInterestPayment, Transaction, AuditLog):
        """
        Выполняет начисление процентов для одного депозита
        """
        try:
            # Создаем запись о начислении процентов
            period_start = self.get_previous_accrual_date(deposit, accrual_date)

            interest_payment = DepositInterestPayment.objects.create(
                deposit=deposit,
                period_start=period_start,
                period_end=accrual_date,
                amount=interest_amount,
                payment_date=accrual_date
            )

            # Обновляем баланс счета
            deposit.account.balance += interest_amount
            deposit.account.save()

            # Создаем транзакцию
            transaction_description = (
                f'Начисление процентов по депозиту {deposit.id} '
                f'за период {period_start} - {accrual_date}'
            )

            Transaction.objects.create(
                from_account=None,  # Проценты начисляются от банка
                to_account=deposit.account,
                amount=interest_amount,
                currency=deposit.account.currency,
                transaction_type='interest_accrual',
                description=transaction_description,
                status='completed'
            )

            # Если капитализация включена, обновляем сумму депозита
            if deposit.capitalization != 'none':
                deposit.amount += interest_amount
                deposit.save()

            # Обновляем дату последнего начисления
            deposit.last_interest_accrual = accrual_date
            deposit.save()

            # Записываем в аудит
            AuditLog.objects.create(
                user=None,  # Системная операция
                action='deposit_interest_accrual',
                model_name='Deposit',
                object_id=deposit.id,
                details=(
                    f'Начислены проценты по депозиту {deposit.id}: {interest_amount} '
                    f'{deposit.account.currency.code}. Период: {period_start} - {accrual_date}'
                ),
                ip_address='127.0.0.1'  # Локальный IP для системных операций
            )

            return True

        except Exception as e:
            logger.error(f'Ошибка при начислении процентов для депозита {deposit.id}: {str(e)}')
            # Откатываем транзакцию через декоратор @transaction.atomic
            raise