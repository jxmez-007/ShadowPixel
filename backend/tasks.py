"""
Background tasks for resume processing.
"""

from django.conf import settings
from .models import Resume, ProcessingLog
from .services import TextExtractionService, ResumeAnalysisService, GitHubService
import logging
import os

logger = logging.getLogger(__name__)

def process_resume(resume_id: int):
    """Process a resume: extract text, analyze content, and sync GitHub data."""
    try:
        resume = Resume.objects.get(id=resume_id)
        resume.status = 'processing'
        resume.save()
        
        # Log processing start
        ProcessingLog.objects.create(
            resume=resume,
            stage='start',
            message='Starting resume processing'
        )
        
        # Extract text from file
        file_path = resume.file_path.path
        file_extension = os.path.splitext(resume.original_filename)[1]
        
        extracted_text, extraction_success = TextExtractionService.extract_text(
            file_path, file_extension
        )
        
        if extraction_success:
            resume.extracted_text = extracted_text
            
            # Generate summary
            resume.text_summary = ResumeAnalysisService.generate_summary(extracted_text)
            
            # Extract contact information
            contact_info = ResumeAnalysisService.extract_contact_info(extracted_text)
            resume.email = contact_info.get('email')
            resume.phone = contact_info.get('phone')
            
            # Extract skills
            resume.skills = ResumeAnalysisService.extract_skills(extracted_text)
            
            ProcessingLog.objects.create(
                resume=resume,
                stage='text_extraction',
                message=f'Successfully extracted {len(extracted_text)} characters'
            )
        else:
            ProcessingLog.objects.create(
                resume=resume,
                stage='text_extraction',
                message=f'Text extraction failed: {extracted_text}',
                success=False
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
            
            ProcessingLog.objects.create(
                resume=resume,
                stage='github_sync',
                message='Successfully synced GitHub data'
            )
        else:
            ProcessingLog.objects.create(
                resume=resume,
                stage='github_sync',
                message=f'GitHub sync failed: {github_profile.get("error", "Unknown error")}',
                success=False
            )
        
        # Mark as completed
        resume.status = 'completed'
        resume.save()
        
        ProcessingLog.objects.create(
            resume=resume,
            stage='complete',
            message='Resume processing completed successfully'
        )
        
    except Resume.DoesNotExist:
        logger.error(f"Resume with ID {resume_id} not found")
    except Exception as e:
        logger.error(f"Error processing resume {resume_id}: {e}")
        try:
            resume = Resume.objects.get(id=resume_id)
            resume.status = 'failed'
            resume.save()
            
            ProcessingLog.objects.create(
                resume=resume,
                stage='error',
                message=f'Processing failed: {str(e)}',
                success=False
            )
        except:
            pass
