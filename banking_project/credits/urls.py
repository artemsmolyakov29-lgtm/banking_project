from django.urls import path
from . import views

app_name = 'credits'

urlpatterns = [
    path('', views.credit_list, name='credit_list'),
    path('products/', views.credit_products, name='credit_products'),
    path('apply/', views.credit_apply, name='credit_apply'),
    path('<int:pk>/', views.credit_detail, name='credit_detail'),
    path('<int:pk>/payments/', views.credit_payments, name='credit_payments'),
    path('<int:pk>/payment/', views.credit_payment, name='credit_payment'),
    path('<int:pk>/schedule/', views.credit_schedule, name='credit_schedule'),
    path('<int:pk>/collaterals/', views.credit_collaterals, name='credit_collaterals'),
]