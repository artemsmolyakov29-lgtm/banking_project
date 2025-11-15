from django.urls import path
from . import views

app_name = 'deposits'

urlpatterns = [
    path('', views.deposit_list, name='deposit_list'),
    path('open/', views.deposit_open, name='deposit_open'),
    path('<int:pk>/', views.deposit_detail, name='deposit_detail'),
    path('<int:pk>/close/', views.deposit_close, name='deposit_close'),
    path('<int:pk>/interest/', views.deposit_interest, name='deposit_interest'),
]