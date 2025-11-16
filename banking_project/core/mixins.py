from django.core.exceptions import PermissionDenied
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404


class RoleRequiredMixin:
    """Миксин для проверки ролей пользователя"""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if request.user.role not in self.allowed_roles:
            raise PermissionDenied("У вас нет прав для доступа к этой странице")
        return super().dispatch(request, *args, **kwargs)


class ClientAccessMixin:
    """Миксин для ограничения доступа клиентов только к своим данным"""

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.request.user.role == 'client':
            # Предполагается, что у Client есть связь с User через OneToOne
            return queryset.filter(user=self.request.user)
        return queryset

    def dispatch(self, request, *args, **kwargs):
        if request.user.role == 'client':
            obj = self.get_object()
            if obj.user != request.user:
                raise PermissionDenied("Вы можете просматривать только свои данные")
        return super().dispatch(request, *args, **kwargs)