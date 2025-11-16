from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.apps import apps


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_credit_model():
    """Ленивая загрузка модели Credit"""
    return apps.get_model('credits', 'Credit')


def get_credit_payment_model():
    """Ленивая загрузка модели CreditPayment"""
    return apps.get_model('credits', 'CreditPayment')


def get_account_model():
    """Ленивая загрузка модели Account"""
    return apps.get_model('accounts', 'Account')


def calculate_annuity_payment(principal, annual_rate, term_months):
    """
    Расчет аннуитетного платежа

    Args:
        principal: основная сумма кредита
        annual_rate: годовая процентная ставка (в процентах)
        term_months: срок кредита в месяцах

    Returns:
        Decimal: сумма ежемесячного платежа
    """
    monthly_rate = Decimal(annual_rate) / Decimal('100') / Decimal('12')

    if monthly_rate == 0:
        return principal / term_months

    coefficient = (monthly_rate * (1 + monthly_rate) ** term_months) / \
                  ((1 + monthly_rate) ** term_months - 1)

    payment = principal * Decimal(coefficient)
    return round(payment, 2)


def calculate_differentiated_payment(principal, annual_rate, term_months, current_month):
    """
    Расчет дифференцированного платежа для указанного месяца

    Args:
        principal: основная сумма кредита
        annual_rate: годовая процентная ставка (в процентах)
        term_months: срок кредита в месяцах
        current_month: номер текущего месяца (начиная с 1)

    Returns:
        Decimal: сумма платежа для указанного месяца
    """
    principal_part = principal / term_months
    remaining_balance = principal - (principal_part * (current_month - 1))
    interest_part = remaining_balance * (Decimal(annual_rate) / Decimal('100') / Decimal('12'))

    return round(principal_part + interest_part, 2)


def calculate_penalty_amount(overdue_amount, overdue_days, penalty_rate=Decimal('0.001')):
    """
    Расчет суммы штрафа за просрочку

    Args:
        overdue_amount: просроченная сумма
        overdue_days: количество дней просрочки
        penalty_rate: ставка штрафа в день (по умолчанию 0.1%)

    Returns:
        Decimal: сумма штрафа
    """
    if overdue_days <= 0:
        return Decimal('0.00')

    return round(overdue_amount * penalty_rate * Decimal(overdue_days), 2)


def generate_payment_schedule(principal, annual_rate, term_months, start_date, payment_method='annuity'):
    """
    Генерация полного графика платежей

    Args:
        principal: основная сумма кредита
        annual_rate: годовая процентная ставка (в процентах)
        term_months: срок кредита в месяцах
        start_date: дата начала кредита
        payment_method: метод платежа ('annuity' или 'differentiated')

    Returns:
        list: список словарей с информацией о платежах
    """
    schedule = []
    balance = Decimal(principal)
    payment_date = start_date

    if payment_method == 'annuity':
        monthly_payment = calculate_annuity_payment(principal, annual_rate, term_months)

        for month in range(1, term_months + 1):
            interest_amount = balance * (Decimal(annual_rate) / Decimal('100') / Decimal('12'))
            principal_amount = monthly_payment - interest_amount
            balance -= principal_amount

            # Корректировка последнего платежа
            if month == term_months:
                principal_amount += balance
                balance = Decimal('0.00')

            schedule.append({
                'payment_number': month,
                'payment_date': payment_date,
                'principal_amount': round(principal_amount, 2),
                'interest_amount': round(interest_amount, 2),
                'total_payment': round(principal_amount + interest_amount, 2),
                'remaining_balance': max(round(balance, 2), 0)
            })

            payment_date += timedelta(days=30)  # Упрощенный расчет дат

    else:  # differentiated
        principal_part = principal / term_months

        for month in range(1, term_months + 1):
            remaining_balance = principal - (principal_part * (month - 1))
            interest_amount = remaining_balance * (Decimal(annual_rate) / Decimal('100') / Decimal('12'))
            total_payment = principal_part + interest_amount
            balance = remaining_balance - principal_part

            schedule.append({
                'payment_number': month,
                'payment_date': payment_date,
                'principal_amount': round(principal_part, 2),
                'interest_amount': round(interest_amount, 2),
                'total_payment': round(total_payment, 2),
                'remaining_balance': max(round(balance, 2), 0)
            })

            payment_date += timedelta(days=30)

    return schedule


def check_overdue_payments():
    """
    Проверка просроченных платежей и обновление статусов кредитов
    """
    Credit = get_credit_model()
    CreditPayment = get_credit_payment_model()

    today = timezone.now().date()
    overdue_credits = Credit.objects.filter(
        status='active',
        next_payment_date__lt=today,
        remaining_balance__gt=0
    )

    for credit in overdue_credits:
        # Расчет дней просрочки
        overdue_days = (today - credit.next_payment_date).days
        credit.overdue_days = overdue_days

        # Расчет просроченной суммы
        expected_payment = credit.calculate_next_payment()
        credit.overdue_amount = expected_payment

        # Обновление статуса если просрочка критическая
        if overdue_days > 30:
            credit.status = 'overdue'
        elif overdue_days > 90:
            credit.status = 'default'

        credit.save()

    return overdue_credits.count()


def calculate_early_repayment_savings(credit, repayment_amount):
    """
    Расчет экономии при досрочном погашении

    Args:
        credit: объект кредита
        repayment_amount: сумма досрочного погашения

    Returns:
        dict: информация об экономии
    """
    if not credit.can_make_early_repayment():
        return {'error': 'Досрочное погашение не разрешено'}

    # Текущий график платежей
    current_schedule = credit.generate_payment_schedule()
    remaining_payments = [p for p in current_schedule if p['remaining_balance'] > 0]

    # Общая сумма оставшихся платежей
    total_remaining = sum(Decimal(p['total_payment']) for p in remaining_payments)

    # Сумма для досрочного погашения
    early_repayment_total = credit.calculate_early_repayment()

    # Экономия
    savings = total_remaining - early_repayment_total

    return {
        'total_remaining': total_remaining,
        'early_repayment_total': early_repayment_total,
        'savings': savings,
        'savings_percentage': (savings / total_remaining * 100) if total_remaining > 0 else 0
    }


def get_credit_statistics(user):
    """
    Получение статистики по кредитам для пользователя

    Args:
        user: объект пользователя

    Returns:
        dict: статистика по кредитам
    """
    Credit = get_credit_model()
    Client = get_client_model()

    if user.role == 'client':
        client = Client.objects.filter(user=user).first()
        if not client:
            return {}
        credits = client.credits.all()
    else:
        credits = Credit.objects.all()

    total_credits = credits.count()
    active_credits = credits.filter(status='active').count()
    overdue_credits = credits.filter(status='overdue').count()
    total_debt = sum(credit.remaining_balance for credit in credits.filter(status='active'))
    total_paid = sum(credit.total_paid for credit in credits.filter(status__in=['active', 'closed']))

    return {
        'total_credits': total_credits,
        'active_credits': active_credits,
        'overdue_credits': overdue_credits,
        'total_debt': total_debt,
        'total_paid': total_paid
    }


def validate_credit_application(client, product, amount, term_months):
    """
    Валидация заявки на кредит

    Args:
        client: объект клиента
        product: кредитный продукт
        amount: запрашиваемая сумма
        term_months: срок кредита

    Returns:
        tuple: (is_valid, errors)
    """
    errors = []

    # Проверка суммы
    if amount < product.min_amount:
        errors.append(f"Минимальная сумма кредита: {product.min_amount}")
    if amount > product.max_amount:
        errors.append(f"Максимальная сумма кредита: {product.max_amount}")

    # Проверка срока
    if term_months < product.min_term_months:
        errors.append(f"Минимальный срок кредита: {product.min_term_months} месяцев")
    if term_months > product.max_term_months:
        errors.append(f"Максимальный срок кредита: {product.max_term_months} месяцев")

    # Проверка кредитного рейтинга
    if client.credit_score < product.min_credit_score:
        errors.append(f"Требуется минимальный кредитный рейтинг: {product.min_credit_score}")

    is_valid = len(errors) == 0
    return is_valid, errors