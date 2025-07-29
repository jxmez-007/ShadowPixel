from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    path('', views.index, name='home'),
    path('upload/', views.upload_resume, name='upload_resume'),
    path('resumes/', views.uploaded_resumes, name='resumes'),
]
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)