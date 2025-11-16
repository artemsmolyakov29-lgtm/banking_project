from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.apps import apps
from django.views.generic import ListView, CreateView, UpdateView, DetailView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden


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
class ClientListView(LoginRequiredMixin, RoleRequiredMixin, ListView):
    """Список клиентов - классовая версия"""
    template_name = 'clients/client_list.html'
    context_object_name = 'clients'
    paginate_by = 20
    allowed_roles = ['employee', 'admin']

    def get_queryset(self):
        Client = get_client_model()
        return Client.objects.select_related('user').all().order_by('-created_at')


class ClientDetailView(LoginRequiredMixin, DetailView):
    """Детальная информация о клиенте - классовая версия"""
    template_name = 'clients/client_detail.html'
    context_object_name = 'client'

    def get_queryset(self):
        Client = get_client_model()
        if self.request.user.role == 'client':
            return Client.objects.filter(user=self.request.user).select_related('user')
        return Client.objects.all().select_related('user')

    def get(self, request, *args, **kwargs):
        client = self.get_object()
        if request.user.role == 'client' and client.user != request.user:
            messages.error(request, 'У вас нет доступа к этому профилю')
            return redirect('clients:client_detail', pk=request.user.client.pk)
        return super().get(request, *args, **kwargs)


class ClientCreateView(LoginRequiredMixin, RoleRequiredMixin, CreateView):
    """Создание нового клиента - классовая версия"""
    template_name = 'clients/client_form.html'
    success_url = reverse_lazy('clients:client_list')
    allowed_roles = ['employee', 'admin']

    def get_form_class(self):
        from .forms import ClientForm
        return ClientForm

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Клиент {self.object.full_name} успешно создан')
        return response

    def form_invalid(self, form):
        messages.error(self.request, 'Пожалуйста, исправьте ошибки в форме')
        return super().form_invalid(form)


class ClientUpdateView(LoginRequiredMixin, RoleRequiredMixin, UpdateView):
    """Редактирование клиента - классовая версия"""
    template_name = 'clients/client_form.html'
    context_object_name = 'client'
    allowed_roles = ['employee', 'admin']

    def get_queryset(self):
        Client = get_client_model()
        return Client.objects.all().select_related('user')

    def get_form_class(self):
        from .forms import ClientForm
        return ClientForm

    def get_success_url(self):
        return reverse_lazy('clients:client_detail', kwargs={'pk': self.object.pk})

    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, f'Данные клиента {self.object.full_name} успешно обновлены')
        return response


class ClientDeleteView(LoginRequiredMixin, RoleRequiredMixin, DeleteView):
    """Удаление клиента - классовая версия"""
    template_name = 'clients/client_confirm_delete.html'
    success_url = reverse_lazy('clients:client_list')
    allowed_roles = ['admin']

    def get_queryset(self):
        Client = get_client_model()
        return Client.objects.all().select_related('user')

    def delete(self, request, *args, **kwargs):
        client = self.get_object()
        messages.success(request, f'Клиент {client.full_name} успешно удален')
        return super().delete(request, *args, **kwargs)


# Существующие функциональные представления (оставляем для обратной совместимости)
@login_required
def client_list_old(request):
    """Список клиентов - старая версия"""
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
def client_create_old(request):
    """Создание нового клиента - старая версия"""
    if request.method == 'POST':
        # Здесь будет логика создания клиента
        messages.success(request, 'Клиент успешно создан')
        return redirect('clients:client_list')
    return render(request, 'clients/client_form.html')


@login_required
def client_detail_old(request, pk):
    """Детальная информация о клиенте - старая версия"""
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
def client_update_old(request, pk):
    """Редактирование клиента - старая версия"""
    Client = get_client_model()
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        # Здесь будет логика обновления клиента
        messages.success(request, 'Данные клиента обновлены')
        return redirect('clients:client_detail', pk=client.pk)
    return render(request, 'clients/client_form.html', {'client': client})


@login_required
@employee_required
def client_delete_old(request, pk):
    """Удаление клиента - старая версия"""
    Client = get_client_model()
    client = get_object_or_404(Client, pk=pk)

    if request.method == 'POST':
        client.delete()
        messages.success(request, 'Клиент успешно удален')
        return redirect('clients:client_list')
    return render(request, 'clients/client_confirm_delete.html', {'client': client})


# Специальные представления (оставляем без изменений)
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