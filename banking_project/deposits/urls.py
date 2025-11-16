from django.urls import path
from . import views

app_name = 'deposits'

urlpatterns = [
    # Классовые представления CRUD
    path('', views.DepositListView.as_view(), name='deposit_list'),
    path('create/', views.DepositCreateView.as_view(), name='deposit_create'),
    path('<int:pk>/', views.DepositDetailView.as_view(), name='deposit_detail'),
    path('<int:pk>/update/', views.DepositUpdateView.as_view(), name='deposit_update'),
    path('<int:pk>/delete/', views.DepositDeleteView.as_view(), name='deposit_delete'),

    # Функциональные представления
    path('open/', views.deposit_open, name='deposit_open'),
    path('<int:pk>/close/', views.deposit_close, name='deposit_close'),
    path('<int:pk>/interest/', views.deposit_interest, name='deposit_interest'),
    path('<int:pk>/early-close/', views.deposit_early_close, name='deposit_early_close'),

    # Новые маршруты для начисления процентов
    path('<int:pk>/accrue-interest/', views.accrue_interest_manual, name='accrue_interest_manual'),
    path('accrue-interest-all/', views.accrue_interest_all, name='accrue_interest_all'),
    path('<int:pk>/get-expected-interest/', views.get_expected_interest, name='get_expected_interest'),
    path('interest-report/', views.interest_accrual_report, name='interest_accrual_report'),
]