from django.urls import path
from . import views

app_name = 'clients'

urlpatterns = [
    path('', views.client_list, name='client_list'),
    path('create/', views.client_create, name='client_create'),
    path('<int:pk>/', views.client_detail, name='client_detail'),
    path('<int:pk>/update/', views.client_update, name='client_update'),
    path('<int:pk>/delete/', views.client_delete, name='client_delete'),
    path('<int:pk>/documents/', views.client_documents, name='client_documents'),
    path('<int:pk>/contacts/', views.client_contacts, name='client_contacts'),
    path('search/', views.client_search, name='client_search'),
]