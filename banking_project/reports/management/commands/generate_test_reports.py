from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.apps import apps
from django.utils import timezone
import json


class Command(BaseCommand):
    help = 'Генерация тестовых отчетов для демонстрации'

    def add_arguments(self, parser):
        parser.add_argument(
            '--user-id',
            type=int,
            help='ID пользователя для создания тестовых данных',
        )
        parser.add_argument(
            '--clear-existing',
            action='store_true',
            help='Очистить существующие тестовые данные',
        )

    def get_models(self):
        """Ленивая загрузка моделей"""
        return {
            'ReportTemplate': apps.get_model('reports', 'ReportTemplate'),
            'SavedReport': apps.get_model('reports', 'SavedReport'),
        }

    def handle(self, *args, **options):
        user_id = options['user_id']
        clear_existing = options['clear_existing']

        models = self.get_models()
        User = get_user_model()

        if user_id:
            try:
                user = User.objects.get(id=user_id)
            except User.DoesNotExist:
                self.stdout.write(
                    self.style.ERROR(f"Пользователь с ID {user_id} не найден")
                )
                return
        else:
            # Используем первого суперпользователя
            user = User.objects.filter(is_superuser=True).first()
            if not user:
                self.stdout.write(
                    self.style.ERROR("Не найден суперпользователь для создания тестовых данных")
                )
                return

        self.stdout.write(
            self.style.SUCCESS(f"Создание тестовых данных для пользователя: {user.username}")
        )

        if clear_existing:
            # Очистка существующих тестовых данных
            deleted_templates, _ = models['ReportTemplate'].objects.filter(
                name__startswith="[TEST]"
            ).delete()
            deleted_reports, _ = models['SavedReport'].objects.filter(
                name__startswith="[TEST]"
            ).delete()

            self.stdout.write(
                self.style.SUCCESS(
                    f"Удалено тестовых шаблонов: {deleted_templates}, отчетов: {deleted_reports}"
                )
            )

        # Создание тестовых шаблонов отчетов
        test_templates = [
            {
                'name': '[TEST] Финансовый отчет',
                'report_type': 'financial',
                'description': 'Тестовый шаблон финансового отчета',
                'default_format': 'pdf',
                'category': 'financial',
            },
            {
                'name': '[TEST] Отчет по клиентам',
                'report_type': 'client',
                'description': 'Тестовый шаблон отчета по клиентам',
                'default_format': 'xlsx',
                'category': 'client',
            },
            {
                'name': '[TEST] Отчет по депозитам',
                'report_type': 'deposit',
                'description': 'Тестовый шаблон отчета по депозитам',
                'default_format': 'html',
                'category': 'deposit',
            },
        ]

        created_templates = []
        for template_data in test_templates:
            template, created = models['ReportTemplate'].objects.get_or_create(
                name=template_data['name'],
                defaults={
                    'report_type': template_data['report_type'],
                    'description': template_data['description'],
                    'default_format': template_data['default_format'],
                    'category': template_data['category'],
                    'created_by': user,
                    'template_parameters': {'test': True},
                    'is_active': True,
                }
            )
            if created:
                created_templates.append(template)
                self.stdout.write(
                    self.style.SUCCESS(f"Создан шаблон: {template.name}")
                )

        # Создание тестовых сохраненных отчетов
        test_reports = [
            {
                'name': '[TEST] Финансовый отчет за последний месяц',
                'report_type': 'financial',
                'file_format': 'pdf',
                'parameters': {'period': 'last_month'},
            },
            {
                'name': '[TEST] Список клиентов VIP',
                'report_type': 'client',
                'file_format': 'xlsx',
                'parameters': {'is_vip': True},
            },
            {
                'name': '[TEST] Активные депозиты',
                'report_type': 'deposit',
                'file_format': 'html',
                'parameters': {'status': 'active'},
            },
        ]

        created_reports = []
        for report_data in test_reports:
            report = models['SavedReport'].objects.create(
                name=report_data['name'],
                report_type=report_data['report_type'],
                parameters=report_data['parameters'],
                generated_by=user,
                file_format=report_data['file_format'],
                file_path=f"/tmp/test_{report_data['report_type']}.{report_data['file_format']}",
                file_size=1024,  # 1KB тестовый размер
                is_temporary=False,
                generation_status='completed',
            )
            created_reports.append(report)
            self.stdout.write(
                self.style.SUCCESS(f"Создан отчет: {report.name}")
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Создано тестовых шаблонов: {len(created_templates)}, отчетов: {len(created_reports)}"
            )
        )