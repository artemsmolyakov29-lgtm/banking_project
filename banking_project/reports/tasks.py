"""
Задачи для системы отчетности.
ВНИМАНИЕ: Celery в проекте не используется, это синхронные задачи для management commands.
"""
import logging
import time
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction, models
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings

logger = logging.getLogger(__name__)


class ReportTasks:
    """Класс с задачами для системы отчетности"""

    @staticmethod
    def generate_financial_report(date_from=None, date_to=None, user=None):
        """
        Генерация финансового отчета

        Args:
            date_from: Дата начала периода
            date_to: Дата окончания периода
            user: Пользователь, инициировавший генерацию

        Returns:
            dict: Результат выполнения задачи
        """
        start_time = time.time()

        try:
            from .utils import ReportExporter, DataProcessor, AnalyticsCalculator
            from .models import SavedReport, ReportTemplate

            # Условный импорт для аудита - если приложение существует
            try:
                from audit.models import AuditLog
                has_audit = True
            except ImportError:
                has_audit = False
                logger.warning("Приложение audit не найдено, логирование отключено")

            # Устанавливаем период по умолчанию
            if not date_from:
                date_from = timezone.now() - timedelta(days=30)
            if not date_to:
                date_to = timezone.now()

            logger.info(f"Начало генерации финансового отчета за период {date_from} - {date_to}")

            # Получаем финансовые метрики
            metrics = AnalyticsCalculator.calculate_financial_metrics(date_from, date_to)

            # Подготавливаем данные для отчета
            report_data = {
                'period': {
                    'from': date_from.strftime('%Y-%m-%d'),
                    'to': date_to.strftime('%Y-%m-%d')
                },
                'metrics': metrics,
                'generated_at': timezone.now().isoformat(),
                'generated_by': user.username if user else 'system'
            }

            # Создаем сохраненный отчет
            report = SavedReport.objects.create(
                name=f"Финансовый отчет {date_from.strftime('%Y-%m-%d')} - {date_to.strftime('%Y-%m-%d')}",
                report_type='financial',
                parameters={
                    'date_from': date_from.isoformat(),
                    'date_to': date_to.isoformat()
                },
                generated_by=user,
                file_format='html',
                file_path='',  # Временный отчет, файл не сохраняется
                file_size=0,
                is_temporary=True,
                generation_status='completed',
                preview_data=report_data
            )

            execution_time = (time.time() - start_time) * 1000  # в миллисекундах

            # Логируем успешное выполнение
            if user and has_audit:
                AuditLog.log_report_generation(
                    user=user,
                    report_type='financial',
                    parameters={'date_from': date_from.isoformat(), 'date_to': date_to.isoformat()},
                    format='html',
                    is_successful=True,
                    execution_time=execution_time
                )

            logger.info(f"Финансовый отчет успешно сгенерирован за {execution_time:.2f} мс")

            return {
                'status': 'success',
                'report_id': report.id,
                'execution_time': execution_time,
                'data': report_data
            }

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Ошибка генерации финансового отчета: {str(e)}")

            # Логируем ошибку
            if user and has_audit:
                AuditLog.log_report_generation(
                    user=user,
                    report_type='financial',
                    parameters={'date_from': date_from.isoformat() if date_from else None,
                                'date_to': date_to.isoformat() if date_to else None},
                    format='html',
                    is_successful=False,
                    error_message=str(e),
                    execution_time=execution_time
                )

            return {
                'status': 'error',
                'error_message': str(e),
                'execution_time': execution_time
            }

    @staticmethod
    def generate_client_report(parameters=None, user=None):
        """
        Генерация отчета по клиентам

        Args:
            parameters: Параметры отчета
            user: Пользователь, инициировавший генерацию

        Returns:
            dict: Результат выполнения задачи
        """
        start_time = time.time()

        try:
            from django.apps import apps
            from .utils import DataProcessor
            from .models import SavedReport

            # Условный импорт для аудита - если приложение существует
            try:
                from audit.models import AuditLog
                has_audit = True
            except ImportError:
                has_audit = False
                logger.warning("Приложение audit не найдено, логирование отключено")

            Client = apps.get_model('clients', 'Client')

            logger.info("Начало генерации отчета по клиентам")

            # Применяем фильтры
            clients = Client.objects.all()

            if parameters:
                if parameters.get('is_vip') == 'true':
                    clients = clients.filter(is_vip=True)
                elif parameters.get('is_vip') == 'false':
                    clients = clients.filter(is_vip=False)

                if parameters.get('min_rating'):
                    clients = clients.filter(credit_rating__gte=parameters['min_rating'])

            # Подготавливаем данные
            clients_data = DataProcessor.prepare_client_data(clients)

            # Вычисляем средний рейтинг
            avg_rating_result = clients.aggregate(avg=models.Avg('credit_rating'))
            avg_rating = avg_rating_result['avg'] or Decimal('0')

            report_data = {
                'filters': parameters or {},
                'total_clients': clients.count(),
                'vip_clients': clients.filter(is_vip=True).count(),
                'avg_rating': float(avg_rating),
                'clients': clients_data,
                'generated_at': timezone.now().isoformat(),
                'generated_by': user.username if user else 'system'
            }

            # Создаем сохраненный отчет
            report = SavedReport.objects.create(
                name="Отчет по клиентам",
                report_type='client',
                parameters=parameters or {},
                generated_by=user,
                file_format='html',
                file_path='',
                file_size=0,
                is_temporary=True,
                generation_status='completed',
                preview_data=report_data
            )

            execution_time = (time.time() - start_time) * 1000

            # Логируем успешное выполнение
            if user and has_audit:
                AuditLog.log_report_generation(
                    user=user,
                    report_type='client',
                    parameters=parameters or {},
                    format='html',
                    is_successful=True,
                    execution_time=execution_time
                )

            logger.info(f"Отчет по клиентам успешно сгенерирован за {execution_time:.2f} мс")

            return {
                'status': 'success',
                'report_id': report.id,
                'execution_time': execution_time,
                'data': report_data
            }

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Ошибка генерации отчета по клиентам: {str(e)}")

            if user and has_audit:
                AuditLog.log_report_generation(
                    user=user,
                    report_type='client',
                    parameters=parameters or {},
                    format='html',
                    is_successful=False,
                    error_message=str(e),
                    execution_time=execution_time
                )

            return {
                'status': 'error',
                'error_message': str(e),
                'execution_time': execution_time
            }

    @staticmethod
    def execute_scheduled_report(schedule_id):
        """
        Выполнение запланированного отчета

        Args:
            schedule_id: ID расписания

        Returns:
            dict: Результат выполнения задачи
        """
        start_time = time.time()

        try:
            from .models import ReportSchedule, SavedReport
            from django.contrib.auth import get_user_model

            # Условный импорт для аудита - если приложение существует
            try:
                from audit.models import AuditLog
                has_audit = True
            except ImportError:
                has_audit = False
                logger.warning("Приложение audit не найдено, логирование отключено")

            User = get_user_model()

            logger.info(f"Выполнение запланированного отчета #{schedule_id}")

            # Получаем расписание
            schedule = ReportSchedule.objects.get(id=schedule_id, is_active=True)
            user = schedule.created_by

            # Получаем параметры
            parameters = schedule.extra_parameters or {}
            parameters.update(schedule.template.template_parameters or {})

            # Генерируем отчет в зависимости от типа
            if schedule.template.report_type == 'financial':
                date_from = timezone.now() - timedelta(days=30)
                date_to = timezone.now()
                result = ReportTasks.generate_financial_report(date_from, date_to, user)
            elif schedule.template.report_type == 'client':
                result = ReportTasks.generate_client_report(parameters, user)
            else:
                # Базовая реализация для других типов отчетов
                result = ReportTasks.generate_financial_report(user=user)

            # Обновляем время последнего выполнения
            schedule.last_generated = timezone.now()
            schedule.save()

            execution_time = (time.time() - start_time) * 1000

            # Логируем выполнение
            if has_audit:
                AuditLog.log_report_schedule(
                    user=user,
                    schedule_name=schedule.name,
                    frequency=schedule.frequency,
                    is_successful=result['status'] == 'success',
                    error_message=result.get('error_message', '')
                )

            if result['status'] == 'success':
                logger.info(f"Запланированный отчет #{schedule_id} выполнен успешно за {execution_time:.2f} мс")
            else:
                logger.error(
                    f"Ошибка выполнения запланированного отчета #{schedule_id}: {result.get('error_message', '')}")

            return result

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Ошибка выполнения запланированного отчета #{schedule_id}: {str(e)}")

            return {
                'status': 'error',
                'error_message': str(e),
                'execution_time': execution_time
            }

    @staticmethod
    def send_report_by_email(report_id, recipients, user=None):
        """
        Отправка отчета по email

        Args:
            report_id: ID отчета
            recipients: Список email получателей
            user: Пользователь, инициировавший отправку

        Returns:
            dict: Результат выполнения задачи
        """
        start_time = time.time()

        try:
            from .models import SavedReport

            # Условный импорт для аудита - если приложение существует
            try:
                from audit.models import AuditLog
                has_audit = True
            except ImportError:
                has_audit = False
                logger.warning("Приложение audit не найдено, логирование отключено")

            logger.info(f"Отправка отчета #{report_id} по email")

            # Получаем отчет
            report = SavedReport.objects.get(id=report_id)

            # Подготавливаем email
            subject = f"Отчет: {report.name}"

            # Генерируем HTML содержимое
            context = {
                'report': report,
                'generated_at': report.generated_at,
                'user': user,
            }

            html_message = render_to_string('reports/email/report_notification.html', context)
            plain_message = f"Отчет '{report.name}' был сгенерирован {report.generated_at.strftime('%Y-%m-%d %H:%M')}"

            # Отправляем email
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=recipients,
                html_message=html_message,
                fail_silently=False
            )

            execution_time = (time.time() - start_time) * 1000

            # Логируем отправку
            if user and has_audit:
                AuditLog.log_system_action(
                    user=user,
                    action_description=f"Отправка отчета '{report.name}' по email",
                    is_successful=True,
                    severity='low'
                )

            logger.info(f"Отчет #{report_id} успешно отправлен по email за {execution_time:.2f} мс")

            return {
                'status': 'success',
                'recipients_count': len(recipients),
                'execution_time': execution_time
            }

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Ошибка отправки отчета #{report_id} по email: {str(e)}")

            if user and has_audit:
                AuditLog.log_system_action(
                    user=user,
                    action_description=f"Ошибка отправки отчета по email: {str(e)}",
                    is_successful=False,
                    error_message=str(e),
                    severity='medium'
                )

            return {
                'status': 'error',
                'error_message': str(e),
                'execution_time': execution_time
            }

    @staticmethod
    def cleanup_old_reports(days_old=30):
        """
        Очистка старых отчетов

        Args:
            days_old: Возраст отчетов в днях для удаления

        Returns:
            dict: Результат выполнения задачи
        """
        start_time = time.time()

        try:
            from .models import SavedReport

            # Условный импорт для аудита - если приложение существует
            try:
                from audit.models import AuditLog
                has_audit = True
            except ImportError:
                has_audit = False
                logger.warning("Приложение audit не найдено, логирование отключено")

            logger.info(f"Очистка отчетов старше {days_old} дней")

            cutoff_date = timezone.now() - timedelta(days=days_old)
            old_reports = SavedReport.objects.filter(
                is_temporary=True,
                generated_at__lt=cutoff_date
            )

            deleted_count = 0
            total_size = 0

            for report in old_reports:
                try:
                    if report.cleanup_file():
                        total_size += report.file_size
                        report.delete()
                        deleted_count += 1
                except Exception as e:
                    logger.warning(f"Ошибка удаления отчета #{report.id}: {str(e)}")
                    continue

            execution_time = (time.time() - start_time) * 1000

            # Логируем очистку
            if has_audit:
                AuditLog.log_system_action(
                    user=None,  # Системное действие
                    action_description=f"Очистка старых отчетов: удалено {deleted_count} отчетов, освобождено {total_size} байт",
                    is_successful=True,
                    severity='low'
                )

            logger.info(f"Очистка отчетов завершена: удалено {deleted_count} отчетов за {execution_time:.2f} мс")

            return {
                'status': 'success',
                'deleted_count': deleted_count,
                'freed_space': total_size,
                'execution_time': execution_time
            }

        except Exception as e:
            execution_time = (time.time() - start_time) * 1000
            logger.error(f"Ошибка очистки старых отчетов: {str(e)}")

            if has_audit:
                AuditLog.log_system_action(
                    user=None,
                    action_description=f"Ошибка очистки старых отчетов: {str(e)}",
                    is_successful=False,
                    error_message=str(e),
                    severity='medium'
                )

            return {
                'status': 'error',
                'error_message': str(e),
                'execution_time': execution_time
            }


# Функции-обертки для удобства использования
def generate_financial_report_task(date_from=None, date_to=None, user=None):
    """Обертка для генерации финансового отчета"""
    return ReportTasks.generate_financial_report(date_from, date_to, user)


def generate_client_report_task(parameters=None, user=None):
    """Обертка для генерации отчета по клиентам"""
    return ReportTasks.generate_client_report(parameters, user)


def execute_scheduled_report_task(schedule_id):
    """Обертка для выполнения запланированного отчета"""
    return ReportTasks.execute_scheduled_report(schedule_id)


def send_report_email_task(report_id, recipients, user=None):
    """Обертка для отправки отчета по email"""
    return ReportTasks.send_report_by_email(report_id, recipients, user)


def cleanup_reports_task(days_old=30):
    """Обертка для очистки старых отчетов"""
    return ReportTasks.cleanup_old_reports(days_old)