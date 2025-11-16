from django.urls import path
from . import views

app_name = 'cards'

urlpatterns = [
    # Классовые представления CRUD
    path('', views.CardListView.as_view(), name='card_list'),
    path('create/', views.CardCreateView.as_view(), name='card_create'),
    path('<int:pk>/', views.CardDetailView.as_view(), name='card_detail'),
    path('<int:pk>/update/', views.CardUpdateView.as_view(), name='card_update'),
    path('<int:pk>/delete/', views.CardDeleteView.as_view(), name='card_delete'),

    # Функциональные представления
    path('issue/', views.card_issue, name='card_issue'),
    path('<int:pk>/block/confirm/', views.card_block_confirm, name='card_block_confirm'),
    path('<int:pk>/block/', views.card_block, name='card_block'),
    path('<int:pk>/unblock/confirm/', views.card_unblock_confirm, name='card_unblock_confirm'),
    path('<int:pk>/unblock/', views.card_unblock, name='card_unblock'),
    path('<int:pk>/transactions/', views.card_transactions, name='card_transactions'),
    path('<int:pk>/limits/', views.card_limits, name='card_limits'),
    path('<int:pk>/reissue/', views.card_reissue, name='card_reissue'),
    path('<int:pk>/status-history/', views.card_status_history, name='card_status_history'),
]