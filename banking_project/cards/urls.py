from django.urls import path
from . import views

app_name = 'cards'

urlpatterns = [
    path('', views.card_list, name='card_list'),
    path('issue/', views.card_issue, name='card_issue'),
    path('<int:pk>/', views.card_detail, name='card_detail'),
    path('<int:pk>/block/', views.card_block, name='card_block'),
    path('<int:pk>/unblock/', views.card_unblock, name='card_unblock'),
    path('<int:pk>/transactions/', views.card_transactions, name='card_transactions'),
    path('<int:pk>/limits/', views.card_limits, name='card_limits'),
]