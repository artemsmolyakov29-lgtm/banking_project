from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    # Классовые представления CRUD
    path('', views.AccountListView.as_view(), name='account_list'),
    path('create/', views.AccountCreateView.as_view(), name='account_create'),
    path('<int:pk>/', views.AccountDetailView.as_view(), name='account_detail'),
    path('<int:pk>/update/', views.AccountUpdateView.as_view(), name='account_update'),
    path('<int:pk>/delete/', views.AccountDeleteView.as_view(), name='account_delete'),

    # Функциональные представления для специальных операций
    path('<int:pk>/close/', views.account_close, name='account_close'),
    path('<int:pk>/transactions/', views.account_transactions, name='account_transactions'),
    path('<int:pk>/deposit/', views.account_deposit, name='account_deposit'),
    path('<int:pk>/withdraw/', views.account_withdraw, name='account_withdraw'),
    path('transfer/', views.account_transfer, name='account_transfer'),
    path('currencies/', views.currency_list, name='currency_list'),

    # Старые URL для обратной совместимости (можно удалить после миграции)
    path('old/', views.account_list_old, name='account_list_old'),
    path('old/create/', views.account_create_old, name='account_create_old'),
    path('old/<int:pk>/', views.account_detail_old, name='account_detail_old'),
    path('old/<int:pk>/update/', views.account_update_old, name='account_update_old'),
]