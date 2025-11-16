from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import models

# Импортируем миксины из core (если есть) или создадим локальные версии
try:
    from core.mixins import RoleRequiredMixin
except ImportError:
    # Создаем локальную версию миксина, если core.mixins недоступен
    from django.core.exceptions import PermissionDenied
    from django.contrib.auth.mixins import UserPassesTestMixin


    class RoleRequiredMixin(UserPassesTestMixin):
        allowed_roles = []

        def test_func(self):
            return self.request.user.is_authenticated and self.request.user.role in self.allowed_roles

        def handle_no_permission(self):
            raise PermissionDenied("У вас нет доступа к этой странице.")


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


def get_account_form():
    """Ленивая загрузка формы Account"""
    from .forms import AccountForm
    return AccountForm


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


# Классовые представления для CRUD операций

class AccountListView(LoginRequiredMixin, ListView):
    """Список счетов - классовая версия"""
    template_name = 'accounts/account_list.html'
    context_object_name = 'accounts'
    paginate_by = 20

    def get_queryset(self):
        Account = get_account_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            # Клиенты видят только свои счета
            client = get_object_or_404(Client, user=self.request.user)
            accounts = client.accounts.all()
        else:
            # Сотрудники и админы видят все счета
            accounts = Account.objects.all()

        # Добавляем связанные данные для оптимизации запросов
        accounts = accounts.select_related('client', 'client__user')
        return accounts.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_role'] = self.request.user.role
        return context


class AccountDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о счете - классовая версия"""
    template_name = 'accounts/account_detail.html'
    context_object_name = 'account'

    def get_queryset(self):
        Account = get_account_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            # Клиенты видят только свои счета
            client = get_object_or_404(Client, user=self.request.user)
            return Account.objects.filter(client=client).select_related('client', 'client__user')
        return Account.objects.all().select_related('client', 'client__user')

    def get(self, request, *args, **kwargs):
        # Дополнительная проверка прав доступа
        account = self.get_object()
        if request.user.role == 'client' and account.client.user != request.user:
            messages.error(request, 'У вас нет доступа к этому счету')
            return redirect('accounts:account_list')
        return super().get(request, *args, **kwargs)


class AccountCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """Создание нового счета - классовая версия"""
    template_name = 'accounts/account_form.html'
    success_url = reverse_lazy('accounts:account_list')
    allowed_roles = ['employee', 'admin']

    def get_form_class(self):
        return get_account_form()

    def form_valid(self, form):
        Account = get_account_model()

        # Генерация номера счета, если не указан
        if not form.instance.account_number:
            from datetime import datetime
            form.instance.account_number = f"ACC{datetime.now().strftime('%Y%m%d%H%M%S')}"

        response = super().form_valid(form)
        messages.success(self.request, f'Счет №{self.object.account_number} успешно создан')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        # Для сотрудников и администраторов добавляем поле выбора клиента
        if self.request.user.role in ['employee', 'admin']:
            Client = get_client_model()
            form.fields['client'] = models.ModelChoiceField(
                queryset=Client.objects.all(),
                label="Клиент",
                widget=form.Select(attrs={'class': 'form-select'})
            )
        return form


class AccountUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """Редактирование счета - классовая версия"""
    template_name = 'accounts/account_form.html'
    context_object_name = 'account'
    allowed_roles = ['employee', 'admin']

    def get_form_class(self):
        return get_account_form()

    def get_queryset(self):
        Account = get_account_model()
        return Account.objects.all().select_related('client', 'client__user')

    def get_success_url(self):
        return reverse_lazy('accounts:account_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Счет №{self.object.account_number} успешно обновлен')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)


class AccountDeleteView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    """Удаление счета - классовая версия"""
    template_name = 'accounts/account_confirm_delete.html'
    success_url = reverse_lazy('accounts:account_list')
    allowed_roles = ['admin']

    def get_queryset(self):
        Account = get_account_model()
        return Account.objects.all().select_related('client', 'client__user')

    def delete(self, request, *args, **kwargs):
        account = self.get_object()
        messages.success(request, f'Счет №{account.account_number} успешно удален')
        return super().delete(request, *args, **kwargs)


# Существующие функциональные представления (оставляем как есть)

@login_required
def account_list_old(request):
    """Список счетов - старая версия (для обратной совместимости)"""
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
def account_detail_old(request, pk):
    """Детальная информация о счете - старая версия"""
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
def account_create_old(request):
    """Создание нового счета - старая версия"""
    Account = get_account_model()
    AccountForm = get_account_form()

    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save()
            messages.success(request, f'Счет №{account.account_number} успешно создан')
            return redirect('accounts:account_list')
    else:
        form = AccountForm()

    return render(request, 'accounts/account_form.html', {'form': form})


@login_required
@role_required(['employee', 'admin'])
def account_update_old(request, pk):
    """Редактирование счета - старая версия"""
    Account = get_account_model()
    AccountForm = get_account_form()

    account = get_object_or_404(Account, pk=pk)

    if request.method == 'POST':
        form = AccountForm(request.POST, instance=account)
        if form.is_valid():
            form.save()
            messages.success(request, f'Счет №{account.account_number} успешно обновлен')
            return redirect('accounts:account_detail', pk=account.pk)
    else:
        form = AccountForm(instance=account)

    return render(request, 'accounts/account_form.html', {'form': form, 'account': account})


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