"""
Сигналы для автоматического создания профилей клиентов
"""
from django.db.models.signals import post_save, pre_save, pre_delete
from django.dispatch import receiver
from django.conf import settings
from django.utils import timezone
import random
import string
from datetime import date, timedelta


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_client_profile(sender, instance, created, **kwargs):
    """
    Автоматически создает профиль клиента при создании пользователя с ролью 'client'
    """
    if created and instance.role == 'client':
        try:
            from .models import Client

            # Проверяем, нет ли уже профиля
            if not hasattr(instance, 'client_profile'):
                # Формируем полное имя
                full_name_parts = []
                if instance.last_name:
                    full_name_parts.append(instance.last_name)
                if instance.first_name:
                    full_name_parts.append(instance.first_name)
                # Проверяем наличие middle_name через hasattr
                if hasattr(instance, 'middle_name') and instance.middle_name:
                    full_name_parts.append(instance.middle_name)

                full_name = ' '.join(full_name_parts) if full_name_parts else 'Клиент'

                # Генерируем временные данные для обязательных полей
                Client.objects.create(
                    user=instance,
                    full_name=full_name,
                    passport_series='0000',
                    passport_number='000000',
                    passport_issued_by='ПОДЛЕЖИТ ЗАПОЛНЕНИЮ',
                    passport_issue_date=date(2000, 1, 1),
                    passport_department_code='000-000',
                    registration_address='ПОДЛЕЖИТ ЗАПОЛНЕНИЮ',
                    inn=''.join(random.choices(string.digits, k=12)),
                    snils=f"{''.join(random.choices(string.digits, k=3))}-"
                          f"{''.join(random.choices(string.digits, k=3))}-"
                          f"{''.join(random.choices(string.digits, k=3))} 00",
                    marital_status='single',
                    education_level='secondary',
                    work_experience=0,
                    monthly_income=0,
                    credit_rating=500,  # Средний рейтинг по умолчанию
                    is_vip=False,
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )
                print(f"Создан профиль клиента для пользователя: {instance.username}")
        except Exception as e:
            print(f"Ошибка при создании профиля клиента: {e}")


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_client_for_employee_or_admin(sender, instance, created, **kwargs):
    """
    Создает профиль Client для сотрудников и администраторов,
    чтобы они могли работать с системой
    """
    if created and instance.role in ['employee', 'admin']:
        try:
            from .models import Client

            # Проверяем, нет ли уже профиля
            if not hasattr(instance, 'client_profile'):
                # Формируем полное имя
                full_name_parts = []
                if instance.last_name:
                    full_name_parts.append(instance.last_name)
                if instance.first_name:
                    full_name_parts.append(instance.first_name)
                # Проверяем наличие middle_name через hasattr
                if hasattr(instance, 'middle_name') and instance.middle_name:
                    full_name_parts.append(instance.middle_name)

                full_name = ' '.join(full_name_parts) if full_name_parts else 'Сотрудник'

                Client.objects.create(
                    user=instance,
                    full_name=full_name,
                    passport_series='EMP' + str(instance.id).zfill(4),
                    passport_number=str(instance.id).zfill(6),
                    passport_issued_by='СОТРУДНИК БАНКА',
                    passport_issue_date=date(2000, 1, 1),
                    passport_department_code='000-000',
                    registration_address='АДРЕС БАНКА',
                    inn=''.join(random.choices(string.digits, k=12)),
                    snils=f"{''.join(random.choices(string.digits, k=3))}-"
                          f"{''.join(random.choices(string.digits, k=3))}-"
                          f"{''.join(random.choices(string.digits, k=3))} 00",
                    marital_status='single',
                    education_level='higher',
                    work_place='БАНКОВСКАЯ СИСТЕМА',
                    position='Сотрудник' if instance.role == 'employee' else 'Администратор',
                    work_experience=1,
                    monthly_income=50000 if instance.role == 'employee' else 100000,
                    credit_rating=800,  # Высокий рейтинг для сотрудников
                    is_vip=True,
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )
                print(f"Создан профиль клиента для сотрудника: {instance.username}")
        except Exception as e:
            print(f"Ошибка при создании профиля клиента для сотрудника: {e}")


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def update_existing_users_without_client(sender, instance, created, **kwargs):
    """
    Обновляет существующих пользователей без профиля клиента
    """
    if not created:
        try:
            from .models import Client

            # Если у пользователя нет профиля клиента, создаем его
            if not hasattr(instance, 'client_profile'):
                # Определяем тип пользователя
                if instance.role == 'client':
                    create_client_profile(sender, instance, True, **kwargs)
                elif instance.role in ['employee', 'admin']:
                    create_client_for_employee_or_admin(sender, instance, True, **kwargs)
        except Exception as e:
            print(f"Ошибка при обновлении пользователя: {e}")


@receiver(pre_save, sender='clients.Client')
def update_client_full_name(sender, instance, **kwargs):
    """
    Обновляет full_name клиента при сохранении, если оно пустое
    """
    if instance.user:
        full_name_parts = []
        if instance.user.last_name:
            full_name_parts.append(instance.user.last_name)
        if instance.user.first_name:
            full_name_parts.append(instance.user.first_name)
        # Используем hasattr для безопасной проверки наличия middle_name
        if hasattr(instance.user, 'middle_name') and instance.user.middle_name:
            full_name_parts.append(instance.user.middle_name)

        if full_name_parts:
            instance.full_name = ' '.join(full_name_parts)


@receiver(pre_save, sender='clients.Client')
def validate_client_data(sender, instance, **kwargs):
    """
    Проверка и валидация данных клиента перед сохранением
    """
    # Проверяем ИНН (должен быть 12 цифр)
    if instance.inn and len(instance.inn) != 12:
        # Если ИНН невалидный, генерируем новый
        instance.inn = ''.join(random.choices(string.digits, k=12))

    # Проверяем, что дата выдачи паспорта не в будущем
    if instance.passport_issue_date and instance.passport_issue_date > date.today():
        # Устанавливаем разумную дату по умолчанию
        instance.passport_issue_date = date.today() - timedelta(days=365 * 5)  # 5 лет назад


@receiver(pre_delete, sender=settings.AUTH_USER_MODEL)
def delete_client_profile(sender, instance, **kwargs):
    """
    Удаляет профиль клиента при удалении пользователя
    """
    try:
        if hasattr(instance, 'client_profile'):
            instance.client_profile.delete()
    except Exception as e:
        print(f"Ошибка при удалении профиля клиента: {e}")


@receiver(post_save, sender='clients.Client')
def log_client_changes(sender, instance, created, **kwargs):
    """
    Логирование изменений в профиле клиента
    """
    if created:
        print(f"Создан новый клиент: {instance.full_name} (ID: {instance.id})")
    else:
        print(f"Обновлен клиент: {instance.full_name} (ID: {instance.id})")
        # Здесь можно добавить запись в журнал аудита


@receiver(pre_save, sender='clients.Client')
def update_credit_rating(sender, instance, **kwargs):
    """
    Автоматическое обновление кредитного рейтинга на основе данных клиента
    """
    if not instance.pk:  # Новый клиент
        instance.credit_rating = 500  # Средний рейтинг по умолчанию
    else:
        # Получаем старую версию для сравнения
        try:
            old_instance = sender.objects.get(pk=instance.pk)

            # Если доход увеличился, повышаем рейтинг
            if instance.monthly_income and old_instance.monthly_income:
                if instance.monthly_income > old_instance.monthly_income:
                    instance.credit_rating = min(1000, instance.credit_rating + 10)
                elif instance.monthly_income < old_instance.monthly_income:
                    instance.credit_rating = max(300, instance.credit_rating - 5)

            # Если стаж увеличился, повышаем рейтинг
            if instance.work_experience > old_instance.work_experience:
                instance.credit_rating = min(1000, instance.credit_rating + 5)
        except sender.DoesNotExist:
            pass  # Это новый клиент