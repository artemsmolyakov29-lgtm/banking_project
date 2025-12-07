from django.core.management.base import BaseCommand
from django.apps import apps
import random
import string
from datetime import date
from django.utils import timezone


class Command(BaseCommand):
    help = 'Создает Client профили для пользователей без них'

    def handle(self, *args, **options):
        try:
            # Получаем модели через apps.get_model для избежания ошибок импорта
            User = apps.get_model('users', 'User')
            Client = apps.get_model('clients', 'Client')
        except LookupError as e:
            self.stderr.write(f'Ошибка загрузки моделей: {e}')
            self.stderr.write('Проверьте, что приложения users и clients установлены в INSTALLED_APPS')
            return

        try:
            users_without_client = User.objects.filter(
                role='client',
                client_profile__isnull=True
            )
        except Exception as e:
            self.stderr.write(f'Ошибка получения пользователей: {e}')
            self.stderr.write('Возможно, поле role или client_profile не существует в модели User')
            return

        count = 0
        skipped = 0

        for user in users_without_client:
            # Проверяем, не создан ли уже Client профиль в процессе
            try:
                if hasattr(user, 'client_profile') and user.client_profile:
                    skipped += 1
                    continue
            except:
                pass

            # Генерируем уникальные ИНН и СНИЛС
            while True:
                inn = ''.join(random.choices(string.digits, k=12))
                if not Client.objects.filter(inn=inn).exists():
                    break

            while True:
                snils = f"{''.join(random.choices(string.digits, k=3))}-" \
                        f"{''.join(random.choices(string.digits, k=3))}-" \
                        f"{''.join(random.choices(string.digits, k=3))} 00"
                if not Client.objects.filter(snils=snils).exists():
                    break

            # Создаем профиль клиента
            try:
                Client.objects.create(
                    user=user,
                    full_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or user.username,
                    passport_series='0000',
                    passport_number='000000',
                    passport_issued_by='АВТОМАТИЧЕСКИ СОЗДАНО СИСТЕМОЙ',
                    passport_issue_date=date(2000, 1, 1),
                    passport_department_code='000-000',
                    registration_address='НЕ УКАЗАНО',
                    inn=inn,
                    snils=snils,
                    marital_status='single',
                    education_level='secondary',
                    work_experience=0,
                    monthly_income=0,
                    credit_rating=500,
                    is_vip=False,
                    created_at=timezone.now(),
                    updated_at=timezone.now()
                )

                count += 1
                self.stdout.write(f'✓ Создан Client для пользователя {user.username}')
            except Exception as e:
                self.stderr.write(f'✗ Ошибка создания Client для {user.username}: {e}')

        self.stdout.write(self.style.SUCCESS(f'Успешно создано {count} Client профилей'))
        if skipped > 0:
            self.stdout.write(self.style.WARNING(f'Пропущено {skipped} пользователей (уже имеют Client профиль)'))