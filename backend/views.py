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
from django.conf import settings as django_settings
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

# Import AI summary functions
try:
    from .utils import generate_ai_summary, generate_simple_summary
    AI_SUMMARY_AVAILABLE = True
except ImportError:
    AI_SUMMARY_AVAILABLE = False
    def generate_ai_summary(resume_text: str) -> str:
        return "AI summary not available"
    def generate_simple_summary(resume_text: str) -> str:
        return "Summary generation not available"

# FIXED: Always create service classes to avoid None attribute errors
class _FallbackTextExtraction:
    @staticmethod
    def extract_text(file_path: str, file_extension: str) -> Tuple[str, bool]:
        return "Service not available", False

class _FallbackResumeAnalysis:
    @staticmethod
    def generate_summary(text: str) -> str:
        return "Service not available"
    @staticmethod
    def extract_contact_info(text: str) -> Dict[str, Any]:
        return {}
    @staticmethod
    def extract_skills(text: str) -> List[str]:
        return []

class _FallbackGitHub:
    @staticmethod
    def get_user_profile(username: str) -> Tuple[Dict[str, Any], bool]:
        return {"error": "Service not available"}, False
    @staticmethod
    def get_user_repositories(username: str) -> Tuple[List[Any], bool]:
        return [], False

# FIXED: Always assign service classes - never None
try:
    from .services import TextExtractionService as _RealTextExtraction
    from .services import ResumeAnalysisService as _RealResumeAnalysis
    from .services import GitHubService as _RealGitHub
    
    TextExtractionService = _RealTextExtraction
    ResumeAnalysisService = _RealResumeAnalysis
    GitHubService = _RealGitHub
    SERVICES_AVAILABLE = True
    
except ImportError:
    TextExtractionService = _FallbackTextExtraction
    ResumeAnalysisService = _FallbackResumeAnalysis
    GitHubService = _FallbackGitHub
    SERVICES_AVAILABLE = False

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
    """Process a resume using your existing services and models with AI SUMMARY"""
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
        
        # Step 1: Text extraction - FIXED: Services are never None now
        if resume.resume_file:
            start_time = time.time()
            
            try:
                file_path = resume.resume_file.path
                file_extension = getattr(resume, 'file_extension', '')
                
                # FIXED: No None check needed - always has extract_text method
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
                    # Step 2: Enhanced Resume analysis with AI SUMMARY
                    start_time = time.time()
                    
                    # Generate AI summary using our utils.py function
                    if AI_SUMMARY_AVAILABLE:
                        try:
                            ai_summary = generate_ai_summary(extracted_text)
                            resume.text_summary = ai_summary
                            print(f"✅ AI Summary Generated: {ai_summary[:100]}...")
                        except Exception as e:
                            print(f"❌ AI Summary failed, using fallback: {e}")
                            resume.text_summary = generate_simple_summary(extracted_text)
                    else:
                        # Use existing ResumeAnalysisService or simple fallback
                        try:
                            # FIXED: No None check needed
                            resume.text_summary = ResumeAnalysisService.generate_summary(extracted_text)
                        except Exception:
                            resume.text_summary = generate_simple_summary(extracted_text)
                    
                    # Extract contact information - FIXED: No None check needed
                    contact_info = ResumeAnalysisService.extract_contact_info(extracted_text)
                    if contact_info.get('email'):
                        resume.email = contact_info['email']
                    if contact_info.get('phone'):
                        resume.phone = contact_info['phone']
                    
                    # Extract skills - FIXED: No None check needed
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
                            message=f"Generated AI summary and extracted {len(skills)} skills",
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
        
        # Step 3: GitHub integration - FIXED: No None check needed
        if resume.github_username:
            start_time = time.time()
            
            try:
                profile_data, profile_success = GitHubService.get_user_profile(resume.github_username)
                repos_data, repos_success = GitHubService.get_user_repositories(resume.github_username)
                
                if profile_success:
                    github_data = {
                        'profile': profile_data,
                        'repositories': repos_data if repos_success else []
                    }
                    resume.github_data = github_data
                    resume.github_sync_success = True
                    resume.github_last_sync = timezone.now()
                    
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
        return True, "Processing completed with AI summary"
        
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
    """Process a resume in background: extract text and sync GitHub data with AI SUMMARY."""
    if not SERVICES_AVAILABLE or Resume is None or ResumeProcessingLog is None:
        return
    
    try:
        resume = Resume.objects.get(id=resume_id)
        resume.mark_processing("Starting background processing")
        
        ResumeProcessingLog.objects.create(
            resume=resume,
            step='processing_start',
            status='started',
            message='Background processing started'
        )
        
        start_time = time.time()
        
        # Extract text from file - FIXED: No None check needed
        if resume.resume_file:
            file_path = resume.resume_file.path
            file_extension = getattr(resume, 'file_extension', '')
            
            extraction_start = time.time()
            extracted_text, extraction_success = TextExtractionService.extract_text(
                file_path, file_extension
            )
            extraction_time = int((time.time() - extraction_start) * 1000)
            
            if extraction_success:
                resume.extracted_text = extracted_text
                resume.text_extraction_success = True
                
                # Generate AI summary
                if AI_SUMMARY_AVAILABLE and extracted_text.strip():
                    try:
                        ai_summary = generate_ai_summary(extracted_text)
                        resume.text_summary = ai_summary
                        print(f"✅ Background AI Summary: {ai_summary[:50]}...")
                    except Exception as e:
                        print(f"❌ Background AI failed: {e}")
                        resume.text_summary = generate_simple_summary(extracted_text)
                else:
                    # Fallback to existing service - FIXED: No None check needed
                    resume.text_summary = ResumeAnalysisService.generate_summary(extracted_text)
                
                # Extract contact information - FIXED: No None check needed
                contact_info = ResumeAnalysisService.extract_contact_info(extracted_text)
                if contact_info.get('email') and not getattr(resume, 'email', ''):
                    resume.email = contact_info['email']
                if contact_info.get('phone') and not getattr(resume, 'phone', ''):
                    resume.phone = contact_info['phone']
                
                # Extract skills - FIXED: No None check needed
                skills_list = ResumeAnalysisService.extract_skills(extracted_text)
                resume.skills_json = skills_list
                resume.skills = ', '.join(skills_list)
                
                resume.save()
                
                ResumeProcessingLog.objects.create(
                    resume=resume,
                    step='text_extraction',
                    status='completed',
                    message=f'Successfully extracted {len(extracted_text)} characters and generated AI summary',
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
        
        # GitHub sync - FIXED: No None check needed
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
            message='All processing steps completed with AI summary',
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

# Main views
def index(request):
    """Home page with dashboard overview."""
    try:
        context: Dict[str, Any] = {
            'stats': {},
            'recent_resumes': [],
            'ai_summary_available': AI_SUMMARY_AVAILABLE
        }
        
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
        context: Dict[str, Any] = {'stats': {}, 'recent_resumes': [], 'ai_summary_available': AI_SUMMARY_AVAILABLE}
        return render(request, 'resume/index.html', context)

@require_http_methods(["GET", "POST"])
def upload_resume(request):
    """Handle resume upload with enhanced processing."""
    if request.method == 'GET':
        context = {
            'services_available': SERVICES_AVAILABLE,
            'ai_summary_available': AI_SUMMARY_AVAILABLE,
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
            
            if not validate_github_username(github_username):
                messages.error(request, 'Invalid GitHub username format.')
                return render(request, 'resume/upload.html')
            
            if Resume is not None and Resume.objects.filter(github_username=github_username).exists():
                messages.error(request, f'Resume for GitHub username "{github_username}" already exists.')
                return render(request, 'resume/upload.html')
            
            if not validate_file_security(resume_file.name):
                messages.error(request, 'Invalid filename contains dangerous characters.')
                return render(request, 'resume/upload.html')
            
            if resume_file.size > 5 * 1024 * 1024:
                messages.error(request, 'File too large. Maximum size is 5MB.')
                return render(request, 'resume/upload.html')
            
            allowed_extensions = {'.pdf', '.docx', '.txt'}
            file_extension = Path(resume_file.name).suffix.lower()
            if file_extension not in allowed_extensions:
                messages.error(request, f'File type not allowed. Supported types: {", ".join(allowed_extensions)}')
                return render(request, 'resume/upload.html')
            
            # Create Resume record
            if Resume is not None:
                resume_obj = Resume.objects.create(
                    github_username=github_username,
                    resume_file=resume_file,
                    original_filename=resume_file.name,
                    file_size=resume_file.size,
                    status='pending'
                )
                
                # Enhanced processing with AI summary
                if SERVICES_AVAILABLE:
                    try:
                        success, message = process_uploaded_resume(resume_obj.pk)
                        if success:
                            success_message = '🎉 Resume uploaded and processed successfully! ✨ AI-powered summary generated. Check the details page to see your AI analysis!'
                        else:
                            processing_thread = threading.Thread(
                                target=process_resume_async,
                                args=(resume_obj.pk,),
                                daemon=True
                            )
                            processing_thread.start()
                            success_message = f'Resume uploaded! 🚀 AI processing started in background. {message}'
                    except Exception as e:
                        success_message = f'Resume uploaded but AI processing failed: {str(e)}'
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

# ADDED: All missing view functions to fix the server error
def uploaded_resumes(request):
    """Display list of uploaded resumes with filtering."""
    context: Dict[str, Any] = {'resumes': [], 'filter_status': 'all'}
    
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
        paginator = Paginator(resumes, 10)
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
        
        # Get processing logs if available
        processing_logs = []
        if ResumeProcessingLog is not None:
            processing_logs_manager = getattr(resume, 'processing_logs', None)
            if processing_logs_manager is not None:
                processing_logs = processing_logs_manager.all()[:10]

        skill_list = []
        if resume.skills:
            skill_list = [skill.strip() for skill in resume.skills.split(',')]
        
        context = {
            'resume': resume,
            'skills': skill_list,
            'processing_logs': processing_logs,
            'services_available': SERVICES_AVAILABLE,
            'ai_summary_available': AI_SUMMARY_AVAILABLE,
            'github_profile': getattr(resume, 'github_profile', None),
            'github_repositories': getattr(resume, 'github_repositories', [])[:5],
        }
        
        return render(request, 'resume/resume_detail.html', context)
    except Exception:
        return render(request, 'resume/resume_detail.html', {'resume': None, 'pk': pk})

def dashboard(request):
    """Dashboard view - redirect to index."""
    return redirect('resume:index')

def statistics(request):
    """Display comprehensive system statistics."""
    context: Dict[str, Any] = {'stats': {}}
    
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
        
        recent_resumes: List[Any] = list(Resume.objects.order_by('-updated_at')[:10])
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
    
    try:
        success, message = process_uploaded_resume(resume.pk)
        if success:
            messages.success(request, '🎉 Resume reprocessed successfully! AI summary regenerated.')
        else:
            processing_thread = threading.Thread(
                target=process_resume_async,
                args=(resume.pk,),
                daemon=True
            )
            processing_thread.start()
            messages.success(request, f'Resume reprocessing started in background. {message}')
    except Exception as e:
        messages.error(request, f'Reprocessing failed: {str(e)}')
    
    return redirect('resume:resume_detail', pk=pk)

def help_page(request):
    """Display help and documentation."""
    context = {
        'services_available': SERVICES_AVAILABLE,
        'ai_summary_available': AI_SUMMARY_AVAILABLE,
        'supported_formats': ['.pdf', '.docx', '.txt']
    }
    return render(request, 'resume/help.html', context)

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
    context: Dict[str, Any] = {'query': query, 'results': []}
    
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
    context: Dict[str, Any] = {'username': username}
    
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
    context: Dict[str, Any] = {}
    
    if Resume is not None:
        context['total_resumes'] = Resume.objects.count()
        context['recent_summaries'] = Resume.objects.filter(
            text_summary__isnull=False
        ).exclude(text_summary='')[:10]
    
    return render(request, 'resume/summary.html', context)

def about(request):
    """About page."""
    return render(request, 'resume/about.html')

def settings(request):
    """Settings page."""
    return render(request, 'resume/settings.html')

# API endpoints
def api_resumes_list(request):
    """API endpoint for resumes list."""
    if Resume is None:
        return JsonResponse({'resumes': []})
    
    resumes = Resume.objects.all()
    
    status = request.GET.get('status')
    if status:
        resumes = resumes.filter(status=status)
    
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
        'ai_summary_available': AI_SUMMARY_AVAILABLE,
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

# Placeholder views for all URL mappings
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
