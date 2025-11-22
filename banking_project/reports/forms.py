from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from .models import ReportTemplate, ReportSchedule, DashboardWidget, AnalyticsDashboard, ExportFormat


class ReportParametersForm(forms.ModelForm):
    """Форма для параметров отчета"""

    class Meta:
        model = ReportTemplate
        fields = [
            'name', 'report_type', 'description', 'template_parameters',
            'default_format', 'is_active', 'category'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'report_type': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'default_format': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.TextInput(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Название шаблона',
            'report_type': 'Тип отчета',
            'description': 'Описание',
            'template_parameters': 'Параметры шаблона',
            'default_format': 'Формат по умолчанию',
            'is_active': 'Активен',
            'category': 'Категория',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['template_parameters'].widget = forms.HiddenInput()


class ScheduleReportForm(forms.ModelForm):
    """Форма для планирования отчетов"""

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Ограничиваем выбор шаблонов только созданными пользователем или активными
        if self.user:
            self.fields['template'].queryset = ReportTemplate.objects.filter(
                Q(created_by=self.user) | Q(is_active=True)
            )

        # Динамическое отображение полей в зависимости от частоты
        if self.instance and self.instance.frequency:
            self.update_fields_visibility(self.instance.frequency)

    class Meta:
        model = ReportSchedule
        fields = [
            'name', 'template', 'frequency', 'day_of_week', 'day_of_month',
            'generation_time', 'recipients', 'is_active', 'extra_parameters',
            'export_formats', 'save_reports', 'reports_keep_count'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'template': forms.Select(attrs={'class': 'form-control'}),
            'frequency': forms.Select(attrs={'class': 'form-control', 'onchange': 'updateScheduleFields()'}),
            'day_of_week': forms.Select(attrs={'class': 'form-control'}),
            'day_of_month': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31}),
            'generation_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'recipients': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'email1@example.com, email2@example.com'}),
            'extra_parameters': forms.HiddenInput(),
            'export_formats': forms.SelectMultiple(attrs={'class': 'form-control'}),
        }
        labels = {
            'name': 'Название расписания',
            'template': 'Шаблон отчета',
            'frequency': 'Частота',
            'day_of_week': 'День недели',
            'day_of_month': 'День месяца',
            'generation_time': 'Время генерации',
            'recipients': 'Получатели (email через запятую)',
            'is_active': 'Активно',
            'extra_parameters': 'Дополнительные параметры',
            'export_formats': 'Форматы экспорта',
            'save_reports': 'Сохранять отчеты',
            'reports_keep_count': 'Хранить последних отчетов',
        }

    def clean_recipients(self):
        """Валидация email получателей"""
        recipients = self.cleaned_data.get('recipients', '')
        if recipients:
            emails = [email.strip() for email in recipients.split(',')]
            for email in emails:
                if email and '@' not in email:
                    raise ValidationError(f'Некорректный email: {email}')
        return recipients

    def clean_day_of_month(self):
        """Валидация дня месяца"""
        day_of_month = self.cleaned_data.get('day_of_month')
        frequency = self.cleaned_data.get('frequency')

        if frequency == 'monthly' and not day_of_month:
            raise ValidationError('Для ежемесячного расписания необходимо указать день месяца.')

        if day_of_month and (day_of_month < 1 or day_of_month > 31):
            raise ValidationError('День месяца должен быть между 1 и 31.')

        return day_of_month

    def clean_day_of_week(self):
        """Валидация дня недели"""
        day_of_week = self.cleaned_data.get('day_of_week')
        frequency = self.cleaned_data.get('frequency')

        if frequency == 'weekly' and not day_of_week:
            raise ValidationError('Для еженедельного расписания необходимо указать день недели.')

        return day_of_week

    def clean(self):
        """Общая валидация формы"""
        cleaned_data = super().clean()
        frequency = cleaned_data.get('frequency')
        day_of_week = cleaned_data.get('day_of_week')
        day_of_month = cleaned_data.get('day_of_month')

        if frequency == 'weekly' and not day_of_week:
            self.add_error('day_of_week', 'Для еженедельного расписания необходимо указать день недели.')

        if frequency == 'monthly' and not day_of_month:
            self.add_error('day_of_month', 'Для ежемесячного расписания необходимо указать день месяца.')

        if frequency == 'quarterly' and not day_of_month:
            self.add_error('day_of_month', 'Для ежеквартального расписания необходимо указать день месяца.')

        if frequency == 'yearly' and not day_of_month:
            self.add_error('day_of_month', 'Для ежегодного расписания необходимо указать день месяца.')

        return cleaned_data

    def update_fields_visibility(self, frequency):
        """Обновление видимости полей в зависимости от частоты"""
        if frequency == 'daily':
            self.fields['day_of_week'].widget = forms.HiddenInput()
            self.fields['day_of_month'].widget = forms.HiddenInput()
        elif frequency == 'weekly':
            self.fields['day_of_week'].widget = forms.Select(attrs={'class': 'form-control'})
            self.fields['day_of_month'].widget = forms.HiddenInput()
        elif frequency in ['monthly', 'quarterly', 'yearly']:
            self.fields['day_of_week'].widget = forms.HiddenInput()
            self.fields['day_of_month'].widget = forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 31})


class ExportFormatForm(forms.Form):
    """Форма для выбора формата экспорта"""

    DATA_TYPE_CHOICES = (
        ('clients', 'Клиенты'),
        ('credits', 'Кредиты'),
        ('deposits', 'Депозиты'),
        ('transactions', 'Транзакции'),
        ('financial', 'Финансовый отчет'),
        ('cards', 'Карты'),
        ('interest_accruals', 'Начисленные проценты'),
    )

    EXPORT_FORMAT_CHOICES = (
        ('json', 'JSON'),
        ('csv', 'CSV'),
        ('xlsx', 'Excel'),
        ('pdf', 'PDF'),
    )

    COMPRESSION_CHOICES = (
        (False, 'Без сжатия'),
        (True, 'Со сжатием'),
    )

    data_type = forms.ChoiceField(
        choices=DATA_TYPE_CHOICES,
        label='Тип данных',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    export_format = forms.ChoiceField(
        choices=EXPORT_FORMAT_CHOICES,
        label='Формат экспорта',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    include_metadata = forms.BooleanField(
        required=False,
        initial=True,
        label='Включать метаданные',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    compression = forms.ChoiceField(
        choices=COMPRESSION_CHOICES,
        required=False,
        initial=False,
        label='Сжатие',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    date_from = forms.DateField(
        required=False,
        label='Дата с',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    date_to = forms.DateField(
        required=False,
        label='Дата по',
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    def clean(self):
        """Валидация дат"""
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')

        if date_from and date_to and date_from > date_to:
            raise ValidationError('Дата "с" не может быть позже даты "по".')

        return cleaned_data


class DashboardWidgetForm(forms.ModelForm):
    """Форма для виджетов дашборда"""

    class Meta:
        model = DashboardWidget
        fields = [
            'name', 'widget_type', 'chart_type', 'data_source', 'parameters',
            'position', 'width', 'is_visible', 'refresh_interval', 'color', 'icon', 'description'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'widget_type': forms.Select(attrs={'class': 'form-control', 'onchange': 'updateWidgetFields()'}),
            'chart_type': forms.Select(attrs={'class': 'form-control'}),
            'data_source': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.NumberInput(attrs={'class': 'form-control'}),
            'width': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('col-md-3', '25%'),
                ('col-md-4', '33%'),
                ('col-md-6', '50%'),
                ('col-md-8', '66%'),
                ('col-md-12', '100%'),
            ]),
            'refresh_interval': forms.NumberInput(attrs={'class': 'form-control'}),
            'color': forms.Select(attrs={'class': 'form-control'}, choices=[
                ('primary', 'Синий'),
                ('secondary', 'Серый'),
                ('success', 'Зеленый'),
                ('danger', 'Красный'),
                ('warning', 'Желтый'),
                ('info', 'Голубой'),
                ('light', 'Светлый'),
                ('dark', 'Темный'),
            ]),
            'icon': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'fa fa-chart-line'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'parameters': forms.HiddenInput(),
        }
        labels = {
            'name': 'Название виджета',
            'widget_type': 'Тип виджета',
            'chart_type': 'Тип графика',
            'data_source': 'Источник данных',
            'parameters': 'Параметры',
            'position': 'Позиция',
            'width': 'Ширина',
            'is_visible': 'Видимый',
            'refresh_interval': 'Интервал обновления (сек)',
            'color': 'Цвет',
            'icon': 'Иконка',
            'description': 'Описание',
        }

    def clean_refresh_interval(self):
        """Валидация интервала обновления"""
        refresh_interval = self.cleaned_data.get('refresh_interval', 0)
        if refresh_interval < 0:
            raise ValidationError('Интервал обновления не может быть отрицательным.')
        return refresh_interval


class AnalyticsDashboardForm(forms.ModelForm):
    """Форма для дашбордов аналитики"""

    class Meta:
        model = AnalyticsDashboard
        fields = [
            'name', 'description', 'widgets', 'is_default', 'is_public', 'settings'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'widgets': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'settings': forms.HiddenInput(),
        }
        labels = {
            'name': 'Название дашборда',
            'description': 'Описание',
            'widgets': 'Виджеты',
            'is_default': 'Дашборд по умолчанию',
            'is_public': 'Публичный дашборд',
            'settings': 'Настройки',
        }

    def clean(self):
        """Валидация формы"""
        cleaned_data = super().clean()
        is_default = cleaned_data.get('is_default')

        if is_default:
            # Снимаем флаг "по умолчанию" с других дашбордов
            AnalyticsDashboard.objects.filter(is_default=True).update(is_default=False)

        return cleaned_data


class ReportGenerationForm(forms.Form):
    """Форма для генерации отчетов с параметрами"""

    TEMPLATE_CHOICES = ()

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        report_type = kwargs.pop('report_type', None)
        super().__init__(*args, **kwargs)

        if self.user and report_type:
            templates = ReportTemplate.objects.filter(
                Q(created_by=self.user) | Q(is_active=True),
                report_type=report_type
            )
            self.fields['template'].choices = [(t.id, t.name) for t in templates]

        # Динамически добавляем поля в зависимости от типа отчета
        if report_type == 'financial':
            self.fields['date_from'] = forms.DateField(
                label='Дата с',
                widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
            )
            self.fields['date_to'] = forms.DateField(
                label='Дата по',
                widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
            )
        elif report_type == 'client':
            self.fields['is_vip'] = forms.ChoiceField(
                choices=[('', 'Все'), ('true', 'VIP'), ('false', 'Не VIP')],
                required=False,
                label='Тип клиента',
                widget=forms.Select(attrs={'class': 'form-control'})
            )
            self.fields['min_rating'] = forms.IntegerField(
                required=False,
                min_value=0,
                max_value=100,
                label='Минимальный кредитный рейтинг',
                widget=forms.NumberInput(attrs={'class': 'form-control'})
            )

    template = forms.ChoiceField(
        choices=TEMPLATE_CHOICES,
        required=False,
        label='Шаблон отчета',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    format = forms.ChoiceField(
        choices=ExportFormat.FORMAT_CHOICES,
        initial='html',
        label='Формат',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    save_report = forms.BooleanField(
        required=False,
        initial=True,
        label='Сохранить отчет',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class QuickExportForm(forms.Form):
    """Форма для быстрого экспорта"""

    data_types = forms.MultipleChoiceField(
        choices=ExportFormatForm.DATA_TYPE_CHOICES,
        label='Типы данных',
        widget=forms.SelectMultiple(attrs={'class': 'form-control'})
    )

    format = forms.ChoiceField(
        choices=(
            ('json', 'JSON'),
            ('csv', 'CSV'),
            ('xlsx', 'Excel'),
        ),
        initial='csv',
        label='Формат',
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    def clean_data_types(self):
        """Валидация выбранных типов данных"""
        data_types = self.cleaned_data.get('data_types', [])
        if not data_types:
            raise ValidationError('Выберите хотя бы один тип данных для экспорта.')
        return data_types