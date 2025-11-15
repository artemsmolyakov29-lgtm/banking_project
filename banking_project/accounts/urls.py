from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('', views.account_list, name='account_list'),
    path('create/', views.account_create, name='account_create'),
    path('<int:pk>/', views.account_detail, name='account_detail'),
    path('<int:pk>/update/', views.account_update, name='account_update'),
    path('<int:pk>/close/', views.account_close, name='account_close'),
    path('<int:pk>/transactions/', views.account_transactions, name='account_transactions'),
    path('<int:pk>/deposit/', views.account_deposit, name='account_deposit'),
    path('<int:pk>/withdraw/', views.account_withdraw, name='account_withdraw'),
    path('transfer/', views.account_transfer, name='account_transfer'),
    path('currencies/', views.currency_list, name='currency_list'),
]