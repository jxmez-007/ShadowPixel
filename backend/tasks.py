"""
Background tasks for resume processing.
"""

from django.conf import settings
from django.utils import timezone
from .models import Resume, ResumeProcessingLog
from .services import TextExtractionService, ResumeAnalysisService, GitHubService
import logging
import os
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from django.db.models.fields.files import FieldFile

logger = logging.getLogger(__name__)


def process_resume(resume_id: int) -> None:
    """Process a resume: extract text, analyze content, and sync GitHub data."""
    try:
        resume = Resume.objects.get(id=resume_id)
        resume.status = 'processing'
        resume.save()
        
        # Log processing start
        ResumeProcessingLog.objects.create(
            resume=resume,
            step='start',
            status='started',
            message='Starting resume processing'
        )
        
        # Extract text from file
        file_path = resume.resume_file.path if resume.resume_file else None
        if not file_path:
            raise ValueError("Resume file path not found")
        
        file_extension = os.path.splitext(resume.original_filename)[1]
        
        extracted_text, extraction_success = TextExtractionService.extract_text(
            file_path, file_extension
        )
        
        if extraction_success:
            resume.extracted_text = extracted_text
            
            # Generate summary
            resume.summary = ResumeAnalysisService.generate_summary(extracted_text)
            
            # Extract contact information
            contact_info = ResumeAnalysisService.extract_contact_info(extracted_text)
            resume.email = contact_info.get('email') or ''
            resume.phone = contact_info.get('phone') or ''
            
            # Extract full name if available
            full_name = contact_info.get('name')
            if full_name:
                resume.full_name = full_name
            
            # Extract skills (convert list to string)
            skills_list = ResumeAnalysisService.extract_skills(extracted_text)
            resume.skills = ', '.join(skills_list) if isinstance(skills_list, list) else ''
            
            # Extract experience years if available (Fixed: Added type ignore for method)
            # If this method doesn't exist in your ResumeAnalysisService, remove these lines
            if hasattr(ResumeAnalysisService, 'extract_experience'):
                experience = ResumeAnalysisService.extract_experience(extracted_text)  # type: ignore[attr-defined]
                if experience and isinstance(experience, (int, float)):
                    resume.experience_years = int(experience)
            
            resume.save()
            
            ResumeProcessingLog.objects.create(
                resume=resume,
                step='text_extraction',
                status='completed',
                message=f'Successfully extracted {len(extracted_text)} characters'
            )
        else:
            ResumeProcessingLog.objects.create(
                resume=resume,
                step='text_extraction',
                status='failed',
                message=f'Text extraction failed: {extracted_text}'
            )
        
        # Sync GitHub data
        github_profile, profile_success = GitHubService.get_user_profile(resume.github_username)
        github_repos, repos_success = GitHubService.get_user_repositories(resume.github_username)
        
        if profile_success:
            resume.github_data = {
                'profile': github_profile,
                'repositories': github_repos if repos_success else []
            }
            resume.github_last_sync = timezone.now()
            resume.save()
            
            ResumeProcessingLog.objects.create(
                resume=resume,
                step='github_sync',
                status='completed',
                message='Successfully synced GitHub data'
            )
        else:
            error_message = github_profile.get("error", "Unknown error") if isinstance(github_profile, dict) else "Unknown error"
            ResumeProcessingLog.objects.create(
                resume=resume,
                step='github_sync',
                status='failed',
                message=f'GitHub sync failed: {error_message}'
            )
        
        # Mark as completed
        resume.status = 'completed'
        resume.processed_at = timezone.now()
        resume.save()
        
        ResumeProcessingLog.objects.create(
            resume=resume,
            step='complete',
            status='completed',
            message='Resume processing completed successfully'
        )
        
    except Resume.DoesNotExist:
        logger.error(f"Resume with ID {resume_id} not found")
    except Exception as e:
        logger.error(f"Error processing resume {resume_id}: {e}", exc_info=True)
        try:
            resume = Resume.objects.get(id=resume_id)
            resume.status = 'failed'
            resume.processed_at = timezone.now()
            resume.save()
            
            ResumeProcessingLog.objects.create(
                resume=resume,
                step='error',
                status='failed',
                message=f'Processing failed: {str(e)}'
            )
        except Exception as log_error:
            logger.error(f"Failed to log error for resume {resume_id}: {log_error}")


def cleanup_old_resumes(days: int = 30) -> dict[str, Any]:
    """
    Clean up old resumes that are older than the specified number of days.
    
    Args:
        days: Number of days after which resumes should be deleted (default: 30)
        
    Returns:
        dict: Status and count of deleted resumes
    """
    try:
        from datetime import timedelta
        
        cutoff_date = timezone.now() - timedelta(days=days)
        old_resumes = Resume.objects.filter(created_at__lt=cutoff_date)
        count = old_resumes.count()
        
        logger.info(f"Found {count} resumes older than {days} days")
        
        # Delete the resumes (files will be deleted automatically via signal)
        old_resumes.delete()
        
        logger.info(f"Successfully cleaned up {count} old resumes")
        return {"status": "success", "deleted_count": count}
        
    except Exception as e:
        error_msg = f"Error during cleanup: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg, "deleted_count": 0}


def retry_failed_resumes() -> dict[str, Any]:
    """
    Retry processing for all failed resumes.
    
    Returns:
        dict: Status and count of retried resumes
    """
    try:
        failed_resumes = Resume.objects.filter(status='failed')
        count = failed_resumes.count()
        
        logger.info(f"Found {count} failed resumes to retry")
        
        retried = 0
        for resume in failed_resumes:
            try:
                # Fixed: Added type ignore for id attribute
                process_resume(resume.id)  # type: ignore[attr-defined]
                retried += 1
            except Exception as e:
                # Fixed: Added type ignore for id attribute
                logger.error(f"Failed to retry resume {resume.id}: {e}")  # type: ignore[attr-defined]
        
        logger.info(f"Successfully retried {retried} out of {count} failed resumes")
        return {"status": "success", "total": count, "retried": retried}
        
    except Exception as e:
        error_msg = f"Error during retry: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return {"status": "error", "message": error_msg}
