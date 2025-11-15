from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.http import HttpResponse, HttpResponseForbidden
from django.db import models
import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal


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


@login_required
@employee_required
def report_dashboard(request):
    """Дашборд отчетности"""
    Client = get_client_model()
    Account = get_account_model()
    Credit = get_credit_model()
    Deposit = get_deposit_model()
    Transaction = get_transaction_model()

    # Базовая статистика
    total_clients = Client.objects.count()
    total_accounts = Account.objects.filter(status='active').count()
    active_credits = Credit.objects.filter(status='active').count()
    active_deposits = Deposit.objects.filter(status='active').count()

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

    # Статистика за последние 30 дней
    thirty_days_ago = datetime.now() - timedelta(days=30)
    recent_transactions = Transaction.objects.filter(
        created_at__gte=thirty_days_ago
    )
    transaction_volume = recent_transactions.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0')

    return render(request, 'reports/report_dashboard.html', {
        'total_clients': total_clients,
        'total_accounts': total_accounts,
        'active_credits': active_credits,
        'active_deposits': active_deposits,
        'total_balance': total_balance,
        'total_credit_amount': total_credit_amount,
        'total_deposit_amount': total_deposit_amount,
        'transaction_volume': transaction_volume,
        'recent_transactions_count': recent_transactions.count()
    })


@login_required
@employee_required
def client_report(request):
    """Отчет по клиентам"""
    Client = get_client_model()

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

    # Статистика
    vip_count = Client.objects.filter(is_vip=True).count()
    avg_rating = clients.aggregate(avg=models.Avg('credit_rating'))['avg'] or 0

    return render(request, 'reports/client_report.html', {
        'clients': clients,
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

    deposits = Deposit.objects.all()

    if status:
        deposits = deposits.filter(status=status)
    if deposit_type:
        deposits = deposits.filter(deposit_type=deposit_type)

    # Статистика
    total_amount = deposits.aggregate(total=models.Sum('amount'))['total'] or Decimal('0')
    avg_interest = deposits.aggregate(avg=models.Avg('interest_rate'))['avg'] or 0

    # Группировка по типам
    by_type = Deposit.objects.values('deposit_type').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount'),
        avg_interest=models.Avg('interest_rate')
    )

    return render(request, 'reports/deposit_report.html', {
        'deposits': deposits,
        'total_amount': total_amount,
        'avg_interest': avg_interest,
        'by_type': by_type,
        'status': status,
        'deposit_type': deposit_type
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

    # Доходы (комиссии за период)
    transaction_fees = Transaction.objects.filter(
        created_at__date__range=[date_from, date_to]
    ).aggregate(total_fee=models.Sum('fee'))['total_fee'] or Decimal('0')

    # Процентные доходы (упрощенно)
    interest_income = Credit.objects.filter(
        status='active'
    ).aggregate(total_interest=models.Sum('interest_amount'))['total_interest'] or Decimal('0')

    return render(request, 'reports/financial_report.html', {
        'total_assets': total_assets,
        'credit_portfolio': credit_portfolio,
        'deposit_portfolio': deposit_portfolio,
        'transaction_fees': transaction_fees,
        'interest_income': interest_income,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
@employee_required
def export_json(request):
    """Экспорт данных в JSON"""
    data_type = request.GET.get('type', 'clients')

    if data_type == 'clients':
        Client = get_client_model()
        data = list(Client.objects.values())
        filename = 'clients_export.json'
    elif data_type == 'credits':
        Credit = get_credit_model()
        data = list(Credit.objects.values())
        filename = 'credits_export.json'
    elif data_type == 'deposits':
        Deposit = get_deposit_model()
        data = list(Deposit.objects.values())
        filename = 'deposits_export.json'
    else:
        messages.error(request, 'Неподдерживаемый тип данных для экспорта')
        return redirect('reports:report_dashboard')

    response = HttpResponse(json.dumps(data, ensure_ascii=False), content_type='application/json')
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
    else:
        messages.error(request, 'Неподдерживаемый тип данных для экспорта')
        return redirect('reports:report_dashboard')

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'

    writer = csv.writer(response)

    # Заголовки (зависит от типа данных)
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
        writer.writerow(['ID', 'Клиент', 'Сумма', 'Процентная ставка', 'Тип', 'Статус', 'Дата открытия'])
        for item in data:
            writer.writerow([
                item.id, item.client.full_name, item.amount, item.interest_rate,
                item.get_deposit_type_display(), item.get_status_display(),
                item.start_date.strftime('%Y-%m-%d')
            ])

    return response


@login_required
@employee_required
def export_excel(request):
    """Экспорт данных в Excel"""
    # Для простоты реализуем как CSV, но с другим content-type
    # В реальном проекте можно использовать openpyxl или xlwt
    return export_csv(request)


@login_required
@employee_required
def export_pdf(request):
    """Экспорт данных в PDF"""
    # Заглушка для PDF экспорта
    # В реальном проекте можно использовать reportlab или weasyprint
    messages.info(request, 'PDF экспорт будет реализован в следующей версии')
    return redirect('reports:report_dashboard')