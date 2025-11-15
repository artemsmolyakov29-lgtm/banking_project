from django.db import models
from django.conf import settings
from django.utils import timezone


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
        ]

    def __str__(self):
        return f"{self.user} - {self.get_action_display()} - {self.table_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log_action(cls, user, action, module, table_name, record_id=None,
                   description='', ip_address=None, user_agent='',
                   old_values=None, new_values=None, is_successful=True, error_message=''):
        """
        Статический метод для удобного логирования действий
        """
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
            error_message=error_message
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

    class Meta:
        verbose_name = 'Настройка системы'
        verbose_name_plural = 'Настройки системы'

    def __str__(self):
        return self.key

    def get_typed_value(self):
        """Получение значения в правильном типе данных"""
        if self.data_type == 'integer':
            return int(self.value)
        elif self.data_type == 'float':
            return float(self.value)
        elif self.data_type == 'boolean':
            return self.value.lower() in ('true', '1', 'yes')
        elif self.data_type == 'json':
            import json
            return json.loads(self.value)
        else:
            return self.value


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

    class Meta:
        verbose_name = 'История резервного копирования'
        verbose_name_plural = 'История резервного копирования'
        ordering = ['-start_time']

    def __str__(self):
        return f"Бэкап {self.backup_file} - {self.start_time.strftime('%Y-%m-%d %H:%M')}"

    def duration(self):
        """Длительность операции бэкапа"""
        if self.end_time and self.start_time:
            return self.end_time - self.start_time
        return None

    def mark_completed(self, file_size=0, storage_location=''):
        """Отметить бэкап как завершенный"""
        self.status = 'success'
        self.end_time = timezone.now()
        self.backup_size = file_size
        self.storage_location = storage_location
        self.save()

    def mark_failed(self, error_message=''):
        """Отметить бэкап как неуспешный"""
        self.status = 'failed'
        self.end_time = timezone.now()
        self.error_message = error_message
        self.save()