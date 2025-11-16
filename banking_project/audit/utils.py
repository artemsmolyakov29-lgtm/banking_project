from django.apps import apps
from django.contrib.auth import get_user_model
from django.utils import timezone


def get_audit_log_model():
    """Ленивая загрузка модели AuditLog"""
    try:
        return apps.get_model('audit', 'AuditLog')
    except LookupError:
        return None


def get_card_model():
    """Ленивая загрузка модели Card"""
    try:
        return apps.get_model('cards', 'Card')
    except LookupError:
        return None


def log_event(user, action, model_name, object_id=None, details=None, ip_address=None, user_agent=None):
    """
    Основная функция логирования событий в системе аудита
    """
    AuditLog = get_audit_log_model()
    if not AuditLog:
        return None

    try:
        audit_log = AuditLog(
            user=user,
            action=action,
            model_name=model_name,
            object_id=object_id,
            details=details or '',
            ip_address=ip_address,
            user_agent=user_agent,
            timestamp=timezone.now()
        )
        audit_log.save()
        return audit_log
    except Exception as e:
        # Логируем ошибку, но не прерываем выполнение основной логики
        print(f"Ошибка при записи в аудит-лог: {e}")
        return None


def log_card_status_change(user, card, old_status, new_status, reason=None, block_reason=None, ip_address=None,
                           user_agent=None):
    """
    Специализированная функция для логирования изменения статуса карты
    """
    # Получаем модель Card для получения choices
    Card = get_card_model()
    if not Card:
        return None

    action_map = {
        ('active', 'blocked'): 'CARD_BLOCKED',
        ('blocked', 'active'): 'CARD_UNBLOCKED',
        ('active', 'lost'): 'CARD_MARKED_LOST',
        ('active', 'stolen'): 'CARD_MARKED_STOLEN',
        ('active', 'closed'): 'CARD_CLOSED',
    }

    action = action_map.get((old_status, new_status), 'CARD_STATUS_CHANGED')

    details_parts = [
        f"Изменение статуса карты: {old_status} -> {new_status}",
        f"Номер карты: {card.get_masked_number()}",
        f"Владелец: {card.cardholder_name}",
    ]

    if reason:
        details_parts.append(f"Причина: {reason}")

    if block_reason:
        # Получаем отображаемое значение причины блокировки
        block_reason_display = dict(Card.BLOCK_REASONS).get(block_reason, block_reason)
        details_parts.append(f"Тип блокировки: {block_reason_display}")

    details = "\n".join(details_parts)

    return log_event(
        user=user,
        action=action,
        model_name='Card',
        object_id=card.id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_card_creation(user, card, ip_address=None, user_agent=None):
    """
    Логирование создания новой карты
    """
    details = (
        f"Создана новая карта: {card.get_masked_number()}\n"
        f"Тип: {card.get_card_type_display()}\n"
        f"Платежная система: {card.get_card_system_display()}\n"
        f"Владелец: {card.cardholder_name}\n"
        f"Счет: {card.account.account_number}"
    )

    return log_event(
        user=user,
        action='CARD_CREATED',
        model_name='Card',
        object_id=card.id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_card_deletion(user, card_data, ip_address=None, user_agent=None):
    """
    Логирование удаления карты
    """
    details = (
        f"Удалена карта: {card_data.get('masked_number', 'N/A')}\n"
        f"Владелец: {card_data.get('cardholder_name', 'N/A')}\n"
        f"Тип: {card_data.get('card_type', 'N/A')}"
    )

    return log_event(
        user=user,
        action='CARD_DELETED',
        model_name='Card',
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_card_limit_change(user, card, old_limit, new_limit, ip_address=None, user_agent=None):
    """
    Логирование изменения лимитов карты
    """
    details = (
        f"Изменен дневной лимит карты: {card.get_masked_number()}\n"
        f"Старый лимит: {old_limit}\n"
        f"Новый лимит: {new_limit}\n"
        f"Владелец: {card.cardholder_name}"
    )

    return log_event(
        user=user,
        action='CARD_LIMIT_CHANGED',
        model_name='Card',
        object_id=card.id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )


def log_card_transaction(user, card, transaction, ip_address=None, user_agent=None):
    """
    Логирование операций по карте
    """
    details = (
        f"Операция по карте: {card.get_masked_number()}\n"
        f"Тип: {transaction.get_transaction_type_display()}\n"
        f"Сумма: {transaction.amount} {transaction.currency.code}\n"
        f"Мерчант: {transaction.merchant_name or 'N/A'}\n"
        f"Статус: {'Успешно' if transaction.is_successful else 'Неуспешно'}"
    )

    return log_event(
        user=user,
        action='CARD_TRANSACTION',
        model_name='CardTransaction',
        object_id=transaction.id,
        details=details,
        ip_address=ip_address,
        user_agent=user_agent
    )


def get_card_audit_logs(card_id, days=30):
    """
    Получение аудит-логов для конкретной карты за указанный период
    """
    AuditLog = get_audit_log_model()
    if not AuditLog:
        return AuditLog.objects.none()

    start_date = timezone.now() - timezone.timedelta(days=days)

    return AuditLog.objects.filter(
        model_name='Card',
        object_id=card_id,
        timestamp__gte=start_date
    ).order_by('-timestamp')


def get_user_card_actions(user_id, days=30):
    """
    Получение всех действий пользователя с картами за указанный период
    """
    AuditLog = get_audit_log_model()
    if not AuditLog:
        return AuditLog.objects.none()

    start_date = timezone.now() - timezone.timedelta(days=days)
    card_actions = ['CARD_CREATED', 'CARD_BLOCKED', 'CARD_UNBLOCKED',
                    'CARD_DELETED', 'CARD_LIMIT_CHANGED', 'CARD_STATUS_CHANGED']

    return AuditLog.objects.filter(
        user_id=user_id,
        action__in=card_actions,
        timestamp__gte=start_date
    ).order_by('-timestamp')


# Функция для регистрации в конфигурации приложения
def register_audit_functions():
    """Регистрирует функции аудита для использования в других приложениях"""
    return {
        'log_card_status_change': log_card_status_change,
        'log_card_creation': log_card_creation,
        'log_card_deletion': log_card_deletion,
        'log_card_limit_change': log_card_limit_change,
        'log_card_transaction': log_card_transaction,
    }