from django.apps import AppConfig


class ClientsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'clients'

    def ready(self):
        """
        Регистрируем сигналы при запуске приложения
        """
        # Импортируем сигналы внутри метода ready, чтобы избежать циклических импортов
        try:
            from . import signals
        except ImportError:
            # Если файл сигналов еще не создан, просто пропускаем
            pass