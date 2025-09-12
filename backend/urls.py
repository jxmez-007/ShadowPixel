"""
URL configuration for Resume Upload and Management System.

This module defines all URL patterns for the resume application,
including CRUD operations, API endpoints, and administrative functions.
"""

from django.urls import path, include
from django.views.generic import RedirectView
from . import views

# Application namespace
app_name = 'resume'

# Main URL patterns
urlpatterns = [
    # Home and dashboard
    path('', views.index, name='index'),
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Resume upload
    path('upload/', views.upload_resume, name='upload_resume'),
    path('resumes/<int:pk>/', views.resume_detail, name='resume_detail'),
    path('resumes/<int:pk>/text/', views.resume_text, name='resume_text'),
    
    # Resume management
    path('resumes/', views.uploaded_resumes, name='uploaded_resumes'),
    path('resumes/<int:pk>/', views.resume_detail, name='resume_detail'),
    path('resumes/<int:pk>/edit/', views.edit_resume, name='edit_resume'),
    path('resumes/<int:pk>/delete/', views.delete_resume, name='delete_resume'),
    path('resumes/<int:pk>/download/', views.download_resume, name='download_resume'),
    path('resumes/<int:pk>/reprocess/', views.reprocess_resume, name='reprocess_resume'),
    path('resumes/<int:pk>/summary/', views.resume_summary, name='resume_summary'),
    path('resumes/<int:pk>/analysis/', views.resume_analysis, name='resume_analysis'),
    path('resumes/<int:pk>/text/', views.resume_text, name='resume_text'),
    path('resumes/<int:pk>/logs/', views.resume_processing_logs, name='resume_processing_logs'),
    path('resumes/<int:pk>/status/', views.resume_status, name='resume_status'),
    path('resumes/<int:pk>/github/', views.resume_github_sync, name='resume_github_sync'),
    
    # Processing and analysis
    path('summary/', views.summary_page, name='summary_page'),
    path('processing-queue/', views.processing_queue, name='processing_queue'),
    
    # GitHub integration
    path('github/<str:username>/', views.github_profile, name='github_profile'),
    
    # Search and filtering
    path('search/', views.search_resumes, name='search_resumes'),
    path('filter/', views.filter_resumes, name='filter_resumes'),
    path('resumes/by-status/<str:status>/', views.resumes_by_status, name='resumes_by_status'),
    path('resumes/by-skill/<str:skill>/', views.resumes_by_skill, name='resumes_by_skill'),
    
    # Bulk operations
    path('bulk-actions/', views.bulk_actions, name='bulk_actions'),
    path('bulk-delete/', views.bulk_delete, name='bulk_delete'),
    path('bulk-process/', views.bulk_process, name='bulk_process'),
    
    # Statistics and reporting
    path('stats/', views.statistics, name='statistics'),
    path('reports/', views.reports, name='reports'),
    path('analytics/', views.analytics, name='analytics'),
    
    # Export functionality
    path('export/', views.export_resumes, name='export_resumes'),
    path('export/csv/', views.export_csv, name='export_csv'),
    path('export/json/', views.export_json, name='export_json'),
    path('export/pdf-report/', views.export_pdf_report, name='export_pdf_report'),
    
    # Settings and configuration
    path('settings/', views.settings, name='settings'),  # This now matches your views.py
    path('preferences/', views.user_preferences, name='user_preferences'),
    
    # Help and documentation
    path('help/', views.help_page, name='help'),
    path('about/', views.about, name='about'),
    
    # API endpoints
    path('api/resumes/', views.api_resumes_list, name='api_resumes_list'),
    path('api/resumes/<int:pk>/', views.api_resume_detail, name='api_resume_detail'),
    path('api/upload/', views.api_upload_resume, name='api_upload_resume'),
    path('api/search/', views.api_search_resumes, name='api_search_resumes'),
    path('api/stats/', views.api_statistics, name='api_statistics'),
    
    # System health and monitoring
    path('system/health/', views.health_check, name='health_check'),
    path('system/metrics/', views.metrics, name='metrics'),
    path('system/status/', views.system_status, name='system_status'),
    
    # Legacy redirects for backward compatibility
    path('list/', RedirectView.as_view(pattern_name='resume:uploaded_resumes', permanent=True)),
    path('summaries/', RedirectView.as_view(pattern_name='resume:summary_page', permanent=True)),
]
