from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.apps import apps


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_client_model():
    """Ленивая загрузка модели Client"""
    return apps.get_model('clients', 'Client')


def get_employee_model():
    """Ленивая загрузка модели Employee"""
    return apps.get_model('users', 'Employee')


# Декораторы будем импортировать внутри функций или создавать локальные версии
def role_required(allowed_roles):
    """Локальная версия декоратора role_required"""
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


def employee_required(view_func):
    """Локальная версия декоратора employee_required"""
    return role_required(['employee', 'admin'])(view_func)


def admin_required(view_func):
    """Локальная версия декоратора admin_required"""
    return role_required(['admin'])(view_func)


@login_required
def client_list(request):
    """Список клиентов"""
    User = get_user_model()
    Client = get_client_model()

    if request.user.role == 'client':
        # Клиенты видят только свой профиль
        client = get_object_or_404(Client, user=request.user)
        return render(request, 'clients/client_detail.html', {'client': client})

    # Сотрудники и админы видят всех клиентов
    clients = Client.objects.all()
    return render(request, 'clients/client_list.html', {'clients': clients})


@login_required
@employee_required
def client_create(request):
    """Создание нового клиента"""
    if request.method == 'POST':
        # Здесь будет логика создания клиента
        messages.success(request, 'Клиент успешно создан')
        return redirect('clients:client_list')
    return render(request, 'clients/client_form.html')


@login_required
def client_detail(request, pk):
    """Детальная информация о клиенте"""
    Client = get_client_model()
    User = get_user_model()

    if request.user.role == 'client':
        # Клиенты могут видеть только свой профиль
        client = get_object_or_404(Client, user=request.user)
    else:
        # Сотрудники и админы могут видеть любого клиента
        client = get_object_or_404(Client, pk=pk)

    return render(request, 'clients/client_detail.html', {'client': client})


@login_required
@employee_required
def client_update(request, pk):
    """Редактирование клиента"""
    Client = get_client_model()
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        # Здесь будет логика обновления клиента
        messages.success(request, 'Данные клиента обновлены')
        return redirect('clients:client_detail', pk=client.pk)
    return render(request, 'clients/client_form.html', {'client': client})


@login_required
@employee_required
def client_delete(request, pk):
    """Удаление клиента"""
    Client = get_client_model()
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        client.delete()
        messages.success(request, 'Клиент успешно удален')
        return redirect('clients:client_list')
    return render(request, 'clients/client_confirm_delete.html', {'client': client})


@login_required
def client_documents(request, pk):
    """Документы клиента"""
    Client = get_client_model()
    client = get_object_or_404(Client, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and client.user != request.user:
        messages.error(request, 'У вас нет доступа к этим документам')
        return redirect('clients:client_list')

    documents = client.documents.all()
    return render(request, 'clients/client_documents.html', {
        'client': client,
        'documents': documents
    })


@login_required
def client_contacts(request, pk):
    """Контакты клиента"""
    Client = get_client_model()
    client = get_object_or_404(Client, pk=pk)

    # Проверка прав доступа
    if request.user.role == 'client' and client.user != request.user:
        messages.error(request, 'У вас нет доступа к этим контактам')
        return redirect('clients:client_list')

    contacts = client.contacts.all()
    return render(request, 'clients/client_contacts.html', {
        'client': client,
        'contacts': contacts
    })


@login_required
@employee_required
def client_search(request):
    """Поиск клиентов"""
    Client = get_client_model()
    query = request.GET.get('q', '')
    clients = Client.objects.filter(
        Q(full_name__icontains=query) |
        Q(inn__icontains=query) |
        Q(snils__icontains=query) |
        Q(passport_series__icontains=query) |
        Q(passport_number__icontains=query)
    )
    return render(request, 'clients/client_list.html', {
        'clients': clients,
        'search_query': query
    })