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
from django.core.paginator import Paginator
from .forms import TransferForm
from decimal import Decimal


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

    # Поиск по номеру транзакции или описанию
    search_query = request.GET.get('search')
    if search_query:
        transactions = transactions.filter(
            Q(reference_number__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Пагинация
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'transactions/transaction_list.html', {
        'page_obj': page_obj,
        'transaction_type': transaction_type,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query
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
    total_amount = transactions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    total_fee = transactions.aggregate(total=models.Sum('fee'))['total'] or Decimal('0.00')

    # Группировка по типам транзакций
    by_type = transactions.values('transaction_type').annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount'),
        total_fee=models.Sum('fee')
    )

    # НОВАЯ СТАТИСТИКА: Начисления процентов по депозитам
    deposit_interest_transactions = transactions.filter(
        transaction_type__in=['deposit_interest', 'interest_accrual']
    )
    total_deposit_interest = deposit_interest_transactions.aggregate(
        total=models.Sum('amount')
    )['total'] or Decimal('0.00')

    return render(request, 'transactions/transaction_report.html', {
        'transactions': transactions,
        'total_count': total_count,
        'total_amount': total_amount,
        'total_fee': total_fee,
        'total_deposit_interest': total_deposit_interest,  # НОВАЯ СТАТИСТИКА
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
            'reference_number': transaction.reference_number,
            'deposit_id': transaction.deposit.id if transaction.deposit else None,  # НОВОЕ ПОЛЕ
            'credit_id': transaction.credit.id if transaction.credit else None,  # НОВОЕ ПОЛЕ
        })

    response = HttpResponse(json.dumps(data, ensure_ascii=False), content_type='application/json')
    response['Content-Disposition'] = f'attachment; filename="transactions_{date_from}_{date_to}.json"'
    return response


# НОВЫЕ ПРЕДСТАВЛЕНИЯ ДЛЯ ПЕРЕВОДОВ МЕЖДУ СЧЕТАМИ

@login_required
def transfer_view(request):
    """Представление для перевода между счетами"""
    if request.method == 'POST':
        form = TransferForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                transaction = form.save()
                messages.success(request,
                                 f'Перевод на сумму {transaction.amount} выполнен успешно! Комиссия: {transaction.fee}')
                return redirect('transactions:transfer_success', transaction_id=transaction.id)
            except Exception as e:
                messages.error(request, f'Ошибка при выполнении перевода: {str(e)}')
    else:
        form = TransferForm(user=request.user)

    # Получаем счета пользователя для автозаполнения (для клиентов)
    Account = get_account_model()
    if request.user.role == 'client':
        user_accounts = Account.objects.filter(client__user=request.user, status='active')
    else:
        user_accounts = Account.objects.filter(status='active')[:10]  # Ограничим для сотрудников

    return render(request, 'transactions/transfer.html', {
        'form': form,
        'user_accounts': user_accounts
    })


@login_required
def transfer_success(request, transaction_id):
    """Страница успешного перевода"""
    Transaction = get_transaction_model()
    transaction = get_object_or_404(Transaction, id=transaction_id)

    # Проверяем права доступа
    if request.user.role == 'client':
        Client = get_client_model()
        client = get_object_or_404(Client, user=request.user)
        client_accounts = client.accounts.all()
        if (transaction.from_account not in client_accounts and
                transaction.to_account not in client_accounts):
            messages.error(request, 'У вас нет доступа к этой транзакции')
            return redirect('transactions:transaction_list')

    return render(request, 'transactions/transfer_success.html', {
        'transaction': transaction
    })


@login_required
def transaction_history(request):
    """История транзакций пользователя (специализированная для клиентов)"""
    Transaction = get_transaction_model()
    Client = get_client_model()

    # Для клиентов показываем только их транзакции
    if request.user.role == 'client':
        client = get_object_or_404(Client, user=request.user)
        accounts = client.accounts.all()
        transactions = Transaction.objects.filter(
            Q(from_account__in=accounts) | Q(to_account__in=accounts)
        ).select_related('from_account', 'to_account', 'currency').order_by('-created_at')
    else:
        # Для сотрудников и админов - все транзакции
        transactions = Transaction.objects.all().select_related(
            'from_account', 'to_account', 'currency'
        ).order_by('-created_at')

    # Фильтрация
    transaction_type = request.GET.get('type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        transactions = transactions.filter(created_at__date__gte=date_from)
    if date_to:
        transactions = transactions.filter(created_at__date__lte=date_to)

    # Пагинация
    paginator = Paginator(transactions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Получаем типы транзакций для фильтра
    transaction_types = Transaction.TRANSACTION_TYPES

    return render(request, 'transactions/history.html', {
        'page_obj': page_obj,
        'transactions_count': transactions.count(),
        'transaction_type': transaction_type,
        'date_from': date_from,
        'date_to': date_to,
        'transaction_types': transaction_types
    })


# НОВОЕ ПРЕДСТАВЛЕНИЕ: Отчет по начислениям процентов
@login_required
@employee_required
def deposit_interest_report(request):
    """Отчет по начислениям процентов по депозитам"""
    Transaction = get_transaction_model()

    # Фильтрация
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))
    deposit_id = request.GET.get('deposit_id')

    # Транзакции начисления процентов
    interest_transactions = Transaction.objects.filter(
        transaction_type__in=['deposit_interest', 'interest_accrual'],
        created_at__date__range=[date_from, date_to]
    ).select_related('deposit', 'deposit__client', 'to_account', 'currency')

    if deposit_id:
        interest_transactions = interest_transactions.filter(deposit_id=deposit_id)

    # Статистика
    total_interest = interest_transactions.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')
    transaction_count = interest_transactions.count()

    # Группировка по депозитам
    by_deposit = interest_transactions.values(
        'deposit_id',
        'deposit__client__full_name',
        'currency__code'
    ).annotate(
        count=models.Count('id'),
        total_amount=models.Sum('amount')
    )

    return render(request, 'transactions/deposit_interest_report.html', {
        'interest_transactions': interest_transactions,
        'total_interest': total_interest,
        'transaction_count': transaction_count,
        'by_deposit': by_deposit,
        'date_from': date_from,
        'date_to': date_to,
        'deposit_id': deposit_id
    })