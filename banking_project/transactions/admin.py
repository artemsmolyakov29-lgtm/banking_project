from django.contrib import admin
from .models import Transaction, TransactionFee


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = [
        'reference_number', 'transaction_type', 'amount', 'fee', 'currency',
        'from_account', 'to_account', 'status', 'created_at'
    ]
    list_filter = [
        'transaction_type', 'status', 'created_at', 'currency'
    ]
    search_fields = [
        'reference_number', 'from_account__account_number',
        'to_account__account_number', 'description'
    ]
    readonly_fields = ['reference_number', 'created_at', 'executed_at']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Основная информация', {
            'fields': (
                'reference_number', 'transaction_type', 'status',
                'amount', 'fee', 'currency', 'exchange_rate'
            )
        }),
        ('Счета', {
            'fields': ('from_account', 'to_account')
        }),
        ('Дополнительная информация', {
            'fields': (
                'description', 'initiated_by', 'created_at', 'executed_at'
            )
        }),
        ('Связанные объекты', {
            'fields': (
                'deposit', 'credit', 'credit_payment',
                'deposit_interest_payment', 'card', 'card_transaction'
            ),
            'classes': ('collapse',)
        }),
    )


@admin.register(TransactionFee)
class TransactionFeeAdmin(admin.ModelAdmin):
    list_display = [
        'name', 'transaction_type', 'fee_type', 'amount',
        'currency', 'is_active', 'created_at'
    ]
    list_filter = ['transaction_type', 'fee_type', 'is_active', 'currency']
    search_fields = ['name', 'description']
    list_editable = ['is_active']