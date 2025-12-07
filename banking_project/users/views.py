from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import get_user_model
from django.apps import apps
from django.utils import timezone
from django.db.models import Sum, Q
from datetime import date, timedelta
from decimal import Decimal

User = get_user_model()


def get_form_class():
    """Ленивая загрузка форм для избежания циклических импортов"""
    from .forms import UserRegistrationForm, UserLoginForm
    return UserRegistrationForm, UserLoginForm


@csrf_protect
def register_view(request):
    """
    Обработка регистрации новых пользователей
    """
    if request.user.is_authenticated:
        return redirect('users:dashboard')

    UserRegistrationForm, _ = get_form_class()

    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                user = form.save()
                login(request, user)
                messages.success(request, 'Регистрация успешно завершена! Добро пожаловать в банковскую систему.')
                return redirect('users:dashboard')
            except Exception as e:
                messages.error(request, f'Произошла ошибка при регистрации: {str(e)}')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f'{field}: {error}')
    else:
        form = UserRegistrationForm()

    return render(request, 'users/register.html', {'form': form})


@csrf_protect
def login_view(request):
    """
    Обработка входа пользователей в систему
    """
    if request.user.is_authenticated:
        return redirect('users:dashboard')

    _, UserLoginForm = get_form_class()

    if request.method == 'POST':
        form = UserLoginForm(data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(request, username=username, password=password)

            if user is not None:
                login(request, user)
                messages.success(request, f'Добро пожаловать, {user.username}!')
                return redirect('users:dashboard')
            else:
                messages.error(request, 'Неверные учетные данные.')
        else:
            messages.error(request, 'Пожалуйста, исправьте ошибки в форме.')
    else:
        form = UserLoginForm()

    return render(request, 'users/login.html', {'form': form})


def logout_view(request):
    """
    Выход пользователя из системы
    """
    logout(request)
    messages.success(request, 'Вы успешно вышли из системы.')
    return redirect('users:login')


@login_required
def dashboard_view(request):
    """
    Главная страница системы - дашборд для разных ролей
    """
    user = request.user
    context = {}

    try:
        if user.role == 'client':
            # Дашборд для клиента
            Client = apps.get_model('clients', 'Client')
            Account = apps.get_model('accounts', 'Account')
            Transaction = apps.get_model('transactions', 'Transaction')
            Credit = apps.get_model('credits', 'Credit')
            Deposit = apps.get_model('deposits', 'Deposit')
            CreditPayment = apps.get_model('credits', 'CreditPayment')

            # Получаем клиента
            client = Client.objects.filter(user=user).first()

            if client:
                # Активные счета
                accounts = Account.objects.filter(client=client, status='active').order_by('-created_at')[:5]

                # Активные кредиты
                credits = Credit.objects.filter(client=client, status='active').order_by('-created_at')[:5]

                # Активные депозиты
                deposits = Deposit.objects.filter(client=client, status='active').order_by('-created_at')[:5]

                # Общий баланс по всем счетам
                total_balance = accounts.aggregate(total=Sum('balance'))['total'] or Decimal('0.00')

                # Последние транзакции
                account_ids = accounts.values_list('id', flat=True)
                recent_transactions = Transaction.objects.filter(
                    Q(from_account__in=account_ids) | Q(to_account__in=account_ids)
                ).order_by('-created_at')[:10]

                # Ближайшие платежи по кредитам
                credit_ids = credits.values_list('id', flat=True)
                credit_notifications = CreditPayment.objects.filter(
                    credit_id__in=credit_ids,
                    status='pending',
                    due_date__gte=timezone.now().date()
                ).order_by('due_date')[:5]

                context.update({
                    'client': client,
                    'accounts': accounts,
                    'credits': credits,
                    'deposits': deposits,
                    'total_balance': total_balance,
                    'recent_transactions': recent_transactions,
                    'credit_notifications': credit_notifications,
                    'active_credits': credits,
                    'products_count': {
                        'accounts': accounts.count(),
                        'credits': credits.count(),
                        'deposits': deposits.count(),
                        'total': accounts.count() + credits.count() + deposits.count()
                    },
                })

            template = 'users/dashboard_client.html'

        elif user.role in ['employee', 'admin']:
            # Дашборд для сотрудника и администратора
            Client = apps.get_model('clients', 'Client')
            Account = apps.get_model('accounts', 'Account')
            Transaction = apps.get_model('transactions', 'Transaction')
            Credit = apps.get_model('credits', 'Credit')
            CreditPayment = apps.get_model('credits', 'CreditPayment')

            # Статистика
            total_clients = Client.objects.count()
            total_accounts = Account.objects.filter(status='active').count()
            total_transactions = Transaction.objects.count()
            total_balance_result = Account.objects.filter(
                status='active'
            ).aggregate(total=Sum('balance'))
            total_balance = total_balance_result['total'] or Decimal('0.00')

            # Статистика по кредитам
            total_credits = Credit.objects.count()
            active_credits = Credit.objects.filter(status='active').count()
            overdue_credits = Credit.objects.filter(status='overdue').count()

            # Ближайшие платежи
            credit_notifications = CreditPayment.objects.filter(
                status='pending',
                due_date__gte=timezone.now().date()
            ).order_by('due_date')[:5]

            # Активные кредиты
            active_credits_list = Credit.objects.filter(
                status='active'
            ).order_by('-created_at')[:5]

            # Последние транзакции
            recent_transactions = Transaction.objects.all().order_by('-created_at')[:10]

            # Недавние клиенты
            recent_clients = Client.objects.order_by('-created_at')[:5]

            stats = {
                'total_clients': total_clients,
                'total_accounts': total_accounts,
                'total_transactions': total_transactions,
                'total_balance': total_balance,
            }

            credit_stats = {
                'total_credits': total_credits,
                'active_credits': active_credits,
                'overdue_credits': overdue_credits,
                'total_paid': 0,  # Здесь нужно добавить логику расчета
                'total_debt': 0,  # Здесь нужно добавить логику расчета
            }

            context.update({
                'stats': stats,
                'credit_stats': credit_stats,
                'credit_notifications': credit_notifications,
                'active_credits': active_credits_list,
                'recent_transactions': recent_transactions,
                'recent_clients': recent_clients,
                'notifications': [],  # Заглушка для уведомлений
            })

            if user.role == 'admin':
                context['total_users'] = User.objects.count()
                context['recent_users'] = User.objects.order_by('-date_joined')[:5]

            template = 'users/dashboard.html'  # Используем общий шаблон для сотрудников

        else:
            # Дефолтный шаблон для других ролей
            template = 'users/dashboard.html'

    except Exception as e:
        messages.error(request, f'Ошибка загрузки данных: {str(e)}')
        template = 'users/dashboard.html'

    return render(request, template, context)


@login_required
def profile_view(request):
    """
    Просмотр и редактирование профиля пользователя
    """
    user = request.user
    Client = apps.get_model('clients', 'Client')
    client = Client.objects.filter(user=user).first()

    if request.method == 'POST':
        user.email = request.POST.get('email', user.email)
        user.phone = request.POST.get('phone', user.phone)

        if client:
            client.full_name = request.POST.get('full_name', client.full_name)
            client.address = request.POST.get('address', client.address)
            client.save()

        user.save()
        messages.success(request, 'Профиль успешно обновлен.')
        return redirect('users:profile')

    context = {
        'user': user,
        'client': client,
    }
    return render(request, 'users/profile.html', context)