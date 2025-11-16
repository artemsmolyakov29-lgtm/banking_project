from django.contrib import admin
from django.apps import apps
from django.utils.html import format_html
from django.urls import reverse
from django.contrib import messages
from django.http import HttpResponseRedirect
from django.utils import timezone
from datetime import date


def get_card_model():
    return apps.get_model('cards', 'Card')


def get_card_transaction_model():
    return apps.get_model('cards', 'CardTransaction')


def get_card_status_history_model():
    return apps.get_model('cards', 'CardStatusHistory')


def _log_card_status_change(user, card, old_status, new_status, reason=None, block_reason=None):
    """Внутренняя функция для логирования изменения статуса карты через ленивую загрузку"""
    try:
        # Ленивая загрузка функции логирования через apps
        audit_app = apps.get_app_config('audit')
        if hasattr(audit_app, 'log_card_status_change'):
            audit_app.log_card_status_change(
                user=user,
                card=card,
                old_status=old_status,
                new_status=new_status,
                reason=reason,
                block_reason=block_reason
            )
    except (LookupError, AttributeError):
        # Если модуль аудита недоступен, просто игнорируем логирование
        pass


class CardStatusHistoryInline(admin.TabularInline):
    """Inline для отображения истории статусов карты"""
    model = get_card_status_history_model()
    extra = 0
    readonly_fields = ['changed_by', 'old_status', 'new_status', 'change_reason', 'block_reason', 'changed_at']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CardTransactionInline(admin.TabularInline):
    """Inline для отображения операций по карте"""
    model = get_card_transaction_model()
    extra = 0
    readonly_fields = ['transaction_type', 'amount', 'currency', 'merchant_name', 'transaction_date', 'is_successful']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(get_card_model())
class CardAdmin(admin.ModelAdmin):
    """Административный интерфейс для модели Card"""
    list_display = [
        'get_masked_number_display',
        'cardholder_name',
        'account_link',
        'card_type_display',
        'card_system_display',
        'status_display',
        'daily_limit',
        'expiry_date',
        'is_expired_display',
        'created_at'
    ]
    list_filter = [
        'status',
        'card_type',
        'card_system',
        'is_virtual',
        'created_at',
        'expiry_date'
    ]
    search_fields = [
        'card_number',
        'cardholder_name',
        'account__account_number',
        'account__client__user__first_name',
        'account__client__user__last_name'
    ]
    readonly_fields = [
        'created_at',
        'status_changed_at',
        'get_masked_number',
        'is_expired'
    ]
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'account',
                'card_number',
                'cardholder_name',
                'expiry_date',
                'card_type',
                'card_system',
                'is_virtual'
            )
        }),
        ('Статус и лимиты', {
            'fields': (
                'status',
                'daily_limit',
                'block_reason',
                'block_description',
                'status_changed_at'
            )
        }),
        ('Системная информация', {
            'fields': (
                'created_at',
                'get_masked_number',
                'is_expired'
            ),
            'classes': ('collapse',)
        })
    )
    inlines = [CardStatusHistoryInline, CardTransactionInline]
    actions = ['block_cards', 'unblock_cards', 'mark_as_lost', 'mark_as_stolen']

    def get_masked_number_display(self, obj):
        return obj.get_masked_number()

    get_masked_number_display.short_description = 'Номер карты'

    def card_type_display(self, obj):
        return obj.get_card_type_display()

    card_type_display.short_description = 'Тип карты'

    def card_system_display(self, obj):
        return obj.get_card_system_display()

    card_system_display.short_description = 'Платежная система'

    def status_display(self, obj):
        color_map = {
            'active': 'green',
            'blocked': 'red',
            'expired': 'orange',
            'lost': 'red',
            'stolen': 'red',
            'closed': 'gray'
        }
        color = color_map.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_display.short_description = 'Статус'

    def account_link(self, obj):
        url = reverse('admin:accounts_account_change', args=[obj.account.id])
        return format_html('<a href="{}">{}</a>', url, obj.account.account_number)

    account_link.short_description = 'Счет'

    def is_expired_display(self, obj):
        if obj.is_expired():
            return format_html('<span style="color: red; font-weight: bold;">✓</span>')
        return format_html('<span style="color: green;">✗</span>')

    is_expired_display.short_description = 'Просрочена'

    # Действия администратора
    def block_cards(self, request, queryset):
        """Массовая блокировка карт"""
        success_count = 0
        for card in queryset:
            if card.block_card(reason='blocked', block_reason='admin_action',
                               block_description='Массовая блокировка через админ-панель', user=request.user):
                success_count += 1

        if success_count > 0:
            self.message_user(
                request,
                f'Успешно заблокировано {success_count} карт(ы)',
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'Не удалось заблокировать выбранные карты',
                messages.WARNING
            )

    block_cards.short_description = 'Заблокировать выбранные карты'

    def unblock_cards(self, request, queryset):
        """Массовая разблокировка карт"""
        success_count = 0
        for card in queryset:
            if card.unblock_card(user=request.user):
                success_count += 1

        if success_count > 0:
            self.message_user(
                request,
                f'Успешно разблокировано {success_count} карт(ы)',
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'Не удалось разблокировать выбранные карты',
                messages.WARNING
            )

    unblock_cards.short_description = 'Разблокировать выбранные карты'

    def mark_as_lost(self, request, queryset):
        """Пометить карты как утерянные"""
        success_count = 0
        for card in queryset:
            if card.block_card(reason='lost', block_reason='lost_card',
                               block_description='Отмечено как утерянная через админ-панель', user=request.user):
                success_count += 1

        if success_count > 0:
            self.message_user(
                request,
                f'Успешно отмечено как утерянные {success_count} карт(ы)',
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'Не удалось отметить выбранные карты как утерянные',
                messages.WARNING
            )

    mark_as_lost.short_description = 'Пометить как утерянные'

    def mark_as_stolen(self, request, queryset):
        """Пометить карты как украденные"""
        success_count = 0
        for card in queryset:
            if card.block_card(reason='stolen', block_reason='stolen_card',
                               block_description='Отмечено как украденная через админ-панель', user=request.user):
                success_count += 1

        if success_count > 0:
            self.message_user(
                request,
                f'Успешно отмечено как украденные {success_count} карт(ы)',
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                'Не удалось отметить выбранные карты как украденные',
                messages.WARNING
            )

    mark_as_stolen.short_description = 'Пометить как украденные'

    def save_model(self, request, obj, form, change):
        """Сохранение модели с логированием изменений"""
        if change:
            # Получаем оригинальный объект для сравнения
            original_obj = self.model.objects.get(pk=obj.pk)

            # Если статус изменился, логируем изменение
            if original_obj.status != obj.status:
                _log_card_status_change(
                    user=request.user,
                    card=obj,
                    old_status=original_obj.status,
                    new_status=obj.status,
                    reason="Изменение через админ-панель"
                )

        super().save_model(request, obj, form, change)


@admin.register(get_card_transaction_model())
class CardTransactionAdmin(admin.ModelAdmin):
    """Административный интерфейс для модели CardTransaction"""
    list_display = [
        'id',
        'card_link',
        'transaction_type_display',
        'amount',
        'currency',
        'merchant_name',
        'transaction_date',
        'is_successful_display'
    ]
    list_filter = [
        'transaction_type',
        'is_successful',
        'transaction_date',
        'currency'
    ]
    search_fields = [
        'card__card_number',
        'merchant_name',
        'authorization_code'
    ]
    readonly_fields = [
        'created_at'
    ]
    date_hierarchy = 'transaction_date'

    def card_link(self, obj):
        url = reverse('admin:cards_card_change', args=[obj.card.id])
        return format_html('<a href="{}">{}</a>', url, obj.card.get_masked_number())

    card_link.short_description = 'Карта'

    def transaction_type_display(self, obj):
        return obj.get_transaction_type_display()

    transaction_type_display.short_description = 'Тип операции'

    def is_successful_display(self, obj):
        if obj.is_successful:
            return format_html('<span style="color: green; font-weight: bold;">✓</span>')
        return format_html('<span style="color: red; font-weight: bold;">✗</span>')

    is_successful_display.short_description = 'Успешно'


@admin.register(get_card_status_history_model())
class CardStatusHistoryAdmin(admin.ModelAdmin):
    """Административный интерфейс для модели CardStatusHistory"""
    list_display = [
        'card_link',
        'old_status_display',
        'new_status_display',
        'changed_by',
        'block_reason_display',
        'changed_at'
    ]
    list_filter = [
        'new_status',
        'block_reason',
        'changed_at'
    ]
    search_fields = [
        'card__card_number',
        'changed_by__username',
        'changed_by__first_name',
        'changed_by__last_name'
    ]
    readonly_fields = [
        'card',
        'old_status',
        'new_status',
        'changed_by',
        'change_reason',
        'block_reason',
        'changed_at'
    ]
    date_hierarchy = 'changed_at'

    def card_link(self, obj):
        url = reverse('admin:cards_card_change', args=[obj.card.id])
        return format_html('<a href="{}">{}</a>', url, obj.card.get_masked_number())

    card_link.short_description = 'Карта'

    def old_status_display(self, obj):
        return obj.get_old_status_display()

    old_status_display.short_description = 'Предыдущий статус'

    def new_status_display(self, obj):
        color_map = {
            'active': 'green',
            'blocked': 'red',
            'expired': 'orange',
            'lost': 'red',
            'stolen': 'red',
            'closed': 'gray'
        }
        color = color_map.get(obj.new_status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_new_status_display()
        )

    new_status_display.short_description = 'Новый статус'

    def block_reason_display(self, obj):
        if obj.block_reason:
            return obj.get_block_reason_display()
        return '-'

    block_reason_display.short_description = 'Причина блокировки'

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False