from django.shortcuts import redirect
from django.http import HttpResponseForbidden
from django.urls import reverse
from django.apps import apps


class ClientRequiredMixin:
    """
    Миксин для проверки наличия Client у пользователя
    и автоматического создания при необходимости
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')

        # Получаем модель Client
        Client = apps.get_model('clients', 'Client')

        # Для пользователей с ролью 'client'
        if request.user.role == 'client':
            try:
                request.user.client_profile
            except Client.DoesNotExist:
                # Создаем Client для пользователя
                from .signals import create_client_profile
                create_client_profile(Client, request.user, created=True)

        # Для сотрудников и администраторов тоже нужен Client для работы с системой
        elif request.user.role in ['employee', 'admin']:
            try:
                request.user.client_profile
            except Client.DoesNotExist:
                # Создаем Client для сотрудника/администратора
                from .signals import create_client_for_employee_or_admin
                create_client_for_employee_or_admin(Client, request.user, created=True)

        return super().dispatch(request, *args, **kwargs)


class RoleRequiredMixin:
    """
    Миксин для проверки ролей пользователя
    """
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')

        if request.user.role not in self.allowed_roles:
            return HttpResponseForbidden("У вас нет доступа к этой странице.")

        return super().dispatch(request, *args, **kwargs)


class ClientAccessMixin:
    """
    Миксин для проверки доступа клиента к своему профилю
    """

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')

        # Если пользователь - клиент, проверяем, что он обращается к своему профилю
        if request.user.role == 'client':
            pk = kwargs.get('pk')
            if pk and str(pk) != str(request.user.pk):
                return HttpResponseForbidden("У вас нет доступа к этому профилю.")

        return super().dispatch(request, *args, **kwargs)


class EmployeeOrAdminRequiredMixin(RoleRequiredMixin):
    """
    Миксин для требований сотрудника или администратора
    """
    allowed_roles = ['employee', 'admin']


class AdminRequiredMixin(RoleRequiredMixin):
    """
    Миксин для требований администратора
    """
    allowed_roles = ['admin']