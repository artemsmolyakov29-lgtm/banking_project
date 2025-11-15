from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.csrf import csrf_protect
from django.contrib.auth import get_user_model
from django.apps import apps

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

    if user.role == 'client':
        # Дашборд для клиента
        try:
            client = user.client_profile
            accounts = client.accounts.filter(status='active')[:5] if hasattr(client, 'accounts') else []
            credits = client.credits.filter(status='active')[:5] if hasattr(client, 'credits') else []
            deposits = client.deposits.filter(status='active')[:5] if hasattr(client, 'deposits') else []

            context.update({
                'client': client,
                'accounts': accounts,
                'credits': credits,
                'deposits': deposits,
                'total_balance': 0,
                'products_count': {
                    'accounts': len(accounts),
                    'credits': len(credits),
                    'deposits': len(deposits),
                    'total': len(accounts) + len(credits) + len(deposits)
                },
            })
        except Exception as e:
            messages.error(request, f'Ошибка загрузки данных клиента: {str(e)}')

        template = 'users/dashboard_client.html'

    elif user.role in ['employee', 'admin']:
        # Дашборд для сотрудника и администратора
        try:
            Client = apps.get_model('clients', 'Client')
            Account = apps.get_model('accounts', 'Account')
            Credit = apps.get_model('credits', 'Credit')

            context.update({
                'total_clients': Client.objects.count(),
                'total_accounts': Account.objects.filter(status='active').count(),
                'active_credits': Credit.objects.filter(status='active').count(),
                'recent_clients': Client.objects.order_by('-created_at')[:5],
            })

            if user.role == 'admin':
                context['total_users'] = User.objects.count()
                context['recent_users'] = User.objects.order_by('-date_joined')[:5]

        except Exception as e:
            messages.error(request, f'Ошибка загрузки данных: {str(e)}')

        template = 'users/dashboard_employee.html'

    else:
        template = 'users/dashboard.html'

    return render(request, template, context)


@login_required
def profile_view(request):
    """
    Просмотр и редактирование профиля пользователя
    """
    user = request.user
    client = getattr(user, 'client_profile', None)

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