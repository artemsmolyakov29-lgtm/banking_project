from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.apps import apps
from django.http import HttpResponseForbidden


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


@login_required
def credit_list(request):
    """Список кредитов"""
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
def credit_detail(request, pk):
    """Детальная информация о кредите"""
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
def credit_payment(request, pk):
    """Внесение платежа по кредиту"""
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