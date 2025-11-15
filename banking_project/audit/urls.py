from django.urls import path
from . import views

app_name = 'audit'

urlpatterns = [
    path('', views.audit_log, name='audit_log'),
    path('backup/', views.backup_list, name='backup_list'),
    path('backup/create/', views.backup_create, name='backup_create'),
    path('backup/<int:pk>/restore/', views.backup_restore, name='backup_restore'),
    path('settings/', views.system_settings, name='system_settings'),
]