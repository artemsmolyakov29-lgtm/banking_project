from django.core.management.base import BaseCommand
from django.utils import timezone
from django.apps import apps
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Ежедневные автоматические задачи банковской системы'

    def add_arguments(self, parser):
        parser.add_argument(
            '--task',
            type=str,
            help='Конкретная задача для выполнения (deposit_interest, credit_check, etc.)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать какие задачи будут выполнены без реального выполнения'
        )

    def handle(self, *args, **options):
        task = options.get('task')
        dry_run = options.get('dry_run')

        self.stdout.write(
            self.style.SUCCESS(
                f'{"ТЕСТОВЫЙ РЕЖИМ" if dry_run else "ВЫПОЛНЕНИЕ"} ежедневных задач на дату: {timezone.now().date()}'
            )
        )

        tasks_executed = []
        errors = []

        # Выполняем все задачи или конкретную задачу
        if not task or task == 'deposit_interest':
            success, message = self.accrue_deposit_interest(dry_run)
            if success:
                tasks_executed.append('Начисление процентов по депозитам')
            else:
                errors.append(f'Начисление процентов: {message}')

        if not task or task == 'credit_check':
            success, message = self.check_overdue_credits(dry_run)
            if success:
                tasks_executed.append('Проверка просроченных кредитов')
            else:
                errors.append(f'Проверка кредитов: {message}')

        if not task or task == 'deposit_maturity':
            success, message = self.check_deposit_maturity(dry_run)
            if success:
                tasks_executed.append('Проверка зрелости депозитов')
            else:
                errors.append(f'Проверка депозитов: {message}')

        if not task or task == 'account_maintenance':
            success, message = self.account_maintenance_tasks(dry_run)
            if success:
                tasks_executed.append('Обслуживание счетов')
            else:
                errors.append(f'Обслуживание счетов: {message}')

        # Вывод результатов
        self.stdout.write('\n' + '=' * 60)
        self.stdout.write(self.style.SUCCESS('РЕЗУЛЬТАТЫ ВЫПОЛНЕНИЯ ЗАДАЧ:'))

        if tasks_executed:
            self.stdout.write(self.style.SUCCESS(f'Успешно выполнено: {len(tasks_executed)} задач'))
            for task_name in tasks_executed:
                self.stdout.write(f'  ✓ {task_name}')
        else:
            self.stdout.write(self.style.WARNING('Не выполнено ни одной задачи'))

        if errors:
            self.stdout.write(self.style.ERROR(f'Ошибки ({len(errors)}):'))
            for error in errors:
                self.stdout.write(self.style.ERROR(f'  ✗ {error}'))

        if dry_run:
            self.stdout.write(self.style.WARNING('\nРЕЖИМ ТЕСТИРОВАНИЯ: Задачи не были выполнены фактически'))

    def accrue_deposit_interest(self, dry_run=False):
        """Начисление процентов по депозитам"""
        try:
            from django.core.management import call_command
            from django.core.management.base import CommandError

            if dry_run:
                self.stdout.write('\n' + '-' * 40)
                self.stdout.write('ЗАДАЧА: Начисление процентов по депозитам (ТЕСТ)')
                self.stdout.write('Была бы вызвана команда: accrue_deposits_interest')
                return True, "Тестовый режим - команда не выполнена"

            try:
                call_command('accrue_deposits_interest')
                self.stdout.write(self.style.SUCCESS('Начисление процентов по депозитам выполнено'))
                return True, "Успешно"
            except CommandError as e:
                logger.error(f'Ошибка при начислении процентов: {str(e)}')
                return False, str(e)

        except Exception as e:
            logger.error(f'Неожиданная ошибка при начислении процентов: {str(e)}')
            return False, str(e)

    def check_overdue_credits(self, dry_run=False):
        """Проверка просроченных кредитов"""
        try:
            Credit = apps.get_model('credits', 'Credit')
            today = timezone.now().date()

            # Находим просроченные кредиты
            overdue_credits = Credit.objects.filter(
                status='active',
                next_payment_date__lt=today
            ).select_related('client', 'account')

            if dry_run:
                self.stdout.write('\n' + '-' * 40)
                self.stdout.write('ЗАДАЧА: Проверка просроченных кредитов (ТЕСТ)')
                self.stdout.write(f'Найдено просроченных кредитов: {overdue_credits.count()}')
                for credit in overdue_credits[:5]:  # Показываем первые 5
                    self.stdout.write(f'  - Кредит #{credit.id}, клиент: {credit.client.full_name}')
                if overdue_credits.count() > 5:
                    self.stdout.write(f'  ... и еще {overdue_credits.count() - 5} кредитов')
                return True, "Тестовый режим"

            # Реальная логика обработки просроченных кредитов
            processed_count = 0
            for credit in overdue_credits:
                try:
                    # Здесь может быть логика начисления штрафов, уведомлений и т.д.
                    # Например: credit.apply_late_fee()
                    processed_count += 1
                except Exception as e:
                    logger.error(f'Ошибка обработки кредита {credit.id}: {str(e)}')

            self.stdout.write(self.style.SUCCESS(f'Обработано просроченных кредитов: {processed_count}'))
            return True, f"Обработано {processed_count} кредитов"

        except Exception as e:
            logger.error(f'Ошибка при проверке кредитов: {str(e)}')
            return False, str(e)

    def check_deposit_maturity(self, dry_run=False):
        """Проверка зрелости депозитов"""
        try:
            Deposit = apps.get_model('deposits', 'Deposit')
            today = timezone.now().date()

            # Находим депозиты, срок которых истек
            matured_deposits = Deposit.objects.filter(
                status='active',
                end_date__lte=today
            ).select_related('client', 'account')

            if dry_run:
                self.stdout.write('\n' + '-' * 40)
                self.stdout.write('ЗАДАЧА: Проверка зрелости депозитов (ТЕСТ)')
                self.stdout.write(f'Найдено депозитов с истекшим сроком: {matured_deposits.count()}')
                for deposit in matured_deposits[:5]:
                    self.stdout.write(f'  - Депозит #{deposit.id}, клиент: {deposit.client.full_name}')
                if matured_deposits.count() > 5:
                    self.stdout.write(f'  ... и еще {matured_deposits.count() - 5} депозитов')
                return True, "Тестовый режим"

            # Реальная логика обработки зрелых депозитов
            processed_count = 0
            for deposit in matured_deposits:
                try:
                    # Автоматическое закрытие депозита или другие действия
                    deposit.status = 'matured'
                    deposit.save()
                    processed_count += 1

                    # Здесь может быть логика уведомления клиента
                    # или автоматического перевода средств

                except Exception as e:
                    logger.error(f'Ошибка обработки депозита {deposit.id}: {str(e)}')

            self.stdout.write(self.style.SUCCESS(f'Обработано депозитов с истекшим сроком: {processed_count}'))
            return True, f"Обработано {processed_count} депозитов"

        except Exception as e:
            logger.error(f'Ошибка при проверке депозитов: {str(e)}')
            return False, str(e)

    def account_maintenance_tasks(self, dry_run=False):
        """Задачи по обслуживанию счетов"""
        try:
            Account = apps.get_model('accounts', 'Account')

            # Находим счета с отрицательным балансом
            negative_balance_accounts = Account.objects.filter(
                balance__lt=0,
                status='active'
            ).select_related('client')

            if dry_run:
                self.stdout.write('\n' + '-' * 40)
                self.stdout.write('ЗАДАЧА: Обслуживание счетов (ТЕСТ)')
                self.stdout.write(f'Найдено счетов с отрицательным балансом: {negative_balance_accounts.count()}')
                for account in negative_balance_accounts[:5]:
                    self.stdout.write(f'  - Счет #{account.id}, баланс: {account.balance}')
                if negative_balance_accounts.count() > 5:
                    self.stdout.write(f'  ... и еще {negative_balance_accounts.count() - 5} счетов')
                return True, "Тестовый режим"

            # Реальная логика обслуживания счетов
            processed_count = 0

            # Пример: блокировка счетов с отрицательным балансом
            for account in negative_balance_accounts:
                try:
                    # account.status = 'blocked'
                    # account.save()
                    processed_count += 1
                except Exception as e:
                    logger.error(f'Ошибка обработки счета {account.id}: {str(e)}')

            # Другие задачи обслуживания...
            # - Проверка неактивных счетов
            # - Начисление комиссий за обслуживание
            # - Автоматическое закрытие пустых счетов и т.д.

            self.stdout.write(self.style.SUCCESS(f'Выполнены задачи обслуживания счетов'))
            return True, "Задачи обслуживания выполнены"

        except Exception as e:
            logger.error(f'Ошибка при обслуживании счетов: {str(e)}')
            return False, str(e)

    def generate_daily_report(self):
        """Генерация ежедневного отчета"""
        # Эта функция может быть вызвана из других методов
        # для генерации отчетов о выполненных задачах

        report_data = {
            'date': timezone.now().date(),
            'tasks_completed': [],
            'issues_found': [],
            'statistics': {}
        }

        # Здесь может быть логика сбора статистики и генерации отчета
        # который можно сохранить в базу или отправить по email администраторам

        return report_data