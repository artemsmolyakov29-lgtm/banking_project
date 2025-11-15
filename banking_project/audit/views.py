from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.apps import apps
from django.http import HttpResponseForbidden, HttpResponse
import csv
import json
from datetime import datetime, timedelta


def get_user_model():
    """Ленивая загрузка модели User"""
    return apps.get_model('users', 'User')


def get_audit_log_model():
    """Ленивая загрузка модели AuditLog"""
    return apps.get_model('audit', 'AuditLog')


def get_backup_history_model():
    """Ленивая загрузка модели BackupHistory"""
    return apps.get_model('audit', 'BackupHistory')


def get_system_settings_model():
    """Ленивая загрузка модели SystemSettings"""
    return apps.get_model('audit', 'SystemSettings')


# Локальные декораторы
def role_required(allowed_roles):
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


def admin_required(view_func):
    return role_required(['admin'])(view_func)


@login_required
@admin_required
def audit_log(request):
    """Просмотр лога аудита"""
    AuditLog = get_audit_log_model()

    # Фильтрация
    user_id = request.GET.get('user_id')
    action = request.GET.get('action')
    module = request.GET.get('module')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')

    logs = AuditLog.objects.all().order_by('-timestamp')

    if user_id:
        logs = logs.filter(user_id=user_id)
    if action:
        logs = logs.filter(action=action)
    if module:
        logs = logs.filter(module=module)
    if date_from:
        logs = logs.filter(timestamp__date__gte=date_from)
    if date_to:
        logs = logs.filter(timestamp__date__lte=date_to)

    # Пагинация (упрощенная)
    page = int(request.GET.get('page', 1))
    per_page = 50
    start = (page - 1) * per_page
    end = start + per_page

    total_logs = logs.count()
    logs_page = logs[start:end]

    return render(request, 'audit/audit_log.html', {
        'logs': logs_page,
        'total_logs': total_logs,
        'page': page,
        'per_page': per_page,
        'user_id': user_id,
        'action': action,
        'module': module,
        'date_from': date_from,
        'date_to': date_to
    })


@login_required
@admin_required
def audit_log_detail(request, pk):
    """Детальная информация о записи аудита"""
    AuditLog = get_audit_log_model()

    log_entry = get_object_or_404(AuditLog, pk=pk)

    return render(request, 'audit/audit_log_detail.html', {
        'log_entry': log_entry
    })


@login_required
@admin_required
def backup_list(request):
    """Список резервных копий"""
    BackupHistory = get_backup_history_model()

    backups = BackupHistory.objects.all().order_by('-start_time')

    return render(request, 'audit/backup_list.html', {
        'backups': backups
    })


@login_required
@admin_required
def backup_create(request):
    """Создание резервной копии"""
    BackupHistory = get_backup_history_model()
    AuditLog = get_audit_log_model()

    if request.method == 'POST':
        backup_type = request.POST.get('backup_type', 'full')

        try:
            # Создание записи о бэкапе
            backup = BackupHistory.objects.create(
                backup_file=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.sql",
                backup_size=0,
                backup_type=backup_type,
                status='in_progress',
                initiated_by=request.user
            )

            # Здесь будет логика создания резервной копии через management command
            # Для демонстрации просто отмечаем как успешный
            backup.mark_completed(file_size=1024000, storage_location='local')

            # Логируем действие
            AuditLog.log_action(
                user=request.user,
                action='backup',
                module='system',
                table_name='backup_history',
                record_id=backup.id,
                description=f'Создана резервная копия типа {backup_type}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

            messages.success(request, 'Резервная копия успешно создана')
            return redirect('audit:backup_list')

        except Exception as e:
            messages.error(request, f'Ошибка при создании резервной копии: {str(e)}')

    return render(request, 'audit/backup_create.html')


@login_required
@admin_required
def backup_restore(request, pk):
    """Восстановление из резервной копии"""
    BackupHistory = get_backup_history_model()
    AuditLog = get_audit_log_model()

    backup = get_object_or_404(BackupHistory, pk=pk)

    if request.method == 'POST':
        try:
            # Здесь будет логика восстановления из резервной копии
            # Для демонстрации просто логируем действие

            # Логируем действие
            AuditLog.log_action(
                user=request.user,
                action='restore',
                module='system',
                table_name='backup_history',
                record_id=backup.id,
                description=f'Восстановление из резервной копии {backup.backup_file}',
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )

            messages.success(request, 'Восстановление из резервной копии запущено')
            return redirect('audit:backup_list')

        except Exception as e:
            messages.error(request, f'Ошибка при восстановлении: {str(e)}')

    return render(request, 'audit/backup_restore.html', {
        'backup': backup
    })


@login_required
@admin_required
def system_settings(request):
    """Настройки системы"""
    SystemSettings = get_system_settings_model()

    settings_list = SystemSettings.objects.all()

    if request.method == 'POST':
        # Обработка изменений настроек
        for setting in settings_list:
            new_value = request.POST.get(f'setting_{setting.id}')
            if new_value is not None and new_value != setting.value:
                setting.value = new_value
                setting.updated_by = request.user
                setting.save()

        messages.success(request, 'Настройки успешно обновлены')
        return redirect('audit:system_settings')

    return render(request, 'audit/system_settings.html', {
        'settings_list': settings_list
    })


@login_required
@admin_required
def export_audit_log(request):
    """Экспорт лога аудита"""
    AuditLog = get_audit_log_model()

    format_type = request.GET.get('format', 'csv')
    date_from = request.GET.get('date_from', (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d'))
    date_to = request.GET.get('date_to', datetime.now().strftime('%Y-%m-%d'))

    logs = AuditLog.objects.filter(
        timestamp__date__range=[date_from, date_to]
    ).order_by('-timestamp')

    if format_type == 'csv':
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="audit_log_{date_from}_{date_to}.csv"'

        writer = csv.writer(response)
        writer.writerow(
            ['ID', 'Время', 'Пользователь', 'Действие', 'Модуль', 'Таблица', 'ID записи', 'Успешно', 'IP адрес'])

        for log in logs:
            writer.writerow([
                log.id,
                log.timestamp.strftime('%Y-%m-%d %H:%M'),
                log.user.username,
                log.get_action_display(),
                log.get_module_display(),
                log.table_name,
                log.record_id or '',
                'Да' if log.is_successful else 'Нет',
                log.ip_address or ''
            ])

        return response

    elif format_type == 'json':
        data = []
        for log in logs:
            data.append({
                'id': log.id,
                'timestamp': log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
                'user': log.user.username,
                'action': log.action,
                'action_display': log.get_action_display(),
                'module': log.module,
                'module_display': log.get_module_display(),
                'table_name': log.table_name,
                'record_id': log.record_id,
                'description': log.description,
                'ip_address': log.ip_address,
                'is_successful': log.is_successful,
                'error_message': log.error_message
            })

        response = HttpResponse(json.dumps(data, ensure_ascii=False), content_type='application/json')
        response['Content-Disposition'] = f'attachment; filename="audit_log_{date_from}_{date_to}.json"'
        return response

    else:
        messages.error(request, 'Неподдерживаемый формат экспорта')
        return redirect('audit:audit_log')