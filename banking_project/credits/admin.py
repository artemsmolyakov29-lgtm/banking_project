from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Sum, Count
from .models import CreditProduct, Credit, CreditPayment, CreditCollateral

User = get_user_model()


class CreditProductAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'credit_type', 'min_amount', 'max_amount',
        'min_interest_rate', 'max_interest_rate', 'is_active', 'created_at'
    ]
    list_filter = ['credit_type', 'is_active', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']
    fieldsets = (
        ('Основная информация', {
            'fields': ('name', 'credit_type', 'description', 'is_active')
        }),
        ('Финансовые параметры', {
            'fields': (
                'min_amount', 'max_amount',
                'min_interest_rate', 'max_interest_rate',
                'min_term_months', 'max_term_months',
                'currency', 'payment_method'
            )
        }),
        ('Требования', {
            'fields': (
                'early_repayment_allowed',
                'requires_collateral',
                'requires_guarantor',
                'min_credit_score'
            )
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )


class CreditPaymentInline(admin.TabularInline):
    model = CreditPayment
    extra = 0
    readonly_fields = ['payment_number', 'payment_date', 'amount', 'status']
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


class CreditCollateralInline(admin.TabularInline):
    model = CreditCollateral
    extra = 0
    fields = ['collateral_type', 'description', 'estimated_value', 'is_insured']


class CreditAdmin(admin.ModelAdmin):
    list_display = [
        'contract_number', 'client_link', 'credit_product', 'amount',
        'interest_rate', 'status_badge', 'remaining_balance',
        'next_payment_date', 'created_at'
    ]
    list_filter = ['status', 'credit_product', 'created_at', 'next_payment_date']
    search_fields = [
        'contract_number', 'application_number',
        'client__user__first_name', 'client__user__last_name'
    ]
    readonly_fields = [
        'application_number', 'contract_number', 'created_at',
        'updated_at', 'remaining_balance', 'total_paid',
        'overdue_amount', 'overdue_days'
    ]
    inlines = [CreditPaymentInline, CreditCollateralInline]

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'application_number', 'contract_number',
                'client', 'credit_product', 'status'
            )
        }),
        ('Финансовые параметры', {
            'fields': (
                'amount', 'interest_rate', 'term_months',
                'remaining_balance', 'total_paid'
            )
        }),
        ('Даты', {
            'fields': (
                'start_date', 'end_date', 'next_payment_date'
            )
        }),
        ('Просрочка', {
            'fields': (
                'overdue_amount', 'overdue_days'
            ),
            'classes': ('collapse',)
        }),
        ('Дополнительная информация', {
            'fields': ('purpose', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Одобрение', {
            'fields': ('approved_by', 'approved_date'),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        })
    )

    def client_link(self, obj):
        url = reverse('admin:clients_client_change', args=[obj.client.id])
        return format_html('<a href="{}">{}</a>', url, obj.client.get_full_name())

    client_link.short_description = 'Клиент'

    def status_badge(self, obj):
        status_colors = {
            'application': 'bg-secondary',
            'under_review': 'bg-info',
            'approved': 'bg-success',
            'rejected': 'bg-danger',
            'active': 'bg-primary',
            'closed': 'bg-dark',
            'overdue': 'bg-warning',
            'default': 'bg-danger',
        }
        color = status_colors.get(obj.status, 'bg-secondary')
        return format_html(
            '<span class="badge {}">{}</span>',
            color, obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'client', 'client__user', 'credit_product'
        )


class CreditPaymentAdmin(admin.ModelAdmin):
    list_display = [
        'payment_number', 'credit_link', 'payment_date', 'amount',
        'principal_amount', 'interest_amount', 'status_badge',
        'payment_method', 'processed_date'
    ]
    list_filter = ['status', 'payment_method', 'payment_date', 'processed_date']
    search_fields = [
        'credit__contract_number', 'credit__client__user__first_name',
        'credit__client__user__last_name'
    ]
    readonly_fields = ['created_at', 'processed_date']

    fieldsets = (
        ('Основная информация', {
            'fields': ('credit', 'payment_number', 'payment_date', 'due_date')
        }),
        ('Финансовые параметры', {
            'fields': (
                'amount', 'principal_amount', 'interest_amount', 'penalty_amount'
            )
        }),
        ('Статус и обработка', {
            'fields': ('status', 'payment_method', 'transaction', 'processed_by')
        }),
        ('Дополнительная информация', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
        ('Системная информация', {
            'fields': ('created_at', 'processed_date'),
            'classes': ('collapse',)
        })
    )

    def credit_link(self, obj):
        url = reverse('admin:credits_credit_change', args=[obj.credit.id])
        return format_html('<a href="{}">{}</a>', url, obj.credit.contract_number)

    credit_link.short_description = 'Кредит'

    def status_badge(self, obj):
        status_colors = {
            'pending': 'bg-warning',
            'completed': 'bg-success',
            'failed': 'bg-danger',
            'partial': 'bg-info',
        }
        color = status_colors.get(obj.status, 'bg-secondary')
        return format_html(
            '<span class="badge {}">{}</span>',
            color, obj.get_status_display()
        )

    status_badge.short_description = 'Статус'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'credit', 'credit__client', 'credit__client__user'
        )


class CreditCollateralAdmin(admin.ModelAdmin):
    list_display = [
        'credit_link', 'collateral_type', 'estimated_value',
        'is_insured', 'created_at'
    ]
    list_filter = ['collateral_type', 'is_insured', 'created_at']
    search_fields = [
        'credit__contract_number', 'description',
        'document_number', 'insurance_company'
    ]
    readonly_fields = ['created_at']

    fieldsets = (
        ('Основная информация', {
            'fields': ('credit', 'collateral_type', 'description')
        }),
        ('Оценка и документы', {
            'fields': (
                'estimated_value', 'document_number', 'document_date'
            )
        }),
        ('Страхование', {
            'fields': (
                'is_insured', 'insurance_company', 'insurance_policy_number'
            )
        }),
        ('Системная информация', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        })
    )

    def credit_link(self, obj):
        url = reverse('admin:credits_credit_change', args=[obj.credit.id])
        return format_html('<a href="{}">{}</a>', url, obj.credit.contract_number)

    credit_link.short_description = 'Кредит'


# Регистрация моделей в админ-панели
admin.site.register(CreditProduct, CreditProductAdmin)
admin.site.register(Credit, CreditAdmin)
admin.site.register(CreditPayment, CreditPaymentAdmin)
admin.site.register(CreditCollateral, CreditCollateralAdmin)