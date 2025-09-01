from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.http import HttpResponse
import os

# Admin customization
admin.site.site_header = "ShadowPixel Resume Management Admin"
admin.site.site_title = "Resume Admin Portal"
admin.site.index_title = "Welcome to Resume Management Administration"

# Simple view functions for endpoints without templates
def health_check_view(request):
    """Simple health check endpoint."""
    return HttpResponse("OK", content_type="text/plain")

def robots_txt_view(request):
    """Robots.txt content."""
    content = """User-agent: *
Disallow: /admin/
Disallow: /dev/
Allow: /
"""
    return HttpResponse(content, content_type="text/plain")

def security_txt_view(request):
    """Security.txt content."""
    content = """Contact: admin@shadowpixel.com
Expires: 2026-12-31T23:59:59.000Z
Preferred-Languages: en
"""
    return HttpResponse(content, content_type="text/plain")

# Main URL patterns
urlpatterns = [
    # Admin interface - FIXED: Use hardcoded 'admin/' instead of settings.ADMIN_URL
    path('admin/', admin.site.urls),
    
    # Main application routes
    path('', include('backend.urls')),
    
    # Health check endpoint
    path('health/', health_check_view, name='health_check'),
    
    # Robots.txt
    path('robots.txt', robots_txt_view, name='robots'),
    
    # Security endpoint
    path('.well-known/security.txt', security_txt_view, name='security'),
    
    # Favicon redirect
    path('favicon.ico', RedirectView.as_view(
        url='/static/favicon.ico',
        permanent=True
    )),
]

# CRITICAL: Serve static and media files during development
if settings.DEBUG:
    # FIXED: Use STATICFILES_DIRS[0] instead of STATIC_ROOT for development
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    
    # Media files serving
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    
    # Debug toolbar
    if 'debug_toolbar' in settings.INSTALLED_APPS:
        import debug_toolbar
        urlpatterns += [
            path('__debug__/', include(debug_toolbar.urls)),
        ]
    
    # Development shortcuts
    def dev_admin_redirect(request):
        return RedirectView.as_view(url='/admin/login/', permanent=False)(request)
    
    def dev_cache_clear(request):
        from django.core.cache import cache
        cache.clear()
        return HttpResponse("Cache cleared successfully!", content_type="text/plain")
    
    urlpatterns += [
        path('dev/admin-login/', dev_admin_redirect, name='dev_admin_login'),
        path('dev/clear-cache/', dev_cache_clear, name='dev_clear_cache'),
    ]

# Environment-specific URLs
if os.getenv('DJANGO_ENV') == 'production':
    def status_view(request):
        return HttpResponse("System Status: Operational", content_type="text/plain")
    
    def ping_view(request):
        return HttpResponse("pong", content_type="text/plain")
    
    urlpatterns += [
        path('status/', status_view, name='status_index'),
        path('ping/', ping_view, name='ping'),
    ]

elif os.getenv('DJANGO_ENV') == 'staging':
    def staging_info_view(request):
        return HttpResponse("Staging Environment - ShadowPixel v2.0", content_type="text/plain")
    
    urlpatterns += [
        path('staging-info/', staging_info_view, name='staging_info'),
    ]
