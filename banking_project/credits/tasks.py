import logging
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.db.models import Q, Sum
from datetime import datetime, timedelta
from django.apps import apps

logger = logging.getLogger(__name__)


def get_shared_task():
    """Ленивая загрузка shared_task из celery"""
    try:
        from celery import shared_task
        return shared_task
    except ImportError:
        # Заглушка для случаев когда Celery не установлен
        def shared_task_stub(func):
            return func

        return shared_task_stub


def get_credit_model():
    """Ленивая загрузка модели Credit"""
    return apps.get_model('credits', 'Credit')


def get_credit_payment_model():
    """Ленивая загрузка модели CreditPayment"""
    return apps.get_model('credits', 'CreditPayment')


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_account_model():
    """Ленивая загрузка модели Account"""
    return apps.get_model('accounts', 'Account')


# Инициализация shared_task с ленивой загрузкой
shared_task = get_shared_task()


@shared_task
def check_overdue_credit_payments():
    """
    Ежедневная проверка просроченных платежей по кредитам
    """
    try:
        Credit = get_credit_model()
        today = timezone.now().date()
        logger.info(f"Запуск проверки просроченных платежей на {today}")

        # Находим активные кредиты с просроченными платежами
        overdue_credits = Credit.objects.filter(
            status='active',
            next_payment_date__lt=today,
            remaining_balance__gt=0
        ).select_related('client', 'client__user')

        processed_count = 0

        for credit in overdue_credits:
            try:
                # Расчет дней просрочки
                overdue_days = (today - credit.next_payment_date).days

                # Обновляем информацию о просрочке
                credit.overdue_days = overdue_days
                credit.overdue_amount = credit.calculate_next_payment()

                # Изменяем статус при длительной просрочке
                if overdue_days > 30 and credit.status != 'overdue':
                    credit.status = 'overdue'
                    logger.info(f"Кредит {credit.contract_number} переведен в статус 'Просрочен'")

                elif overdue_days > 90 and credit.status != 'default':
                    credit.status = 'default'
                    logger.info(f"Кредит {credit.contract_number} переведен в статус 'Дефолт'")

                credit.save()
                processed_count += 1

                # Отправка уведомления при первой просрочке
                if overdue_days == 1:
                    send_payment_reminder.delay(credit.id, 'overdue')

            except Exception as e:
                logger.error(f"Ошибка обработки кредита {credit.contract_number}: {str(e)}")
                continue

        logger.info(f"Проверка просроченных платежей завершена. Обработано: {processed_count}")
        return processed_count

    except Exception as e:
        logger.error(f"Критическая ошибка в задаче проверки просроченных платежей: {str(e)}")
        return 0


@shared_task
def calculate_daily_penalties():
    """
    Ежедневный расчет штрафов за просрочку
    """
    try:
        Credit = get_credit_model()
        today = timezone.now().date()
        logger.info(f"Запуск расчета штрафов на {today}")

        # Находим кредиты с просрочкой
        overdue_credits = Credit.objects.filter(
            Q(status='overdue') | Q(status='default'),
            overdue_days__gt=0,
            remaining_balance__gt=0
        )

        penalty_total = 0
        processed_count = 0

        for credit in overdue_credits:
            try:
                # Расчет штрафа
                penalty = credit.calculate_penalty()

                # Создаем запись о штрафе в виде неуспешного платежа
                if penalty > 0:
                    CreditPayment = get_credit_payment_model()

                    payment = CreditPayment.objects.create(
                        credit=credit,
                        payment_number=credit.payments.count() + 1,
                        payment_date=today,
                        due_date=credit.next_payment_date,
                        amount=penalty,
                        principal_amount=0,
                        interest_amount=0,
                        penalty_amount=penalty,
                        status='failed',  # Штраф как неуспешный платеж
                        payment_method='auto',
                        notes=f'Автоматически начисленный штраф за просрочку ({credit.overdue_days} дней)'
                    )

                    penalty_total += penalty
                    processed_count += 1

                    logger.info(f"Начислен штраф {penalty} для кредита {credit.contract_number}")

            except Exception as e:
                logger.error(f"Ошибка расчета штрафа для кредита {credit.contract_number}: {str(e)}")
                continue

        logger.info(f"Расчет штрафов завершен. Обработано: {processed_count}, Сумма: {penalty_total}")
        return {'processed_count': processed_count, 'penalty_total': penalty_total}

    except Exception as e:
        logger.error(f"Критическая ошибка в задаче расчета штрафов: {str(e)}")
        return {'processed_count': 0, 'penalty_total': 0}


@shared_task
def send_payment_reminders():
    """
    Отправка напоминаний о предстоящих платежах
    """
    try:
        Credit = get_credit_model()
        today = timezone.now().date()

        # Платежи в ближайшие 3 дня
        reminder_date = today + timedelta(days=3)

        upcoming_payments = Credit.objects.filter(
            status='active',
            next_payment_date=reminder_date,
            remaining_balance__gt=0
        ).select_related('client', 'client__user')

        sent_count = 0

        for credit in upcoming_payments:
            try:
                send_payment_reminder.delay(credit.id, 'upcoming')
                sent_count += 1

            except Exception as e:
                logger.error(f"Ошибка отправки напоминания для кредита {credit.contract_number}: {str(e)}")
                continue

        logger.info(f"Отправка напоминаний завершена. Отправлено: {sent_count}")
        return sent_count

    except Exception as e:
        logger.error(f"Критическая ошибка в задаче отправки напоминаний: {str(e)}")
        return 0


@shared_task
def send_payment_reminder(credit_id, reminder_type):
    """
    Отправка напоминания о платеже конкретному клиенту
    """
    try:
        Credit = get_credit_model()
        User = get_user_model()

        credit = Credit.objects.select_related('client', 'client__user').get(id=credit_id)
        user = credit.client.user
        next_payment = credit.calculate_next_payment()
        penalty = credit.calculate_penalty()
        total_due = next_payment + penalty

        if reminder_type == 'upcoming':
            subject = f"Напоминание о предстоящем платеже по кредиту {credit.contract_number}"
            message = f"""
Уважаемый(ая) {user.get_full_name()}!

Напоминаем, что {credit.next_payment_date.strftime('%d.%m.%Y')} у вас запланирован платеж по кредиту {credit.contract_number}.

Сумма к оплате: {total_due} {credit.account.currency.code}
В том числе:
- Основной платеж: {next_payment} {credit.account.currency.code}
- Штрафы: {penalty} {credit.account.currency.code}

Пожалуйста, убедитесь, что на вашем счете достаточно средств для автоматического списания.

С уважением,
Банковская система
            """
        else:  # overdue
            subject = f"Просрочка платежа по кредиту {credit.contract_number}"
            message = f"""
Уважаемый(ая) {user.get_full_name()}!

Информируем вас о просрочке платежа по кредиту {credit.contract_number}.
Платеж должен был быть внесен {credit.next_payment_date.strftime('%d.%m.%Y')}.

Просрочка: {credit.overdue_days} дней
Сумма задолженности: {total_due} {credit.account.currency.code}

Во избежание увеличения штрафов, пожалуйста, внесите платеж как можно скорее.

С уважением,
Банковская система
            """

        # В реальной системе здесь будет отправка email или SMS
        logger.info(f"Напоминание отправлено: {subject}")

        # Для демонстрации просто логируем
        if settings.DEBUG:
            try:
                send_mail(
                    subject,
                    message,
                    settings.DEFAULT_FROM_EMAIL,
                    [user.email],
                    fail_silently=True,
                )
            except Exception as e:
                logger.warning(f"Не удалось отправить email: {str(e)}")

        return True

    except Exception as e:
        logger.error(f"Ошибка отправки напоминания: {str(e)}")
        return False


@shared_task
def generate_credit_reports():
    """
    Генерация отчетов по кредитному портфелю
    """
    try:
        Credit = get_credit_model()
        today = timezone.now().date()

        # Статистика по кредитному портфелю
        total_credits = Credit.objects.count()
        active_credits = Credit.objects.filter(status='active').count()
        overdue_credits = Credit.objects.filter(status='overdue').count()
        default_credits = Credit.objects.filter(status='default').count()

        # Финансовая статистика
        total_issued = Credit.objects.aggregate(Sum('amount'))['amount__sum'] or 0
        total_remaining = Credit.objects.aggregate(Sum('remaining_balance'))['remaining_balance__sum'] or 0
        total_paid = Credit.objects.aggregate(Sum('total_paid'))['total_paid__sum'] or 0

        report_data = {
            'report_date': today,
            'total_credits': total_credits,
            'active_credits': active_credits,
            'overdue_credits': overdue_credits,
            'default_credits': default_credits,
            'total_issued': total_issued,
            'total_remaining': total_remaining,
            'total_paid': total_paid,
            'recovery_rate': (total_paid / total_issued * 100) if total_issued > 0 else 0
        }

        logger.info(f"Отчет по кредитному портфелю сгенерирован: {report_data}")

        # Здесь можно добавить сохранение отчета в базу или отправку по email
        return report_data

    except Exception as e:
        logger.error(f"Ошибка генерации отчета по кредитам: {str(e)}")
        return {}


@shared_task
def process_automatic_payments():
    """
    Автоматическое списание регулярных платежей по кредитам
    """
    try:
        Credit = get_credit_model()
        Account = get_account_model()
        today = timezone.now().date()
        logger.info(f"Запуск автоматического списания платежей на {today}")

        # Находим кредиты с сегодняшней датой платежа
        due_credits = Credit.objects.filter(
            status='active',
            next_payment_date=today,
            remaining_balance__gt=0
        ).select_related('client', 'client__user', 'account')

        processed_count = 0
        successful_count = 0

        for credit in due_credits:
            try:
                # Расчет суммы платежа
                payment_amount = credit.calculate_next_payment()
                penalty_amount = credit.calculate_penalty()
                total_amount = payment_amount + penalty_amount

                # Проверяем наличие средств на счете клиента
                client_accounts = credit.client.accounts.filter(
                    currency=credit.account.currency,
                    status='active'
                )

                if not client_accounts:
                    logger.warning(f"Нет активных счетов у клиента для кредита {credit.contract_number}")
                    continue

                client_account = client_accounts.first()

                if client_account.balance >= total_amount:
                    # Выполняем автоматический платеж
                    success, message = credit.make_payment(
                        total_amount,
                        'auto',
                        None  # Системный пользователь
                    )

                    if success:
                        successful_count += 1
                        logger.info(f"Автоматический платеж выполнен для кредита {credit.contract_number}")
                    else:
                        logger.warning(
                            f"Ошибка автоматического платежа для кредита {credit.contract_number}: {message}")

                else:
                    logger.warning(
                        f"Недостаточно средств для автоматического платежа по кредиту {credit.contract_number}")

                processed_count += 1

            except Exception as e:
                logger.error(f"Ошибка автоматического платежа для кредита {credit.contract_number}: {str(e)}")
                continue

        logger.info(f"Автоматическое списание завершено. Обработано: {processed_count}, Успешно: {successful_count}")
        return {'processed_count': processed_count, 'successful_count': successful_count}

    except Exception as e:
        logger.error(f"Критическая ошибка в задаче автоматического списания: {str(e)}")
        return {'processed_count': 0, 'successful_count': 0}


@shared_task
def update_credit_scores():
    """
    Обновление кредитных рейтингов клиентов на основе истории платежей
    """
    try:
        Client = get_client_model()
        Credit = get_credit_model()

        clients = Client.objects.all()
        updated_count = 0

        for client in clients:
            try:
                # Получаем все кредиты клиента
                client_credits = Credit.objects.filter(client=client)

                if not client_credits.exists():
                    continue

                # Расчет кредитного рейтинга на основе истории платежей
                total_credits = client_credits.count()
                closed_credits = client_credits.filter(status='closed').count()
                overdue_credits = client_credits.filter(status__in=['overdue', 'default']).count()

                # Базовый рейтинг
                base_score = 500

                # Бонус за закрытые кредиты
                if closed_credits > 0:
                    base_score += min(closed_credits * 50, 200)

                # Штраф за просроченные кредиты
                if overdue_credits > 0:
                    base_score -= min(overdue_credits * 100, 300)

                # Бонус за долгосрочные отношения
                oldest_credit = client_credits.order_by('created_at').first()
                if oldest_credit:
                    credit_age_months = (timezone.now().date() - oldest_credit.created_at.date()).days // 30
                    base_score += min(credit_age_months * 2, 100)

                # Ограничиваем рейтинг в диапазоне 300-850
                new_score = max(300, min(850, base_score))

                if client.credit_score != new_score:
                    client.credit_score = new_score
                    client.save()
                    updated_count += 1
                    logger.info(f"Обновлен кредитный рейтинг клиента {client.get_full_name()}: {new_score}")

            except Exception as e:
                logger.error(f"Ошибка обновления кредитного рейтинга для клиента {client.id}: {str(e)}")
                continue

        logger.info(f"Обновление кредитных рейтингов завершено. Обновлено: {updated_count}")
        return updated_count

    except Exception as e:
        logger.error(f"Критическая ошибка в задаче обновления кредитных рейтингов: {str(e)}")
        return 0