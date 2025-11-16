from django.urls import path
from . import views

app_name = 'clients'

urlpatterns = [
    # Основные CRUD представления (классовые)
    path('', views.ClientListView.as_view(), name='client_list'),
    path('create/', views.ClientCreateView.as_view(), name='client_create'),
    path('<int:pk>/', views.ClientDetailView.as_view(), name='client_detail'),
    path('<int:pk>/update/', views.ClientUpdateView.as_view(), name='client_update'),
    path('<int:pk>/delete/', views.ClientDeleteView.as_view(), name='client_delete'),

    # Специальные представления (функциональные)
    path('search/', views.client_search, name='client_search'),
    path('<int:pk>/documents/', views.client_documents, name='client_documents'),
    path('<int:pk>/contacts/', views.client_contacts, name='client_contacts'),
]