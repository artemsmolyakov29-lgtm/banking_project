from django.conf import settings

def project_context(request):
    """
    Context processor that adds banking settings to all templates
    """
    return {
        'APP_NAME': settings.BANKING_SETTINGS.get('APP_NAME', 'Банковская система'),
        'APP_VERSION': settings.BANKING_SETTINGS.get('APP_VERSION', '1.0.0'),
        'SUPPORT_EMAIL': settings.BANKING_SETTINGS.get('SUPPORT_EMAIL', ''),
        'DEFAULT_CURRENCY': settings.BANKING_SETTINGS.get('DEFAULT_CURRENCY', 'RUB'),
    }