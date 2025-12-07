from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.http import HttpResponseForbidden, JsonResponse
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.db import models
from decimal import Decimal
import datetime


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
            # Клиенты видят только свои депозиты
            try:
                client = Client.objects.get(user=self.request.user)
                deposits = client.deposits.all()
            except Client.DoesNotExist:
                deposits = Deposit.objects.none()
                messages.warning(self.request, 'Клиентский профиль не найден')
        else:
            deposits = Deposit.objects.all()

        return deposits.select_related('client', 'client__user', 'account', 'account__currency').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_role'] = self.request.user.role

        if self.request.user.role == 'client':
            context['page_title'] = 'Мои депозиты'
        else:
            context['page_title'] = 'Все депозиты'

        # Добавляем информацию о процентах для сотрудников и админов
        if self.request.user.role in ['employee', 'admin']:
            deposits = context['deposits']
            for deposit in deposits:
                try:
                    deposit.expected_interest = deposit.get_expected_interest()
                except:
                    deposit.expected_interest = Decimal('0.00')

                try:
                    deposit.next_accrual_date = deposit.get_next_accrual_date()
                except:
                    deposit.next_accrual_date = None

                try:
                    deposit.total_accrued_interest = deposit.get_total_accrued_interest()
                except:
                    deposit.total_accrued_interest = Decimal('0.00')

        return context


class DepositDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о депозите - классовая версия"""
    template_name = 'deposits/deposit_detail.html'
    context_object_name = 'deposit'

    def get_queryset(self):
        Deposit = get_deposit_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            try:
                client = Client.objects.get(user=self.request.user)
                return Deposit.objects.filter(client=client).select_related('client', 'client__user', 'account',
                                                                            'account__currency')
            except Client.DoesNotExist:
                return Deposit.objects.none()
        return Deposit.objects.all().select_related('client', 'client__user', 'account', 'account__currency')

    def get(self, request, *args, **kwargs):
        try:
            deposit = self.get_object()
        except:
            messages.error(request, 'Депозит не найден')
            return redirect('deposits:deposit_list')

        if request.user.role == 'client' and deposit.client.user != request.user:
            messages.error(request, 'У вас нет доступа к этому депозиту')
            return redirect('deposits:deposit_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        deposit = context['deposit']

        # Добавляем информацию о процентах с обработкой исключений
        try:
            context['expected_interest'] = deposit.get_expected_interest()
        except:
            context['expected_interest'] = Decimal('0.00')

        try:
            context['next_accrual_date'] = deposit.get_next_accrual_date()
        except:
            context['next_accrual_date'] = None

        try:
            context['total_accrued_interest'] = deposit.get_total_accrued_interest()
        except:
            context['total_accrued_interest'] = Decimal('0.00')

        try:
            context['interest_history'] = deposit.get_interest_history()[:10]  # Последние 10 начислений
        except:
            context['interest_history'] = []

        try:
            context['can_accrue_interest'] = deposit.can_accrue_interest()
        except:
            context['can_accrue_interest'] = False

        return context


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
        return Deposit.objects.all().select_related('client', 'client__user', 'account', 'account__currency')

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
        return Deposit.objects.all().select_related('client', 'client__user', 'account', 'account__currency')

    def delete(self, request, *args, **kwargs):
        deposit = self.get_object()
        messages.success(request, f'Депозит успешно удален')
        return super().delete(request, *args, **kwargs)


# Существующие функциональные представления

@login_required
def deposit_list_old(request):
    """Список депозитов - старая версия"""
    Deposit = get_deposit_model()
    Client = get_client_model()

    if request.user.role == 'client':
        # Клиенты видят только свои депозиты
        try:
            client = Client.objects.get(user=request.user)
            deposits = client.deposits.all()
        except Client.DoesNotExist:
            deposits = Deposit.objects.none()
            messages.warning(request, 'Клиентский профиль не найден')
    else:
        # Сотрудники и админы видят все депозиты
        deposits = Deposit.objects.all()

    return render(request, 'deposits/deposit_list.html', {
        'deposits': deposits,
        'user_role': request.user.role
    })


@login_required
def deposit_open(request):
    """Открытие нового депозита"""
    Client = get_client_model()
    Deposit = get_deposit_model()
    Currency = get_currency_model()

    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
        except Client.DoesNotExist:
            messages.error(request, 'Клиентский профиль не найден')
            return redirect('deposits:deposit_list')
    else:
        client = None

    if request.method == 'POST':
        # Здесь будет логика открытия депозита
        messages.success(request, 'Депозит успешно открыт')
        return redirect('deposits:deposit_list')

    currencies = Currency.objects.filter(is_active=True)
    return render(request, 'deposits/deposit_open.html', {
        'client': client,
        'currencies': currencies,
        'user_role': request.user.role
    })


@login_required
def deposit_detail_old(request, pk):
    """Детальная информация о депозите - старая версия"""
    Deposit = get_deposit_model()
    Client = get_client_model()

    try:
        deposit = Deposit.objects.get(pk=pk)
    except Deposit.DoesNotExist:
        messages.error(request, 'Депозит не найден')
        return redirect('deposits:deposit_list')

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            if deposit.client != client:
                messages.error(request, 'У вас нет доступа к этому депозиту')
                return redirect('deposits:deposit_list')
        except Client.DoesNotExist:
            messages.error(request, 'Клиентский профиль не найден')
            return redirect('deposits:deposit_list')

    # Расчет начисленных процентов
    try:
        interest = deposit.calculate_interest()
    except:
        interest = Decimal('0.00')

    try:
        total_amount = deposit.get_total_amount()
    except:
        total_amount = deposit.amount

    return render(request, 'deposits/deposit_detail.html', {
        'deposit': deposit,
        'interest': interest,
        'total_amount': total_amount,
        'user_role': request.user.role
    })


@login_required
def deposit_close(request, pk):
    """Закрытие депозита"""
    Deposit = get_deposit_model()
    Client = get_client_model()

    try:
        deposit = Deposit.objects.get(pk=pk)
    except Deposit.DoesNotExist:
        messages.error(request, 'Депозит не найден')
        return redirect('deposits:deposit_list')

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            if deposit.client != client:
                messages.error(request, 'У вас нет доступа к этому депозиту')
                return redirect('deposits:deposit_list')
        except Client.DoesNotExist:
            messages.error(request, 'Клиентский профиль не найден')
            return redirect('deposits:deposit_list')

    if request.method == 'POST':
        if hasattr(deposit, 'close_deposit'):
            if deposit.close_deposit():
                messages.success(request, 'Депозит успешно закрыт')
            else:
                messages.error(request, 'Не удалось закрыть депозит')
        else:
            deposit.status = 'closed'
            deposit.closed_at = timezone.now()
            deposit.save()
            messages.success(request, 'Депозит успешно закрыт')

        return redirect('deposits:deposit_detail', pk=deposit.pk)

    return render(request, 'deposits/deposit_confirm_close.html', {
        'deposit': deposit,
        'user_role': request.user.role
    })


@login_required
def deposit_interest(request, pk):
    """Начисленные проценты по депозиту"""
    Deposit = get_deposit_model()
    Client = get_client_model()

    try:
        deposit = Deposit.objects.get(pk=pk)
    except Deposit.DoesNotExist:
        messages.error(request, 'Депозит не найден')
        return redirect('deposits:deposit_list')

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            client = Client.objects.get(user=request.user)
            if deposit.client != client:
                messages.error(request, 'У вас нет доступа к процентам этого депозита')
                return redirect('deposits:deposit_list')
        except Client.DoesNotExist:
            messages.error(request, 'Клиентский профиль не найден')
            return redirect('deposits:deposit_list')

    # Получаем историю начисления процентов
    if hasattr(deposit, 'interest_payments'):
        interest_payments = deposit.interest_payments.all()
    else:
        interest_payments = []

    try:
        current_interest = deposit.calculate_interest()
    except:
        current_interest = Decimal('0.00')

    return render(request, 'deposits/deposit_interest.html', {
        'deposit': deposit,
        'interest_payments': interest_payments,
        'current_interest': current_interest,
        'user_role': request.user.role
    })


@login_required
@employee_required
def deposit_early_close(request, pk):
    """Досрочное закрытие депозита сотрудником"""
    Deposit = get_deposit_model()

    try:
        deposit = Deposit.objects.get(pk=pk)
    except Deposit.DoesNotExist:
        messages.error(request, 'Депозит не найден')
        return redirect('deposits:deposit_list')

    if request.method == 'POST':
        # Здесь будет логика досрочного закрытия с пересчетом процентов
        if hasattr(deposit, 'close_deposit'):
            if deposit.close_deposit():
                messages.success(request, 'Депозит досрочно закрыт')
            else:
                messages.error(request, 'Не удалось закрыть депозит')
        else:
            deposit.status = 'closed'
            deposit.closed_at = timezone.now()
            deposit.save()
            messages.success(request, 'Депозит досрочно закрыт')

        return redirect('deposits:deposit_detail', pk=deposit.pk)

    return render(request, 'deposits/deposit_early_close.html', {
        'deposit': deposit,
        'user_role': request.user.role
    })


# Новые представления для начисления процентов

@login_required
@employee_required
def accrue_interest_manual(request, pk):
    """Ручное начисление процентов по депозиту"""
    Deposit = get_deposit_model()

    try:
        deposit = Deposit.objects.get(pk=pk)
    except Deposit.DoesNotExist:
        messages.error(request, 'Депозит не найден')
        return redirect('deposits:deposit_list')

    if not hasattr(deposit, 'can_accrue_interest') or not deposit.can_accrue_interest():
        messages.error(request, 'Невозможно начислить проценты по этому депозиту')
        return redirect('deposits:deposit_detail', pk=deposit.pk)

    if request.method == 'POST':
        try:
            # Пытаемся использовать management command для начисления
            from django.core.management import call_command
            from django.core.management.base import CommandError

            try:
                call_command('accrue_deposits_interest', deposit_id=deposit.id)
                messages.success(request, f'Проценты по депозиту успешно начислены')

                # Обновляем объект депозита
                deposit.refresh_from_db()

            except CommandError as e:
                messages.error(request, f'Ошибка при начислении процентов: {str(e)}')
            except Exception as e:
                messages.error(request, f'Ошибка при начислении процентов: {str(e)}')

            return redirect('deposits:deposit_detail', pk=deposit.pk)

        except Exception as e:
            messages.error(request, f'Ошибка при начислении процентов: {str(e)}')

    # Расчет ожидаемых процентов для отображения
    try:
        expected_interest = deposit.get_expected_interest()
    except:
        expected_interest = Decimal('0.00')

    return render(request, 'deposits/deposit_accrue_interest.html', {
        'deposit': deposit,
        'expected_interest': expected_interest
    })


@login_required
@employee_required
def accrue_interest_all(request):
    """Начисление процентов по всем депозитам"""
    Deposit = get_deposit_model()

    if request.method == 'POST':
        try:
            from django.core.management import call_command
            from django.core.management.base import CommandError

            try:
                call_command('accrue_deposits_interest')
                messages.success(request, 'Проценты по всем депозитам успешно начислены')
            except CommandError as e:
                messages.error(request, f'Ошибка при начислении процентов: {str(e)}')

        except Exception as e:
            messages.error(request, f'Ошибка при начислении процентов: {str(e)}')

        return redirect('deposits:deposit_list')

    # Статистика для отображения
    active_deposits = Deposit.objects.filter(status='active').count()
    deposits_for_accrual = Deposit.objects.filter(
        status='active',
        start_date__lte=timezone.now().date(),
        end_date__gte=timezone.now().date()
    ).count()

    return render(request, 'deposits/accrue_interest_all.html', {
        'active_deposits': active_deposits,
        'deposits_for_accrual': deposits_for_accrual
    })


@require_POST
@login_required
@employee_required
def get_expected_interest(request, pk):
    """API для получения ожидаемых процентов"""
    Deposit = get_deposit_model()

    try:
        deposit = Deposit.objects.get(pk=pk)
    except Deposit.DoesNotExist:
        return JsonResponse({'error': 'Депозит не найден'}, status=404)

    try:
        expected_interest = deposit.get_expected_interest()
    except:
        expected_interest = Decimal('0.00')

    try:
        next_accrual_date = deposit.get_next_accrual_date()
    except:
        next_accrual_date = None

    return JsonResponse({
        'expected_interest': float(expected_interest),
        'currency': deposit.account.currency.code if deposit.account and deposit.account.currency else 'RUB',
        'next_accrual_date': next_accrual_date.isoformat() if next_accrual_date else None
    })


@login_required
@employee_required
def interest_accrual_report(request):
    """Отчет по начисленным процентам"""
    try:
        DepositInterestPayment = apps.get_model('deposits', 'DepositInterestPayment')
    except:
        messages.error(request, 'Модель DepositInterestPayment не найдена')
        return redirect('deposits:deposit_list')

    # Фильтры
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    deposit_id = request.GET.get('deposit_id')

    interest_payments = DepositInterestPayment.objects.select_related(
        'deposit', 'deposit__client', 'deposit__account', 'deposit__account__currency'
    ).all()

    if date_from:
        interest_payments = interest_payments.filter(payment_date__gte=date_from)
    if date_to:
        interest_payments = interest_payments.filter(payment_date__lte=date_to)
    if deposit_id:
        interest_payments = interest_payments.filter(deposit_id=deposit_id)

    interest_payments = interest_payments.order_by('-payment_date')

    # Суммарная статистика
    total_accrued = interest_payments.aggregate(total=models.Sum('amount'))['total'] or Decimal('0.00')

    context = {
        'interest_payments': interest_payments,
        'total_accrued': total_accrued,
        'date_from': date_from,
        'date_to': date_to,
        'deposit_id': deposit_id,
    }

    return render(request, 'deposits/interest_accrual_report.html', context)