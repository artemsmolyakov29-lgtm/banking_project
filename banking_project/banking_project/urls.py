from django.contrib import admin
from django.urls import path, include
from django.views.generic import RedirectView, TemplateView
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', RedirectView.as_view(pattern_name='users:dashboard'), name='home'),
    path('users/', include('users.urls')),
    path('clients/', include('clients.urls')),
    path('accounts/', include('accounts.urls')),
    path('credits/', include('credits.urls')),
    path('deposits/', include('deposits.urls')),
    path('cards/', include('cards.urls')),
    path('transactions/', include('transactions.urls')),
    path('audit/', include('audit.urls')),
    path('reports/', include('reports.urls')),
    # Добавляем маршрут для страницы "в разработке"
    path('under-construction/',
         TemplateView.as_view(template_name='under_construction.html'),
         name='under_construction'),
]

if settings.DEBUG:
    import debug_toolbar

    urlpatterns += [
        path('__debug__/', include(debug_toolbar.urls)),
    ]

    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)