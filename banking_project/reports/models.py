from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from decimal import Decimal
import json


class ReportTemplate(models.Model):
    """
    Шаблоны отчетов для повторного использования
    """
    REPORT_TYPES = (
        ('financial', 'Финансовый отчет'),
        ('client', 'Отчет по клиентам'),
        ('credit', 'Отчет по кредитам'),
        ('deposit', 'Отчет по депозитам'),
        ('transaction', 'Отчет по транзакциям'),
        ('interest_accrual', 'Отчет по начисленным процентам'),  # НОВЫЙ ТИП
        ('custom', 'Пользовательский отчет'),
    )

    FORMAT_CHOICES = (
        ('html', 'HTML'),
        ('pdf', 'PDF'),
        ('excel', 'Excel'),
        ('csv', 'CSV'),
        ('json', 'JSON'),
    )

    name = models.CharField(
        max_length=200,
        verbose_name='Название шаблона'
    )
    report_type = models.CharField(
        max_length=20,
        choices=REPORT_TYPES,
        verbose_name='Тип отчета'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    template_parameters = models.JSONField(
        default=dict,
        verbose_name='Параметры шаблона'
    )
    default_format = models.CharField(
        max_length=10,
        choices=FORMAT_CHOICES,
        default='html',
        verbose_name='Формат по умолчанию'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_report_templates',
        verbose_name='Создатель'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    # НОВОЕ ПОЛЕ: Категория для организации шаблонов
    category = models.CharField(
        max_length=100,
        default='general',
        verbose_name='Категория'
    )

    class Meta:
        verbose_name = 'Шаблон отчета'
        verbose_name_plural = 'Шаблоны отчетов'
        ordering = ['category', 'name']

    def __str__(self):
        return f"{self.name} ({self.get_report_type_display()})"

    def get_parameters_display(self):
        """Отображение параметров в читаемом формате"""
        return json.dumps(self.template_parameters, ensure_ascii=False, indent=2)

    def clone_template(self, new_name, new_creator):
        """Создание копии шаблона"""
        return ReportTemplate.objects.create(
            name=new_name,
            report_type=self.report_type,
            description=self.description,
            template_parameters=self.template_parameters.copy(),
            default_format=self.default_format,
            created_by=new_creator,
            category=self.category
        )


class SavedReport(models.Model):
    """
    Сохраненные отчеты для истории и повторного использования
    """
    name = models.CharField(
        max_length=200,
        verbose_name='Название отчета'
    )
    report_type = models.CharField(
        max_length=20,
        choices=ReportTemplate.REPORT_TYPES,
        verbose_name='Тип отчета'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    parameters = models.JSONField(
        default=dict,
        verbose_name='Параметры отчета'
    )
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='generated_reports',
        verbose_name='Кем сгенерирован'
    )
    generated_at = models.DateTimeField(
        default=timezone.now,
        verbose_name='Время генерации'
    )
    file_format = models.CharField(
        max_length=10,
        choices=ReportTemplate.FORMAT_CHOICES,
        verbose_name='Формат файла'
    )
    file_path = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Путь к файлу'
    )
    file_size = models.BigIntegerField(
        default=0,
        verbose_name='Размер файла (байты)'
    )
    is_temporary = models.BooleanField(
        default=False,
        verbose_name='Временный файл'
    )
    # НОВОЕ ПОЛЕ: Ссылка на шаблон (если отчет создан из шаблона)
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='saved_reports',
        verbose_name='Шаблон'
    )
    # НОВОЕ ПОЛЕ: Данные отчета в сжатом виде (для быстрого предпросмотра)
    preview_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Данные для предпросмотра'
    )

    class Meta:
        verbose_name = 'Сохраненный отчет'
        verbose_name_plural = 'Сохраненные отчеты'
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['report_type', 'generated_at']),
            models.Index(fields=['generated_by', 'generated_at']),
        ]

    def __str__(self):
        return f"{self.name} - {self.generated_at.strftime('%Y-%m-%d %H:%M')}"

    def get_readable_file_size(self):
        """Человеко-читаемый размер файла"""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{self.file_size / 1024:.2f} KB"
        elif self.file_size < 1024 * 1024 * 1024:
            return f"{self.file_size / (1024 * 1024):.2f} MB"
        else:
            return f"{self.file_size / (1024 * 1024 * 1024):.2f} GB"

    def get_parameters_display(self):
        """Отображение параметров в читаемом формате"""
        return json.dumps(self.parameters, ensure_ascii=False, indent=2)

    def mark_as_permanent(self):
        """Пометить отчет как постоянный"""
        self.is_temporary = False
        self.save()

    def cleanup_file(self):
        """Очистка файла отчета (если временный)"""
        import os
        if self.is_temporary and self.file_path and os.path.exists(self.file_path):
            try:
                os.remove(self.file_path)
                return True
            except OSError:
                return False
        return False


class ReportSchedule(models.Model):
    """
    Расписание автоматической генерации отчетов
    """
    FREQUENCY_CHOICES = (
        ('daily', 'Ежедневно'),
        ('weekly', 'Еженедельно'),
        ('monthly', 'Ежемесячно'),
        ('quarterly', 'Ежеквартально'),
        ('yearly', 'Ежегодно'),
    )

    DAY_OF_WEEK_CHOICES = (
        (1, 'Понедельник'),
        (2, 'Вторник'),
        (3, 'Среда'),
        (4, 'Четверг'),
        (5, 'Пятница'),
        (6, 'Суббота'),
        (7, 'Воскресенье'),
    )

    name = models.CharField(
        max_length=200,
        verbose_name='Название расписания'
    )
    template = models.ForeignKey(
        ReportTemplate,
        on_delete=models.CASCADE,
        related_name='schedules',
        verbose_name='Шаблон отчета'
    )
    frequency = models.CharField(
        max_length=20,
        choices=FREQUENCY_CHOICES,
        verbose_name='Частота'
    )
    # Параметры для еженедельного расписания
    day_of_week = models.IntegerField(
        choices=DAY_OF_WEEK_CHOICES,
        null=True,
        blank=True,
        verbose_name='День недели'
    )
    # Параметры для ежемесячного расписания
    day_of_month = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(31)],
        null=True,
        blank=True,
        verbose_name='День месяца'
    )
    # Время генерации
    generation_time = models.TimeField(
        default=timezone.now,
        verbose_name='Время генерации'
    )
    # Получатели отчета (email)
    recipients = models.TextField(
        blank=True,
        verbose_name='Получатели (email через запятую)'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активно'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='created_schedules',
        verbose_name='Создатель'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    last_generated = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Последняя генерация'
    )
    # НОВОЕ ПОЛЕ: Дополнительные параметры
    extra_parameters = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Дополнительные параметры'
    )

    class Meta:
        verbose_name = 'Расписание отчетов'
        verbose_name_plural = 'Расписания отчетов'
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_frequency_display()})"

    def get_recipients_list(self):
        """Получение списка получателей"""
        if self.recipients:
            return [email.strip() for email in self.recipients.split(',')]
        return []

    def should_generate_now(self):
        """Проверка, нужно ли генерировать отчет сейчас"""
        now = timezone.now()

        # Проверяем время
        if now.time() < self.generation_time:
            return False

        # Проверяем частоту
        if self.frequency == 'daily':
            return True
        elif self.frequency == 'weekly':
            return now.isoweekday() == self.day_of_week
        elif self.frequency == 'monthly':
            return now.day == self.day_of_month
        elif self.frequency == 'quarterly':
            # Кварталы: Jan-Mar, Apr-Jun, Jul-Sep, Oct-Dec
            quarter_month = ((now.month - 1) // 3 + 1) * 3  # Последний месяц квартала
            return now.month == quarter_month and now.day == self.day_of_month
        elif self.frequency == 'yearly':
            return now.month == 12 and now.day == self.day_of_month

        return False

    def mark_generated(self):
        """Отметить отчет как сгенерированный"""
        self.last_generated = timezone.now()
        self.save()


class DashboardWidget(models.Model):
    """
    Виджеты для дашборда отчетности
    """
    WIDGET_TYPES = (
        ('statistic', 'Статистика'),
        ('chart', 'График'),
        ('table', 'Таблица'),
        ('progress', 'Прогресс'),
    )

    CHART_TYPES = (
        ('bar', 'Столбчатая'),
        ('line', 'Линейная'),
        ('pie', 'Круговая'),
        ('doughnut', 'Кольцевая'),
    )

    name = models.CharField(
        max_length=100,
        verbose_name='Название виджета'
    )
    widget_type = models.CharField(
        max_length=20,
        choices=WIDGET_TYPES,
        verbose_name='Тип виджета'
    )
    chart_type = models.CharField(
        max_length=20,
        choices=CHART_TYPES,
        blank=True,
        verbose_name='Тип графика'
    )
    data_source = models.CharField(
        max_length=100,
        verbose_name='Источник данных'
    )
    parameters = models.JSONField(
        default=dict,
        verbose_name='Параметры'
    )
    position = models.IntegerField(
        default=0,
        verbose_name='Позиция'
    )
    width = models.CharField(
        max_length=20,
        default='col-md-6',
        verbose_name='Ширина'
    )
    is_visible = models.BooleanField(
        default=True,
        verbose_name='Видимый'
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name='Создатель'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    # НОВОЕ ПОЛЕ: Обновление данных в реальном времени
    refresh_interval = models.IntegerField(
        default=0,
        verbose_name='Интервал обновления (сек)'
    )

    class Meta:
        verbose_name = 'Виджет дашборда'
        verbose_name_plural = 'Виджеты дашборда'
        ordering = ['position', 'name']

    def __str__(self):
        return self.name

    def get_data(self):
        """Получение данных для виджета"""
        # Здесь может быть сложная логика получения данных
        # В зависимости от data_source и parameters
        return {
            'value': 0,
            'previous_value': 0,
            'change_percent': 0,
            'data': []
        }