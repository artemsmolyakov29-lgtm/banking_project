from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.http import HttpResponseForbidden


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_card_model():
    """Ленивая загрузка модели Card"""
    return apps.get_model('cards', 'Card')


def get_card_transaction_model():
    """Ленивая загрузка модели CardTransaction"""
    return apps.get_model('cards', 'CardTransaction')


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


@login_required
def card_list(request):
    """Список карт"""
    User = get_user_model()
    Client = get_client_model()
    Card = get_card_model()

    if request.user.role == 'client':
        # Клиенты видят только свои карты
        client = get_object_or_404(Client, user=request.user)
        # Получаем карты через связанные счета клиента
        accounts = client.accounts.all()
        cards = Card.objects.filter(account__in=accounts)
    else:
        # Сотрудники и админы видят все карты
        cards = Card.objects.all()

    return render(request, 'cards/card_list.html', {'cards': cards})


@login_required
@employee_required
def card_issue(request):
    """Выпуск новой карты"""
    Client = get_client_model()
    Card = get_card_model()
    Account = get_account_model()

    if request.method == 'POST':
        # Здесь будет логика выпуска карты
        messages.success(request, 'Карта успешно выпущена')
        return redirect('cards:card_list')

    clients = Client.objects.all()
    accounts = Account.objects.filter(status='active')

    return render(request, 'cards/card_issue.html', {
        'clients': clients,
        'accounts': accounts
    })


@login_required
def card_detail(request, pk):
    """Детальная информация о карте"""
    Card = get_card_model()
    Client = get_client_model()
    User = get_user_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этой карте')
        return redirect('cards:card_list')

    return render(request, 'cards/card_detail.html', {'card': card})


@login_required
def card_block(request, pk):
    """Блокировка карты"""
    Card = get_card_model()
    Client = get_client_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этой карте')
        return redirect('cards:card_list')

    if request.method == 'POST':
        reason = request.POST.get('reason', 'blocked')
        if card.block_card(reason):
            messages.success(request, 'Карта успешно заблокирована')
        else:
            messages.error(request, 'Не удалось заблокировать карту')
        return redirect('cards:card_detail', pk=card.pk)

    return render(request, 'cards/card_confirm_block.html', {'card': card})


@login_required
def card_unblock(request, pk):
    """Разблокировка карты"""
    Card = get_card_model()
    Client = get_client_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этой карте')
        return redirect('cards:card_list')

    if request.method == 'POST':
        if card.unblock_card():
            messages.success(request, 'Карта успешно разблокирована')
        else:
            messages.error(request, 'Не удалось разблокировать карту')
        return redirect('cards:card_detail', pk=card.pk)

    return render(request, 'cards/card_confirm_unblock.html', {'card': card})


@login_required
def card_transactions(request, pk):
    """Операции по карте"""
    Card = get_card_model()
    CardTransaction = get_card_transaction_model()
    Client = get_client_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к операциям этой карты')
        return redirect('cards:card_list')

    transactions = card.transactions.all() if hasattr(card, 'transactions') else []

    return render(request, 'cards/card_transactions.html', {
        'card': card,
        'transactions': transactions
    })


@login_required
def card_limits(request, pk):
    """Управление лимитами карты"""
    Card = get_card_model()
    Client = get_client_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к настройкам этой карты')
        return redirect('cards:card_list')

    if request.method == 'POST':
        daily_limit = request.POST.get('daily_limit')
        # Здесь будет логика обновления лимитов
        messages.success(request, 'Лимиты карты успешно обновлены')
        return redirect('cards:card_detail', pk=card.pk)

    return render(request, 'cards/card_limits.html', {'card': card})


@login_required
@employee_required
def card_reissue(request, pk):
    """Перевыпуск карты"""
    Card = get_card_model()

    card = get_object_or_404(Card, pk=pk)

    if request.method == 'POST':
        # Здесь будет логика перевыпуска карты
        messages.success(request, 'Карта успешно перевыпущена')
        return redirect('cards:card_detail', pk=card.pk)

    return render(request, 'cards/card_reissue.html', {'card': card})