from django.core.management.base import BaseCommand
from django.utils import timezone
from django.apps import apps
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Генерация отчетов по расписанию'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Показать какие отчеты будут сгенерированы без фактического выполнения',
        )
        parser.add_argument(
            '--schedule-id',
            type=int,
            help='ID конкретного расписания для выполнения',
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
                def check_pending_schedules():
                    return []

                @staticmethod
                def execute_schedule(schedule):
                    return False

                @staticmethod
                def cleanup_old_reports(days_old=30):
                    return 0

            return StubReportScheduler

    def get_models(self):
        """Ленивая загрузка моделей"""
        try:
            return {
                'ReportSchedule': apps.get_model('reports', 'ReportSchedule'),
            }
        except LookupError as e:
            logger.error(f"Ошибка загрузки моделей: {e}")
            return {}

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        schedule_id = options['schedule_id']

        ReportScheduler = self.get_report_scheduler()
        models = self.get_models()

        if not models:
            self.stdout.write(
                self.style.ERROR("Не удалось загрузить модели отчетов")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Запуск генерации отчетов по расписанию. Dry run: {dry_run}"
            )
        )

        if schedule_id:
            # Выполнение конкретного расписания
            try:
                schedule = models['ReportSchedule'].objects.get(id=schedule_id, is_active=True)
                schedules_to_run = [schedule]
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Выполнение конкретного расписания: {schedule.name}"
                    )
                )
            except models['ReportSchedule'].DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(
                        f"Расписание с ID {schedule_id} не найдено или не активно"
                    )
                )
                return
        else:
            # Проверка всех активных расписаний
            schedules_to_run = ReportScheduler.check_pending_schedules()

        if not schedules_to_run:
            self.stdout.write(
                self.style.WARNING("Нет отчетов для генерации по расписанию")
            )
            return

        self.stdout.write(
            self.style.SUCCESS(
                f"Найдено отчетов для генерации: {len(schedules_to_run)}"
            )
        )

        for schedule in schedules_to_run:
            self.stdout.write(
                f" - {schedule.name} ({schedule.get_frequency_display()})"
            )

        if dry_run:
            self.stdout.write(
                self.style.SUCCESS("Dry run завершен. Отчеты не были сгенерированы.")
            )
            return

        # Фактическое выполнение
        successful = 0
        failed = 0

        for schedule in schedules_to_run:
            try:
                self.stdout.write(
                    f"Генерация отчета: {schedule.name}..."
                )

                if ReportScheduler.execute_schedule(schedule):
                    successful += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✓ Отчет {schedule.name} успешно сгенерирован"
                        )
                    )
                else:
                    failed += 1
                    self.stdout.write(
                        self.style.ERROR(
                            f"✗ Ошибка при генерации отчета {schedule.name}"
                        )
                    )

            except Exception as e:
                failed += 1
                logger.error(f"Ошибка при выполнении расписания {schedule.name}: {str(e)}")
                self.stdout.write(
                    self.style.ERROR(
                        f"✗ Исключение при генерации отчета {schedule.name}: {str(e)}"
                    )
                )

        # Очистка старых отчетов
        cleaned_count = ReportScheduler.cleanup_old_reports()
        if cleaned_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"Очищено старых временных отчетов: {cleaned_count}"
                )
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Генерация отчетов завершена. Успешно: {successful}, Ошибки: {failed}"
            )
        )