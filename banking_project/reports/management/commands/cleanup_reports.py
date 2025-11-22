from django.core.management.base import BaseCommand
from django.apps import apps
from django.utils import timezone
from datetime import timedelta
import os
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Очистка старых и временных отчетов'

    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Количество дней для хранения отчетов (по умолчанию: 30)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать какие отчеты будут удалены без фактического удаления',
        )
        parser.add_argument(
            '--only-temporary',
            action='store_true',
            help='Удалять только временные отчеты',
        )

    def get_report_scheduler(self):
        """Ленивая загрузка ReportScheduler"""
        try:
            from ...utils import ReportScheduler
            return ReportScheduler
        except ImportError as e:
            logger.error(f"Ошибка импорта ReportScheduler: {e}")

            # Создаем заглушку если импорт не удался
            class StubReportScheduler:
                @staticmethod
                def cleanup_old_reports(days_old=30):
                    # Базовая реализация очистки
                    SavedReport = apps.get_model('reports', 'SavedReport')
                    cutoff_date = timezone.now() - timedelta(days=days_old)
                    old_reports = SavedReport.objects.filter(
                        is_temporary=True,
                        generated_at__lt=cutoff_date
                    )

                    deleted_count = 0
                    for report in old_reports:
                        try:
                            if report.file_path and os.path.exists(report.file_path):
                                os.remove(report.file_path)
                            report.delete()
                            deleted_count += 1
                        except Exception:
                            continue

                    return deleted_count

            return StubReportScheduler

    def get_models(self):
        """Ленивая загрузка моделей"""
        try:
            return {
                'SavedReport': apps.get_model('reports', 'SavedReport'),
            }
        except LookupError as e:
            logger.error(f"Ошибка загрузки моделей: {e}")
            return {}

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        only_temporary = options['only_temporary']

        ReportScheduler = self.get_report_scheduler()
        models = self.get_models()

        if not models:
            self.stdout.write(
                self.style.ERROR("Не удалось загрузить модели отчетов")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Запуск очистки отчетов старше {days} дней"
            )
        )

        cutoff_date = timezone.now() - timedelta(days=days)

        # Построение запроса
        if only_temporary:
            reports_to_delete = models['SavedReport'].objects.filter(
                is_temporary=True,
                generated_at__lt=cutoff_date
            )
            report_type = "временные"
        else:
            reports_to_delete = models['SavedReport'].objects.filter(
                generated_at__lt=cutoff_date
            )
            report_type = "все"

        count = reports_to_delete.count()

        if count == 0:
            self.stdout.write(
                self.style.WARNING(f"Нет {report_type} отчетов для удаления")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Найдено {report_type} отчетов для удаления: {count}"
            )
        )

        if dry_run:
            # Показать отчеты которые будут удалены
            for report in reports_to_delete[:10]:  # Ограничим вывод
                self.stdout.write(
                    f" - {report.name} ({report.generated_at.strftime('%Y-%m-%d')})"
                )
            if count > 10:
                self.stdout.write(f" - ... и еще {count - 10} отчетов")

            self.stdout.write(
                self.style.SUCCESS("Dry run завершен. Отчеты не были удалены.")
            )
            return

        # Фактическое удаление
        if only_temporary:
            # Используем ReportScheduler для временных отчетов
            deleted_count = ReportScheduler.cleanup_old_reports(days)
        else:
            # Ручное удаление для всех отчетов
            deleted_count = 0
            for report in reports_to_delete:
                try:
                    # Очистка файла
                    if report.file_path and os.path.exists(report.file_path):
                        os.remove(report.file_path)
                    report.delete()
                    deleted_count += 1
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Ошибка при удалении отчета {report.name}: {str(e)}"
                        )
                    )

        self.stdout.write(
            self.style.SUCCESS(
                f"Очистка завершена. Удалено отчетов: {deleted_count}"
            )
        )