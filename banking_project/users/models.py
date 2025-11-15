from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.utils import timezone


class UserRole(models.TextChoices):
    CLIENT = 'client', 'Клиент'
    EMPLOYEE = 'employee', 'Сотрудник'
    ADMIN = 'admin', 'Администратор'


class Department(models.Model):
    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Название отдела'
    )
    description = models.TextField(
        blank=True,
        verbose_name='Описание отдела'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'
        ordering = ['name']

    def __str__(self):
        return self.name


class User(AbstractUser):
    phone_regex = RegexValidator(
        regex=r'^\+?1?\d{9,15}$',
        message="Номер телефона должен быть в формате: '+79999999999'. До 15 цифр."
    )

    email = models.EmailField(
        unique=True,
        verbose_name='Email адрес'
    )
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.CLIENT,
        verbose_name='Роль пользователя'
    )
    phone = models.CharField(
        validators=[phone_regex],
        max_length=17,
        blank=True,
        verbose_name='Номер телефона'
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='Подтвержденный аккаунт'
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата рождения'
    )
    avatar = models.ImageField(
        upload_to='avatars/',
        null=True,
        blank=True,
        verbose_name='Аватар'
    )
    last_login_ip = models.GenericIPAddressField(
        null=True,
        blank=True,
        verbose_name='IP последнего входа'
    )
    login_attempts = models.IntegerField(
        default=0,
        verbose_name='Неудачных попыток входа'
    )
    locked_until = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Заблокирован до'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата регистрации'
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата обновления'
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email']),
            models.Index(fields=['role']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"

    def save(self, *args, **kwargs):
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    def is_locked(self):
        """Проверка, заблокирован ли пользователь"""
        if self.locked_until:
            return timezone.now() < self.locked_until
        return False

    def reset_login_attempts(self):
        """Сброс счетчика неудачных попыток входа"""
        self.login_attempts = 0
        self.locked_until = None
        self.save()

    def increment_login_attempts(self):
        """Увеличение счетчика неудачных попыток входа"""
        self.login_attempts += 1
        if self.login_attempts >= 5:  # Блокировка после 5 неудачных попыток
            self.locked_until = timezone.now() + timezone.timedelta(minutes=30)
        self.save()


class Employee(models.Model):
    POSITION_CHOICES = (
        ('manager', 'Менеджер'),
        ('credit_specialist', 'Кредитный специалист'),
        ('operator', 'Оператор'),
        ('analyst', 'Аналитик'),
        ('director', 'Директор'),
    )

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='employee_profile',
        verbose_name='Пользователь'
    )
    employee_id = models.CharField(
        max_length=20,
        unique=True,
        verbose_name='Табельный номер'
    )
    position = models.CharField(
        max_length=50,
        choices=POSITION_CHOICES,
        verbose_name='Должность'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees',
        verbose_name='Отдел'
    )
    hire_date = models.DateField(
        verbose_name='Дата приема на работу'
    )
    salary = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Зарплата'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активный сотрудник'
    )
    office_location = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Место работы'
    )
    work_phone = models.CharField(
        max_length=20,
        blank=True,
        verbose_name='Рабочий телефон'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата создания'
    )

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ['-hire_date']
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['department', 'position']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.get_position_display()}"

    def get_work_experience(self):
        """Стаж работы в компании"""
        from datetime import date
        if self.hire_date:
            today = date.today()
            experience = today - self.hire_date
            return experience.days // 365  # Округляем до лет
        return 0


class UserSession(models.Model):
    """История сессий пользователей"""
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='sessions',
        verbose_name='Пользователь'
    )
    session_key = models.CharField(
        max_length=40,
        verbose_name='Ключ сессии'
    )
    ip_address = models.GenericIPAddressField(
        verbose_name='IP адрес'
    )
    user_agent = models.TextField(
        verbose_name='User Agent'
    )
    login_time = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Время входа'
    )
    last_activity = models.DateTimeField(
        auto_now=True,
        verbose_name='Последняя активность'
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активная сессия'
    )

    class Meta:
        verbose_name = 'Сессия пользователя'
        verbose_name_plural = 'Сессии пользователей'
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.user.email} - {self.login_time.strftime('%Y-%m-%d %H:%M')}"