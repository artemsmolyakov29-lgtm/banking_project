from django.db import models
from django.conf import settings
from django.utils import timezone
import uuid


class AuditLog(models.Model):
    """
    Лог всех действий пользователей в системе
    """
    ACTION_TYPES = (
        ('create', 'Создание'),
        ('update', 'Обновление'),
        ('delete', 'Удаление'),
        ('view', 'Просмотр'),
        ('login', 'Вход в систему'),
        ('logout', 'Выход из системы'),
        ('export', 'Экспорт данных'),
        ('backup', 'Резервное копирование'),
        ('restore', 'Восстановление'),
        ('interest_accrual', 'Начисление процентов'),
        ('report_generate', 'Генерация отчета'),
        ('report_export', 'Экспорт отчета'),  # НОВЫЙ ТИП ДЕЙСТВИЯ
        ('report_schedule', 'Планирование отчета'),  # НОВЫЙ ТИП ДЕЙСТВИЯ
        ('system', 'Системное действие'),  # НОВЫЙ ТИП ДЕЙСТВИЯ
    )

    MODULE_CHOICES = (
        ('users', 'Пользователи'),
        ('clients', 'Клиенты'),
        ('accounts', 'Счета'),
        ('cards', 'Карты'),
        ('credits', 'Кредиты'),
        ('deposits', 'Депозиты'),
        ('transactions', 'Транзакции'),
        ('reports', 'Отчеты'),
        ('system', 'Система'),
        ('interest', 'Проценты'),
        ('audit', 'Аудит'),  # НОВЫЙ МОДУЛЬ
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='audit_logs',
        verbose_name='Пользователь'
    )
    action = models.CharField(
        max_length=20,
        choices=ACTION_TYPES,
        verbose_name='Действие'
    )
    module = models.CharField(
        max_length=20,
        choices=MODULE_CHOICES,
        verbose_name='Модуль'
    )
    table_name = models.CharField(
        max_length=100,
        verbose_name='Таблица/Модель'
    )
    record_id = models.IntegerField(
        null=True,
        blank=True,
        verbose_name='ID записи'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP адрес'
    )
    user_agent = models.TextField(
        blank=True,
        verbose_name='User Agent'
    )
    old_values = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Старые значения'
    )
    new_values = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Новые значения'
    )
    timestamp = models.DateTimeField(
        default=timezone.now,
        verbose_name='Время события'
    )
    is_successful = models.BooleanField(
        default=True,
        verbose_name='Успешно'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Сообщение об ошибке'
    )
    related_objects = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Связанные объекты'
    )
    # НОВОЕ ПОЛЕ: Уникальный идентификатор для группировки связанных действий
    session_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        verbose_name='ID сессии'
    )
    # НОВОЕ ПОЛЕ: Уровень важности события
    SEVERITY_LEVELS = (
        ('low', 'Низкий'),
        ('medium', 'Средний'),
        ('high', 'Высокий'),
        ('critical', 'Критический'),
    )
    severity = models.CharField(
        max_length=10,
        choices=SEVERITY_LEVELS,
        default='medium',
        verbose_name='Важность'
    )
    # НОВОЕ ПОЛЕ: Время выполнения операции (миллисекунды)
    execution_time = models.FloatField(
        null=True,
        blank=True,
        verbose_name='Время выполнения (мс)'
    )

    class Meta:
        verbose_name = 'Запись аудита'
        verbose_name_plural = 'Записи аудита'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['module', 'timestamp']),
            models.Index(fields=['table_name', 'record_id']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['is_successful']),
            models.Index(fields=['severity']),  # НОВЫЙ ИНДЕКС
            models.Index(fields=['session_id']),  # НОВЫЙ ИНДЕКС
        ]

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.table_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log_action(cls, user, action, module, table_name, record_id=None,
                   description='', ip_address=None, user_agent='',
                   old_values=None, new_values=None, is_successful=True,
                   error_message='', related_objects=None, severity='medium',
                   execution_time=None, session_id=None):
        """
        Статический метод для удобного логирования действий
        """
        if not session_id:
            session_id = uuid.uuid4()

        return cls.objects.create(
            user=user,
            action=action,
            module=module,
            table_name=table_name,
            record_id=record_id,
            description=description,
            ip_address=ip_address,
            user_agent=user_agent,
            old_values=old_values,
            new_values=new_values,
            is_successful=is_successful,
            error_message=error_message,
            related_objects=related_objects,
            severity=severity,
            execution_time=execution_time,
            session_id=session_id
        )

    @classmethod
    def log_interest_accrual(cls, user, deposit, amount, is_successful=True, error_message=''):
        """Специальный метод для логирования начисления процентов"""
        description = f"Начисление процентов по депозиту {deposit.id}: {amount} {deposit.account.currency.code}"

        related_objects = {
            'deposit_id': deposit.id,
            'client_id': deposit.client.id,
            'amount': str(amount),
            'currency': deposit.account.currency.code
        }

        return cls.log_action(
            user=user,
            action='interest_accrual',
            module='interest',
            table_name='DepositInterestPayment',
            description=description,
            is_successful=is_successful,
            error_message=error_message,
            related_objects=related_objects,
            severity='high' if is_successful else 'critical'
        )

    @classmethod
    def log_report_generation(cls, user, report_type, parameters, format='html',
                              is_successful=True, error_message='', execution_time=None):
        """Специальный метод для логирования генерации отчетов"""
        description = f"Генерация отчета: {report_type} в формате {format}"

        return cls.log_action(
            user=user,
            action='report_generate',
            module='reports',
            table_name='Report',
            description=description,
            is_successful=is_successful,
            error_message=error_message,
            related_objects={
                'report_type': report_type,
                'parameters': parameters,
                'format': format
            },
            severity='medium',
            execution_time=execution_time
        )

    @classmethod
    def log_report_export(cls, user, report_type, export_format, record_count,
                          is_successful=True, error_message='', execution_time=None):
        """Специальный метод для логирования экспорта отчетов"""
        description = f"Экспорт отчета {report_type} в формате {export_format} ({record_count} записей)"

        return cls.log_action(
            user=user,
            action='report_export',
            module='reports',
            table_name='Export',
            description=description,
            is_successful=is_successful,
            error_message=error_message,
            related_objects={
                'report_type': report_type,
                'export_format': export_format,
                'record_count': record_count
            },
            severity='low',
            execution_time=execution_time
        )

    @classmethod
    def log_report_schedule(cls, user, schedule_name, frequency, is_successful=True, error_message=''):
        """Специальный метод для логирования планирования отчетов"""
        description = f"Планирование отчета: {schedule_name} ({frequency})"

        return cls.log_action(
            user=user,
            action='report_schedule',
            module='reports',
            table_name='ReportSchedule',
            description=description,
            is_successful=is_successful,
            error_message=error_message,
            related_objects={
                'schedule_name': schedule_name,
                'frequency': frequency
            },
            severity='medium'
        )

    @classmethod
    def log_system_action(cls, user, action_description, is_successful=True,
                          error_message='', severity='medium'):
        """Специальный метод для логирования системных действий"""
        return cls.log_action(
            user=user,
            action='system',
            module='system',
            table_name='System',
            description=action_description,
            is_successful=is_successful,
            error_message=error_message,
            severity=severity
        )


class SystemSettings(models.Model):
    """
    Настройки системы для аудита и мониторинга
    """
    key = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Ключ настройки'
    )
    value = models.TextField(
        verbose_name='Значение'
    )
    data_type = models.CharField(
        max_length=20,
        choices=(
            ('string', 'Строка'),
            ('integer', 'Целое число'),
            ('float', 'Дробное число'),
            ('boolean', 'Логическое'),
            ('json', 'JSON'),
        ),
        default='string',
        verbose_name='Тип данных'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание'
    )
    is_public = models.BooleanField(
        default=False,
        verbose_name='Публичная настройка'
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Кем обновлено'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )
    category = models.CharField(
        max_length=50,
        default='general',
        verbose_name='Категория'
    )
    # НОВОЕ ПОЛЕ: Версия настройки для отслеживания изменений
    version = models.IntegerField(
        default=1,
        verbose_name='Версия'
    )
    # НОВОЕ ПОЛЕ: Активна ли настройка
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активна'
    )

    class Meta:
        verbose_name = 'Настройка системы'
        verbose_name_plural = 'Настройки системы'
        ordering = ['category', 'key']

    def __str__(self):
        return f"{self.category}.{self.key}"

    def get_typed_value(self):
        """Получение значения в правильном типе данных"""
        try:
            if self.data_type == 'integer':
                return int(self.value)
            elif self.data_type == 'float':
                return float(self.value)
            elif self.data_type == 'boolean':
                return self.value.lower() in ('true', '1', 'yes', 'on')
            elif self.data_type == 'json':
                import json
                return json.loads(self.value)
            else:
                return self.value
        except (ValueError, TypeError, json.JSONDecodeError):
            # Возвращаем значение по умолчанию в случае ошибки
            if self.data_type == 'integer':
                return 0
            elif self.data_type == 'float':
                return 0.0
            elif self.data_type == 'boolean':
                return False
            elif self.data_type == 'json':
                return {}
            else:
                return self.value

    @classmethod
    def get_setting(cls, key, default=None):
        """Получение значения настройки по ключу"""
        try:
            setting = cls.objects.get(key=key, is_active=True)
            return setting.get_typed_value()
        except cls.DoesNotExist:
            return default

    @classmethod
    def set_setting(cls, key, value, data_type='string', category='general',
                    description='', is_public=False, user=None):
        """Установка значения настройки"""
        if isinstance(value, (dict, list)):
            import json
            value = json.dumps(value, ensure_ascii=False)
            data_type = 'json'
        elif isinstance(value, bool):
            value = 'true' if value else 'false'
            data_type = 'boolean'
        elif isinstance(value, (int, float)):
            value = str(value)
            data_type = 'float' if isinstance(value, float) else 'integer'
        else:
            value = str(value)
            data_type = 'string'

        setting, created = cls.objects.get_or_create(
            key=key,
            defaults={
                'value': value,
                'data_type': data_type,
                'category': category,
                'description': description,
                'is_public': is_public,
                'updated_by': user,
            }
        )

        if not created:
            setting.value = value
            setting.data_type = data_type
            setting.category = category
            setting.description = description
            setting.is_public = is_public
            setting.updated_by = user
            setting.version += 1
            setting.save()

        return setting


class BackupHistory(models.Model):
    """
    История резервных копий
    """
    backup_file = models.CharField(
        max_length=255,
        verbose_name='Файл резервной копии'
    )
    backup_size = models.BigIntegerField(
        verbose_name='Размер файла (байты)'
    )
    backup_type = models.CharField(
        max_length=20,
        choices=(
            ('full', 'Полная'),
            ('incremental', 'Инкрементальная'),
            ('differential', 'Дифференциальная'),
        ),
        default='full',
        verbose_name='Тип резервной копии'
    )
    status = models.CharField(
        max_length=20,
        choices=(
            ('success', 'Успешно'),
            ('failed', 'Ошибка'),
            ('in_progress', 'В процессе'),
        ),
        default='in_progress',
        verbose_name='Статус'
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Инициатор'
    )
    start_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время начала'
    )
    end_time = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Время завершения'
    )
    error_message = models.TextField(
        blank=True,
        verbose_name='Сообщение об ошибке'
    )
    storage_location = models.CharField(
        max_length=500,
        blank=True,
        verbose_name='Место хранения'
    )
    included_data = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Включенные данные'
    )
    # НОВОЕ ПОЛЕ: Уникальный идентификатор бэкапа
    backup_id = models.UUIDField(
        default=uuid.uuid4,
        editable=False,
        unique=True,
        verbose_name='ID резервной копии'
    )
    # НОВОЕ ПОЛЕ: Хэш для проверки целостности
    checksum = models.CharField(
        max_length=64,
        blank=True,
        verbose_name='Контрольная сумма'
    )
    # НОВОЕ ПОЛЕ: Метadata бэкапа
    metadata = models.JSONField(
        null=True,
        blank=True,
        verbose_name='Метаданные'
    )

    class Meta:
        verbose_name = 'История резервного копирования'
        verbose_name_plural = 'История резервного копирования'
        ordering = ['-start_time']
        indexes = [
            models.Index(fields=['status', 'start_time']),
            models.Index(fields=['backup_type', 'start_time']),
            models.Index(fields=['backup_id']),
        ]

    def __str__(self):
        return f"Бэкап {self.backup_file} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def duration(self):
        """Длительность операции бэкапа"""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None

    def mark_completed(self, file_size=0, storage_location='', included_data=None,
                       checksum='', metadata=None):
        """Отметить бэкап как завершенный"""
        self.status = 'success'
        self.end_time = timezone.now()
        self.backup_size = file_size
        self.storage_location = storage_location
        if included_data:
            self.included_data = included_data
        if checksum:
            self.checksum = checksum
        if metadata:
            self.metadata = metadata
        self.save()

        # Логируем успешное завершение бэкапа
        AuditLog.log_system_action(
            user=self.initiated_by,
            action_description=f"Резервное копирование завершено: {self.backup_file}",
            is_successful=True,
            severity='high'
        )

    def mark_failed(self, error_message=''):
        """Отметить бэкап как неуспешный"""
        self.status = 'failed'
        self.end_time = timezone.now()
        self.error_message = error_message
        self.save()

        # Логируем ошибку бэкапа
        AuditLog.log_system_action(
            user=self.initiated_by,
            action_description=f"Ошибка резервного копирования: {error_message}",
            is_successful=False,
            error_message=error_message,
            severity='critical'
        )

    def get_readable_size(self):
        """Человеко-читаемый размер файла"""
        if self.backup_size < 1024:
            return f"{self.backup_size} B"
        elif self.backup_size < 1024 * 1024:
            return f"{self.backup_size / 1024:.2f} KB"
        elif self.backup_size < 1024 * 1024 * 1024:
            return f"{self.backup_size / (1024 * 1024):.2f} MB"
        else:
            return f"{self.backup_size / (1024 * 1024 * 1024):.2f} GB"

    def is_integrity_valid(self, current_checksum):
        """Проверка целостности бэкапа"""
        return self.checksum == current_checksum if self.checksum else False