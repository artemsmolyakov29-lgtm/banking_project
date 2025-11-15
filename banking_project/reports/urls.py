from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('', views.report_dashboard, name='report_dashboard'),
    path('clients/', views.client_report, name='client_report'),
    path('credits/', views.credit_report, name='credit_report'),
    path('deposits/', views.deposit_report, name='deposit_report'),
    path('transactions/', views.transaction_report, name='transaction_report'),
    path('financial/', views.financial_report, name='financial_report'),
    path('export/json/', views.export_json, name='export_json'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/excel/', views.export_excel, name='export_excel'),
    path('export/pdf/', views.export_pdf, name='export_pdf'),
]