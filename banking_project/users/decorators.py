from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from functools import wraps
from django.apps import apps


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def role_required(allowed_roles):
    """
    Декоратор для проверки ролей пользователя
    Использование: @role_required(['admin', 'employee'])
    """

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


def client_required(view_func):
    """
    Декоратор для доступа только клиентам
    """
    return role_required(['client'])(view_func)


def employee_required(view_func):
    """
    Декоратор для доступа только сотрудникам
    """
    return role_required(['employee', 'admin'])(view_func)


def admin_required(view_func):
    """
    Декоратор для доступа только администраторам
    """
    return role_required(['admin'])(view_func)


def check_client_ownership(model_name, id_parameter='pk'):
    """
    Декоратор для проверки, что клиент имеет доступ только к своим данным
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            User = get_user_model()

            if request.user.role != 'client':
                return view_func(request, *args, **kwargs)

            # Ленивая загрузка модели
            Model = apps.get_model(model_name.split('.')[0], model_name.split('.')[1])
            obj_id = kwargs.get(id_parameter)

            try:
                obj = Model.objects.get(id=obj_id)
                # Проверяем, принадлежит ли объект клиенту
                if hasattr(obj, 'client') and obj.client.user == request.user:
                    return view_func(request, *args, **kwargs)
                else:
                    return HttpResponseForbidden("У вас нет доступа к этому объекту.")
            except Model.DoesNotExist:
                return HttpResponseForbidden("Объект не найден.")

        return wrapper

    return decorator