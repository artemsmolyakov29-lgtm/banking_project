from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.apps import apps
from django.http import HttpResponseForbidden, HttpResponse
from django.db import models
import csv
import json
from datetime import datetime, timedelta


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_transaction_model():
    """Ленивая загрузка модели Transaction"""
    return apps.get_model('transactions', 'Transaction')


def get_transaction_fee_model():
    """Ленивая загрузка модели TransactionFee"""
    return apps.get_model('transactions', 'TransactionFee')


def get_account_model():
    """Ленивая загрузка модели Account"""
    return apps.get_model('accounts', 'Account')


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


@login_required
def transaction_list(request):
    """Список транзакций"""
    User = get_user_model()
    Client = get_client_model()
    Transaction = get_transaction_model()

    if request.user.role == 'client':
        # Клиенты видят только свои транзакции
        client = get_object_or_404(Client, user=request.user)
        # Транзакции где клиент является отправителем или получателем
        accounts = client.accounts.all()
        transactions = Transaction.objects.filter(
            Q(from_account__in=accounts) | Q(to_account__in=accounts)
        ).distinct().order_by('-created_at')
    else:
        # Сотрудники и админы видят все транзакции
        transactions = Transaction.objects.all().order_by('-created_at')

    # Фильтрация по типу транзакции
    transaction_type = request.GET.get('type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    # Фильтрация по дате
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)

    return render(request, 'transactions/transaction_list.html', {
        'transactions': transactions,
        'transaction_type': transaction_type,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
def transaction_detail(request, pk):
    """Детальная информация о транзакции"""
    Transaction = get_transaction_model()
    Client = get_client_model()
    User = get_user_model()

    transaction = get_object_or_404(Transaction, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client':
        client = get_object_or_404(Client, user=request.user)
        client_accounts = client.accounts.all()
        if (transaction.from_account not in client_accounts and
                transaction.to_account not in client_accounts):
            messages.error(request, 'У вас нет доступа к этой транзакции')
            return redirect('transactions:transaction_list')

    return render(request, 'transactions/transaction_detail.html', {
        'transaction': transaction
    })


@login_required
def transaction_create(request):
    """Создание новой транзакции"""
    Client = get_client_model()
    Account = get_account_model()

    if request.user.role == 'client':
        client = get_object_or_404(Client, user=request.user)
        accounts = client.accounts.filter(status='active')
    else:
        accounts = Account.objects.filter(status='active')

    if request.method == 'POST':
        # Здесь будет логика создания транзакции
        from_account_id = request.POST.get('from_account')
        to_account_id = request.POST.get('to_account')
        amount = request.POST.get('amount')
        description = request.POST.get('description', '')

        # Валидация и создание транзакции
        try:
            from_account = Account.objects.get(id=from_account_id) if from_account_id else None
            to_account = Account.objects.get(id=to_account_id)

            # Проверка прав доступа для клиентов
            if request.user.role == 'client':
                client_accounts = client.accounts.all()
                if from_account and from_account not in client_accounts:
                    messages.error(request, 'У вас нет доступа к счету отправителя')
                    return redirect('transactions:transaction_create')
                if to_account not in client_accounts:
                    messages.error(request, 'У вас нет доступа к счету получателя')
                    return redirect('transactions:transaction_create')

            # Здесь будет вызов метода execute_transaction
            messages.success(request, 'Транзакция успешно создана')
            return redirect('transactions:transaction_list')

        except Account.DoesNotExist:
            messages.error(request, 'Один из счетов не найден')
        except Exception as e:
            messages.error(request, f'Ошибка при создании транзакции: {str(e)}')

    return render(request, 'transactions/transaction_create.html', {
        'accounts': accounts
    })


@login_required
@employee_required
def transaction_fees(request):
    """Тарифы комиссий за транзакции"""
    TransactionFee = get_transaction_fee_model()
    fees = TransactionFee.objects.filter(is_active=True)
    return render(request, 'transactions/transaction_fees.html', {'fees': fees})


@login_required
def transaction_report(request):
    """Отчет по транзакциям"""
    User = get_user_model()
    Client = get_client_model()
    Transaction = get_transaction_model()

    # Параметры фильтрации
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))
    transaction_type = request.GET.get('transaction_type', '')

    if request.user.role == 'client':
        client = get_object_or_404(Client, user=request.user)
        accounts = client.accounts.all()
        transactions = Transaction.objects.filter(
            Q(from_account__in=accounts) | Q(to_account__in=accounts),
            created_at__date__range=[date_from, date_to]
        ).distinct()
    else:
        transactions = Transaction.objects.filter(
            created_at__date__range=[date_from, date_to]
        )

    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    # Статистика
    total_count = transactions.count()
    total_amount = sum(t.amount for t in transactions)
    total_fee = sum(t.fee for t in transactions)

    # Группировка по типам транзакций
    by_type = transactions.values('transaction_type').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount'),
        total_fee=models.Sum('fee')
    )

    return render(request, 'transactions/transaction_report.html', {
        'transactions': transactions,
        'total_count': total_count,
        'total_amount': total_amount,
        'total_fee': total_fee,
        'by_type': by_type,
        'date_from': date_from,
        'date_to': date_to,
        'transaction_type': transaction_type
    })


@login_required
@employee_required
def export_transactions_csv(request):
    """Экспорт транзакций в CSV"""
    Transaction = get_transaction_model()

    # Фильтрация (аналогично transaction_report)
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))

    transactions = Transaction.objects.filter(
        created_at__date__range=[date_from, date_to]
    )

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="transactions_{date_from}_{date_to}.csv"'

    writer = csv.writer(response)
    writer.writerow(['ID', 'Дата', 'От счета', 'На счет', 'Сумма', 'Комиссия', 'Тип', 'Статус', 'Описание'])

    for transaction in transactions:
        writer.writerow([
            transaction.id,
            transaction.created_at.strftime('%Y-%m-%d %H:%M'),
            transaction.from_account.account_number if transaction.from_account else '-',
            transaction.to_account.account_number,
            transaction.amount,
            transaction.fee,
            transaction.get_transaction_type_display(),
            transaction.get_status_display(),
            transaction.description
        ])

    return response


@login_required
@employee_required
def export_transactions_json(request):
    """Экспорт транзакций в JSON"""
    Transaction = get_transaction_model()

    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))

    transactions = Transaction.objects.filter(
        created_at__date__range=[date_from, date_to]
    )

    data = []
    for transaction in transactions:
        data.append({
            'id': transaction.id,
            'date': transaction.created_at.strftime('%Y-%m-%d %H:%M'),
            'from_account': transaction.from_account.account_number if transaction.from_account else None,
            'to_account': transaction.to_account.account_number,
            'amount': str(transaction.amount),
            'fee': str(transaction.fee),
            'type': transaction.transaction_type,
            'type_display': transaction.get_transaction_type_display(),
            'status': transaction.status,
            'status_display': transaction.get_status_display(),
            'description': transaction.description,
            'reference_number': transaction.reference_number
        })

    response = HttpResponse(json.dumps(data, ensure_ascii=False), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="transactions_{date_from}_{date_to}.json"'
    return response