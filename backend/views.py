"""
Views for Resume Upload and Management System.

This module handles all view logic for the resume application,
including upload, processing, and display functionality.
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.core.files.storage import default_storage
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.conf import settings as django_settings  # Renamed to avoid conflict
from django.utils import timezone
from typing import Optional, Any, Union, List, Dict, Tuple
import os
import uuid
import json
import re
import threading
import time
from datetime import datetime
from pathlib import Path

# Fixed model imports with proper error handling
try:
    from .models import Resume, ResumeProcessingLog
except ImportError:
    Resume = None
    ResumeProcessingLog = None

try:
    from .services import TextExtractionService as BackendTextExtractionService
    from .services import ResumeAnalysisService as BackendResumeAnalysisService
    from .services import GitHubService as BackendGitHubService

    TextExtractionService = BackendTextExtractionService
    ResumeAnalysisService = BackendResumeAnalysisService
    GitHubService = BackendGitHubService
    
    SERVICES_AVAILABLE = True
except ImportError:
    SERVICES_AVAILABLE = False

    # Fallback placeholder classes
    class TextExtractionService:
        @staticmethod
        def extract_text(file_path: str, file_extension: str) -> tuple[str, bool]:
            return "Service not available", False
    
    class ResumeAnalysisService:
        @staticmethod
        def generate_summary(text: str) -> str:
            return "Service not available"
        @staticmethod
        def extract_contact_info(text: str) -> dict:
            return {}
        @staticmethod
        def extract_skills(text: str) -> list:
            return []
    
    class GitHubService:
        @staticmethod
        def get_user_profile(username: str) -> tuple[dict, bool]:
            return {"error": "Service not available"}, False
        @staticmethod
        def get_user_repositories(username: str) -> tuple[list, bool]:
            return [], False


def validate_github_username(username: str) -> bool:
    """Validate GitHub username format according to GitHub rules."""
    if not username or len(username) > 39:
        return False
    
    if len(username) == 1:
        return username.isalnum()
    
    if username.startswith('-') or username.endswith('-') or '--' in username:
        return False
    
    pattern = r'^[a-zA-Z0-9][a-zA-Z0-9-]*[a-zA-Z0-9]$'
    return bool(re.match(pattern, username))


def validate_file_security(filename: str) -> bool:
    """Validate filename for security issues."""
    if not filename:
        return False
    
    dangerous_patterns = ['..', '/', '\\', '~', '<', '>', ':', '"', '|', '?', '*']
    return not any(pattern in filename for pattern in dangerous_patterns)


def process_uploaded_resume(resume_id: int) -> Tuple[bool, str]:
    """Process a resume using your existing services and models"""
    if Resume is None:
        return False, "Resume model not available"
    
    try:
        resume = Resume.objects.get(pk=resume_id)
        
        resume.mark_processing("Starting resume processing...")
        
        if ResumeProcessingLog is not None:
            ResumeProcessingLog.objects.create(
                resume=resume,
                step="processing_start",
                status="started",
                message="Beginning resume processing pipeline"
            )
        
        processing_success = True
        
        # Step 1: Text extraction
        if resume.resume_file:
            start_time = time.time()
            
            try:
                file_path = resume.resume_file.path
                file_extension = getattr(resume, 'file_extension', '')
                
                extracted_text, extraction_success = TextExtractionService.extract_text(
                    file_path, file_extension
                )
                
                resume.extracted_text = extracted_text
                resume.text_extraction_success = extraction_success
                
                # Log text extraction
                if ResumeProcessingLog is not None:
                    execution_time = int((time.time() - start_time) * 1000)
                    ResumeProcessingLog.objects.create(
                        resume=resume,
                        step="text_extraction",
                        status="completed" if extraction_success else "failed",
                        message=f"Extracted {len(extracted_text)} characters" if extraction_success else "Text extraction failed",
                        execution_time_ms=execution_time
                    )
                
                if extraction_success and extracted_text.strip():
                    # Step 2: Resume analysis using your ResumeAnalysisService
                    start_time = time.time()
                    
                    # Generate summary
                    summary = ResumeAnalysisService.generate_summary(extracted_text)
                    resume.text_summary = summary
                    
                    # Extract contact information  
                    contact_info = ResumeAnalysisService.extract_contact_info(extracted_text)
                    if contact_info.get('email'):
                        resume.email = contact_info['email']
                    if contact_info.get('phone'):
                        resume.phone = contact_info['phone']
                    
                    # Extract skills
                    skills = ResumeAnalysisService.extract_skills(extracted_text)
                    if skills:
                        resume.skills_json = skills
                        resume.skills = ', '.join(skills)
                    
                    if ResumeProcessingLog is not None:
                        execution_time = int((time.time() - start_time) * 1000)
                        ResumeProcessingLog.objects.create(
                            resume=resume,
                            step="resume_analysis",
                            status="completed",
                            message=f"Extracted {len(skills)} skills and contact info",
                            execution_time_ms=execution_time
                        )
                
            except Exception as e:
                processing_success = False
                if ResumeProcessingLog is not None:
                    ResumeProcessingLog.objects.create(
                        resume=resume,
                        step="text_extraction",
                        status="failed",
                        message=f"Text extraction error: {str(e)}"
                    )
        
        # Step 3: GitHub integration
        if resume.github_username:
            start_time = time.time()
            
            try:
                # Get GitHub profile using your GitHubService
                profile_data, profile_success = GitHubService.get_user_profile(resume.github_username)
                
                # Get repositories
                repos_data, repos_success = GitHubService.get_user_repositories(resume.github_username)
                
                if profile_success:
                    # Store GitHub data in your existing github_data JSONField
                    github_data = {
                        'profile': profile_data,
                        'repositories': repos_data if repos_success else []
                    }
                    resume.github_data = github_data
                    resume.github_sync_success = True
                    resume.github_last_sync = timezone.now()
                    
                    # Update full_name if available from GitHub
                    if profile_data.get('name') and not getattr(resume, 'full_name', ''):
                        resume.full_name = profile_data['name']
                    
                    if ResumeProcessingLog is not None:
                        execution_time = int((time.time() - start_time) * 1000)
                        ResumeProcessingLog.objects.create(
                            resume=resume,
                            step="github_sync",
                            status="completed",
                            message=f"Synced GitHub profile and {len(repos_data)} repositories",
                            execution_time_ms=execution_time
                        )
                else:
                    resume.github_sync_success = False
                    if ResumeProcessingLog is not None:
                        ResumeProcessingLog.objects.create(
                            resume=resume,
                            step="github_sync",
                            status="failed",
                            message=f"GitHub API error: {profile_data.get('error', 'Unknown error')}"
                        )
                    
            except Exception as e:
                resume.github_sync_success = False
                if ResumeProcessingLog is not None:
                    ResumeProcessingLog.objects.create(
                        resume=resume,
                        step="github_sync",
                        status="failed",
                        message=f"GitHub sync error: {str(e)}"
                    )
        
        # Final step: Mark as completed or failed
        if processing_success and getattr(resume, 'text_extraction_success', False):
            resume.mark_completed("Resume processing completed successfully")
            if ResumeProcessingLog is not None:
                ResumeProcessingLog.objects.create(
                    resume=resume,
                    step="processing_complete",
                    status="completed",
                    message="All processing steps completed successfully"
                )
        else:
            resume.mark_failed("Processing completed with errors")
            if ResumeProcessingLog is not None:
                ResumeProcessingLog.objects.create(
                    resume=resume,
                    step="processing_complete",
                    status="failed",
                    message="Processing completed with errors"
                )
        
        resume.save()
        return True, "Processing completed"
        
    except Exception as e:
        if Resume is not None:
            try:
                resume = Resume.objects.get(pk=resume_id)
                resume.mark_failed(f"Processing error: {str(e)}")
                if ResumeProcessingLog is not None:
                    ResumeProcessingLog.objects.create(
                        resume=resume,
                        step="processing_error",
                        status="failed",
                        message=str(e)
                    )
            except Exception:
                pass
        return False, f"Processing failed: {str(e)}"


def process_resume_async(resume_id: int) -> None:
    """Process a resume in background: extract text and sync GitHub data."""
    if not SERVICES_AVAILABLE or Resume is None or ResumeProcessingLog is None:
        return
    
    try:
        resume = Resume.objects.get(id=resume_id)
        resume.mark_processing("Starting background processing")
        
        # Log processing start
        ResumeProcessingLog.objects.create(
            resume=resume,
            step='processing_start',
            status='started',
            message='Background processing started'
        )
        
        start_time = time.time()
        
        # Extract text from file
        if resume.resume_file:
            file_path = resume.resume_file.path
            file_extension = getattr(resume, 'file_extension', '')
            
            extraction_start = time.time()
            extracted_text, extraction_success = TextExtractionService.extract_text(
                file_path, file_extension
            )
            extraction_time = int((time.time() - extraction_start) * 1000)
            
            if extraction_success:
                # Save extracted text
                resume.extracted_text = extracted_text
                resume.text_extraction_success = True
                
                # Generate summary
                resume.text_summary = ResumeAnalysisService.generate_summary(extracted_text)
                
                # Extract contact information
                contact_info = ResumeAnalysisService.extract_contact_info(extracted_text)
                if contact_info.get('email') and not getattr(resume, 'email', ''):
                    resume.email = contact_info['email']
                if contact_info.get('phone') and not getattr(resume, 'phone', ''):
                    resume.phone = contact_info['phone']
                
                # Extract skills
                skills_list = ResumeAnalysisService.extract_skills(extracted_text)
                resume.skills_json = skills_list
                resume.skills = ', '.join(skills_list)
                
                resume.save()
                
                ResumeProcessingLog.objects.create(
                    resume=resume,
                    step='text_extraction',
                    status='completed',
                    message=f'Successfully extracted {len(extracted_text)} characters',
                    execution_time_ms=extraction_time
                )
            else:
                resume.text_extraction_success = False
                resume.save()
                
                ResumeProcessingLog.objects.create(
                    resume=resume,
                    step='text_extraction',
                    status='failed',
                    message=f'Text extraction failed: {extracted_text}',
                    execution_time_ms=extraction_time
                )
        
        # Sync GitHub data
        github_start = time.time()
        github_profile, profile_success = GitHubService.get_user_profile(resume.github_username)
        github_repos, repos_success = GitHubService.get_user_repositories(resume.github_username)
        github_time = int((time.time() - github_start) * 1000)
        
        if profile_success:
            resume.github_data = {
                'profile': github_profile,
                'repositories': github_repos if repos_success else []
            }
            resume.github_last_sync = timezone.now()
            resume.github_sync_success = True
            
            ResumeProcessingLog.objects.create(
                resume=resume,
                step='github_sync',
                status='completed',
                message='Successfully synced GitHub data',
                execution_time_ms=github_time
            )
        else:
            resume.github_sync_success = False
            
            ResumeProcessingLog.objects.create(
                resume=resume,
                step='github_sync',
                status='failed',
                message=f'GitHub sync failed: {github_profile.get("error", "Unknown error")}',
                execution_time_ms=github_time
            )
        
        resume.save()
        
        # Mark as completed
        total_time = int((time.time() - start_time) * 1000)
        resume.mark_completed("Processing completed successfully")
        
        ResumeProcessingLog.objects.create(
            resume=resume,
            step='processing_complete',
            status='completed',
            message='All processing steps completed',
            execution_time_ms=total_time
        )
        
    except Exception as e:
        if Resume is not None:
            try:
                resume = Resume.objects.get(id=resume_id)
                resume.mark_failed(f'Processing failed: {str(e)}')
                
                if ResumeProcessingLog is not None:
                    ResumeProcessingLog.objects.create(
                        resume=resume,
                        step='processing_error',
                        status='failed',
                        message=f'Processing failed with error: {str(e)}'
                    )
            except Exception:
                pass


# Main views (enhanced versions)
def index(request):
    """Home page with dashboard overview."""
    try:
        context = {
            'stats': {},
            'recent_resumes': []
        }
        
        # Add comprehensive stats if Resume model exists
        if Resume is not None:
            context['stats'] = {
                'total_resumes': Resume.objects.count(),
                'completed_processing': Resume.objects.filter(status='completed').count(),
                'pending_processing': Resume.objects.filter(status='pending').count(),
                'failed_processing': Resume.objects.filter(status='failed').count(),
                'text_extraction_success': Resume.objects.filter(text_extraction_success=True).count(),
                'github_sync_success': Resume.objects.filter(github_sync_success=True).count(),
            }
            context['recent_resumes'] = list(Resume.objects.all().order_by('-created_at')[:5])
        
        return render(request, 'resume/index.html', context)
    except Exception as e:
        # Fallback for when models don't exist
        context = {'stats': {}, 'recent_resumes': []}
        return render(request, 'resume/index.html', context)


@require_http_methods(["GET", "POST"])
def upload_resume(request):
    """Handle resume upload with enhanced processing."""
    if request.method == 'GET':
        # Show the upload form
        context = {
            'services_available': SERVICES_AVAILABLE,
            'supported_formats': ['.pdf', '.docx', '.txt']
        }
        return render(request, 'resume/upload.html', context)
    
    elif request.method == 'POST':
        try:
            # Get form data
            github_username = request.POST.get('github', '').strip()
            resume_file = request.FILES.get('resume')
            
            # Validate inputs
            if not github_username or not resume_file:
                messages.error(request, 'GitHub username and resume file are required.')
                return render(request, 'resume/upload.html')
            
            # Validate GitHub username
            if not validate_github_username(github_username):
                messages.error(request, 'Invalid GitHub username format.')
                return render(request, 'resume/upload.html')
            
            # Check for duplicate username
            if Resume is not None and Resume.objects.filter(github_username=github_username).exists():
                messages.error(request, f'Resume for GitHub username "{github_username}" already exists.')
                return render(request, 'resume/upload.html')
            
            # Validate file
            if not validate_file_security(resume_file.name):
                messages.error(request, 'Invalid filename contains dangerous characters.')
                return render(request, 'resume/upload.html')
            
            # Check file size (5MB limit)
            if resume_file.size > 5 * 1024 * 1024:
                messages.error(request, 'File too large. Maximum size is 5MB.')
                return render(request, 'resume/upload.html')
            
            # Check file extension
            allowed_extensions = {'.pdf', '.docx', '.txt'}
            file_extension = Path(resume_file.name).suffix.lower()
            if file_extension not in allowed_extensions:
                messages.error(request, f'File type not allowed. Supported types: {", ".join(allowed_extensions)}')
                return render(request, 'resume/upload.html')
            
            # Create Resume record if model exists
            if Resume is not None:
                resume_obj = Resume.objects.create(
                    github_username=github_username,
                    resume_file=resume_file,  # Let Django handle the file saving
                    original_filename=resume_file.name,
                    file_size=resume_file.size,
                    file_extension=file_extension,
                    status='pending'
                )
                
                # Enhanced processing with immediate execution
                if SERVICES_AVAILABLE:
                    try:
                        # Try immediate processing first
                        success, message = process_uploaded_resume(resume_obj.pk)
                        if success:
                            success_message = 'Resume uploaded and processed successfully! Check the details page to see AI analysis results.'
                        else:
                            # Fall back to background processing if immediate fails
                            processing_thread = threading.Thread(
                                target=process_resume_async,
                                args=(resume_obj.pk,),
                                daemon=True
                            )
                            processing_thread.start()
                            success_message = f'Resume uploaded! Processing started in background. Error: {message}'
                    except Exception as e:
                        success_message = f'Resume uploaded but processing failed: {str(e)}'
                else:
                    success_message = f'Resume uploaded successfully! File: {resume_file.name}'
                
                messages.success(request, success_message)
                return redirect('resume:resume_detail', pk=resume_obj.pk)
            else:
                messages.success(request, f'Resume uploaded successfully! File: {resume_file.name}')
                return redirect('resume:uploaded_resumes')
            
        except Exception as e:
            messages.error(request, f'Upload failed: {str(e)}')
            return render(request, 'resume/upload.html')


def uploaded_resumes(request):
    """Display list of uploaded resumes with filtering."""
    context = {'resumes': [], 'filter_status': 'all'}
    
    if Resume is not None:
        resumes = Resume.objects.all().order_by('-created_at')
        
        # Filter by status if requested
        status_filter = request.GET.get('status')
        if status_filter and status_filter != 'all':
            resumes = resumes.filter(status=status_filter)
            context['filter_status'] = status_filter
        
        # Search functionality
        search_query = request.GET.get('q')
        if search_query:
            resumes = resumes.filter(
                Q(github_username__icontains=search_query) |
                Q(original_filename__icontains=search_query) |
                Q(full_name__icontains=search_query) |
                Q(email__icontains=search_query)
            )
            context['search_query'] = search_query
        
        # Add pagination
        paginator = Paginator(resumes, 10)  # Show 10 resumes per page
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context['resumes'] = page_obj
        context['total_count'] = resumes.count()
        
        # Add status counts for filter buttons
        context['status_counts'] = {
            'all': Resume.objects.count(),
            'pending': Resume.objects.filter(status='pending').count(),
            'processing': Resume.objects.filter(status='processing').count(),
            'completed': Resume.objects.filter(status='completed').count(),
            'failed': Resume.objects.filter(status='failed').count(),
        }
    
    return render(request, 'resume/resumes_list.html', context)


def resume_detail(request, pk):
    """Display detailed view of a specific resume with processing info."""
    if Resume is None:
        return render(request, 'resume/resume_detail.html', {'resume': None, 'pk': pk})
    
    try:
        resume = get_object_or_404(Resume, pk=pk)
        
        # FIXED: Get processing logs if available using getattr to avoid attribute errors
        processing_logs = []
        if ResumeProcessingLog is not None:
            # Use getattr to safely access the processing_logs relationship
            processing_logs_manager = getattr(resume, 'processing_logs', None)
            if processing_logs_manager is not None:
                processing_logs = processing_logs_manager.all()[:10]
        
        context = {
            'resume': resume,
            'processing_logs': processing_logs,
            'services_available': SERVICES_AVAILABLE,
            'github_profile': getattr(resume, 'github_profile', None),
            'github_repositories': getattr(resume, 'github_repositories', [])[:5],
        }
        
        return render(request, 'resume/resume_detail.html', context)
    except Exception:
        return render(request, 'resume/resume_detail.html', {'resume': None, 'pk': pk})


def statistics(request):
    """Display comprehensive system statistics."""
    context = {'stats': {}}
    
    if Resume is not None:
        total_resumes = Resume.objects.count()
        
        context['stats'] = {
            'total_resumes': total_resumes,
            'completed_processing': Resume.objects.filter(status='completed').count(),
            'pending_processing': Resume.objects.filter(status='pending').count(),
            'failed_processing': Resume.objects.filter(status='failed').count(),
            'processing_rate': Resume.objects.filter(status='processing').count(),
            'text_extraction_success': Resume.objects.filter(text_extraction_success=True).count(),
            'github_sync_success': Resume.objects.filter(github_sync_success=True).count(),
            'total_file_size': sum(getattr(r, 'file_size', 0) for r in Resume.objects.all()) / (1024 * 1024),
        }
        
        # Calculate success rates
        if total_resumes > 0:
            context['stats']['completion_rate'] = round(
                (context['stats']['completed_processing'] / total_resumes) * 100, 1
            )
            context['stats']['text_extraction_rate'] = round(
                (context['stats']['text_extraction_success'] / total_resumes) * 100, 1
            )
            context['stats']['github_sync_rate'] = round(
                (context['stats']['github_sync_success'] / total_resumes) * 100, 1
            )
        
        # FIXED: Recent activity - convert QuerySet to list to avoid type error
        recent_resumes = list(Resume.objects.order_by('-updated_at')[:10])
        context['recent_activity'] = recent_resumes
    
    return render(request, 'resume/statistics.html', context)


def resume_text(request, pk):
    """Display extracted text from resume."""
    if Resume is None:
        return HttpResponse("Resume functionality not available")
    
    resume = get_object_or_404(Resume, pk=pk)
    
    context = {
        'resume': resume,
        'extracted_text': getattr(resume, 'extracted_text', ''),
        'word_count': getattr(resume, 'word_count', 0),
        'text_preview': getattr(resume, 'text_preview', ''),
    }
    
    return render(request, 'resume/resume_text.html', context)


def resume_processing_logs(request, pk):
    """Display processing logs for a resume."""
    if Resume is None or ResumeProcessingLog is None:
        return HttpResponse("Logging functionality not available")
    
    resume = get_object_or_404(Resume, pk=pk)
    
    # FIXED: Use getattr to safely access processing_logs relationship
    logs = []
    processing_logs_manager = getattr(resume, 'processing_logs', None)
    if processing_logs_manager is not None:
        logs = processing_logs_manager.all()
    
    context = {
        'resume': resume,
        'logs': logs,
    }
    
    return render(request, 'resume/processing_logs.html', context)


def resume_github_sync(request, pk):
    """Manually trigger GitHub sync for a resume."""
    if Resume is None or not SERVICES_AVAILABLE:
        messages.error(request, "GitHub sync functionality not available")
        return redirect('resume:resume_detail', pk=pk)
    
    resume = get_object_or_404(Resume, pk=pk)
    
    try:
        # Trigger GitHub sync
        github_profile, profile_success = GitHubService.get_user_profile(resume.github_username)
        github_repos, repos_success = GitHubService.get_user_repositories(resume.github_username)
        
        if profile_success:
            resume.github_data = {
                'profile': github_profile,
                'repositories': github_repos if repos_success else []
            }
            resume.github_last_sync = timezone.now()
            resume.github_sync_success = True
            resume.save()
            
            messages.success(request, 'GitHub data synchronized successfully!')
        else:
            messages.error(request, f'GitHub sync failed: {github_profile.get("error", "Unknown error")}')
    
    except Exception as e:
        messages.error(request, f'GitHub sync failed: {str(e)}')
    
    return redirect('resume:resume_detail', pk=pk)


def reprocess_resume(request, pk):
    """Manually reprocess a resume."""
    if Resume is None or not SERVICES_AVAILABLE:
        messages.error(request, "Reprocessing functionality not available")
        return redirect('resume:resume_detail', pk=pk)
    
    resume = get_object_or_404(Resume, pk=pk)
    
    # Try immediate processing first
    try:
        success, message = process_uploaded_resume(resume.pk)
        if success:
            messages.success(request, 'Resume reprocessed successfully!')
        else:
            # Fall back to background processing
            processing_thread = threading.Thread(
                target=process_resume_async,
                args=(resume.pk,),
                daemon=True
            )
            processing_thread.start()
            messages.success(request, f'Resume reprocessing started. Error: {message}')
    except Exception as e:
        messages.error(request, f'Reprocessing failed: {str(e)}')
    
    return redirect('resume:resume_detail', pk=pk)


def help_page(request):
    """Display help and documentation."""
    context = {
        'services_available': SERVICES_AVAILABLE,
        'supported_formats': ['.pdf', '.docx', '.txt']
    }
    return render(request, 'resume/help.html', context)


def dashboard(request):
    """Dashboard view."""
    return redirect('resume:index')


def edit_resume(request, pk):
    """Edit resume details."""
    if Resume is None:
        return render(request, 'resume/edit_resume.html', {'resume': None, 'pk': pk})
    
    resume = get_object_or_404(Resume, pk=pk)
    return render(request, 'resume/edit_resume.html', {'resume': resume})


def delete_resume(request, pk):
    """Delete resume."""
    if Resume is None:
        messages.error(request, "Resume functionality not available")
        return redirect('resume:uploaded_resumes')
    
    resume = get_object_or_404(Resume, pk=pk)
    if request.method == 'POST':
        resume.delete()
        messages.success(request, 'Resume deleted successfully.')
        return redirect('resume:uploaded_resumes')
    
    return render(request, 'resume/delete_confirm.html', {'resume': resume})


def download_resume(request, pk):
    """Download resume file."""
    if Resume is None:
        return HttpResponse("Resume functionality not available")
    
    resume = get_object_or_404(Resume, pk=pk)
    
    if resume.resume_file:
        response = HttpResponse(
            resume.resume_file.read(),
            content_type='application/octet-stream'
        )
        response['Content-Disposition'] = f'attachment; filename="{resume.original_filename}"'
        return response
    else:
        messages.error(request, 'Resume file not found.')
        return redirect('resume:resume_detail', pk=pk)


def search_resumes(request):
    """Enhanced search resumes."""
    query = request.GET.get('q', '')
    context = {'query': query, 'results': []}
    
    if Resume is not None and query:
        results = Resume.objects.filter(
            Q(github_username__icontains=query) |
            Q(original_filename__icontains=query) |
            Q(full_name__icontains=query) |
            Q(email__icontains=query) |
            Q(skills__icontains=query) |
            Q(extracted_text__icontains=query)
        ).distinct()
        
        context['results'] = results
        context['count'] = results.count()
    
    return render(request, 'resume/search_results.html', context)


def github_profile(request, username):
    """Display GitHub profile integration."""
    context = {'username': username}
    
    # Try to find resume with this GitHub username
    if Resume is not None:
        try:
            resume = Resume.objects.get(github_username=username)
            context['resume'] = resume
            context['github_data'] = getattr(resume, 'github_data', {})
        except Resume.DoesNotExist:
            pass
    
    return render(request, 'resume/github_profile.html', context)


def summary_page(request):
    """Display summary page."""
    context = {}
    
    if Resume is not None:
        context['total_resumes'] = Resume.objects.count()
        context['recent_summaries'] = Resume.objects.filter(
            text_summary__isnull=False
        ).exclude(text_summary='')[:10]
    
    return render(request, 'resume/summary.html', context)


def about(request):
    """About page."""
    return render(request, 'resume/about.html')


# FIXED: Added the missing settings function that matches your URL pattern
def settings(request):
    """Settings page."""
    return render(request, 'resume/settings.html')


# API endpoints (enhanced)
def api_resumes_list(request):
    """API endpoint for resumes list."""
    if Resume is None:
        return JsonResponse({'resumes': []})
    
    resumes = Resume.objects.all()
    
    # Apply filters
    status = request.GET.get('status')
    if status:
        resumes = resumes.filter(status=status)
    
    # Serialize data
    resume_data = []
    for resume in resumes:
        resume_data.append({
            'id': getattr(resume, 'id', None),
            'github_username': resume.github_username,
            'original_filename': resume.original_filename,
            'status': resume.status,
            'file_size': resume.file_size,
            'created_at': resume.created_at.isoformat(),
            'has_extracted_text': getattr(resume, 'has_extracted_text', False),
            'has_github_data': getattr(resume, 'has_github_data', False),
            'text_extraction_success': getattr(resume, 'text_extraction_success', False),
            'github_sync_success': getattr(resume, 'github_sync_success', False),
        })
    
    return JsonResponse({'resumes': resume_data})


def health_check(request):
    """Enhanced system health check."""
    return JsonResponse({
        'status': 'healthy',
        'timestamp': datetime.now().isoformat(),
        'database': Resume is not None,
        'services_available': SERVICES_AVAILABLE,
        'total_resumes': Resume.objects.count() if Resume is not None else 0,
        'processing_queue': Resume.objects.filter(status='processing').count() if Resume is not None else 0,
    })


# Error handler views
def error_404(request, exception):
    """Custom 404 error page"""
    context = {
        'error_code': '404',
        'error_message': 'Page Not Found',
        'error_description': 'The page you are looking for might have been removed, had its name changed, or is temporarily unavailable.'
    }
    return render(request, 'resume/error.html', context, status=404)


def error_500(request):
    """Custom 500 error page"""
    context = {
        'error_code': '500', 
        'error_message': 'Internal Server Error',
        'error_description': 'Something went wrong on our server. We are working to fix the issue.'
    }
    return render(request, 'resume/error.html', context, status=500)


# Keep all remaining placeholder views as they are
def processing_queue(request):
    return HttpResponse("Processing queue - Not implemented yet")


def filter_resumes(request):
    return HttpResponse("Filter resumes - Not implemented yet")


def resumes_by_status(request, status):
    return HttpResponse(f"Resumes by status: {status} - Not implemented yet")


def resumes_by_skill(request, skill):
    return HttpResponse(f"Resumes by skill: {skill} - Not implemented yet")


def bulk_actions(request):
    return HttpResponse("Bulk actions - Not implemented yet")


def bulk_delete(request):
    return HttpResponse("Bulk delete - Not implemented yet")


def bulk_process(request):
    return HttpResponse("Bulk process - Not implemented yet")


def reports(request):
    return HttpResponse("Reports - Not implemented yet")


def analytics(request):
    return HttpResponse("Analytics - Not implemented yet")


def export_resumes(request):
    return HttpResponse("Export resumes - Not implemented yet")


def export_csv(request):
    return HttpResponse("Export CSV - Not implemented yet")


def export_json(request):
    return HttpResponse("Export JSON - Not implemented yet")


def export_pdf_report(request):
    return HttpResponse("Export PDF report - Not implemented yet")


def user_preferences(request):
    return HttpResponse("User preferences - Not implemented yet")


def resume_summary(request, pk):
    return HttpResponse(f"Resume summary {pk} - Not implemented yet")


def resume_analysis(request, pk):
    return HttpResponse(f"Resume analysis {pk} - Not implemented yet")


def resume_status(request, pk):
    return HttpResponse(f"Resume status {pk} - Not implemented yet")


def api_resume_detail(request, pk):
    return JsonResponse({'message': f'API resume detail {pk} - Not implemented yet'})


def api_upload_resume(request):
    return JsonResponse({'message': 'API upload resume - Not implemented yet'})


def api_search_resumes(request):
    return JsonResponse({'message': 'API search resumes - Not implemented yet'})


def api_statistics(request):
    return JsonResponse({'message': 'API statistics - Not implemented yet'})


def metrics(request):
    return JsonResponse({'message': 'Metrics - Not implemented yet'})


def system_status(request):
    return JsonResponse({'message': 'System status - Not implemented yet'})
