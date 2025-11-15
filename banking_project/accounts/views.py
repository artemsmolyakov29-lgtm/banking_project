from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_account_model():
    """Ленивая загрузка модели Account"""
    return apps.get_model('accounts', 'Account')


def get_currency_model():
    """Ленивая загрузка модели Currency"""
    return apps.get_model('accounts', 'Currency')


# Локальная версия декоратора
def role_required(allowed_roles):
    from django.http import HttpResponseForbidden
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


@login_required
def account_list(request):
    """Список счетов"""
    User = get_user_model()
    Client = get_client_model()
    Account = get_account_model()

    if request.user.role == 'client':
        # Клиенты видят только свои счета
        client = get_object_or_404(Client, user=request.user)
        accounts = client.accounts.all()
    else:
        # Сотрудники и админы видят все счета
        accounts = Account.objects.all()

    return render(request, 'accounts/account_list.html', {'accounts': accounts})


@login_required
def account_detail(request, pk):
    """Детальная информация о счете"""
    Account = get_account_model()
    Client = get_client_model()
    User = get_user_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому счету')
        return redirect('accounts:account_list')

    return render(request, 'accounts/account_detail.html', {'account': account})


@login_required
@role_required(['employee', 'admin'])
def account_create(request):
    """Создание нового счета"""
    if request.method == 'POST':
        # Здесь будет логика создания счета
        messages.success(request, 'Счет успешно создан')
        return redirect('accounts:account_list')
    return render(request, 'accounts/account_form.html')


@login_required
@role_required(['employee', 'admin'])
def account_update(request, pk):
    """Редактирование счета"""
    Account = get_account_model()
    account = get_object_or_404(Account, pk=pk)

    if request.method == 'POST':
        # Здесь будет логика обновления счета
        messages.success(request, 'Счет успешно обновлен')
        return redirect('accounts:account_detail', pk=account.pk)
    return render(request, 'accounts/account_form.html', {'account': account})


@login_required
@role_required(['employee', 'admin'])
def account_close(request, pk):
    """Закрытие счета"""
    Account = get_account_model()
    account = get_object_or_404(Account, pk=pk)

    if request.method == 'POST':
        account.status = 'closed'
        account.save()
        messages.success(request, 'Счет успешно закрыт')
        return redirect('accounts:account_list')
    return render(request, 'accounts/account_confirm_close.html', {'account': account})


@login_required
def account_transactions(request, pk):
    """Транзакции по счету"""
    Account = get_account_model()
    Client = get_client_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к транзакциям этого счета')
        return redirect('accounts:account_list')

    # Здесь будет логика получения транзакций
    transactions = []
    return render(request, 'accounts/account_transactions.html', {
        'account': account,
        'transactions': transactions
    })


@login_required
def account_deposit(request, pk):
    """Пополнение счета"""
    Account = get_account_model()
    Client = get_client_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому счету')
        return redirect('accounts:account_list')

    if request.method == 'POST':
        # Здесь будет логика пополнения счета
        messages.success(request, 'Счет успешно пополнен')
        return redirect('accounts:account_detail', pk=account.pk)
    return render(request, 'accounts/deposit_form.html', {'account': account})


@login_required
def account_withdraw(request, pk):
    """Снятие со счета"""
    Account = get_account_model()
    Client = get_client_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому счету')
        return redirect('accounts:account_list')

    if request.method == 'POST':
        # Здесь будет логика снятия средств
        messages.success(request, 'Средства успешно сняты')
        return redirect('accounts:account_detail', pk=account.pk)
    return render(request, 'accounts/withdraw_form.html', {'account': account})


@login_required
def account_transfer(request):
    """Перевод между счетами"""
    if request.method == 'POST':
        # Здесь будет логика перевода
        messages.success(request, 'Перевод выполнен успешно')
        return redirect('accounts:account_list')
    return render(request, 'accounts/transfer_form.html')


@login_required
@role_required(['employee', 'admin'])
def currency_list(request):
    """Список валют"""
    Currency = get_currency_model()
    currencies = Currency.objects.all()
    return render(request, 'accounts/currency_list.html', {'currencies': currencies})