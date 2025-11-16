from django.urls import path
from . import views

app_name = 'credits'

urlpatterns = [
    # Классовые представления CRUD
    path('', views.CreditListView.as_view(), name='credit_list'),
    path('create/', views.CreditCreateView.as_view(), name='credit_create'),
    path('<int:pk>/', views.CreditDetailView.as_view(), name='credit_detail'),
    path('<int:pk>/update/', views.CreditUpdateView.as_view(), name='credit_update'),
    path('<int:pk>/delete/', views.CreditDeleteView.as_view(), name='credit_delete'),

    # Функциональные представления
    path('products/', views.credit_products, name='credit_products'),
    path('apply/', views.credit_apply, name='credit_apply'),
    path('<int:pk>/payments/', views.credit_payments, name='credit_payments'),
    path('<int:pk>/payment/', views.credit_payment, name='credit_payment'),
    path('<int:pk>/schedule/', views.credit_schedule, name='credit_schedule'),
    path('<int:pk>/collaterals/', views.credit_collaterals, name='credit_collaterals'),
    path('<int:pk>/approve/', views.credit_approve, name='credit_approve'),
    path('<int:pk>/reject/', views.credit_reject, name='credit_reject'),
]