from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.db import models
from django.core.paginator import Paginator
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Sum, Avg, Count, F
from django.template.loader import render_to_string
import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
import os
import tempfile

from .models import ReportTemplate, SavedReport, ReportSchedule, DashboardWidget, ExportFormat, AnalyticsDashboard
from .forms import ReportParametersForm, ScheduleReportForm, ExportFormatForm, DashboardWidgetForm, \
    AnalyticsDashboardForm, ReportGenerationForm, QuickExportForm


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_account_model():
    """Ленивая загрузка модели Account"""
    return apps.get_model('accounts', 'Account')


def get_credit_model():
    """Ленивая загрузка модели Credit"""
    return apps.get_model('credits', 'Credit')


def get_deposit_model():
    """Ленивая загрузка модели Deposit"""
    return apps.get_model('deposits', 'Deposit')


def get_transaction_model():
    """Ленивая загрузка модели Transaction"""
    return apps.get_model('transactions', 'Transaction')


def get_deposit_interest_payment_model():
    """Ленивая загрузка модели DepositInterestPayment"""
    return apps.get_model('deposits', 'DepositInterestPayment')


def get_card_model():
    """Ленивая загрузка модели Card"""
    return apps.get_model('cards', 'Card')


def get_card_status_history_model():
    """Ленивая загрузка модели CardStatusHistory"""
    return apps.get_model('cards', 'CardStatusHistory')


# Локальные декораторы
def role_required(allowed_roles):
    from functools import wraps

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            User = get_user_model()
            if request.user.is_authenticated and request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            else:
                return HttpResponseForbidden("У вас нет доступа к этой странице.")

        return wrapper

    return decorator


def employee_required(view_func):
    return role_required(['employee', 'admin'])(view_func)


def admin_required(view_func):
    return role_required(['admin'])(view_func)


# ============================================================================
# СУЩЕСТВУЮЩИЕ ПРЕДСТАВЛЕНИЯ ОТЧЕТОВ (сохраняем без изменений)
# ============================================================================

@login_required
@employee_required
def report_dashboard(request):
    """Дашборд отчетности"""
    Client = get_client_model()
    Account = get_account_model()
    Credit = get_credit_model()
    Deposit = get_deposit_model()
    Transaction = get_transaction_model()
    DepositInterestPayment = get_deposit_interest_payment_model()
    Card = get_card_model()

    # Базовая статистика
    total_clients = Client.objects.count()
    total_accounts = Account.objects.filter(status='active').count()
    active_credits = Credit.objects.filter(status='active').count()
    active_deposits = Deposit.objects.filter(status='active').count()
    total_cards = Card.objects.count()

    # Финансовая статистика
    total_balance = Account.objects.filter(status='active').aggregate(
        total=models.Sum('balance')
    )['total'] or Decimal('0')

    total_credit_amount = Credit.objects.filter(status='active').aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    total_deposit_amount = Deposit.objects.filter(status='active').aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # НОВАЯ СТАТИСТИКА: Начисленные проценты по депозитам
    total_accrued_interest = DepositInterestPayment.objects.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # Статистика за последние 30 дней
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_transactions = Transaction.objects.filter(
        created_at__gte=thirty_days_ago
    )
    transaction_volume = recent_transactions.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # НОВАЯ СТАТИСТИКА: Начисления процентов за последние 30 дней
    recent_interest_accruals = DepositInterestPayment.objects.filter(
        payment_date__gte=thirty_days_ago.date()
    )
    recent_interest_amount = recent_interest_accruals.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # НОВАЯ СТАТИСТИКА: Карты
    active_cards = Card.objects.filter(status='active').count()
    blocked_cards = Card.objects.filter(status='blocked').count()
    expired_cards = Card.objects.filter(status='expired').count()

    # Топ депозитов по начисленным процентам
    top_deposits_by_interest = Deposit.objects.annotate(
        total_interest=Sum('interest_payments__amount')
    ).filter(total_interest__gt=0).order_by('-total_interest')[:5]

    return render(request, 'reports/report_dashboard.html', {
        'total_clients': total_clients,
        'total_accounts': total_accounts,
        'active_credits': active_credits,
        'active_deposits': active_deposits,
        'total_cards': total_cards,
        'active_cards': active_cards,
        'blocked_cards': blocked_cards,
        'expired_cards': expired_cards,
        'total_balance': total_balance,
        'total_credit_amount': total_credit_amount,
        'total_deposit_amount': total_deposit_amount,
        'total_accrued_interest': total_accrued_interest,
        'transaction_volume': transaction_volume,
        'recent_transactions_count': recent_transactions.count(),
        'recent_interest_amount': recent_interest_amount,
        'top_deposits_by_interest': top_deposits_by_interest,
    })


@login_required
@employee_required
def client_report(request):
    """Отчет по клиентам"""
    Client = get_client_model()
    Deposit = get_deposit_model()
    Credit = get_credit_model()
    Card = get_card_model()

    # Фильтрация
    is_vip = request.GET.get('is_vip')
    min_rating = request.GET.get('min_rating')

    clients = Client.objects.all()

    if is_vip == 'true':
        clients = clients.filter(is_vip=True)
    elif is_vip == 'false':
        clients = clients.filter(is_vip=False)

    if min_rating:
        clients = clients.filter(credit_rating__gte=int(min_rating))

    # НОВАЯ СТАТИСТИКА: Добавляем информацию о депозитах, кредитах и картах клиентов
    clients_with_stats = []
    for client in clients:
        client_deposits = client.deposits.filter(status='active')
        client_credits = client.credits.filter(status='active')
        client_cards = client.cards.all()

        total_deposit_amount = client_deposits.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        total_credit_amount = client_credits.aggregate(total=Sum('amount'))['total'] or Decimal('0')
        active_cards_count = client_cards.filter(status='active').count()
        blocked_cards_count = client_cards.filter(status='blocked').count()

        # Сумма начисленных процентов по депозитам клиента
        total_interest_accrued = Decimal('0')
        for deposit in client_deposits:
            total_interest_accrued += deposit.get_total_accrued_interest()

        clients_with_stats.append({
            'client': client,
            'deposit_count': client_deposits.count(),
            'total_deposit_amount': total_deposit_amount,
            'credit_count': client_credits.count(),
            'total_credit_amount': total_credit_amount,
            'total_interest_accrued': total_interest_accrued,
            'cards_count': client_cards.count(),
            'active_cards_count': active_cards_count,
            'blocked_cards_count': blocked_cards_count,
        })

    # Статистика
    vip_count = Client.objects.filter(is_vip=True).count()
    avg_rating = clients.aggregate(avg=models.Avg('credit_rating'))['avg'] or 0

    return render(request, 'reports/client_report.html', {
        'clients_with_stats': clients_with_stats,
        'vip_count': vip_count,
        'avg_rating': avg_rating,
        'is_vip': is_vip,
        'min_rating': min_rating
    })


@login_required
@employee_required
def credit_report(request):
    """Отчет по кредитам"""
    Credit = get_credit_model()

    # Фильтрация
    status = request.GET.get('status', 'active')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    credits = Credit.objects.all()

    if status:
        credits = credits.filter(status=status)
    if date_from:
        credits = credits.filter(created_at__date__gte=date_from)
    if date_to:
        credits = credits.filter(created_at__date__lte=date_to)

    # Статистика
    total_amount = credits.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    avg_interest = credits.aggregate(avg=models.Avg('interest_rate'))['avg'] or 0
    total_overdue = credits.aggregate(total=models.Sum('overdue_amount'))['total'] or Decimal('0')

    # Группировка по статусам
    by_status = Credit.objects.values('status').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount')
    )

    return render(request, 'reports/credit_report.html', {
        'credits': credits,
        'total_amount': total_amount,
        'avg_interest': avg_interest,
        'total_overdue': total_overdue,
        'by_status': by_status,
        'status': status,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
@employee_required
def deposit_report(request):
    """Отчет по депозитам"""
    Deposit = get_deposit_model()

    # Фильтрация
    status = request.GET.get('status', 'active')
    deposit_type = request.GET.get('deposit_type')
    min_interest_rate = request.GET.get('min_interest_rate')

    deposits = Deposit.objects.all()

    if status:
        deposits = deposits.filter(status=status)
    if deposit_type:
        deposits = deposits.filter(deposit_type=deposit_type)
    if min_interest_rate:
        deposits = deposits.filter(interest_rate__gte=min_interest_rate)

    # НОВАЯ СТАТИСТИКА: Добавляем информацию о начисленных процентах
    deposits_with_interest = []
    for deposit in deposits:
        total_accrued_interest = deposit.get_total_accrued_interest()
        expected_interest = deposit.get_expected_interest()
        deposits_with_interest.append({
            'deposit': deposit,
            'total_accrued_interest': total_accrued_interest,
            'expected_interest': expected_interest,
        })

    # Статистика
    total_amount = deposits.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    avg_interest = deposits.aggregate(avg=models.Avg('interest_rate'))['avg'] or 0

    # НОВАЯ СТАТИСТИКА: Общая сумма начисленных процентов
    total_accrued_interest_all = Decimal('0')
    for item in deposits_with_interest:
        total_accrued_interest_all += item['total_accrued_interest']

    # Группировка по типам
    by_type = Deposit.objects.values('deposit_type').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount'),
        avg_interest=models.Avg('interest_rate')
    )

    # НОВАЯ СТАТИСТИКА: Группировка по капитализации
    by_capitalization = Deposit.objects.values('capitalization').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount'),
        avg_interest=models.Avg('interest_rate')
    )

    return render(request, 'reports/deposit_report.html', {
        'deposits_with_interest': deposits_with_interest,
        'total_amount': total_amount,
        'avg_interest': avg_interest,
        'total_accrued_interest_all': total_accrued_interest_all,
        'by_type': by_type,
        'by_capitalization': by_capitalization,
        'status': status,
        'deposit_type': deposit_type,
        'min_interest_rate': min_interest_rate,
    })


@login_required
@employee_required
def card_report(request):
    """Отчет по банковским картам"""
    Card = get_card_model()
    CardStatusHistory = get_card_status_history_model()

    # Фильтрация
    status = request.GET.get('status', '')
    card_type = request.GET.get('card_type', '')
    card_system = request.GET.get('card_system', '')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    cards = Card.objects.select_related('account', 'account__client', 'account__client__user')

    if status:
        cards = cards.filter(status=status)
    if card_type:
        cards = cards.filter(card_type=card_type)
    if card_system:
        cards = cards.filter(card_system=card_system)

    # Статистика
    total_cards = cards.count()
    active_cards = cards.filter(status='active').count()
    blocked_cards = cards.filter(status='blocked').count()
    expired_cards = cards.filter(status='expired').count()

    # НОВАЯ СТАТИСТИКА: История блокировок за период
    if date_from and date_to:
        block_history = CardStatusHistory.objects.filter(
            changed_at__date__range=[date_from, date_to],
            new_status='blocked'
        ).count()
        unblock_history = CardStatusHistory.objects.filter(
            changed_at__date__range=[date_from, date_to],
            new_status='active',
            old_status='blocked'
        ).count()
    else:
        block_history = 0
        unblock_history = 0

    # Группировка по статусам
    by_status = cards.values('status').annotate(
        count=models.Count('id')
    )

    # Группировка по типам карт
    by_type = cards.values('card_type').annotate(
        count=models.Count('id')
    )

    # Группировка по платежным системам
    by_system = cards.values('card_system').annotate(
        count=models.Count('id')
    )

    # Топ карт по количеству транзакций
    top_cards_by_transactions = cards.annotate(
        transaction_count=models.Count('transactions')
    ).order_by('-transaction_count')[:10]

    return render(request, 'reports/card_report.html', {
        'cards': cards,
        'total_cards': total_cards,
        'active_cards': active_cards,
        'blocked_cards': blocked_cards,
        'expired_cards': expired_cards,
        'block_history': block_history,
        'unblock_history': unblock_history,
        'by_status': by_status,
        'by_type': by_type,
        'by_system': by_system,
        'top_cards_by_transactions': top_cards_by_transactions,
        'status': status,
        'card_type': card_type,
        'card_system': card_system,
        'date_from': date_from,
        'date_to': date_to,
    })


@login_required
@employee_required
def transaction_report(request):
    """Расширенный отчет по транзакциям"""
    Transaction = get_transaction_model()

    # Фильтрация
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))
    transaction_type = request.GET.get('transaction_type', '')

    transactions = Transaction.objects.filter(
        created_at__date__range=[date_from, date_to]
    )

    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    # Детальная статистика
    total_count = transactions.count()
    total_amount = transactions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    total_fee = transactions.aggregate(total=models.Sum('fee'))['total'] or Decimal('0')

    # НОВАЯ СТАТИСТИКА: Начисления процентов по депозитам
    interest_transactions = transactions.filter(
        transaction_type__in=['deposit_interest', 'interest_accrual']
    )
    total_interest_amount = interest_transactions.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # НОВАЯ СТАТИСТИКА: Карточные операции
    card_transactions = transactions.filter(
        transaction_type__in=['card_payment', 'card_withdrawal']
    )
    total_card_amount = card_transactions.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # Группировка по дням
    daily_stats = transactions.extra(
        {'date': "DATE(created_at)"}
    ).values('date').annotate(
        count=models.Count('id'),
        amount=models.Sum('amount'),
        fee=models.Sum('fee')
    ).order_by('date')

    # Группировка по типам
    type_stats = transactions.values('transaction_type').annotate(
        count=models.Count('id'),
        amount=models.Sum('amount'),
        fee=models.Sum('fee')
    )

    return render(request, 'reports/transaction_report.html', {
        'transactions': transactions,
        'total_count': total_count,
        'total_amount': total_amount,
        'total_fee': total_fee,
        'total_interest_amount': total_interest_amount,
        'total_card_amount': total_card_amount,
        'card_transactions_count': card_transactions.count(),
        'daily_stats': daily_stats,
        'type_stats': type_stats,
        'date_from': date_from,
        'date_to': date_to,
        'transaction_type': transaction_type
    })


@login_required
@employee_required
def financial_report(request):
    """Финансовый отчет"""
    Account = get_account_model()
    Credit = get_credit_model()
    Deposit = get_deposit_model()
    Transaction = get_transaction_model()
    DepositInterestPayment = get_deposit_interest_payment_model()
    Card = get_card_model()

    # Период для отчета
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))

    # Активы (счета)
    total_assets = Account.objects.filter(status='active').aggregate(
        total=models.Sum('balance')
    )['total'] or Decimal('0')

    # Кредитный портфель
    credit_portfolio = Credit.objects.filter(status='active').aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # Депозитный портфель
    deposit_portfolio = Deposit.objects.filter(status='active').aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # Карточный портфель
    total_cards = Card.objects.count()
    active_cards = Card.objects.filter(status='active').count()

    # Доходы (комиссии за период)
    transaction_fees = Transaction.objects.filter(
        created_at__date__range=[date_from, date_to]
    ).aggregate(total_fee=models.Sum('fee'))['total_fee'] or Decimal('0')

    # НОВЫЙ РАСЧЕТ: Процентные доходы от депозитов
    deposit_interest_income = DepositInterestPayment.objects.filter(
        payment_date__range=[date_from, date_to]
    ).aggregate(total_interest=models.Sum('amount'))['total_interest'] or Decimal('0')

    # Процентные доходы от кредитов (упрощенно)
    credit_interest_income = Credit.objects.filter(
        status='active'
    ).aggregate(total_interest=models.Sum('interest_amount'))['total_interest'] or Decimal('0')

    # Общие процентные доходы
    total_interest_income = deposit_interest_income + credit_interest_income

    # НОВАЯ СТАТИСТИКА: Рентабельность
    total_income = transaction_fees + total_interest_income

    return render(request, 'reports/financial_report.html', {
        'total_assets': total_assets,
        'credit_portfolio': credit_portfolio,
        'deposit_portfolio': deposit_portfolio,
        'total_cards': total_cards,
        'active_cards': active_cards,
        'transaction_fees': transaction_fees,
        'deposit_interest_income': deposit_interest_income,
        'credit_interest_income': credit_interest_income,
        'total_interest_income': total_interest_income,
        'total_income': total_income,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
@employee_required
def interest_accrual_report(request):
    """Отчет по начисленным процентам по депозитам"""
    DepositInterestPayment = get_deposit_interest_payment_model()
    Deposit = get_deposit_model()

    # Фильтрация
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))
    deposit_id = request.GET.get('deposit_id')
    deposit_type = request.GET.get('deposit_type')

    interest_payments = DepositInterestPayment.objects.select_related(
        'deposit', 'deposit__client', 'deposit__account', 'deposit__account__currency'
    ).filter(
        payment_date__range=[date_from, date_to]
    )

    if deposit_id:
        interest_payments = interest_payments.filter(deposit_id=deposit_id)

    if deposit_type:
        interest_payments = interest_payments.filter(deposit__deposit_type=deposit_type)

    # Статистика
    total_accrued = interest_payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    payment_count = interest_payments.count()

    # Группировка по депозитам
    by_deposit = interest_payments.values(
        'deposit_id',
        'deposit__client__full_name',
        'deposit__account__currency__code'
    ).annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount')
    ).order_by('-total_amount')

    # Группировка по месяцам
    by_month = interest_payments.extra(
        {'month': "DATE_FORMAT(payment_date, '%%Y-%%m')"}
    ).values('month').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount')
    ).order_by('month')

    # Доступные депозиты для фильтра
    deposits_for_filter = Deposit.objects.filter(status='active')

    return render(request, 'reports/interest_accrual_report.html', {
        'interest_payments': interest_payments,
        'total_accrued': total_accrued,
        'payment_count': payment_count,
        'by_deposit': by_deposit,
        'by_month': by_month,
        'deposits_for_filter': deposits_for_filter,
        'date_from': date_from,
        'date_to': date_to,
        'deposit_id': deposit_id,
        'deposit_type': deposit_type,
    })


@login_required
@employee_required
def card_block_report(request):
    """Отчет по блокировкам и разблокировкам карт"""
    CardStatusHistory = get_card_status_history_model()
    Card = get_card_model()

    # Фильтрация
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))
    action_type = request.GET.get('action_type', '')

    status_history = CardStatusHistory.objects.select_related(
        'card', 'card__account', 'card__account__client', 'changed_by'
    ).filter(
        changed_at__date__range=[date_from, date_to]
    )

    if action_type == 'block':
        status_history = status_history.filter(new_status='blocked')
    elif action_type == 'unblock':
        status_history = status_history.filter(new_status='active', old_status='blocked')

    # Статистика
    total_actions = status_history.count()
    block_actions = status_history.filter(new_status='blocked').count()
    unblock_actions = status_history.filter(new_status='active', old_status='blocked').count()

    # Группировка по причинам блокировки
    block_reasons = status_history.filter(new_status='blocked').values(
        'block_reason'
    ).annotate(
        count=models.Count('id')
    )

    # Группировка по пользователям
    by_user = status_history.values(
        'changed_by__username',
        'changed_by__first_name',
        'changed_by__last_name'
    ).annotate(
        count=models.Count('id')
    ).order_by('-count')

    # Топ карт по количеству блокировок
    top_cards_by_blocks = status_history.filter(new_status='blocked').values(
        'card__card_number',
        'card__cardholder_name'
    ).annotate(
        block_count=models.Count('id')
    ).order_by('-block_count')[:10]

    return render(request, 'reports/card_block_report.html', {
        'status_history': status_history,
        'total_actions': total_actions,
        'block_actions': block_actions,
        'unblock_actions': unblock_actions,
        'block_reasons': block_reasons,
        'by_user': by_user,
        'top_cards_by_blocks': top_cards_by_blocks,
        'date_from': date_from,
        'date_to': date_to,
        'action_type': action_type,
    })


@login_required
@employee_required
def quick_deposit_report(request):
    """Быстрый отчет по депозитам с основной статистикой"""
    Deposit = get_deposit_model()
    DepositInterestPayment = get_deposit_interest_payment_model()

    # Основная статистика
    total_deposits = Deposit.objects.count()
    active_deposits = Deposit.objects.filter(status='active').count()
    total_deposit_amount = Deposit.objects.filter(status='active').aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # Статистика по начисленным процентам
    total_accrued_interest = DepositInterestPayment.objects.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    # Депозиты по типам
    deposits_by_type = Deposit.objects.values('deposit_type').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount')
    )

    # Топ-5 депозитов по начисленным процентам
    top_deposits = Deposit.objects.annotate(
        total_interest=Sum('interest_payments__amount')
    ).filter(total_interest__gt=0).order_by('-total_interest')[:5]

    # Последние начисления процентов
    recent_interest_payments = DepositInterestPayment.objects.select_related(
        'deposit', 'deposit__client'
    ).order_by('-payment_date')[:10]

    return render(request, 'reports/quick_deposit_report.html', {
        'total_deposits': total_deposits,
        'active_deposits': active_deposits,
        'total_deposit_amount': total_deposit_amount,
        'total_accrued_interest': total_accrued_interest,
        'deposits_by_type': deposits_by_type,
        'top_deposits': top_deposits,
        'recent_interest_payments': recent_interest_payments,
    })


@login_required
@employee_required
def quick_card_report(request):
    """Быстрый отчет по картам с основной статистикой"""
    Card = get_card_model()
    CardStatusHistory = get_card_status_history_model()

    # Основная статистика
    total_cards = Card.objects.count()
    active_cards = Card.objects.filter(status='active').count()
    blocked_cards = Card.objects.filter(status='blocked').count()
    expired_cards = Card.objects.filter(status='expired').count()

    # Статистика по типам карт
    cards_by_type = Card.objects.values('card_type').annotate(
        count=models.Count('id')
    )

    # Статистика по платежным системам
    cards_by_system = Card.objects.values('card_system').annotate(
        count=models.Count('id')
    )

    # Последние блокировки карт
    recent_blocks = CardStatusHistory.objects.filter(
        new_status='blocked'
    ).select_related('card', 'changed_by').order_by('-changed_at')[:10]

    # Карты с истекающим сроком действия (в течение 30 дней)
    from datetime import date, timedelta
    expiry_threshold = date.today() + timedelta(days=30)
    expiring_cards = Card.objects.filter(
        expiry_date__lte=expiry_threshold,
        expiry_date__gte=date.today()
    ).order_by('expiry_date')[:10]

    return render(request, 'reports/quick_card_report.html', {
        'total_cards': total_cards,
        'active_cards': active_cards,
        'blocked_cards': blocked_cards,
        'expired_cards': expired_cards,
        'cards_by_type': cards_by_type,
        'cards_by_system': cards_by_system,
        'recent_blocks': recent_blocks,
        'expiring_cards': expiring_cards,
    })


# ============================================================================
# СИСТЕМА ЭКСПОРТА ДАННЫХ (сохраняем существующие + добавляем новые)
# ============================================================================

@login_required
@employee_required
def export_json(request):
    """Экспорт данных в JSON"""
    data_type = request.GET.get('type', 'clients')

    if data_type == 'clients':
        Client = get_client_model()
        clients = Client.objects.all()
        data = []
        for client in clients:
            data.append({
                'id': client.id,
                'full_name': client.full_name,
                'inn': client.inn,
                'phone': client.user.phone if client.user else '',
                'credit_rating': client.credit_rating,
                'is_vip': client.is_vip,
                'created_at': client.created_at.strftime('%Y-%m-%d') if client.created_at else ''
            })
        filename = 'clients_export.json'
    elif data_type == 'credits':
        Credit = get_credit_model()
        credits = Credit.objects.all()
        data = []
        for credit in credits:
            data.append({
                'id': credit.id,
                'client': credit.client.full_name,
                'amount': str(credit.amount),
                'interest_rate': str(credit.interest_rate),
                'term_months': credit.term_months,
                'status': credit.status,
                'status_display': credit.get_status_display(),
                'start_date': credit.start_date.strftime('%Y-%m-%d') if credit.start_date else '',
                'created_at': credit.created_at.strftime('%Y-%m-%d %H:%M') if credit.created_at else ''
            })
        filename = 'credits_export.json'
    elif data_type == 'deposits':
        Deposit = get_deposit_model()
        deposits = Deposit.objects.all()
        data = []
        for deposit in deposits:
            data.append({
                'id': deposit.id,
                'client': deposit.client.full_name,
                'amount': str(deposit.amount),
                'interest_rate': str(deposit.interest_rate),
                'deposit_type': deposit.deposit_type,
                'deposit_type_display': deposit.get_deposit_type_display(),
                'capitalization': deposit.capitalization,
                'capitalization_display': deposit.get_capitalization_display(),
                'status': deposit.status,
                'status_display': deposit.get_status_display(),
                'start_date': deposit.start_date.strftime('%Y-%m-%d') if deposit.start_date else '',
                'end_date': deposit.end_date.strftime('%Y-%m-%d') if deposit.end_date else '',
                'total_accrued_interest': str(deposit.get_total_accrued_interest()),
            })
        filename = 'deposits_export.json'
    elif data_type == 'interest_accruals':
        DepositInterestPayment = get_deposit_interest_payment_model()
        interest_payments = DepositInterestPayment.objects.all()
        data = []
        for payment in interest_payments:
            data.append({
                'id': payment.id,
                'deposit_id': payment.deposit.id,
                'client': payment.deposit.client.full_name,
                'period_start': payment.period_start.strftime('%Y-%m-%d') if payment.period_start else '',
                'period_end': payment.period_end.strftime('%Y-%m-%d') if payment.period_end else '',
                'amount': str(payment.amount),
                'payment_date': payment.payment_date.strftime('%Y-%m-%d') if payment.payment_date else '',
                'created_at': payment.created_at.strftime('%Y-%m-%d %H:%M') if payment.created_at else ''
            })
        filename = 'interest_accruals_export.json'
    elif data_type == 'cards':
        Card = get_card_model()
        cards = Card.objects.all()
        data = []
        for card in cards:
            data.append({
                'id': card.id,
                'card_number': card.get_masked_number(),
                'cardholder_name': card.cardholder_name,
                'account': card.account.account_number,
                'client': card.account.client.full_name,
                'card_type': card.card_type,
                'card_type_display': card.get_card_type_display(),
                'card_system': card.card_system,
                'card_system_display': card.get_card_system_display(),
                'status': card.status,
                'status_display': card.get_status_display(),
                'daily_limit': str(card.daily_limit),
                'expiry_date': card.expiry_date.strftime('%Y-%m-%d') if card.expiry_date else '',
                'is_virtual': card.is_virtual,
                'created_at': card.created_at.strftime('%Y-%m-%d %H:%M') if card.created_at else ''
            })
        filename = 'cards_export.json'
    else:
        messages.error(request, 'Неподдерживаемый тип данных для экспорта')
        return redirect('reports:report_dashboard')

    response = HttpResponse(json.dumps(data, ensure_ascii=False, indent=2), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


@login_required
@employee_required
def export_csv(request):
    """Экспорт данных в CSV"""
    data_type = request.GET.get('type', 'clients')

    if data_type == 'clients':
        Client = get_client_model()
        data = Client.objects.all()
        filename = 'clients_export.csv'
    elif data_type == 'credits':
        Credit = get_credit_model()
        data = Credit.objects.all()
        filename = 'credits_export.csv'
    elif data_type == 'deposits':
        Deposit = get_deposit_model()
        data = Deposit.objects.all()
        filename = 'deposits_export.csv'
    elif data_type == 'interest_accruals':
        DepositInterestPayment = get_deposit_interest_payment_model()
        data = DepositInterestPayment.objects.all()
        filename = 'interest_accruals_export.csv'
    elif data_type == 'cards':
        Card = get_card_model()
        data = Card.objects.all()
        filename = 'cards_export.csv'
    else:
        messages.error(request, 'Неподдерживаемый тип данных для экспорта')
        return redirect('reports:report_dashboard')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')
    writer = csv.writer(response)

    if data_type == 'clients':
        writer.writerow(['ID', 'ФИО', 'ИНН', 'Телефон', 'Кредитный рейтинг', 'VIP', 'Дата регистрации'])
        for item in data:
            writer.writerow([
                item.id, item.full_name, item.inn, item.user.phone,
                item.credit_rating, 'Да' if item.is_vip else 'Нет',
                item.created_at.strftime('%Y-%m-%d')
            ])
    elif data_type == 'credits':
        writer.writerow(['ID', 'Клиент', 'Сумма', 'Процентная ставка', 'Срок', 'Статус', 'Дата выдачи'])
        for item in data:
            writer.writerow([
                item.id, item.client.full_name, item.amount, item.interest_rate,
                item.term_months, item.get_status_display(),
                item.start_date.strftime('%Y-%m-%d') if item.start_date else ''
            ])
    elif data_type == 'deposits':
        writer.writerow(
            ['ID', 'Клиент', 'Сумма', 'Процентная ставка', 'Тип', 'Капитализация', 'Статус', 'Начислено процентов',
             'Дата открытия'])
        for item in data:
            writer.writerow([
                item.id, item.client.full_name, item.amount, item.interest_rate,
                item.get_deposit_type_display(), item.get_capitalization_display(),
                item.get_status_display(), item.get_total_accrued_interest(),
                item.start_date.strftime('%Y-%m-%d')
            ])
    elif data_type == 'interest_accruals':
        writer.writerow(['ID', 'Депозит ID', 'Клиент', 'Период с', 'Период по', 'Сумма', 'Дата начисления'])
        for item in data:
            writer.writerow([
                item.id, item.deposit.id, item.deposit.client.full_name,
                item.period_start.strftime('%Y-%m-%d') if item.period_start else '',
                item.period_end.strftime('%Y-%m-%d') if item.period_end else '',
                item.amount, item.payment_date.strftime('%Y-%m-%d')
            ])
    elif data_type == 'cards':
        writer.writerow(
            ['ID', 'Номер карты', 'Держатель', 'Счет', 'Клиент', 'Тип', 'Платежная система', 'Статус', 'Дневной лимит',
             'Срок действия', 'Виртуальная', 'Дата создания'])
        for item in data:
            writer.writerow([
                item.id, item.get_masked_number(), item.cardholder_name,
                item.account.account_number, item.account.client.full_name,
                item.get_card_type_display(), item.get_card_system_display(),
                item.get_status_display(), item.daily_limit,
                item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else '',
                'Да' if item.is_virtual else 'Нет',
                item.created_at.strftime('%Y-%m-%d %H:%M')
            ])

    return response


@login_required
@employee_required
def export_excel(request):
    """Экспорт данных в Excel - ЗАМЕНА xlwt на простой CSV с расширением xlsx"""
    data_type = request.GET.get('type', 'clients')

    if data_type == 'clients':
        filename = 'clients_export.xlsx'
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif data_type == 'deposits':
        filename = 'deposits_export.xlsx'
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    elif data_type == 'cards':
        filename = 'cards_export.xlsx'
        content_type = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    else:
        messages.error(request, 'Неподдерживаемый тип данных для экспорта в Excel')
        return redirect('reports:report_dashboard')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Type'] = content_type
    response.write('\ufeff')
    writer = csv.writer(response)

    if data_type == 'clients':
        Client = get_client_model()
        data = Client.objects.all()
        writer.writerow(['ID', 'ФИО', 'ИНН', 'Телефон', 'Кредитный рейтинг', 'VIP', 'Дата регистрации'])
        for item in data:
            writer.writerow([
                item.id, item.full_name, item.inn, item.user.phone,
                item.credit_rating, 'Да' if item.is_vip else 'Нет',
                item.created_at.strftime('%Y-%m-%d')
            ])
    elif data_type == 'deposits':
        Deposit = get_deposit_model()
        data = Deposit.objects.all()
        writer.writerow(
            ['ID', 'Клиент', 'Сумма', 'Процентная ставка', 'Тип', 'Капитализация', 'Статус', 'Начислено процентов',
             'Дата открытия'])
        for item in data:
            writer.writerow([
                item.id, item.client.full_name, item.amount, item.interest_rate,
                item.get_deposit_type_display(), item.get_capitalization_display(),
                item.get_status_display(), item.get_total_accrued_interest(),
                item.start_date.strftime('%Y-%m-%d')
            ])
    elif data_type == 'cards':
        Card = get_card_model()
        data = Card.objects.all()
        writer.writerow(
            ['ID', 'Номер карты', 'Держатель', 'Счет', 'Клиент', 'Тип', 'Платежная система', 'Статус', 'Дневной лимит',
             'Срок действия', 'Виртуальная', 'Дата создания'])
        for item in data:
            writer.writerow([
                item.id, item.get_masked_number(), item.cardholder_name,
                item.account.account_number, item.account.client.full_name,
                item.get_card_type_display(), item.get_card_system_display(),
                item.get_status_display(), item.daily_limit,
                item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else '',
                'Да' if item.is_virtual else 'Нет',
                item.created_at.strftime('%Y-%m-%d %H:%M')
            ])

    messages.info(request,
                  'Excel экспорт временно заменен на CSV. Для полноценного Excel экспорта установите библиотеку openpyxl.')
    return response


@login_required
@employee_required
def export_pdf(request):
    """Экспорт данных в PDF - ЗАМЕНА WeasyPrint на простой HTML"""
    report_type = request.GET.get('type', 'financial')
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))

    if report_type == 'financial':
        context = financial_report(request).context_data
        template = 'reports/pdf/financial_report.html'
        filename = f'financial_report_{date_from}_to_{date_to}.html'
    elif report_type == 'deposit_interest':
        context = interest_accrual_report(request).context_data
        template = 'reports/pdf/interest_accrual_report.html'
        filename = f'deposit_interest_report_{date_from}_to_{date_to}.html'
    elif report_type == 'card_report':
        context = card_report(request).context_data
        template = 'reports/pdf/card_report.html'
        filename = f'card_report_{date_from}_to_{date_to}.html'
    else:
        messages.error(request, 'Неподдерживаемый тип отчета для PDF экспорта')
        return redirect('reports:report_dashboard')

    html_content = render_to_string(template, context)
    response = HttpResponse(html_content, content_type='text/html')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    messages.info(request, 'PDF экспорт временно заменен на HTML. Для полноценного PDF экспорта установите WeasyPrint.')
    return response


@login_required
@employee_required
def print_report(request):
    """Версия отчета для печати"""
    report_type = request.GET.get('type', 'financial')
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))

    if report_type == 'financial':
        context = financial_report(request).context_data
        template = 'reports/print/financial_report.html'
    elif report_type == 'deposit_interest':
        context = interest_accrual_report(request).context_data
        template = 'reports/print/interest_accrual_report.html'
    elif report_type == 'clients':
        context = client_report(request).context_data
        template = 'reports/print/client_report.html'
    elif report_type == 'card_report':
        context = card_report(request).context_data
        template = 'reports/print/card_report.html'
    else:
        messages.error(request, 'Неподдерживаемый тип отчета для печати')
        return redirect('reports:report_dashboard')

    return render(request, template, context)


# ============================================================================
# НОВЫЕ ПРЕДСТАВЛЕНИЯ: УПРАВЛЕНИЕ ШАБЛОНАМИ ОТЧЕТОВ
# ============================================================================

@login_required
@employee_required
def report_template_list(request):
    """Список шаблонов отчетов"""
    templates = ReportTemplate.objects.filter(
        Q(created_by=request.user) | Q(is_active=True)
    ).select_related('created_by')

    category = request.GET.get('category')
    if category:
        templates = templates.filter(category=category)

    search_query = request.GET.get('search')
    if search_query:
        templates = templates.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    paginator = Paginator(templates, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    categories = ReportTemplate.objects.values_list('category', flat=True).distinct()

    return render(request, 'reports/report_template_list.html', {
        'page_obj': page_obj,
        'categories': categories,
        'category': category,
        'search_query': search_query,
    })


@login_required
@employee_required
def report_template_create(request):
    """Создание нового шаблона отчета"""
    if request.method == 'POST':
        form = ReportParametersForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user
            template.save()
            messages.success(request, 'Шаблон отчета успешно создан.')
            return redirect('reports:template_list')
    else:
        form = ReportParametersForm()

    return render(request, 'reports/report_template_form.html', {
        'form': form,
        'title': 'Создание шаблона отчета'
    })


@login_required
@employee_required
def report_template_edit(request, template_id):
    """Редактирование шаблона отчета"""
    template = get_object_or_404(ReportTemplate, id=template_id, created_by=request.user)

    if request.method == 'POST':
        form = ReportParametersForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, 'Шаблон отчета успешно обновлен.')
            return redirect('reports:template_list')
    else:
        form = ReportParametersForm(instance=template)

    return render(request, 'reports/report_template_form.html', {
        'form': form,
        'title': 'Редактирование шаблона отчета',
        'template': template
    })


@login_required
@employee_required
def report_template_delete(request, template_id):
    """Удаление шаблона отчета"""
    template = get_object_or_404(ReportTemplate, id=template_id, created_by=request.user)

    if request.method == 'POST':
        template.delete()
        messages.success(request, 'Шаблон отчета успешно удален.')
        return redirect('reports:template_list')

    return render(request, 'reports/report_template_confirm_delete.html', {
        'template': template
    })


@login_required
@employee_required
def report_template_clone(request, template_id):
    """Клонирование шаблона отчета"""
    template = get_object_or_404(ReportTemplate, id=template_id)

    if request.method == 'POST':
        new_name = request.POST.get('new_name')
        if new_name:
            new_template = template.clone_template(new_name, request.user)
            messages.success(request, f'Шаблон "{template.name}" успешно склонирован как "{new_name}".')
            return redirect('reports:template_edit', template_id=new_template.id)
        else:
            messages.error(request, 'Необходимо указать название для нового шаблона.')

    return render(request, 'reports/report_template_clone.html', {
        'template': template
    })


# ============================================================================
# НОВЫЕ ПРЕДСТАВЛЕНИЯ: УПРАВЛЕНИЕ РАСПИСАНИЯМИ
# ============================================================================

@login_required
@employee_required
def schedule_list(request):
    """Список расписаний отчетов"""
    schedules = ReportSchedule.objects.filter(created_by=request.user).select_related('template')

    active_only = request.GET.get('active_only')
    if active_only:
        schedules = schedules.filter(is_active=True)

    paginator = Paginator(schedules, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'reports/schedule_list.html', {
        'page_obj': page_obj,
        'active_only': active_only
    })


@login_required
@employee_required
def schedule_create(request):
    """Создание нового расписания"""
    if request.method == 'POST':
        form = ScheduleReportForm(request.POST, user=request.user)
        if form.is_valid():
            schedule = form.save(commit=False)
            schedule.created_by = request.user
            schedule.save()
            messages.success(request, 'Расписание успешно создано.')
            return redirect('reports:schedule_list')
    else:
        form = ScheduleReportForm(user=request.user)

    return render(request, 'reports/schedule_form.html', {
        'form': form,
        'title': 'Создание расписания'
    })


@login_required
@employee_required
def schedule_edit(request, schedule_id):
    """Редактирование расписания"""
    schedule = get_object_or_404(ReportSchedule, id=schedule_id, created_by=request.user)

    if request.method == 'POST':
        form = ScheduleReportForm(request.POST, instance=schedule, user=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Расписание успешно обновлено.')
            return redirect('reports:schedule_list')
    else:
        form = ScheduleReportForm(instance=schedule, user=request.user)

    return render(request, 'reports/schedule_form.html', {
        'form': form,
        'title': 'Редактирование расписания',
        'schedule': schedule
    })


@login_required
@employee_required
def schedule_delete(request, schedule_id):
    """Удаление расписания"""
    schedule = get_object_or_404(ReportSchedule, id=schedule_id, created_by=request.user)

    if request.method == 'POST':
        schedule.delete()
        messages.success(request, 'Расписание успешно удалено.')
        return redirect('reports:schedule_list')

    return render(request, 'reports/schedule_confirm_delete.html', {
        'schedule': schedule
    })


@login_required
@employee_required
def schedule_toggle(request, schedule_id):
    """Включение/выключение расписания"""
    schedule = get_object_or_404(ReportSchedule, id=schedule_id, created_by=request.user)

    if request.method == 'POST':
        schedule.is_active = not schedule.is_active
        schedule.save()

        status = "включено" if schedule.is_active else "выключено"
        messages.success(request, f'Расписание "{schedule.name}" {status}.')

    return redirect('reports:schedule_list')


# ============================================================================
# НОВЫЕ ПРЕДСТАВЛЕНИЯ: УПРАВЛЕНИЕ СОХРАНЕННЫМИ ОТЧЕТАМИ
# ============================================================================

@login_required
@employee_required
def saved_report_list(request):
    """Список сохраненных отчетов"""
    reports = SavedReport.objects.filter(generated_by=request.user).select_related('template')

    report_type = request.GET.get('report_type')
    if report_type:
        reports = reports.filter(report_type=report_type)

    status = request.GET.get('status')
    if status:
        reports = reports.filter(generation_status=status)

    search_query = request.GET.get('search')
    if search_query:
        reports = reports.filter(name__icontains=search_query)

    paginator = Paginator(reports, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    report_types = SavedReport.objects.values_list('report_type', flat=True).distinct()

    return render(request, 'reports/saved_report_list.html', {
        'page_obj': page_obj,
        'report_types': report_types,
        'report_type': report_type,
        'status': status,
        'search_query': search_query,
    })


@login_required
@employee_required
def saved_report_detail(request, report_id):
    """Детальная информация о сохраненном отчете"""
    report = get_object_or_404(SavedReport, id=report_id, generated_by=request.user)

    return render(request, 'reports/saved_report_detail.html', {
        'report': report
    })


@login_required
@employee_required
def saved_report_delete(request, report_id):
    """Удаление сохраненного отчета"""
    report = get_object_or_404(SavedReport, id=report_id, generated_by=request.user)

    if request.method == 'POST':
        report.cleanup_file()
        report.delete()
        messages.success(request, 'Отчет успешно удален.')
        return redirect('reports:saved_report_list')

    return render(request, 'reports/saved_report_confirm_delete.html', {
        'report': report
    })


@login_required
@employee_required
def saved_report_download(request, report_id):
    """Скачивание сохраненного отчета"""
    report = get_object_or_404(SavedReport, id=report_id, generated_by=request.user)

    if not report.file_path or not os.path.exists(report.file_path):
        messages.error(request, 'Файл отчета не найден.')
        return redirect('reports:saved_report_list')

    try:
        with open(report.file_path, 'rb') as file:
            response = HttpResponse(file.read(), content_type='application/octet-stream')
            filename = f"{report.name}.{report.file_format}"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            return response
    except IOError:
        messages.error(request, 'Ошибка при чтении файла отчета.')
        return redirect('reports:saved_report_list')


# ============================================================================
# НОВЫЕ ПРЕДСТАВЛЕНИЯ: РАСШИРЕННАЯ СИСТЕМА ЭКСПОРТА
# ============================================================================

@login_required
@employee_required
def export_data_advanced(request):
    """Расширенный экспорт данных с выбором форматов и параметров"""
    if request.method == 'POST':
        form = ExportFormatForm(request.POST)
        if form.is_valid():
            data_type = form.cleaned_data['data_type']
            export_format = form.cleaned_data['export_format']
            include_metadata = form.cleaned_data['include_metadata']
            compression = form.cleaned_data['compression']

            if export_format == 'json':
                return export_json_advanced(request, data_type, include_metadata, compression)
            elif export_format == 'csv':
                return export_csv_advanced(request, data_type, include_metadata, compression)
            elif export_format == 'xlsx':
                return export_excel_advanced(request, data_type, include_metadata)
            elif export_format == 'pdf':
                return export_pdf_advanced(request, data_type)
            else:
                messages.error(request, 'Выбран неподдерживаемый формат экспорта.')
    else:
        form = ExportFormatForm()

    return render(request, 'reports/export_data_advanced.html', {
        'form': form
    })


def export_json_advanced(request, data_type, include_metadata=False, compression=False):
    """Продвинутый экспорт в JSON"""
    data = get_export_data(data_type, request.user)

    if include_metadata:
        export_data = {
            'metadata': {
                'export_type': data_type,
                'export_date': timezone.now().isoformat(),
                'exported_by': request.user.username,
                'record_count': len(data)
            },
            'data': data
        }
    else:
        export_data = data

    response = HttpResponse(
        json.dumps(export_data, ensure_ascii=False, indent=2),
        content_type='application/json'
    )

    filename = f"{data_type}_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.json"

    if compression:
        response['Content-Encoding'] = 'deflate'
        filename += '.deflate'

    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response


def export_csv_advanced(request, data_type, include_metadata=False, compression=False):
    """Продвинутый экспорт в CSV"""
    data = get_export_data(data_type, request.user)

    if not data:
        messages.error(request, 'Нет данных для экспорта.')
        return redirect('reports:export_data_advanced')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"{data_type}_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"

    if compression:
        response['Content-Encoding'] = 'deflate'
        filename += '.deflate'

    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response.write('\ufeff')

    writer = csv.writer(response)

    if data:
        headers = list(data[0].keys())
        writer.writerow(headers)

        for item in data:
            writer.writerow([str(item.get(key, '')) for key in headers])

    if include_metadata:
        writer.writerow([])
        writer.writerow(['# Metadata'])
        writer.writerow(['# Export Type:', data_type])
        writer.writerow(['# Export Date:', timezone.now().isoformat()])
        writer.writerow(['# Exported By:', request.user.username])
        writer.writerow(['# Record Count:', len(data)])

    return response


def export_excel_advanced(request, data_type, include_metadata=False):
    """Продвинутый экспорт в Excel"""
    data = get_export_data(data_type, request.user)

    if not data:
        messages.error(request, 'Нет данных для экспорта.')
        return redirect('reports:export_data_advanced')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    filename = f"{data_type}_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    response.write('\ufeff')

    writer = csv.writer(response)

    if data:
        headers = list(data[0].keys())
        writer.writerow(headers)

        for item in data:
            writer.writerow([str(item.get(key, '')) for key in headers])

    if include_metadata:
        writer.writerow([])
        writer.writerow(['Metadata'])
        writer.writerow(['Export Type:', data_type])
        writer.writerow(['Export Date:', timezone.now().isoformat()])
        writer.writerow(['Exported By:', request.user.username])
        writer.writerow(['Record Count:', len(data)])

    messages.info(request,
                  'Excel экспорт временно заменен на CSV. Для полноценного Excel экспорта установите библиотеку openpyxl.')
    return response


def export_pdf_advanced(request, data_type):
    """Продвинутый экспорт в PDF"""
    context = get_report_context(data_type, request)

    template_map = {
        'clients': 'reports/pdf/client_report.html',
        'credits': 'reports/pdf/credit_report.html',
        'deposits': 'reports/pdf/deposit_report.html',
        'transactions': 'reports/pdf/transaction_report.html',
        'financial': 'reports/pdf/financial_report.html',
        'cards': 'reports/pdf/card_report.html',
    }

    template = template_map.get(data_type, 'reports/pdf/generic_report.html')
    html_content = render_to_string(template, context)

    response = HttpResponse(html_content, content_type='text/html')
    filename = f"{data_type}_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.html"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    messages.info(request, 'PDF экспорт временно заменен на HTML. Для полноценного PDF экспорта установите WeasyPrint.')
    return response


def get_export_data(data_type, user):
    """Получение данных для экспорта"""
    if data_type == 'clients':
        Client = get_client_model()
        clients = Client.objects.all()
        data = []
        for client in clients:
            data.append({
                'id': client.id,
                'full_name': client.full_name,
                'inn': client.inn,
                'phone': client.user.phone if client.user else '',
                'credit_rating': client.credit_rating,
                'is_vip': client.is_vip,
                'created_at': client.created_at.strftime('%Y-%m-%d') if client.created_at else ''
            })
        return data

    elif data_type == 'credits':
        Credit = get_credit_model()
        credits = Credit.objects.all()
        data = []
        for credit in credits:
            data.append({
                'id': credit.id,
                'client': credit.client.full_name,
                'amount': str(credit.amount),
                'interest_rate': str(credit.interest_rate),
                'term_months': credit.term_months,
                'status': credit.status,
                'status_display': credit.get_status_display(),
                'start_date': credit.start_date.strftime('%Y-%m-%d') if credit.start_date else '',
                'created_at': credit.created_at.strftime('%Y-%m-%d %H:%M') if credit.created_at else ''
            })
        return data

    elif data_type == 'deposits':
        Deposit = get_deposit_model()
        deposits = Deposit.objects.all()
        data = []
        for deposit in deposits:
            data.append({
                'id': deposit.id,
                'client': deposit.client.full_name,
                'amount': str(deposit.amount),
                'interest_rate': str(deposit.interest_rate),
                'deposit_type': deposit.deposit_type,
                'deposit_type_display': deposit.get_deposit_type_display(),
                'capitalization': deposit.capitalization,
                'capitalization_display': deposit.get_capitalization_display(),
                'status': deposit.status,
                'status_display': deposit.get_status_display(),
                'start_date': deposit.start_date.strftime('%Y-%m-%d') if deposit.start_date else '',
                'end_date': deposit.end_date.strftime('%Y-%m-%d') if deposit.end_date else '',
                'total_accrued_interest': str(deposit.get_total_accrued_interest()),
            })
        return data

    elif data_type == 'transactions':
        Transaction = get_transaction_model()
        transactions = Transaction.objects.all()[:1000]  # Ограничиваем для производительности
        data = []
        for transaction in transactions:
            data.append({
                'id': transaction.id,
                'amount': str(transaction.amount),
                'transaction_type': transaction.transaction_type,
                'transaction_type_display': transaction.get_transaction_type_display(),
                'description': transaction.description,
                'created_at': transaction.created_at.strftime('%Y-%m-%d %H:%M') if transaction.created_at else '',
            })
        return data

    elif data_type == 'cards':
        Card = get_card_model()
        cards = Card.objects.all()
        data = []
        for card in cards:
            data.append({
                'id': card.id,
                'card_number': card.get_masked_number(),
                'cardholder_name': card.cardholder_name,
                'account': card.account.account_number,
                'client': card.account.client.full_name,
                'card_type': card.card_type,
                'card_type_display': card.get_card_type_display(),
                'card_system': card.card_system,
                'card_system_display': card.get_card_system_display(),
                'status': card.status,
                'status_display': card.get_status_display(),
                'daily_limit': str(card.daily_limit),
                'expiry_date': card.expiry_date.strftime('%Y-%m-%d') if card.expiry_date else '',
                'is_virtual': card.is_virtual,
                'created_at': card.created_at.strftime('%Y-%m-%d %H:%M') if card.created_at else ''
            })
        return data

    return []


def get_report_context(data_type, request):
    """Получение контекста для отчетов"""
    if data_type == 'clients':
        return client_report(request).context_data
    elif data_type == 'credits':
        return credit_report(request).context_data
    elif data_type == 'deposits':
        return deposit_report(request).context_data
    elif data_type == 'transactions':
        return transaction_report(request).context_data
    elif data_type == 'financial':
        return financial_report(request).context_data
    elif data_type == 'cards':
        return card_report(request).context_data
    return {}


# ============================================================================
# НОВЫЕ ПРЕДСТАВЛЕНИЯ: ДАШБОРДЫ АНАЛИТИКИ
# ============================================================================

@login_required
@employee_required
def analytics_dashboard_list(request):
    """Список дашбордов аналитики"""
    dashboards = AnalyticsDashboard.objects.filter(
        Q(created_by=request.user) | Q(is_public=True)
    )

    return render(request, 'reports/analytics_dashboard_list.html', {
        'dashboards': dashboards
    })


@login_required
@employee_required
def analytics_dashboard_view(request, dashboard_id):
    """Просмотр дашборда аналитики"""
    dashboard = get_object_or_404(AnalyticsDashboard, id=dashboard_id)

    if not dashboard.is_public and dashboard.created_by != request.user:
        return HttpResponseForbidden("У вас нет доступа к этому дашборду.")

    return render(request, 'reports/analytics_dashboard_view.html', {
        'dashboard': dashboard
    })


@login_required
@admin_required
def analytics_dashboard_create(request):
    """Создание нового дашборда аналитики"""
    if request.method == 'POST':
        form = AnalyticsDashboardForm(request.POST)
        if form.is_valid():
            dashboard = form.save(commit=False)
            dashboard.created_by = request.user
            dashboard.save()
            form.save_m2m()
            messages.success(request, 'Дашборд успешно создан.')
            return redirect('reports:analytics_dashboard_list')
    else:
        form = AnalyticsDashboardForm()

    return render(request, 'reports/analytics_dashboard_form.html', {
        'form': form,
        'title': 'Создание дашборда'
    })


@login_required
@admin_required
def analytics_dashboard_edit(request, dashboard_id):
    """Редактирование дашборда аналитики"""
    dashboard = get_object_or_404(AnalyticsDashboard, id=dashboard_id, created_by=request.user)

    if request.method == 'POST':
        form = AnalyticsDashboardForm(request.POST, instance=dashboard)
        if form.is_valid():
            form.save()
            messages.success(request, 'Дашборд успешно обновлен.')
            return redirect('reports:analytics_dashboard_list')
    else:
        form = AnalyticsDashboardForm(instance=dashboard)

    return render(request, 'reports/analytics_dashboard_form.html', {
        'form': form,
        'title': 'Редактирование дашборда',
        'dashboard': dashboard
    })


@login_required
@admin_required
def analytics_dashboard_delete(request, dashboard_id):
    """Удаление дашборда аналитики"""
    dashboard = get_object_or_404(AnalyticsDashboard, id=dashboard_id, created_by=request.user)

    if request.method == 'POST':
        dashboard.delete()
        messages.success(request, 'Дашборд успешно удален.')
        return redirect('reports:analytics_dashboard_list')

    return render(request, 'reports/analytics_dashboard_confirm_delete.html', {
        'dashboard': dashboard
    })


# ============================================================================
# НОВЫЕ ПРЕДСТАВЛЕНИЯ: API ДЛЯ ДАННЫХ
# ============================================================================

@login_required
@employee_required
def api_report_data(request, report_type):
    """API для получения данных отчетов"""
    try:
        if report_type == 'clients':
            Client = get_client_model()
            data = list(Client.objects.values(
                'id', 'full_name', 'inn', 'credit_rating', 'is_vip', 'created_at'
            )[:100])

        elif report_type == 'credits':
            Credit = get_credit_model()
            data = list(Credit.objects.values(
                'id', 'client__full_name', 'amount', 'interest_rate',
                'term_months', 'status', 'start_date'
            )[:100])

        elif report_type == 'deposits':
            Deposit = get_deposit_model()
            data = list(Deposit.objects.values(
                'id', 'client__full_name', 'amount', 'interest_rate',
                'deposit_type', 'capitalization', 'status', 'start_date'
            )[:100])

        elif report_type == 'cards':
            Card = get_card_model()
            data = list(Card.objects.values(
                'id', 'cardholder_name', 'card_type', 'card_system',
                'status', 'daily_limit', 'expiry_date'
            )[:100])

        else:
            return JsonResponse({'error': 'Неизвестный тип отчета'}, status=400)

        return JsonResponse({'data': data})

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@employee_required
def api_dashboard_stats(request):
    """API для получения статистики дашборда"""
    try:
        Client = get_client_model()
        Account = get_account_model()
        Credit = get_credit_model()
        Deposit = get_deposit_model()
        Transaction = get_transaction_model()
        Card = get_card_model()

        stats = {
            'total_clients': Client.objects.count(),
            'total_accounts': Account.objects.filter(status='active').count(),
            'active_credits': Credit.objects.filter(status='active').count(),
            'active_deposits': Deposit.objects.filter(status='active').count(),
            'total_cards': Card.objects.count(),
            'active_cards': Card.objects.filter(status='active').count(),
        }

        financial_stats = {
            'total_balance': str(Account.objects.filter(status='active').aggregate(
                total=models.Sum('balance')
            )['total'] or Decimal('0')),
            'total_credit_amount': str(Credit.objects.filter(status='active').aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')),
            'total_deposit_amount': str(Deposit.objects.filter(status='active').aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0')),
        }

        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_stats = {
            'recent_transactions': Transaction.objects.filter(
                created_at__gte=thirty_days_ago
            ).count(),
            'recent_transaction_volume': str(Transaction.objects.filter(
                created_at__gte=thirty_days_ago
            ).aggregate(total=models.Sum('amount'))['total'] or Decimal('0')),
        }

        return JsonResponse({
            'basic_stats': stats,
            'financial_stats': financial_stats,
            'recent_stats': recent_stats
        })

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
@employee_required
def api_quick_export(request):
    """API для быстрого экспорта данных"""
    if request.method == 'POST':
        form = QuickExportForm(request.POST)
        if form.is_valid():
            data_types = form.cleaned_data['data_types']
            export_format = form.cleaned_data['format']

            # Создаем временный файл с данными
            import tempfile
            import zipfile

            temp_dir = tempfile.mkdtemp()
            zip_filename = os.path.join(temp_dir, f"export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.zip")

            with zipfile.ZipFile(zip_filename, 'w') as zip_file:
                for data_type in data_types:
                    data = get_export_data(data_type, request.user)
                    if data:
                        # Сохраняем каждый тип данных в отдельный файл
                        filename = f"{data_type}.{export_format}"
                        filepath = os.path.join(temp_dir, filename)

                        if export_format == 'json':
                            with open(filepath, 'w', encoding='utf-8') as f:
                                json.dump(data, f, ensure_ascii=False, indent=2)
                        elif export_format in ['csv', 'xlsx']:
                            with open(filepath, 'w', encoding='utf-8', newline='') as f:
                                writer = csv.writer(f)
                                if data:
                                    headers = list(data[0].keys())
                                    writer.writerow(headers)
                                    for item in data:
                                        writer.writerow([str(item.get(key, '')) for key in headers])

                        zip_file.write(filepath, filename)

            # Отправляем ZIP архив
            with open(zip_filename, 'rb') as f:
                response = HttpResponse(f.read(), content_type='application/zip')
                response[
                    'Content-Disposition'] = f'attachment; filename="export_{timezone.now().strftime("%Y%m%d_%H%M%S")}.zip"'

            # Очищаем временные файлы
            import shutil
            shutil.rmtree(temp_dir)

            return response

    return JsonResponse({'error': 'Неверный запрос'}, status=400)


# ============================================================================
# НОВЫЕ ПРЕДСТАВЛЕНИЯ: СИСТЕМА УВЕДОМЛЕНИЙ И МОНИТОРИНГА
# ============================================================================

@login_required
@employee_required
def report_generation_status(request):
    """Статус генерации отчетов"""
    reports = SavedReport.objects.filter(generated_by=request.user).order_by('-generated_at')[:10]

    pending_reports = reports.filter(generation_status='pending').count()
    processing_reports = reports.filter(generation_status='processing').count()
    failed_reports = reports.filter(generation_status='failed').count()

    return render(request, 'reports/report_generation_status.html', {
        'reports': reports,
        'pending_reports': pending_reports,
        'processing_reports': processing_reports,
        'failed_reports': failed_reports,
    })


@login_required
@admin_required
def system_health(request):
    """Мониторинг здоровья системы отчетности"""
    # Статистика по шаблонам
    total_templates = ReportTemplate.objects.count()
    active_templates = ReportTemplate.objects.filter(is_active=True).count()

    # Статистика по расписаниям
    total_schedules = ReportSchedule.objects.count()
    active_schedules = ReportSchedule.objects.filter(is_active=True).count()

    # Статистика по отчетам
    total_reports = SavedReport.objects.count()
    recent_reports = SavedReport.objects.filter(
        generated_at__gte=timezone.now() - timedelta(days=7)
    ).count()

    # Статистика по ошибкам
    failed_reports = SavedReport.objects.filter(generation_status='failed').count()

    # Использование дискового пространства
    total_file_size = SavedReport.objects.aggregate(total=models.Sum('file_size'))['total'] or 0

    return render(request, 'reports/system_health.html', {
        'total_templates': total_templates,
        'active_templates': active_templates,
        'total_schedules': total_schedules,
        'active_schedules': active_schedules,
        'total_reports': total_reports,
        'recent_reports': recent_reports,
        'failed_reports': failed_reports,
        'total_file_size': total_file_size,
        'total_file_size_mb': total_file_size / (1024 * 1024) if total_file_size else 0,
    })


@login_required
@employee_required
def generate_custom_report(request):
    """Генерация пользовательского отчета"""
    if request.method == 'POST':
        form = ReportGenerationForm(request.POST, user=request.user)
        if form.is_valid():
            # Здесь будет логика генерации отчета на основе параметров
            template_id = form.cleaned_data.get('template')
            format = form.cleaned_data.get('format')
            save_report = form.cleaned_data.get('save_report', True)

            if template_id:
                template = ReportTemplate.objects.get(id=template_id)
                messages.success(request, f'Отчет "{template.name}" будет сгенерирован в формате {format}.')
            else:
                messages.success(request, f'Пользовательский отчет будет сгенерирован в формате {format}.')

            # Временная заглушка - в реальной реализации здесь будет полная логика генерации
            return redirect('reports:report_dashboard')
    else:
        report_type = request.GET.get('report_type', 'financial')
        form = ReportGenerationForm(user=request.user, report_type=report_type)

    return render(request, 'reports/generate_custom_report.html', {
        'form': form,
    })