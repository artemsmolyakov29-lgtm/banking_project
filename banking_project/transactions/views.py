from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Sum, Count, Avg
from django.apps import apps
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.db import models
from django.core.paginator import Paginator
from django.views.decorators.http import require_POST, require_GET
import csv
import json
from datetime import datetime, timedelta
from decimal import Decimal
import traceback

# Импорт миксинов
try:
    from clients.mixins import ClientRequiredMixin, EmployeeOrAdminRequiredMixin, AdminRequiredMixin
except ImportError:
    # Создаем локальные версии миксинов
    from django.contrib.auth.mixins import UserPassesTestMixin
    from django.http import HttpResponseForbidden as Http403


    class ClientRequiredMixin(UserPassesTestMixin):
        def test_func(self):
            return self.request.user.is_authenticated

        def handle_no_permission(self):
            return Http403("Доступ запрещен")


    class EmployeeOrAdminRequiredMixin(UserPassesTestMixin):
        def test_func(self):
            return self.request.user.is_authenticated and self.request.user.role in ['employee', 'admin']

        def handle_no_permission(self):
            return Http403("Только сотрудники и администраторы имеют доступ к этой странице")


    class AdminRequiredMixin(UserPassesTestMixin):
        def test_func(self):
            return self.request.user.is_authenticated and self.request.user.role == 'admin'

        def handle_no_permission(self):
            return Http403("Только администраторы имеют доступ к этой странице")


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


def get_deposit_model():
    """Ленивая загрузка модели Deposit"""
    return apps.get_model('deposits', 'Deposit')


def get_credit_model():
    """Ленивая загрузка модели Credit"""
    return apps.get_model('credits', 'Credit')


def get_currency_model():
    """Ленивая загрузка модели Currency"""
    return apps.get_model('accounts', 'Currency')


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

    # Определяем доступные транзакции
    if request.user.role == 'client':
        # Клиенты видят только свои транзакции
        try:
            client = Client.objects.get(user=request.user)
            # Получаем счета клиента
            Account = get_account_model()
            client_accounts = Account.objects.filter(client=client)

            # Транзакции где клиент является отправителем или получателем
            transactions = Transaction.objects.filter(
                Q(from_account__in=client_accounts) | Q(to_account__in=client_accounts)
            ).distinct()
        except:
            transactions = Transaction.objects.none()
            messages.warning(request, 'Ваш профиль клиента еще не настроен.')
    else:
        # Сотрудники и админы видят все транзакции
        transactions = Transaction.objects.all()

    # Сортировка по умолчанию
    transactions = transactions.select_related(
        'from_account', 'to_account', 'currency', 'deposit', 'credit'
    ).order_by('-created_at')

    # Фильтрация по типу транзакции
    transaction_type = request.GET.get('type')
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    # Фильтрация по статусу
    status = request.GET.get('status')
    if status:
        transactions = transactions.filter(status=status)

    # Фильтрация по дате
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            transactions = transactions.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            transactions = transactions.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass

    # Поиск по номеру транзакции, описанию или номеру счета
    search_query = request.GET.get('search')
    if search_query:
        transactions = transactions.filter(
            Q(reference_number__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(from_account__account_number__icontains=search_query) |
            Q(to_account__account_number__icontains=search_query)
        )

    # Пагинация
    paginator = Paginator(transactions, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика
    total_transactions = transactions.count()
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_fee = transactions.aggregate(total=Sum('fee'))['total'] or Decimal('0.00')

    return render(request, 'transactions/transaction_list.html', {
        'page_obj': page_obj,
        'total_transactions': total_transactions,
        'total_amount': total_amount,
        'total_fee': total_fee,
        'transaction_type': transaction_type,
        'status': status,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'user_role': request.user.role
    })


@login_required
def transaction_detail(request, pk):
    """Детальная информация о транзакции"""
    Transaction = get_transaction_model()
    Client = get_client_model()

    transaction = get_object_or_404(Transaction, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            Account = get_account_model()
            client_accounts = Account.objects.filter(client=client)

            if (transaction.from_account not in client_accounts and
                    transaction.to_account not in client_accounts):
                messages.error(request, 'У вас нет доступа к этой транзакции')
                return redirect('transactions:transaction_list')
        except:
            messages.error(request, 'У вас нет доступа к этой транзакции')
            return redirect('transactions:transaction_list')

    return render(request, 'transactions/transaction_detail.html', {
        'transaction': transaction
    })


@login_required
@require_GET
def transaction_create(request):
    """Создание новой транзакции"""
    Client = get_client_model()
    Account = get_account_model()

    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            accounts = client.accounts.filter(status='active')
        except:
            accounts = Account.objects.none()
            messages.warning(request, 'У вас нет доступных счетов')
    else:
        accounts = Account.objects.filter(status='active')

    # Получаем типы транзакций
    Transaction = get_transaction_model()
    transaction_types = Transaction.TRANSACTION_TYPES if hasattr(Transaction, 'TRANSACTION_TYPES') else []

    return render(request, 'transactions/transaction_create.html', {
        'accounts': accounts,
        'transaction_types': transaction_types
    })


@login_required
@require_POST
def transaction_create_submit(request):
    """Обработка создания транзакции"""
    try:
        # Получаем данные из формы
        from_account_id = request.POST.get('from_account')
        to_account_id = request.POST.get('to_account')
        amount = request.POST.get('amount')
        transaction_type = request.POST.get('transaction_type', 'transfer')
        description = request.POST.get('description', '')
        currency_id = request.POST.get('currency')

        # Валидация
        if not amount or Decimal(amount) <= 0:
            messages.error(request, 'Некорректная сумма')
            return redirect('transactions:transaction_create')

        # Получаем модели
        Account = get_account_model()
        Transaction = get_transaction_model()
        Client = get_client_model()

        # Проверяем доступ для клиентов
        if request.user.role == 'client':
            try:
                client = Client.objects.get(user=request.user)
                client_accounts = Account.objects.filter(client=client)

                # Проверяем счет отправителя
                if from_account_id:
                    from_account = Account.objects.get(id=from_account_id)
                    if from_account not in client_accounts:
                        messages.error(request, 'У вас нет доступа к этому счету')
                        return redirect('transactions:transaction_create')

                # Проверяем счет получателя
                if to_account_id:
                    to_account = Account.objects.get(id=to_account_id)
                    if to_account not in client_accounts:
                        messages.error(request, 'У вас нет доступа к этому счету')
                        return redirect('transactions:transaction_create')
            except:
                messages.error(request, 'У вас нет доступа к этой операции')
                return redirect('transactions:transaction_create')

        # Создаем транзакцию
        transaction = Transaction.objects.create(
            from_account_id=from_account_id if from_account_id else None,
            to_account_id=to_account_id if to_account_id else None,
            amount=Decimal(amount),
            transaction_type=transaction_type,
            description=description,
            status='pending',  # По умолчанию ожидает обработки
            created_by=request.user,
            created_at=datetime.now()
        )

        # Если указана валюта
        if currency_id:
            try:
                Currency = get_currency_model()
                currency = Currency.objects.get(id=currency_id)
                transaction.currency = currency
                transaction.save()
            except:
                pass

        messages.success(request, f'Транзакция #{transaction.id} создана успешно')
        return redirect('transactions:transaction_detail', pk=transaction.pk)

    except Exception as e:
        messages.error(request, f'Ошибка при создании транзакции: {str(e)}')
        return redirect('transactions:transaction_create')


@login_required
@employee_required
def transaction_fees(request):
    """Тарифы комиссий за транзакции"""
    TransactionFee = get_transaction_fee_model()

    try:
        fees = TransactionFee.objects.filter(is_active=True).order_by('transaction_type', 'min_amount')
    except:
        fees = []
        messages.warning(request, 'Модель комиссий не найдена')

    return render(request, 'transactions/transaction_fees.html', {'fees': fees})


@login_required
def transaction_report(request):
    """Отчет по транзакциям"""
    User = get_user_model()
    Client = get_client_model()
    Transaction = get_transaction_model()

    # Параметры фильтрации по умолчанию
    default_date_from = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
    default_date_to = datetime.now().strftime('%Y-%m-%d')

    date_from = request.GET.get('date_from', default_date_from)
    date_to = request.GET.get('date_to', default_date_to)
    transaction_type = request.GET.get('transaction_type', '')

    # Определяем доступные транзакции
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            Account = get_account_model()
            accounts = Account.objects.filter(client=client)
            transactions = Transaction.objects.filter(
                Q(from_account__in=accounts) | Q(to_account__in=accounts),
                created_at__date__range=[date_from, date_to]
            ).distinct()
        except:
            transactions = Transaction.objects.none()
    else:
        transactions = Transaction.objects.filter(
            created_at__date__range=[date_from, date_to]
        )

    # Дополнительная фильтрация
    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    # Поиск
    search_query = request.GET.get('search')
    if search_query:
        transactions = transactions.filter(
            Q(reference_number__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Статистика
    total_count = transactions.count()
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_fee = transactions.aggregate(total=Sum('fee'))['total'] or Decimal('0.00')

    # Средние значения
    avg_amount = transactions.aggregate(avg=Avg('amount'))['avg'] or Decimal('0.00')
    avg_fee = transactions.aggregate(avg=Avg('fee'))['avg'] or Decimal('0.00')

    # Группировка по типам транзакций
    by_type = transactions.values('transaction_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        total_fee=Sum('fee'),
        avg_amount=Avg('amount')
    ).order_by('-total_amount')

    # Группировка по дням
    daily_stats = transactions.extra(
        select={'day': 'DATE(created_at)'}
    ).values('day').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        total_fee=Sum('fee')
    ).order_by('day')

    # Топ транзакций по сумме
    top_transactions = transactions.order_by('-amount')[:10]

    return render(request, 'transactions/transaction_report.html', {
        'transactions': transactions,
        'total_count': total_count,
        'total_amount': total_amount,
        'total_fee': total_fee,
        'avg_amount': avg_amount,
        'avg_fee': avg_fee,
        'by_type': by_type,
        'daily_stats': daily_stats,
        'top_transactions': top_transactions,
        'date_from': date_from,
        'date_to': date_to,
        'transaction_type': transaction_type,
        'search_query': search_query,
        'user_role': request.user.role
    })


@login_required
@employee_required
def export_transactions_csv(request):
    """Экспорт транзакций в CSV"""
    Transaction = get_transaction_model()

    # Параметры фильтрации
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))
    transaction_type = request.GET.get('transaction_type', '')

    # Фильтрация
    transactions = Transaction.objects.filter(
        created_at__date__range=[date_from, date_to]
    ).select_related('from_account', 'to_account', 'currency', 'deposit', 'credit')

    if transaction_type:
        transactions = transactions.filter(transaction_type=transaction_type)

    # Создаем CSV
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="transactions_{date_from}_{date_to}.csv"'

    # Пишем BOM для корректного отображения кириллицы в Excel
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')

    # Заголовки
    writer.writerow([
        'ID', 'Дата и время', 'Тип транзакции', 'Статус',
        'Счет отправителя', 'Счет получателя', 'Сумма', 'Валюта',
        'Комиссия', 'Описание', 'Номер транзакции',
        'Депозит', 'Кредит', 'Создал'
    ])

    # Данные
    for transaction in transactions:
        writer.writerow([
            transaction.id,
            transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            transaction.get_transaction_type_display(),
            transaction.get_status_display(),
            transaction.from_account.account_number if transaction.from_account else '',
            transaction.to_account.account_number if transaction.to_account else '',
            str(transaction.amount),
            transaction.currency.code if transaction.currency else '',
            str(transaction.fee),
            transaction.description,
            transaction.reference_number,
            transaction.deposit.id if transaction.deposit else '',
            transaction.credit.id if transaction.credit else '',
            transaction.created_by.username if transaction.created_by else ''
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
    ).select_related('from_account', 'to_account', 'currency', 'deposit', 'credit')

    data = []
    for transaction in transactions:
        data.append({
            'id': transaction.id,
            'date': transaction.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'transaction_type': transaction.transaction_type,
            'transaction_type_display': transaction.get_transaction_type_display(),
            'status': transaction.status,
            'status_display': transaction.get_status_display(),
            'from_account': {
                'id': transaction.from_account.id if transaction.from_account else None,
                'number': transaction.from_account.account_number if transaction.from_account else None,
                'client': transaction.from_account.client.full_name if transaction.from_account and transaction.from_account.client else None
            } if transaction.from_account else None,
            'to_account': {
                'id': transaction.to_account.id if transaction.to_account else None,
                'number': transaction.to_account.account_number if transaction.to_account else None,
                'client': transaction.to_account.client.full_name if transaction.to_account and transaction.to_account.client else None
            } if transaction.to_account else None,
            'amount': str(transaction.amount),
            'currency': {
                'code': transaction.currency.code if transaction.currency else None,
                'name': transaction.currency.name if transaction.currency else None
            },
            'fee': str(transaction.fee),
            'description': transaction.description,
            'reference_number': transaction.reference_number,
            'deposit_id': transaction.deposit.id if transaction.deposit else None,
            'credit_id': transaction.credit.id if transaction.credit else None,
            'created_by': transaction.created_by.username if transaction.created_by else None
        })

    response = JsonResponse(data, safe=False, json_dumps_params={'ensure_ascii': False, 'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="transactions_{date_from}_{date_to}.json"'
    return response


@login_required
def transfer_view(request):
    """Представление для перевода между счетами"""
    Client = get_client_model()
    Account = get_account_model()

    # Получаем доступные счета
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            user_accounts = Account.objects.filter(client=client, status='active')
        except:
            user_accounts = Account.objects.none()
            messages.warning(request, 'У вас нет доступных счетов')
    else:
        user_accounts = Account.objects.filter(status='active')[:50]  # Ограничиваем для сотрудников

    if request.method == 'POST':
        try:
            from_account_id = request.POST.get('from_account')
            to_account_id = request.POST.get('to_account')
            amount = request.POST.get('amount')
            description = request.POST.get('description', 'Перевод между счетами')

            # Валидация
            if not from_account_id or not to_account_id or not amount:
                messages.error(request, 'Заполните все обязательные поля')
                return redirect('transactions:transfer')

            from_account = Account.objects.get(id=from_account_id)
            to_account = Account.objects.get(id=to_account_id)
            amount_decimal = Decimal(amount)

            # Проверка прав доступа для клиентов
            if request.user.role == 'client':
                try:
                    client = Client.objects.get(user=request.user)
                    client_accounts = Account.objects.filter(client=client)

                    if from_account not in client_accounts:
                        messages.error(request, 'У вас нет доступа к счету отправителя')
                        return redirect('transactions:transfer')

                    if to_account not in client_accounts:
                        messages.error(request, 'У вас нет доступа к счету получателя')
                        return redirect('transactions:transfer')
                except:
                    messages.error(request, 'У вас нет доступа к этой операции')
                    return redirect('transactions:transfer')

            # Проверка суммы
            if amount_decimal <= 0:
                messages.error(request, 'Сумма должна быть положительной')
                return redirect('transactions:transfer')

            if from_account.balance < amount_decimal:
                messages.error(request, 'Недостаточно средств на счете отправителя')
                return redirect('transactions:transfer')

            # Проверка валюты
            if from_account.currency != to_account.currency:
                messages.error(request, 'Перевод возможен только между счетами в одной валюте')
                return redirect('transactions:transfer')

            # Создаем транзакцию
            Transaction = get_transaction_model()
            transaction = Transaction.objects.create(
                from_account=from_account,
                to_account=to_account,
                amount=amount_decimal,
                currency=from_account.currency,
                transaction_type='transfer',
                status='completed',
                description=description,
                created_by=request.user,
                created_at=datetime.now()
            )

            # Обновляем балансы
            from_account.balance -= amount_decimal
            from_account.save()

            to_account.balance += amount_decimal
            to_account.save()

            messages.success(request,
                             f'Перевод на сумму {amount_decimal} {from_account.currency.code} выполнен успешно!')
            return redirect('transactions:transfer_success', transaction_id=transaction.id)

        except Account.DoesNotExist:
            messages.error(request, 'Один из счетов не найден')
        except ValueError:
            messages.error(request, 'Неверный формат суммы')
        except Exception as e:
            messages.error(request, f'Ошибка при выполнении перевода: {str(e)}')
            print(traceback.format_exc())

    return render(request, 'transactions/transfer.html', {
        'user_accounts': user_accounts
    })


@login_required
def transfer_success(request, transaction_id):
    """Страница успешного перевода"""
    Transaction = get_transaction_model()
    Client = get_client_model()

    transaction = get_object_or_404(Transaction, id=transaction_id)

    # Проверяем права доступа
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            Account = get_account_model()
            client_accounts = Account.objects.filter(client=client)

            if (transaction.from_account not in client_accounts and
                    transaction.to_account not in client_accounts):
                messages.error(request, 'У вас нет доступа к этой транзакции')
                return redirect('transactions:transaction_list')
        except:
            messages.error(request, 'У вас нет доступа к этой транзакции')
            return redirect('transactions:transaction_list')

    return render(request, 'transactions/transfer_success.html', {
        'transaction': transaction
    })


@login_required
def transaction_history(request):
    """История транзакций пользователя"""
    Transaction = get_transaction_model()
    Client = get_client_model()

    # Определяем доступные транзакции
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            Account = get_account_model()
            accounts = Account.objects.filter(client=client)
            transactions = Transaction.objects.filter(
                Q(from_account__in=accounts) | Q(to_account__in=accounts)
            ).select_related('from_account', 'to_account', 'currency').order_by('-created_at')
        except:
            transactions = Transaction.objects.none()
            messages.warning(request, 'Ваш профиль клиента еще не настроен.')
    else:
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
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d')
            transactions = transactions.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d')
            transactions = transactions.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass

    # Поиск
    search_query = request.GET.get('search')
    if search_query:
        transactions = transactions.filter(
            Q(description__icontains=search_query) |
            Q(reference_number__icontains=search_query)
        )

    # Статистика
    total_count = transactions.count()
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

    # Пагинация
    paginator = Paginator(transactions, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Получаем типы транзакций для фильтра
    try:
        transaction_types = Transaction.TRANSACTION_TYPES
    except:
        transaction_types = []

    return render(request, 'transactions/history.html', {
        'page_obj': page_obj,
        'transactions_count': total_count,
        'total_amount': total_amount,
        'transaction_type': transaction_type,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'transaction_types': transaction_types,
        'user_role': request.user.role
    })


@login_required
@employee_required
def deposit_interest_report(request):
    """Отчет по начислениям процентов по депозитам"""
    Transaction = get_transaction_model()
    Deposit = get_deposit_model()

    # Параметры фильтрации
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))
    deposit_id = request.GET.get('deposit_id')

    # Транзакции начисления процентов
    interest_types = ['deposit_interest', 'interest_accrual', 'interest']
    interest_transactions = Transaction.objects.filter(
        transaction_type__in=interest_types,
        created_at__date__range=[date_from, date_to]
    ).select_related('deposit', 'deposit__client', 'to_account', 'currency')

    if deposit_id:
        interest_transactions = interest_transactions.filter(deposit_id=deposit_id)

    # Статистика
    total_interest = interest_transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    transaction_count = interest_transactions.count()

    # Группировка по депозитам
    by_deposit = interest_transactions.values(
        'deposit_id',
        'deposit__client__full_name',
        'currency__code'
    ).annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        avg_amount=Avg('amount')
    ).order_by('-total_amount')

    # Список депозитов для фильтра
    deposits = Deposit.objects.filter(status='active').select_related('client')[:50]

    return render(request, 'transactions/deposit_interest_report.html', {
        'interest_transactions': interest_transactions,
        'total_interest': total_interest,
        'transaction_count': transaction_count,
        'by_deposit': by_deposit,
        'deposits': deposits,
        'date_from': date_from,
        'date_to': date_to,
        'deposit_id': deposit_id
    })


@login_required
def transaction_statistics(request):
    """Статистика по транзакциям"""
    Transaction = get_transaction_model()
    Client = get_client_model()

    # Определяем доступные транзакции
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            Account = get_account_model()
            accounts = Account.objects.filter(client=client)
            transactions = Transaction.objects.filter(
                Q(from_account__in=accounts) | Q(to_account__in=accounts)
            )
        except:
            transactions = Transaction.objects.none()
    else:
        transactions = Transaction.objects.all()

    # Общая статистика
    total_count = transactions.count()
    total_amount = transactions.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    total_fee = transactions.aggregate(total=Sum('fee'))['total'] or Decimal('0.00')

    # Статистика по типам
    type_stats = transactions.values('transaction_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        total_fee=Sum('fee'),
        avg_amount=Avg('amount')
    ).order_by('-total_amount')

    # Статистика по статусам
    status_stats = transactions.values('status').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('status')

    # Ежемесячная статистика
    monthly_stats = transactions.extra(
        select={'month': "DATE_TRUNC('month', created_at)"}
    ).values('month').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        total_fee=Sum('fee')
    ).order_by('month')

    # Топ транзакций
    top_transactions = transactions.order_by('-amount')[:5]

    return render(request, 'transactions/transaction_statistics.html', {
        'total_count': total_count,
        'total_amount': total_amount,
        'total_fee': total_fee,
        'type_stats': type_stats,
        'status_stats': status_stats,
        'monthly_stats': monthly_stats,
        'top_transactions': top_transactions,
        'user_role': request.user.role
    })


@login_required
@employee_required
def process_pending_transactions(request):
    """Обработка ожидающих транзакций"""
    Transaction = get_transaction_model()

    if request.method == 'POST':
        transaction_ids = request.POST.getlist('transaction_ids')
        action = request.POST.get('action')

        if not transaction_ids:
            messages.error(request, 'Не выбраны транзакции для обработки')
            return redirect('transactions:transaction_list')

        transactions = Transaction.objects.filter(id__in=transaction_ids, status='pending')

        if action == 'approve':
            count = 0
            for transaction in transactions:
                try:
                    # Проверяем баланс для исходящих транзакций
                    if transaction.from_account and transaction.from_account.balance < transaction.amount:
                        messages.warning(request, f'Транзакция #{transaction.id}: недостаточно средств')
                        continue

                    # Обновляем балансы
                    if transaction.from_account:
                        transaction.from_account.balance -= transaction.amount
                        transaction.from_account.save()

                    if transaction.to_account:
                        transaction.to_account.balance += transaction.amount
                        transaction.to_account.save()

                    transaction.status = 'completed'
                    transaction.processed_by = request.user
                    transaction.processed_at = datetime.now()
                    transaction.save()
                    count += 1
                except Exception as e:
                    messages.error(request, f'Ошибка при обработке транзакции #{transaction.id}: {str(e)}')

            messages.success(request, f'Одобрено {count} транзакций')

        elif action == 'reject':
            count = transactions.update(
                status='rejected',
                processed_by=request.user,
                processed_at=datetime.now()
            )
            messages.success(request, f'Отклонено {count} транзакций')

        elif action == 'cancel':
            count = transactions.update(
                status='cancelled',
                processed_by=request.user,
                processed_at=datetime.now()
            )
            messages.success(request, f'Отменено {count} транзакций')

    return redirect('transactions:transaction_list')


@login_required
@admin_required
def transaction_settings(request):
    """Настройки транзакций"""
    if request.method == 'POST':
        # Обработка сохранения настроек
        messages.success(request, 'Настройки успешно сохранены')
        return redirect('transactions:transaction_settings')

    return render(request, 'transactions/transaction_settings.html')


@login_required
def transaction_chart_data(request):
    """Данные для графиков транзакций (JSON API)"""
    Transaction = get_transaction_model()
    Client = get_client_model()

    # Определяем доступные транзакции
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            Account = get_account_model()
            accounts = Account.objects.filter(client=client)
            transactions = Transaction.objects.filter(
                Q(from_account__in=accounts) | Q(to_account__in=accounts)
            )
        except:
            transactions = Transaction.objects.none()
    else:
        transactions = Transaction.objects.all()

    # Фильтрация по дате
    days = int(request.GET.get('days', 30))
    date_from = datetime.now() - timedelta(days=days)
    transactions = transactions.filter(created_at__gte=date_from)

    # Данные для графика по дням
    daily_data = transactions.extra(
        select={'day': 'DATE(created_at)'}
    ).values('day').annotate(
        count=Count('id'),
        total_amount=Sum('amount'),
        total_fee=Sum('fee')
    ).order_by('day')

    # Данные для графика по типам
    type_data = transactions.values('transaction_type').annotate(
        count=Count('id'),
        total_amount=Sum('amount')
    ).order_by('-total_amount')

    # Данные для графика по статусам
    status_data = transactions.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    data = {
        'daily_data': list(daily_data),
        'type_data': list(type_data),
        'status_data': list(status_data),
    }

    return JsonResponse(data, safe=False)