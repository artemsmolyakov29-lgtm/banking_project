from django.db import models
from django.conf import settings
from django.core.validators import RegexValidator
from django.utils import timezone
from django.contrib.auth import get_user_model


class Client(models.Model):
    MARITAL_STATUS = (
        ('single', 'Холост/Не замужем'),
        ('married', 'Женат/Замужем'),
        ('divorced', 'Разведен(а)'),
        ('widowed', 'Вдовец/Вдова'),
    )

    EDUCATION_LEVEL = (
        ('secondary', 'Среднее'),
        ('special_secondary', 'Среднее специальное'),
        ('incomplete_higher', 'Неоконченное высшее'),
        ('higher', 'Высшее'),
        ('postgraduate', 'Послевузовское'),
    )

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='client_profile',
        verbose_name='Пользователь'
    )
    full_name = models.CharField(
        max_length=200,
        verbose_name='Полное имя'
    )
    passport_series = models.CharField(
        max_length=4,
        validators=[RegexValidator(regex='^[0-9]{4}$', message='Серия паспорта должна содержать 4 цифры')],
        verbose_name='Серия паспорта'
    )
    passport_number = models.CharField(
        max_length=6,
        validators=[RegexValidator(regex='^[0-9]{6}$', message='Номер паспорта должен содержать 6 цифр')],
        verbose_name='Номер паспорта'
    )
    passport_issued_by = models.TextField(
        verbose_name='Кем выдан паспорт'
    )
    passport_issue_date = models.DateField(
        verbose_name='Дата выдачи паспорта'
    )
    passport_department_code = models.CharField(
        max_length=7,
        validators=[
            RegexValidator(regex='^[0-9]{3}-[0-9]{3}$', message='Код подразделения должен быть в формате 000-000')],
        verbose_name='Код подразделения'
    )
    registration_address = models.TextField(
        verbose_name='Адрес регистрации'
    )
    residential_address = models.TextField(
        blank=True,
        verbose_name='Адрес проживания'
    )
    inn = models.CharField(
        max_length=12,
        unique=True,
        validators=[RegexValidator(regex='^[0-9]{12}$', message='ИНН должен содержать 12 цифр')],
        verbose_name='ИНН'
    )
    snils = models.CharField(
        max_length=14,
        unique=True,
        validators=[RegexValidator(regex='^[0-9]{3}-[0-9]{3}-[0-9]{3} [0-9]{2}$',
                                   message='СНИЛС должен быть в формате 000-000-000 00')],
        verbose_name='СНИЛС'
    )
    marital_status = models.CharField(
        max_length=20,
        choices=MARITAL_STATUS,
        verbose_name='Семейное положение'
    )
    education_level = models.CharField(
        max_length=20,
        choices=EDUCATION_LEVEL,
        verbose_name='Образование'
    )
    work_place = models.CharField(
        max_length=200,
        blank=True,
        verbose_name='Место работы'
    )
    position = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Должность'
    )
    work_experience = models.IntegerField(
        default=0,
        verbose_name='Стаж работы (лет)'
    )
    monthly_income = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Ежемесячный доход'
    )
    credit_rating = models.IntegerField(
        default=0,
        verbose_name='Кредитный рейтинг'
    )
    is_vip = models.BooleanField(
        default=False,
        verbose_name='VIP клиент'
    )
    assigned_manager = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='clients',
        verbose_name='Ответственный менеджер'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания'
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
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['full_name']),
            models.Index(fields=['inn']),
            models.Index(fields=['snils']),
            models.Index(fields=['credit_rating']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        return f"{self.full_name} (ИНН: {self.inn})"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

    def get_passport_data(self):
        """Полные паспортные данные"""
        return f"{self.passport_series} {self.passport_number}"

    def get_age(self):
        """Возраст клиента"""
        if self.user.date_of_birth:
            from datetime import date
            today = date.today()
            age = today.year - self.user.date_of_birth.year
            if today.month < self.user.date_of_birth.month or (
                    today.month == self.user.date_of_birth.month and today.day < self.user.date_of_birth.day
            ):
                age -= 1
            return age
        return None

    def get_total_balance(self):
        """Общий баланс по всем счетам клиента"""
        Account = self._meta.apps.get_model('accounts', 'Account')
        total = Account.objects.filter(
            client=self,
            status='active'
        ).aggregate(total_balance=models.Sum('balance'))['total_balance']
        return total or 0

    def get_active_products_count(self):
        """Количество активных банковских продуктов"""
        accounts_count = self.accounts.filter(status='active').count()
        credits_count = self.credits.filter(status='active').count()
        deposits_count = self.deposits.filter(status='active').count()
        return {
            'accounts': accounts_count,
            'credits': credits_count,
            'deposits': deposits_count,
            'total': accounts_count + credits_count + deposits_count
        }


class ClientDocument(models.Model):
    """Документы клиентов"""
    DOCUMENT_TYPES = (
        ('passport', 'Паспорт'),
        ('driver_license', 'Водительское удостоверение'),
        ('military_id', 'Военный билет'),
        ('education_diploma', 'Диплом об образовании'),
        ('income_certificate', 'Справка о доходах'),
        ('other', 'Другой документ'),
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='documents',
        verbose_name='Клиент'
    )
    document_type = models.CharField(
        max_length=50,
        choices=DOCUMENT_TYPES,
        verbose_name='Тип документа'
    )
    document_number = models.CharField(
        max_length=50,
        verbose_name='Номер документа'
    )
    document_file = models.FileField(
        upload_to='client_documents/',
        verbose_name='Файл документа'
    )
    issue_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Дата выдачи'
    )
    expiration_date = models.DateField(
        null=True,
        blank=True,
        verbose_name='Срок действия'
    )
    is_verified = models.BooleanField(
        default=False,
        verbose_name='Проверен'
    )
    verified_by = models.ForeignKey(
        'users.Employee',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name='Проверил'
    )
    verification_date = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Дата проверки'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    class Meta:
        verbose_name = 'Документ клиента'
        verbose_name_plural = 'Документы клиентов'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.get_document_type_display()} - {self.client.full_name}"

    def is_expired(self):
        """Проверка, истек ли срок действия документа"""
        if self.expiration_date:
            from datetime import date
            return date.today() > self.expiration_date
        return False


class ClientContact(models.Model):
    """Контактные лица клиента"""
    CONTACT_TYPES = (
        ('relative', 'Родственник'),
        ('colleague', 'Коллега'),
        ('friend', 'Друг'),
        ('other', 'Другой'),
    )

    client = models.ForeignKey(
        Client,
        on_delete=models.CASCADE,
        related_name='contacts',
        verbose_name='Клиент'
    )
    full_name = models.CharField(
        max_length=200,
        verbose_name='Полное имя'
    )
    contact_type = models.CharField(
        max_length=20,
        choices=CONTACT_TYPES,
        verbose_name='Тип контакта'
    )
    phone = models.CharField(
        max_length=20,
        verbose_name='Телефон'
    )
    email = models.EmailField(
        blank=True,
        verbose_name='Email'
    )
    relationship = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Отношение'
    )
    is_primary = models.BooleanField(
        default=False,
        verbose_name='Основной контакт'
    )
    notes = models.TextField(
        blank=True,
        verbose_name='Примечания'
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Дата добавления'
    )

    class Meta:
        verbose_name = 'Контакт клиента'
        verbose_name_plural = 'Контакты клиентов'
        ordering = ['-is_primary', 'full_name']

    def __str__(self):
        return f"{self.full_name} ({self.get_contact_type_display()}) - {self.client.full_name}"