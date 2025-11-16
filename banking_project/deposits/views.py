from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.http import HttpResponseForbidden
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_deposit_model():
    """Ленивая загрузка модели Deposit"""
    return apps.get_model('deposits', 'Deposit')


def get_account_model():
    """Ленивая загрузка модели Account"""
    return apps.get_model('accounts', 'Account')


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
class DepositListView(LoginRequiredMixin, ListView):
    """Список депозитов - классовая версия"""
    template_name = 'deposits/deposit_list.html'
    context_object_name = 'deposits'
    paginate_by = 20

    def get_queryset(self):
        Deposit = get_deposit_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            client = get_object_or_404(Client, user=self.request.user)
            deposits = client.deposits.all()
        else:
            deposits = Deposit.objects.all()

        return deposits.select_related('client', 'client__user').order_by('-created_at')


class DepositDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о депозите - классовая версия"""
    template_name = 'deposits/deposit_detail.html'
    context_object_name = 'deposit'

    def get_queryset(self):
        Deposit = get_deposit_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            client = get_object_or_404(Client, user=self.request.user)
            return Deposit.objects.filter(client=client).select_related('client', 'client__user')
        return Deposit.objects.all().select_related('client', 'client__user')

    def get(self, request, *args, **kwargs):
        deposit = self.get_object()
        if request.user.role == 'client' and deposit.client.user != request.user:
            messages.error(request, 'У вас нет доступа к этому депозиту')
            return redirect('deposits:deposit_list')
        return super().get(request, *args, **kwargs)


class DepositCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """Создание нового депозита - классовая версия"""
    template_name = 'deposits/deposit_form.html'
    success_url = reverse_lazy('deposits:deposit_list')
    allowed_roles = ['employee', 'admin']

    def get_form_class(self):
        from .forms import DepositForm
        return DepositForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Депозит для {self.object.client.full_name} успешно создан')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)


class DepositUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """Редактирование депозита - классовая версия"""
    template_name = 'deposits/deposit_form.html'
    context_object_name = 'deposit'
    allowed_roles = ['employee', 'admin']

    def get_queryset(self):
        Deposit = get_deposit_model()
        return Deposit.objects.all().select_related('client', 'client__user')

    def get_form_class(self):
        from .forms import DepositForm
        return DepositForm

    def get_success_url(self):
        return reverse_lazy('deposits:deposit_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Депозит успешно обновлен')
        return response


class DepositDeleteView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    """Удаление депозита - классовая версия"""
    template_name = 'deposits/deposit_confirm_delete.html'
    success_url = reverse_lazy('deposits:deposit_list')
    allowed_roles = ['admin']

    def get_queryset(self):
        Deposit = get_deposit_model()
        return Deposit.objects.all().select_related('client', 'client__user')

    def delete(self, request, *args, **kwargs):
        deposit = self.get_object()
        messages.success(request, f'Депозит успешно удален')
        return super().delete(request, *args, **kwargs)


# Существующие функциональные представления (оставляем без изменений)
@login_required
def deposit_list_old(request):
    """Список депозитов - старая версия"""
    User = get_user_model()
    Client = get_client_model()
    Deposit = get_deposit_model()

    if request.user.role == 'client':
        # Клиенты видят только свои депозиты
        client = get_object_or_404(Client, user=request.user)
        deposits = client.deposits.all()
    else:
        # Сотрудники и админы видят все депозиты
        deposits = Deposit.objects.all()

    return render(request, 'deposits/deposit_list.html', {'deposits': deposits})


@login_required
def deposit_open(request):
    """Открытие нового депозита"""
    Client = get_client_model()
    Deposit = get_deposit_model()
    Account = get_account_model()
    Currency = get_currency_model()

    if request.user.role == 'client':
        client = get_object_or_404(Client, user=request.user)
    else:
        client = None

    if request.method == 'POST':
        # Здесь будет логика открытия депозита
        messages.success(request, 'Депозит успешно открыт')
        return redirect('deposits:deposit_list')

    currencies = Currency.objects.filter(is_active=True)
    return render(request, 'deposits/deposit_open.html', {
        'client': client,
        'currencies': currencies
    })


@login_required
def deposit_detail_old(request, pk):
    """Детальная информация о депозите - старая версия"""
    Deposit = get_deposit_model()
    Client = get_client_model()
    User = get_user_model()

    deposit = get_object_or_404(Deposit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and deposit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому депозиту')
        return redirect('deposits:deposit_list')

    # Расчет начисленных процентов
    interest = deposit.calculate_interest() if hasattr(deposit, 'calculate_interest') else 0
    total_amount = deposit.get_total_amount() if hasattr(deposit, 'get_total_amount') else deposit.amount

    return render(request, 'deposits/deposit_detail.html', {
        'deposit': deposit,
        'interest': interest,
        'total_amount': total_amount
    })


@login_required
def deposit_close(request, pk):
    """Закрытие депозита"""
    Deposit = get_deposit_model()
    Client = get_client_model()

    deposit = get_object_or_404(Deposit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and deposit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому депозиту')
        return redirect('deposits:deposit_list')

    if request.method == 'POST':
        if deposit.close_deposit():
            messages.success(request, 'Депозит успешно закрыт')
        else:
            messages.error(request, 'Не удалось закрыть депозит')
        return redirect('deposits:deposit_detail', pk=deposit.pk)

    return render(request, 'deposits/deposit_confirm_close.html', {'deposit': deposit})


@login_required
def deposit_interest(request, pk):
    """Начисленные проценты по депозиту"""
    Deposit = get_deposit_model()
    Client = get_client_model()

    deposit = get_object_or_404(Deposit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and deposit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к процентам этого депозита')
        return redirect('deposits:deposit_list')

    interest_payments = deposit.interest_payments.all() if hasattr(deposit, 'interest_payments') else []
    current_interest = deposit.calculate_interest() if hasattr(deposit, 'calculate_interest') else 0

    return render(request, 'deposits/deposit_interest.html', {
        'deposit': deposit,
        'interest_payments': interest_payments,
        'current_interest': current_interest
    })


@login_required
@employee_required
def deposit_early_close(request, pk):
    """Досрочное закрытие депозита сотрудником"""
    Deposit = get_deposit_model()

    deposit = get_object_or_404(Deposit, pk=pk)

    if request.method == 'POST':
        # Здесь будет логика досрочного закрытия с пересчетом процентов
        if deposit.close_deposit():
            messages.success(request, 'Депозит досрочно закрыт')
        else:
            messages.error(request, 'Не удалось закрыть депозит')
        return redirect('deposits:deposit_detail', pk=deposit.pk)

    return render(request, 'deposits/deposit_early_close.html', {'deposit': deposit})