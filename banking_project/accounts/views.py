from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.apps import apps
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.db import models
from django.http import HttpResponse, JsonResponse, HttpResponseForbidden
from django.db.models import Sum, Avg, Count
from django.core.paginator import Paginator
from decimal import Decimal
import csv
import json
from datetime import datetime, timedelta
import random
import string
from django import forms

# Импорт миксинов
try:
    from clients.mixins import ClientRequiredMixin, EmployeeOrAdminRequiredMixin, AdminRequiredMixin
except ImportError:
    # Создаем локальные версии миксинов, если они не существуют
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


def get_transaction_model():
    """Ленивая загрузка модели Transaction"""
    return apps.get_model('transactions', 'Transaction')


def create_client_for_user(user):
    """
    Функция для создания профиля клиента для пользователя
    Используется, если сигналы не сработали
    """
    Client = get_client_model()

    # Проверяем, есть ли уже профиль
    if hasattr(user, 'client_profile'):
        return user.client_profile

    # Генерируем уникальные данные
    from django.utils import timezone
    from datetime import date

    # Генерируем уникальные ИНН и СНИЛС
    while True:
        inn = ''.join(random.choices(string.digits, k=12))
        if not Client.objects.filter(inn=inn).exists():
            break

    while True:
        snils = f"{''.join(random.choices(string.digits, k=3))}-" \
                f"{''.join(random.choices(string.digits, k=3))}-" \
                f"{''.join(random.choices(string.digits, k=3))} 00"
        if not Client.objects.filter(snils=snils).exists():
            break

    # Создаем профиль клиента
    client = Client.objects.create(
        user=user,
        full_name=f"{user.first_name or ''} {user.last_name or ''}".strip() or "Не указано",
        passport_series='0000',
        passport_number='000000',
        passport_issued_by='АВТОМАТИЧЕСКИ СОЗДАНО СИСТЕМОЙ',
        passport_issue_date=date(2000, 1, 1),
        passport_department_code='000-000',
        registration_address='НЕ УКАЗАНО',
        inn=inn,
        snils=snils,
        marital_status='single',
        education_level='secondary',
        work_experience=0,
        monthly_income=0,
        credit_rating=500,
        is_vip=False,
        created_at=timezone.now(),
        updated_at=timezone.now()
    )

    return client


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


# Классовые представления для CRUD операций

class AccountListView(LoginRequiredMixin, ListView):
    """Список счетов - классовая версия"""
    template_name = 'accounts/account_list.html'
    context_object_name = 'accounts'
    paginate_by = 20

    def get_queryset(self):
        Account = get_account_model()

        # Если клиент - показываем только его счета
        if self.request.user.role == 'client':
            try:
                Client = get_client_model()
                client = Client.objects.get(user=self.request.user)
                accounts = client.accounts.all()
            except Client.DoesNotExist:
                # Если клиента нет, создаем его
                client = create_client_for_user(self.request.user)
                accounts = client.accounts.all()
            except Exception as e:
                accounts = Account.objects.none()
        # Если сотрудник или администратор - показываем все счета
        elif self.request.user.role in ['employee', 'admin']:
            accounts = Account.objects.all()
        else:
            accounts = Account.objects.none()

        # Добавляем связанные данные для оптимизации запросов
        accounts = accounts.select_related('client', 'client__user', 'currency')
        return accounts.order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['user_role'] = self.request.user.role

        # Статистика по счетам
        Account = get_account_model()
        if self.request.user.role == 'client':
            try:
                Client = get_client_model()
                client = Client.objects.get(user=self.request.user)
                accounts = client.accounts.all()
            except:
                accounts = Account.objects.none()
        else:
            accounts = Account.objects.all()

        total_balance = accounts.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        active_accounts = accounts.filter(status='active').count()
        blocked_accounts = accounts.filter(status='blocked').count()
        closed_accounts = accounts.filter(status='closed').count()

        context.update({
            'total_balance': total_balance,
            'active_accounts': active_accounts,
            'blocked_accounts': blocked_accounts,
            'closed_accounts': closed_accounts,
        })

        return context


class AccountDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о счете - классовая версия"""
    template_name = 'accounts/account_detail.html'
    context_object_name = 'account'

    def get_queryset(self):
        Account = get_account_model()
        return Account.objects.all().select_related('client', 'client__user', 'currency')

    def get(self, request, *args, **kwargs):
        # Дополнительная проверка прав доступа
        account = self.get_object()
        if request.user.role == 'client':
            try:
                Client = get_client_model()
                client = Client.objects.get(user=request.user)
                if account.client != client:
                    messages.error(request, 'У вас нет доступа к этому счету')
                    return redirect('accounts:account_list')
            except:
                messages.error(request, 'У вас нет доступа к этому счету')
                return redirect('accounts:account_list')
        return super().get(request, *args, **kwargs)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Получаем последние транзакции по счету
        Transaction = get_transaction_model()
        try:
            transactions = Transaction.objects.filter(
                models.Q(from_account=self.object) | models.Q(to_account=self.object)
            ).select_related('from_account', 'to_account', 'currency').order_by('-created_at')[:10]
            context['transactions'] = transactions
        except:
            context['transactions'] = []

        return context


class AccountCreateView(LoginRequiredMixin, CreateView):
    """Создание нового счета - классовая версия"""
    template_name = 'accounts/account_form.html'
    success_url = reverse_lazy('accounts:account_list')

    def get_form_class(self):
        return get_account_form()

    def dispatch(self, request, *args, **kwargs):
        # Разрешаем доступ клиентам, сотрудникам и администраторам
        if request.user.role not in ['client', 'employee', 'admin']:
            return HttpResponseForbidden("У вас нет доступа к этой странице.")
        return super().dispatch(request, *args, **kwargs)

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        Client = get_client_model()

        if self.request.user.role == 'client':
            # Для клиентов скрываем поле выбора клиента и устанавливаем текущего клиента
            try:
                client = Client.objects.get(user=self.request.user)
                if 'client' in form.fields:  # Проверяем, существует ли поле
                    form.fields['client'].initial = client
                    form.fields['client'].widget = forms.HiddenInput()
            except Client.DoesNotExist:
                client = create_client_for_user(self.request.user)
                if 'client' in form.fields:  # Проверяем, существует ли поле
                    form.fields['client'].initial = client
                    form.fields['client'].widget = forms.HiddenInput()
        elif self.request.user.role in ['employee', 'admin']:
            # Для сотрудников и администраторов добавляем поле выбора клиента
            if 'client' in form.fields:  # Проверяем, существует ли поле
                form.fields['client'].queryset = Client.objects.all()
                form.fields['client'].widget.attrs.update({'class': 'form-select'})

        return form

    def form_valid(self, form):
        Account = get_account_model()

        # Если пользователь - клиент, автоматически привязываем его к счету
        if self.request.user.role == 'client':
            try:
                Client = get_client_model()
                client = Client.objects.get(user=self.request.user)
                form.instance.client = client
            except Client.DoesNotExist:
                client = create_client_for_user(self.request.user)
                form.instance.client = client

        # Генерация номера счета, если не указан
        if not form.instance.account_number:
            timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
            random_part = ''.join(str(i) for i in range(10))
            form.instance.account_number = f"ACC{timestamp}{random_part[:6]}"

        response = super().form_valid(form)
        messages.success(self.request, f'Счет №{self.object.account_number} успешно создан')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)


class AccountUpdateView(LoginRequiredMixin, EmployeeOrAdminRequiredMixin, UpdateView):
    """Редактирование счета - классовая версия"""
    template_name = 'accounts/account_form.html'
    context_object_name = 'account'

    def get_form_class(self):
        return get_account_form()

    def get_queryset(self):
        Account = get_account_model()
        return Account.objects.all().select_related('client', 'client__user', 'currency')

    def get_success_url(self):
        return reverse_lazy('accounts:account_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Счет №{self.object.account_number} успешно обновлен')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)


class AccountDeleteView(LoginRequiredMixin, AdminRequiredMixin, DeleteView):
    """Удаление счета - классовая версия"""
    template_name = 'accounts/account_confirm_delete.html'
    success_url = reverse_lazy('accounts:account_list')

    def get_queryset(self):
        Account = get_account_model()
        return Account.objects.all().select_related('client', 'client__user', 'currency')

    def delete(self, request, *args, **kwargs):
        account = self.get_object()
        messages.success(request, f'Счет №{account.account_number} успешно удален')
        return super().delete(request, *args, **kwargs)


# Существующие функциональные представления (остаются без изменений для совместимости)

@login_required
def account_list_old(request):
    """Список счетов - функциональная версия"""
    Account = get_account_model()

    if request.user.role == 'client':
        # Клиенты видят только свои счета
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            accounts = client.accounts.all()
        except:
            # Если клиента нет, создаем его
            client = create_client_for_user(request.user)
            accounts = client.accounts.all()
            messages.warning(request, 'Ваш профиль клиента был автоматически создан.')
    else:
        # Сотрудники и админы видят все счета
        accounts = Account.objects.all()

    # Фильтрация
    status = request.GET.get('status')
    if status:
        accounts = accounts.filter(status=status)

    currency = request.GET.get('currency')
    if currency:
        accounts = accounts.filter(currency__code=currency)

    search_query = request.GET.get('search')
    if search_query:
        accounts = accounts.filter(
            models.Q(account_number__icontains=search_query) |
            models.Q(client__full_name__icontains=search_query)
        )

    # Пагинация
    paginator = Paginator(accounts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Статистика
    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

    return render(request, 'accounts/account_list.html', {
        'page_obj': page_obj,
        'user_role': request.user.role,
        'total_balance': total_balance,
        'status': status,
        'currency': currency,
        'search_query': search_query
    })


@login_required
def account_detail_old(request, pk):
    """Детальная информация о счете - функциональная версия"""
    Account = get_account_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            if account.client != client:
                messages.error(request, 'У вас нет доступа к этому счету')
                return redirect('accounts:account_list')
        except:
            messages.error(request, 'У вас нет доступа к этому счету')
            return redirect('accounts:account_list')

    # Получаем транзакции по счету
    Transaction = get_transaction_model()
    try:
        transactions = Transaction.objects.filter(
            models.Q(from_account=account) | models.Q(to_account=account)
        ).select_related('from_account', 'to_account', 'currency').order_by('-created_at')[:20]
    except:
        transactions = []

    return render(request, 'accounts/account_detail.html', {
        'account': account,
        'transactions': transactions
    })


@login_required
def account_create_old(request):
    """Создание нового счета - функциональная версия"""
    AccountForm = get_account_form()
    Client = get_client_model()

    if request.method == 'POST':
        form = AccountForm(request.POST)
        if form.is_valid():
            account = form.save()

            # Генерация номера счета, если не указан
            if not account.account_number:
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
                account.account_number = f"ACC{timestamp}"
                account.save()

            messages.success(request, f'Счет №{account.account_number} успешно создан')
            return redirect('accounts:account_list')
    else:
        form = AccountForm()

    # Для сотрудников и администраторов добавляем список клиентов
    clients = Client.objects.all()

    return render(request, 'accounts/account_form.html', {
        'form': form,
        'clients': clients
    })


@login_required
@employee_required
def account_update_old(request, pk):
    """Редактирование счета - функциональная версия"""
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

    return render(request, 'accounts/account_form.html', {
        'form': form,
        'account': account
    })


@login_required
def account_close(request, pk):
    """Закрытие счета"""
    Account = get_account_model()
    account = get_object_or_404(Account, pk=pk)

    if request.method == 'POST':
        # Проверяем, что счет пуст
        if account.balance > Decimal('0.00'):
            messages.error(request, 'Нельзя закрыть счет с положительным балансом')
            return redirect('accounts:account_detail', pk=account.pk)

        account.status = 'closed'
        account.closed_at = datetime.now()
        account.save()

        messages.success(request, 'Счет успешно закрыт')
        return redirect('accounts:account_list')

    return render(request, 'accounts/account_confirm_close.html', {'account': account})


@login_required
def account_transactions(request, pk):
    """Транзакции по счету"""
    Account = get_account_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            if account.client != client:
                messages.error(request, 'У вас нет доступа к транзакциям этого счета')
                return redirect('accounts:account_list')
        except:
            messages.error(request, 'У вас нет доступа к транзакциям этого счета')
            return redirect('accounts:account_list')

    # Получаем транзакции
    Transaction = get_transaction_model()
    try:
        transactions = Transaction.objects.filter(
            models.Q(from_account=account) | models.Q(to_account=account)
        ).select_related('from_account', 'to_account', 'currency').order_by('-created_at')

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
        paginator = Paginator(transactions, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

    except Exception as e:
        page_obj = None
        messages.error(request, f'Ошибка при загрузке транзакций: {e}')

    return render(request, 'accounts/account_transactions.html', {
        'account': account,
        'page_obj': page_obj,
        'transaction_type': transaction_type,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
def account_deposit(request, pk):
    """Пополнение счета"""
    Account = get_account_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            if account.client != client:
                messages.error(request, 'У вас нет доступа к этому счету')
                return redirect('accounts:account_list')
        except:
            messages.error(request, 'У вас нет доступа к этому счету')
            return redirect('accounts:account_list')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        description = request.POST.get('description', 'Пополнение счета')

        try:
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                messages.error(request, 'Сумма должна быть положительной')
                return redirect('accounts:account_deposit', pk=account.pk)

            # Создаем транзакцию пополнения
            Transaction = get_transaction_model()
            try:
                transaction = Transaction.objects.create(
                    from_account=None,
                    to_account=account,
                    amount=amount_decimal,
                    currency=account.currency,
                    transaction_type='deposit',
                    status='completed',
                    description=description,
                    created_at=datetime.now()
                )

                # Обновляем баланс счета
                account.balance += amount_decimal
                account.save()

                messages.success(request, f'Счет успешно пополнен на {amount_decimal} {account.currency.code}')
                return redirect('accounts:account_detail', pk=account.pk)
            except Exception as e:
                messages.error(request, f'Ошибка при создании транзакции: {e}')
        except ValueError:
            messages.error(request, 'Неверный формат суммы')

    return render(request, 'accounts/deposit_form.html', {'account': account})


@login_required
def account_withdraw(request, pk):
    """Снятие со счета"""
    Account = get_account_model()

    account = get_object_or_404(Account, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client':
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            if account.client != client:
                messages.error(request, 'У вас нет доступа к этому счету')
                return redirect('accounts:account_list')
        except:
            messages.error(request, 'У вас нет доступа к этому счету')
            return redirect('accounts:account_list')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        description = request.POST.get('description', 'Снятие со счета')

        try:
            amount_decimal = Decimal(amount)
            if amount_decimal <= 0:
                messages.error(request, 'Сумма должна быть положительной')
                return redirect('accounts:account_withdraw', pk=account.pk)

            if amount_decimal > account.balance:
                messages.error(request, 'Недостаточно средств на счете')
                return redirect('accounts:account_withdraw', pk=account.pk)

            # Создаем транзакцию снятия
            Transaction = get_transaction_model()
            try:
                transaction = Transaction.objects.create(
                    from_account=account,
                    to_account=None,
                    amount=amount_decimal,
                    currency=account.currency,
                    transaction_type='withdrawal',
                    status='completed',
                    description=description,
                    created_at=datetime.now()
                )

                # Обновляем баланс счета
                account.balance -= amount_decimal
                account.save()

                messages.success(request, f'Со счета снято {amount_decimal} {account.currency.code}')
                return redirect('accounts:account_detail', pk=account.pk)
            except Exception as e:
                messages.error(request, f'Ошибка при создании транзакции: {e}')
        except ValueError:
            messages.error(request, 'Неверный формат суммы')

    return render(request, 'accounts/withdraw_form.html', {'account': account})


@login_required
def account_transfer(request):
    """Перевод между счетами"""
    Account = get_account_model()

    # Получаем параметр from_account из GET-запроса
    from_account_id = request.GET.get('from_account')
    from_account = None

    if from_account_id:
        try:
            if request.user.role == 'client':
                Client = get_client_model()
                client = Client.objects.get(user=request.user)
                from_account = Account.objects.get(id=from_account_id, client=client, status='active')
            else:
                from_account = Account.objects.get(id=from_account_id, status='active')
        except Account.DoesNotExist:
            from_account = None
            messages.warning(request, 'Указанный счет не найден или недоступен')

    # Получаем доступные счета для текущего пользователя
    if request.user.role == 'client':
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            accounts = client.accounts.filter(status='active')
        except Client.DoesNotExist:
            accounts = Account.objects.none()
            messages.warning(request, 'У вас нет доступных счетов')
    else:
        accounts = Account.objects.filter(status='active')

    if request.method == 'POST':
        from_account_id = request.POST.get('from_account')
        to_account_id = request.POST.get('to_account')
        amount = request.POST.get('amount')
        description = request.POST.get('description', 'Перевод между счетами')

        try:
            from_account = Account.objects.get(id=from_account_id)
            to_account = Account.objects.get(id=to_account_id)
            amount_decimal = Decimal(amount)

            # Проверка прав доступа
            if request.user.role == 'client':
                try:
                    Client = get_client_model()
                    client = Client.objects.get(user=request.user)
                    client_accounts = Account.objects.filter(client=client)

                    if from_account not in client_accounts:
                        messages.error(request, 'У вас нет доступа к счету отправителя')
                        return redirect('accounts:account_transfer')
                except:
                    messages.error(request, 'У вас нет доступа к этому счету')
                    return redirect('accounts:account_transfer')

            # Проверка суммы
            if amount_decimal <= 0:
                messages.error(request, 'Сумма должна быть положительной')
                return redirect('accounts:account_transfer')

            if from_account.balance < amount_decimal:
                messages.error(request, 'Недостаточно средств на счете отправителя')
                return redirect('accounts:account_transfer')

            # Проверка валюты
            if from_account.currency != to_account.currency:
                messages.error(request, 'Перевод возможен только между счетами в одной валюте')
                return redirect('accounts:account_transfer')

            # Создаем транзакцию
            Transaction = get_transaction_model()
            try:
                transaction = Transaction.objects.create(
                    from_account=from_account,
                    to_account=to_account,
                    amount=amount_decimal,
                    currency=from_account.currency,
                    transaction_type='transfer',
                    status='completed',
                    description=description,
                    created_at=datetime.now()
                )

                # Обновляем балансы счетов
                from_account.balance -= amount_decimal
                from_account.save()

                to_account.balance += amount_decimal
                to_account.save()

                messages.success(request,
                                 f'Перевод на сумму {amount_decimal} {from_account.currency.code} выполнен успешно')
                return redirect('accounts:account_detail', pk=from_account.pk)
            except Exception as e:
                messages.error(request, f'Ошибка при выполнении перевода: {e}')
        except Account.DoesNotExist:
            messages.error(request, 'Один из счетов не найден')
        except ValueError:
            messages.error(request, 'Неверный формат суммы')

    # Передаем from_account в контекст, даже если он None
    return render(request, 'accounts/transfer_form.html', {
        'accounts': accounts,
        'from_account': from_account  # Добавляем from_account в контекст
    })


@login_required
@employee_required
def currency_list(request):
    """Список валют"""
    Currency = get_currency_model()
    currencies = Currency.objects.all()
    return render(request, 'accounts/currency_list.html', {'currencies': currencies})


@login_required
def account_statistics(request):
    """Статистика по счетам"""
    Account = get_account_model()

    if request.user.role == 'client':
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            accounts = client.accounts.all()
        except:
            accounts = Account.objects.none()
    else:
        accounts = Account.objects.all()

    # Общая статистика
    total_balance = accounts.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
    avg_balance = accounts.aggregate(avg=Avg('balance'))['avg'] or Decimal('0.00')
    total_accounts = accounts.count()

    # Статистика по статусам
    status_stats = accounts.values('status').annotate(
        count=Count('id'),
        total_balance=Sum('balance')
    )

    # Статистика по валютам
    currency_stats = accounts.values('currency__code', 'currency__name').annotate(
        count=Count('id'),
        total_balance=Sum('balance')
    )

    return render(request, 'accounts/account_statistics.html', {
        'total_balance': total_balance,
        'avg_balance': avg_balance,
        'total_accounts': total_accounts,
        'status_stats': status_stats,
        'currency_stats': currency_stats,
        'user_role': request.user.role
    })


@login_required
@employee_required
def export_accounts_csv(request):
    """Экспорт счетов в CSV"""
    Account = get_account_model()
    accounts = Account.objects.all().select_related('client', 'currency')

    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = 'attachment; filename="accounts.csv"'

    # Пишем BOM для корректного отображения кириллицы в Excel
    response.write('\ufeff')

    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Номер счета', 'Клиент', 'Баланс', 'Валюта', 'Статус', 'Дата открытия', 'Дата закрытия'])

    for account in accounts:
        writer.writerow([
            account.account_number,
            account.client.full_name if account.client else '',
            str(account.balance),
            account.currency.code if account.currency else '',
            account.get_status_display(),
            account.created_at.strftime('%Y-%m-%d'),
            account.closed_at.strftime('%Y-%m-%d') if account.closed_at else ''
        ])

    return response


@login_required
def account_chart_data(request):
    """Данные для графиков по счетам (JSON API)"""
    Account = get_account_model()

    if request.user.role == 'client':
        try:
            Client = get_client_model()
            client = Client.objects.get(user=request.user)
            accounts = client.accounts.all()
        except:
            accounts = Account.objects.none()
    else:
        accounts = Account.objects.all()

    # Данные для графика распределения по валютам
    currency_data = accounts.values('currency__code').annotate(
        total=Sum('balance'),
        count=Count('id')
    ).order_by('-total')

    # Данные для графика распределения по статусам
    status_data = accounts.values('status').annotate(
        count=Count('id')
    ).order_by('status')

    # Данные для графика динамики открытия счетов
    timeline_data = accounts.extra(
        select={'month': "DATE_TRUNC('month', created_at)"}
    ).values('month').annotate(
        count=Count('id')
    ).order_by('month')

    data = {
        'currency_data': list(currency_data),
        'status_data': list(status_data),
        'timeline_data': list(timeline_data),
    }

    return JsonResponse(data, safe=False)