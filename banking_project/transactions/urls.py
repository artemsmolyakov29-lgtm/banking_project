from django.urls import path
from . import views

app_name = 'transactions'

urlpatterns = [
    path('', views.transaction_list, name='transaction_list'),
    path('<int:pk>/', views.transaction_detail, name='transaction_detail'),
    path('create/', views.transaction_create, name='transaction_create'),
    path('fees/', views.transaction_fees, name='transaction_fees'),
    path('report/', views.transaction_report, name='transaction_report'),

    path('transfer/', views.transfer_view, name='transfer'),
    path('transfer/success/<int:transaction_id>/', views.transfer_success, name='transfer_success'),
    path('history/', views.transaction_history, name='history'),
]