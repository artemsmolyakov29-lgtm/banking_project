from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    # Основные отчеты
    path('', views.report_dashboard, name='report_dashboard'),
    path('clients/', views.client_report, name='client_report'),
    path('credits/', views.credit_report, name='credit_report'),
    path('deposits/', views.deposit_report, name='deposit_report'),
    path('transactions/', views.transaction_report, name='transaction_report'),
    path('financial/', views.financial_report, name='financial_report'),
    path('interest-accrual/', views.interest_accrual_report, name='interest_accrual_report'),
    path('cards/', views.card_report, name='card_report'),
    path('card-blocks/', views.card_block_report, name='card_block_report'),

    # Быстрые отчеты
    path('quick-deposits/', views.quick_deposit_report, name='quick_deposit_report'),
    path('quick-cards/', views.quick_card_report, name='quick_card_report'),

    # Экспорт данных
    path('export/json/', views.export_json, name='export_json'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/excel/', views.export_excel, name='export_excel'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),
    path('export/advanced/', views.export_data_advanced, name='export_data_advanced'),

    # Печать отчетов
    path('print/', views.print_report, name='print_report'),

    # Управление шаблонами отчетов
    path('templates/', views.report_template_list, name='template_list'),
    path('templates/create/', views.report_template_create, name='template_create'),
    path('templates/<int:template_id>/edit/', views.report_template_edit, name='template_edit'),
    path('templates/<int:template_id>/delete/', views.report_template_delete, name='template_delete'),
    path('templates/<int:template_id>/clone/', views.report_template_clone, name='template_clone'),

    # Управление расписаниями
    path('schedules/', views.schedule_list, name='schedule_list'),
    path('schedules/create/', views.schedule_create, name='schedule_create'),
    path('schedules/<int:schedule_id>/edit/', views.schedule_edit, name='schedule_edit'),
    path('schedules/<int:schedule_id>/delete/', views.schedule_delete, name='schedule_delete'),
    path('schedules/<int:schedule_id>/toggle/', views.schedule_toggle, name='schedule_toggle'),

    # Управление сохраненными отчетами
    path('saved/', views.saved_report_list, name='saved_report_list'),
    path('saved/<int:report_id>/', views.saved_report_detail, name='saved_report_detail'),
    path('saved/<int:report_id>/delete/', views.saved_report_delete, name='saved_report_delete'),
    path('saved/<int:report_id>/download/', views.saved_report_download, name='saved_report_download'),

    # Дашборды аналитики
    path('analytics/', views.analytics_dashboard_list, name='analytics_dashboard_list'),
    path('analytics/<int:dashboard_id>/', views.analytics_dashboard_view, name='analytics_dashboard_view'),
    path('analytics/create/', views.analytics_dashboard_create, name='analytics_dashboard_create'),
    path('analytics/<int:dashboard_id>/edit/', views.analytics_dashboard_edit, name='analytics_dashboard_edit'),
    path('analytics/<int:dashboard_id>/delete/', views.analytics_dashboard_delete, name='analytics_dashboard_delete'),

    # API endpoints
    path('api/report-data/<str:report_type>/', views.api_report_data, name='api_report_data'),
    path('api/dashboard-stats/', views.api_dashboard_stats, name='api_dashboard_stats'),
    path('api/quick-export/', views.api_quick_export, name='api_quick_export'),

    # Мониторинг и системная информация
    path('generation-status/', views.report_generation_status, name='report_generation_status'),
    path('system-health/', views.system_health, name='system_health'),
    path('generate-custom/', views.generate_custom_report, name='generate_custom_report'),
]