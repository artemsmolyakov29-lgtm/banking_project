from django.http import HttpResponseForbidden
from django.contrib.auth.decorators import user_passes_test
from functools import wraps
from .models import UserRole


def role_required(allowed_roles):
    """
    Декоратор для проверки ролей пользователя
    Использование: @role_required([UserRole.ADMIN, UserRole.EMPLOYEE])
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
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
    return role_required([UserRole.CLIENT])(view_func)


def employee_required(view_func):
    """
    Декоратор для доступа только сотрудникам
    """
    return role_required([UserRole.EMPLOYEE, UserRole.ADMIN])(view_func)


def admin_required(view_func):
    """
    Декоратор для доступа только администраторам
    """
    return role_required([UserRole.ADMIN])(view_func)


def check_client_ownership(model_class, id_parameter='pk'):
    """
    Декоратор для проверки, что клиент имеет доступ только к своим данным
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            if request.user.role != UserRole.CLIENT:
                return view_func(request, *args, **kwargs)

            obj_id = kwargs.get(id_parameter)
            try:
                obj = model_class.objects.get(id=obj_id)
                # Проверяем, принадлежит ли объект клиенту
                if hasattr(obj, 'client') and obj.client.user == request.user:
                    return view_func(request, *args, **kwargs)
                else:
                    return HttpResponseForbidden("У вас нет доступа к этому объекту.")
            except model_class.DoesNotExist:
                return HttpResponseForbidden("Объект не найден.")

        return wrapper

    return decorator