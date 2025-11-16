from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.apps import apps
from django.http import HttpResponseForbidden
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.core.paginator import Paginator
from decimal import Decimal
from datetime import datetime, timedelta


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_credit_model():
    """Ленивая загрузка модели Credit"""
    return apps.get_model('credits', 'Credit')


def get_credit_product_model():
    """Ленивая загрузка модели CreditProduct"""
    return apps.get_model('credits', 'CreditProduct')


def get_credit_payment_model():
    """Ленивая загрузка модели CreditPayment"""
    return apps.get_model('credits', 'CreditPayment')


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
class CreditListView(LoginRequiredMixin, ListView):
    """Список кредитов - классовая версия"""
    template_name = 'credits/credit_list.html'
    context_object_name = 'credits'
    paginate_by = 20

    def get_queryset(self):
        Credit = get_credit_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            # Клиенты видят только свои кредиты
            client = get_object_or_404(Client, user=self.request.user)
            credits = client.credits.all()
        else:
            # Сотрудники и админы видят все кредиты
            credits = Credit.objects.all()

        return credits.select_related('client', 'client__user').order_by('-created_at')


class CreditDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о кредите - классовая версия"""
    template_name = 'credits/credit_detail.html'
    context_object_name = 'credit'

    def get_queryset(self):
        Credit = get_credit_model()
        Client = get_client_model()

        if self.request.user.role == 'client':
            client = get_object_or_404(Client, user=self.request.user)
            return Credit.objects.filter(client=client).select_related('client', 'client__user')
        return Credit.objects.all().select_related('client', 'client__user')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        credit = self.object

        # Добавляем информацию о следующем платеже
        context['next_payment_amount'] = credit.calculate_next_payment()
        context['penalty_amount'] = credit.calculate_penalty()
        context['total_due'] = context['next_payment_amount'] + context['penalty_amount']
        context['can_early_repay'] = credit.can_make_early_repayment()
        context['early_repayment_amount'] = credit.calculate_early_repayment()

        # Последние 5 платежей
        context['recent_payments'] = credit.payments.all().order_by('-payment_date')[:5]

        return context

    def get(self, request, *args, **kwargs):
        credit = self.get_object()
        if request.user.role == 'client' and credit.client.user != request.user:
            messages.error(request, 'У вас нет доступа к этому кредиту')
            return redirect('credits:credit_list')
        return super().get(request, *args, **kwargs)


class CreditCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """Создание нового кредита - классовая версия"""
    template_name = 'credits/credit_form.html'
    success_url = reverse_lazy('credits:credit_list')
    allowed_roles = ['employee', 'admin']

    def get_form_class(self):
        from .forms import CreditForm
        return CreditForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Кредит для {self.object.client.full_name} успешно создан')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)


class CreditUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """Редактирование кредита - классовая версия"""
    template_name = 'credits/credit_form.html'
    context_object_name = 'credit'
    allowed_roles = ['employee', 'admin']

    def get_queryset(self):
        Credit = get_credit_model()
        return Credit.objects.all().select_related('client', 'client__user')

    def get_form_class(self):
        from .forms import CreditForm
        return CreditForm

    def get_success_url(self):
        return reverse_lazy('credits:credit_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Кредит успешно обновлен')
        return response


class CreditDeleteView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    """Удаление кредита - классовая версия"""
    template_name = 'credits/credit_confirm_delete.html'
    success_url = reverse_lazy('credits:credit_list')
    allowed_roles = ['admin']

    def get_queryset(self):
        Credit = get_credit_model()
        return Credit.objects.all().select_related('client', 'client__user')

    def delete(self, request, *args, **kwargs):
        credit = self.get_object()
        messages.success(request, f'Кредит успешно удален')
        return super().delete(request, *args, **kwargs)


# НОВЫЕ ПРЕДСТАВЛЕНИЯ ДЛЯ ПЛАТЕЖЕЙ ПО КРЕДИТАМ

@login_required
def credit_payment_view(request, pk):
    """Внесение платежа по кредиту"""
    Credit = get_credit_model()
    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому кредиту')
        return redirect('credits:credit_list')

    if request.method == 'POST':
        from .forms import CreditPaymentForm
        form = CreditPaymentForm(request.POST, credit=credit, user=request.user)
        if form.is_valid():
            success, message = form.save()
            if success:
                messages.success(request, message)
                return redirect('credits:payment_success', pk=credit.pk)
            else:
                messages.error(request, message)
    else:
        from .forms import CreditPaymentForm
        form = CreditPaymentForm(credit=credit, user=request.user)

    return render(request, 'credits/credit_payment.html', {
        'credit': credit,
        'form': form,
        'next_payment_amount': credit.calculate_next_payment(),
        'penalty_amount': credit.calculate_penalty(),
        'total_due': credit.calculate_next_payment() + credit.calculate_penalty()
    })


@login_required
def early_repayment_view(request, pk):
    """Досрочное погашение кредита"""
    Credit = get_credit_model()
    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому кредиту')
        return redirect('credits:credit_list')

    # Проверка возможности досрочного погашения
    if not credit.can_make_early_repayment():
        messages.error(request, 'Досрочное погашение для этого кредита не разрешено')
        return redirect('credits:credit_detail', pk=credit.pk)

    if request.method == 'POST':
        from .forms import EarlyRepaymentForm
        form = EarlyRepaymentForm(request.POST, credit=credit, user=request.user)
        if form.is_valid():
            success, message = form.save()
            if success:
                messages.success(request, message)
                return redirect('credits:payment_success', pk=credit.pk)
            else:
                messages.error(request, message)
    else:
        from .forms import EarlyRepaymentForm
        form = EarlyRepaymentForm(credit=credit, user=request.user)

    return render(request, 'credits/early_repayment.html', {
        'credit': credit,
        'form': form,
        'early_repayment_amount': credit.calculate_early_repayment()
    })


@login_required
def payment_history_view(request, pk):
    """История платежей по кредиту"""
    Credit = get_credit_model()
    CreditPayment = get_credit_payment_model()

    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к платежам этого кредита')
        return redirect('credits:credit_list')

    payments = credit.payments.all().select_related('transaction').order_by('-payment_date')

    # Фильтрация
    status_filter = request.GET.get('status')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    if status_filter:
        payments = payments.filter(status=status_filter)
    if date_from:
        payments = payments.filter(payment_date__gte=date_from)
    if date_to:
        payments = payments.filter(payment_date__lte=date_to)

    # Пагинация
    paginator = Paginator(payments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'credits/payment_history.html', {
        'credit': credit,
        'page_obj': page_obj,
        'payments_count': payments.count(),
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
def payment_schedule_view(request, pk):
    """График платежей по кредиту с фильтрацией"""
    Credit = get_credit_model()
    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к графику платежей этого кредита')
        return redirect('credits:credit_list')

    from .forms import PaymentScheduleFilterForm
    form = PaymentScheduleFilterForm(request.GET or None)

    schedule = credit.generate_payment_schedule() if hasattr(credit, 'generate_payment_schedule') else []

    # Применяем фильтры к графику
    filtered_schedule = schedule
    if form.is_valid():
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')
        status_filter = form.cleaned_data.get('status')

        if date_from:
            filtered_schedule = [p for p in filtered_schedule if p['payment_date'] >= date_from]
        if date_to:
            filtered_schedule = [p for p in filtered_schedule if p['payment_date'] <= date_to]

        # Для статуса используем реальные платежи
        if status_filter:
            actual_payments = credit.payments.filter(status=status_filter).values_list('payment_number', flat=True)
            filtered_schedule = [p for p in filtered_schedule if p['payment_number'] in actual_payments]

    return render(request, 'credits/payment_schedule.html', {
        'credit': credit,
        'schedule': filtered_schedule,
        'form': form,
        'total_schedule': schedule
    })


@login_required
def payment_success(request, pk):
    """Страница успешного платежа"""
    Credit = get_credit_model()
    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому кредиту')
        return redirect('credits:credit_list')

    # Получаем последний платеж
    last_payment = credit.payments.last()

    return render(request, 'credits/payment_success.html', {
        'credit': credit,
        'last_payment': last_payment
    })


@login_required
def calculate_penalty_view(request, pk):
    """Расчет штрафов за просрочку"""
    Credit = get_credit_model()
    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому кредиту')
        return redirect('credits:credit_list')

    penalty_amount = credit.calculate_penalty()

    return render(request, 'credits/calculate_penalty.html', {
        'credit': credit,
        'penalty_amount': penalty_amount,
        'overdue_days': credit.overdue_days,
        'overdue_amount': credit.overdue_amount
    })


# Существующие функциональные представления (оставляем без изменений)
@login_required
def credit_list_old(request):
    """Список кредитов - старая версия"""
    User = get_user_model()
    Client = get_client_model()
    Credit = get_credit_model()

    if request.user.role == 'client':
        # Клиенты видят только свои кредиты
        client = get_object_or_404(Client, user=request.user)
        credits = client.credits.all()
    else:
        # Сотрудники и админы видят все кредиты
        credits = Credit.objects.all()

    return render(request, 'credits/credit_list.html', {'credits': credits})


@login_required
def credit_products(request):
    """Список кредитных продуктов"""
    CreditProduct = get_credit_product_model()
    products = CreditProduct.objects.filter(is_active=True)
    return render(request, 'credits/credit_products.html', {'products': products})


@login_required
def credit_apply(request):
    """Подача заявки на кредит"""
    Client = get_client_model()
    CreditProduct = get_credit_product_model()

    if request.user.role == 'client':
        client = get_object_or_404(Client, user=request.user)
    else:
        client = None

    if request.method == 'POST':
        # Здесь будет логика подачи заявки на кредит
        messages.success(request, 'Заявка на кредит успешно подана')
        return redirect('credits:credit_list')

    products = CreditProduct.objects.filter(is_active=True)
    return render(request, 'credits/credit_apply.html', {
        'client': client,
        'products': products
    })


@login_required
def credit_detail_old(request, pk):
    """Детальная информация о кредите - старая версия"""
    Credit = get_credit_model()
    Client = get_client_model()
    User = get_user_model()

    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому кредиту')
        return redirect('credits:credit_list')

    # Расчет графика платежей
    payment_schedule = credit.generate_payment_schedule() if hasattr(credit, 'generate_payment_schedule') else []

    return render(request, 'credits/credit_detail.html', {
        'credit': credit,
        'payment_schedule': payment_schedule
    })


@login_required
def credit_payments(request, pk):
    """Платежи по кредиту"""
    Credit = get_credit_model()
    CreditPayment = get_credit_payment_model()

    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к платежам этого кредита')
        return redirect('credits:credit_list')

    payments = credit.payments.all()
    return render(request, 'credits/credit_payments.html', {
        'credit': credit,
        'payments': payments
    })


@login_required
def credit_payment_old(request, pk):
    """Внесение платежа по кредиту - старая версия"""
    Credit = get_credit_model()
    CreditPayment = get_credit_payment_model()
    Account = get_account_model()

    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к этому кредиту')
        return redirect('credits:credit_list')

    if request.method == 'POST':
        amount = request.POST.get('amount')
        # Здесь будет логика обработки платежа
        messages.success(request, f'Платеж на сумму {amount} успешно внесен')
        return redirect('credits:credit_detail', pk=credit.pk)

    return render(request, 'credits/credit_payment_form.html', {'credit': credit})


@login_required
def credit_schedule(request, pk):
    """График платежей по кредиту"""
    Credit = get_credit_model()

    credit = get_object_or_404(Credit, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and credit.client.user != request.user:
        messages.error(request, 'У вас нет доступа к графику платежей этого кредита')
        return redirect('credits:credit_list')

    schedule = credit.generate_payment_schedule() if hasattr(credit, 'generate_payment_schedule') else []

    return render(request, 'credits/credit_schedule.html', {
        'credit': credit,
        'schedule': schedule
    })


@login_required
@employee_required
def credit_collaterals(request, pk):
    """Залоговое имущество по кредиту"""
    Credit = get_credit_model()

    credit = get_object_or_404(Credit, pk=pk)
    collaterals = credit.collaterals.all() if hasattr(credit, 'collaterals') else []

    return render(request, 'credits/credit_collaterals.html', {
        'credit': credit,
        'collaterals': collaterals
    })


@login_required
@employee_required
def credit_approve(request, pk):
    """Одобрение кредита сотрудником"""
    Credit = get_credit_model()
    User = get_user_model()

    credit = get_object_or_404(Credit, pk=pk)

    if request.method == 'POST':
        credit.status = 'approved'
        credit.approved_by = request.user
        credit.save()
        messages.success(request, 'Кредит успешно одобрен')
        return redirect('credits:credit_detail', pk=credit.pk)

    return render(request, 'credits/credit_approve.html', {'credit': credit})


@login_required
@employee_required
def credit_reject(request, pk):
    """Отклонение кредита сотрудником"""
    Credit = get_credit_model()

    credit = get_object_or_404(Credit, pk=pk)

    if request.method == 'POST':
        reason = request.POST.get('reason', '')
        credit.status = 'rejected'
        credit.rejection_reason = reason
        credit.save()
        messages.success(request, 'Кредит отклонен')
        return redirect('credits:credit_detail', pk=credit.pk)

    return render(request, 'credits/credit_reject.html', {'credit': credit})