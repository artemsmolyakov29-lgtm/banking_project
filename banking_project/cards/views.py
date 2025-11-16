from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.http import HttpResponseForbidden, JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST

# Ленивая загрузка моделей
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


# Миксин для классовых представлений
class RoleRequiredMixin:
    """Миксин для проверки ролей пользователя в классовых представлениях"""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            return HttpResponseForbidden("У вас нет доступа к этой странице.")
        return super().dispatch(request, *args, **kwargs)


# Классовые представления CRUD
class CardListView(LoginRequiredMixin, ListView):
    """Список карт - классовая версия"""
    template_name = 'cards/card_list.html'
    context_object_name = 'cards'
    paginate_by = 20

    def get_queryset(self):
        Card = get_card_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            # Клиенты видят только свои карты
            client = get_object_or_404(Client, user=self.request.user)
            accounts = client.accounts.all()
            cards = Card.objects.filter(account__in=accounts)
        else:
            # Сотрудники и админы видят все карты
            cards = Card.objects.all()

        return cards.select_related('account', 'account__client', 'account__client__user').order_by('-created_at')


class CardDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о карте - классовая версия"""
    template_name = 'cards/card_detail.html'
    context_object_name = 'card'

    def get_queryset(self):
        Card = get_card_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            client = get_object_or_404(Client, user=self.request.user)
            accounts = client.accounts.all()
            return Card.objects.filter(account__in=accounts).select_related('account', 'account__client',
                                                                            'account__client__user')
        return Card.objects.all().select_related('account', 'account__client', 'account__client__user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        CardStatusHistory = get_card_status_history_model()

        # Добавляем историю статусов в контекст
        context['status_history'] = self.object.status_history.all().select_related('changed_by')[:10]
        return context

    def get(self, request, *args, **kwargs):
        card = self.get_object()
        if request.user.role == 'client' and card.account.client.user != request.user:
            messages.error(request, 'У вас нет доступа к этой карте')
            return redirect('cards:card_list')
        return super().get(request, *args, **kwargs)


class CardCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """Создание новой карты - классовая версия"""
    template_name = 'cards/card_form.html'
    success_url = reverse_lazy('cards:card_list')
    allowed_roles = ['employee', 'admin']

    def get_form_class(self):
        from .forms import CardForm
        return CardForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Карта для {self.object.account.client.full_name} успешно создана')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)


class CardUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """Редактирование карты - классовая версия"""
    template_name = 'cards/card_form.html'
    context_object_name = 'card'
    allowed_roles = ['employee', 'admin']

    def get_queryset(self):
        Card = get_card_model()
        return Card.objects.all().select_related('account', 'account__client', 'account__client__user')

    def get_form_class(self):
        from .forms import CardForm
        return CardForm

    def get_success_url(self):
        return reverse_lazy('cards:card_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Карта успешно обновлена')
        return response


class CardDeleteView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    """Удаление карты - классовая версия"""
    template_name = 'cards/card_confirm_delete.html'
    success_url = reverse_lazy('cards:card_list')
    allowed_roles = ['admin']

    def get_queryset(self):
        Card = get_card_model()
        return Card.objects.all().select_related('account', 'account__client', 'account__client__user')

    def delete(self, request, *args, **kwargs):
        card = self.get_object()
        messages.success(request, f'Карта успешно удалена')
        return super().delete(request, *args, **kwargs)


# Существующие функциональные представления (оставляем без изменений)
@login_required
def card_list_old(request):
    """Список карт - старая версия (для обратной совместимости)"""
    User = get_user_model()
    Client = get_client_model()
    Card = get_card_model()

    if request.user.role == 'client':
        # Клиенты видят только свои карты
        client = get_object_or_404(Client, user=request.user)
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
def card_detail_old(request, pk):
    """Детальная информация о карте - старая версия"""
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
@require_POST
def card_block(request, pk):
    """Блокировка карты"""
    Card = get_card_model()
    Client = get_client_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этой карте')
        return redirect('cards:card_list')

    block_reason = request.POST.get('block_reason')
    block_description = request.POST.get('block_description', '')

    if card.block_card(reason='blocked', block_reason=block_reason,
                       block_description=block_description, user=request.user):
        messages.success(request, 'Карта успешно заблокирована')

        # Если это AJAX-запрос, возвращаем JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Карта успешно заблокирована',
                'status': card.get_status_display(),
                'status_color': 'danger'
            })
    else:
        messages.error(request, 'Не удалось заблокировать карту')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Не удалось заблокировать карту'
            }, status=400)

    return redirect('cards:card_detail', pk=card.pk)


@login_required
@require_POST
def card_unblock(request, pk):
    """Разблокировка карты"""
    Card = get_card_model()
    Client = get_client_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этой карте')
        return redirect('cards:card_list')

    if card.unblock_card(user=request.user):
        messages.success(request, 'Карта успешно разблокирована')

        # Если это AJAX-запрос, возвращаем JSON
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'Карта успешно разблокирована',
                'status': card.get_status_display(),
                'status_color': 'success'
            })
    else:
        messages.error(request, 'Не удалось разблокировать карту')
        if request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'Не удалось разблокировать карту'
            }, status=400)

    return redirect('cards:card_detail', pk=card.pk)


@login_required
def card_block_confirm(request, pk):
    """Подтверждение блокировки карты"""
    Card = get_card_model()
    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этой карте')
        return redirect('cards:card_list')

    return render(request, 'cards/card_confirm_block.html', {
        'card': card,
        'block_reasons': Card.BLOCK_REASONS
    })


@login_required
def card_unblock_confirm(request, pk):
    """Подтверждение разблокировки карты"""
    Card = get_card_model()
    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этой карте')
        return redirect('cards:card_list')

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


@login_required
def card_status_history(request, pk):
    """История изменения статусов карты"""
    Card = get_card_model()
    CardStatusHistory = get_card_status_history_model()

    card = get_object_or_404(Card, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and card.account.client.user != request.user:
        messages.error(request, 'У вас нет доступа к истории этой карты')
        return redirect('cards:card_list')

    status_history = card.status_history.all().select_related('changed_by')

    return render(request, 'cards/card_status_history.html', {
        'card': card,
        'status_history': status_history
    })