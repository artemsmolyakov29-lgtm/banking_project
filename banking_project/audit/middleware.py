from django.utils.deprecation import MiddlewareMixin
from django.apps import apps


class AuditMiddleware(MiddlewareMixin):
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Пропускаем статические файлы и админку
        if request.path.startswith('/static/') or request.path.startswith('/admin/'):
            return self.get_response(request)

        response = self.get_response(request)

        # Логируем действия, требующие изменения данных
        if request.method in ['POST', 'PUT', 'DELETE'] and request.user.is_authenticated:
            try:
                # Ленивая загрузка модели AuditLog
                AuditLog = apps.get_model('audit', 'AuditLog')
                action = f"{request.method} {request.path}"
                AuditLog.objects.create(
                    user=request.user,
                    action=action,
                    table_name='unknown',
                    record_id=0
                )
            except Exception:
                pass  # Игнорируем ошибки логирования

        return response