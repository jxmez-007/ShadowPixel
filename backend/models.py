"""
Django models for Resume Upload Service.

This module contains the Resume model and related functionality for handling
resume uploads with GitHub username validation and file processing.
"""

from typing import Optional
from django.db import models
from django.core.validators import RegexValidator, FileExtensionValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.template.defaultfilters import filesizeformat
import os
import uuid
import json

def resume_upload_path(instance: 'Resume', filename: str) -> str:
    """
    Generate secure upload path for resume files.
    
    Args:
        instance: The Resume model instance
        filename: Original filename
        
    Returns:
        str: Upload path in format 'resumes/{username}_{uuid}.{ext}'
    """
    # Get file extension safely
    name, ext = os.path.splitext(filename)
    ext = ext.lower() if ext else '.pdf'  # Default to PDF if no extension
    
    # Create unique filename with timestamp
    timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')
    unique_filename = f"{instance.github_username}_{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
    
    return os.path.join('resumes', unique_filename)

def validate_file_size(value) -> None:
    """
    Validate file size (max 5MB).
    
    Args:
        value: The uploaded file
        
    Raises:
        ValidationError: If file size exceeds limit
    """
    max_size = 5 * 1024 * 1024  # 5MB
    if value.size > max_size:
        raise ValidationError(
            f"File size cannot exceed {filesizeformat(max_size)}. "
            f"Current file size: {filesizeformat(value.size)}"
        )

def validate_github_username_format(value: str) -> None:
    """
    Enhanced GitHub username validation.
    
    Args:
        value: Username to validate
        
    Raises:
        ValidationError: If username format is invalid
    """
    if not value:
        raise ValidationError("Username cannot be empty")
    
    if len(value) > 39:
        raise ValidationError("Username cannot exceed 39 characters")
    
    # Single character must be alphanumeric
    if len(value) == 1 and not value.isalnum():
        raise ValidationError("Single character username must be alphanumeric")
    
    # Check for invalid patterns
    if value.startswith('-') or value.endswith('-'):
        raise ValidationError("Username cannot start or end with hyphen")
    
    if '--' in value:
        raise ValidationError("Username cannot contain consecutive hyphens")
    
    # Final regex check
    import re
    pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$'
    if not re.match(pattern, value):
        raise ValidationError(
            "Username can only contain alphanumeric characters and hyphens"
        )

class ResumeManager(models.Manager):
    """Custom manager for Resume model with useful methods."""
    
    def by_status(self, status: str):
        """Get resumes by status."""
        return self.filter(status=status)
    
    def pending(self):
        """Get pending resumes."""
        return self.filter(status='pending')
    
    def completed(self):
        """Get completed resumes."""
        return self.filter(status='completed')
    
    def failed(self):
        """Get failed resumes."""
        return self.filter(status='failed')
    
    def recent(self, days: int = 7):
        """Get resumes uploaded in the last N days."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff_date = timezone.now() - timedelta(days=days)
        return self.filter(created_at__gte=cutoff_date)

class Resume(models.Model):
    """
    Model representing an uploaded resume with associated metadata.
    
    This model stores resume files along with extracted information
    and processing status.
    """
    
    # Status choices
    STATUS_CHOICES = [
        ('pending', 'Pending Processing'),
        ('processing', 'Processing'),
        ('completed', 'Processing Completed'),
        ('failed', 'Processing Failed'),
    ]
    
    # GitHub username validation - Enhanced
    github_username_validator = RegexValidator(
        regex=r'^[a-zA-Z0-9]([a-zA-Z0-9-]*[a-zA-Z0-9])?$',
        message="Invalid GitHub username format. Must be alphanumeric with optional hyphens."
    )
    
    # Core fields
    github_username = models.CharField(
        max_length=39,  # GitHub username max length
        validators=[github_username_validator, validate_github_username_format],
        unique=True,
        db_index=True,
        help_text="GitHub username (unique, 1-39 characters)"
    )
    
    resume_file = models.FileField(
        upload_to=resume_upload_path,
        validators=[
            FileExtensionValidator(
                allowed_extensions=['pdf', 'doc', 'docx', 'txt']
            ),
            validate_file_size
        ],
        help_text="Resume file (PDF, DOC, DOCX, TXT only, max 5MB)"
    )
    
    original_filename = models.CharField(
        max_length=255,
        blank=True,
        db_index=True,
        help_text="Original filename when uploaded"
    )
    
    # NEW: Text extraction fields
    extracted_text = models.TextField(
        blank=True,
        null=True,
        help_text="Full text extracted from the resume file"
    )
    
    text_summary = models.TextField(
        max_length=500,
        blank=True,
        null=True,
        help_text="AI-generated summary of the resume content"
    )
    
    # NEW: GitHub integration fields  
    github_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="GitHub profile and repository data (JSON)"
    )
    
    github_last_sync = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Last time GitHub data was synchronized"
    )
    
    # Extracted information fields (keeping your original structure)
    summary = models.TextField(
        blank=True,
        help_text="AI-generated or manual resume summary"
    )
    
    full_name = models.CharField(
        max_length=200,
        blank=True,
        db_index=True,
        help_text="Full name extracted from resume"
    )
    
    email = models.EmailField(
        blank=True,
        db_index=True,
        help_text="Email extracted from resume"
    )
    
    phone = models.CharField(
        max_length=20,
        blank=True,
        help_text="Phone number extracted from resume"
    )
    
    # ENHANCED: Keep text version but also add JSON version for advanced features
    skills = models.TextField(
        blank=True,
        help_text="Skills extracted from resume (comma-separated)"
    )
    
    # NEW: JSON field for skills (for advanced querying)
    skills_json = models.JSONField(
        default=list,
        blank=True,
        help_text="Skills as JSON list for advanced querying"
    )
    
    experience_years = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Years of experience extracted from resume"
    )
    
    # NEW: Education information
    education = models.JSONField(
        default=list,
        blank=True,
        help_text="Education information extracted from resume"
    )
    
    # NEW: Processing success flags
    text_extraction_success = models.BooleanField(
        default=False,
        help_text="Whether text extraction was successful"
    )
    
    github_sync_success = models.BooleanField(
        default=False,
        help_text="Whether GitHub sync was successful"
    )
    
    # NEW: Compatibility fields for services
    file_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="File path for service compatibility"
    )
    
    file_size = models.PositiveIntegerField(
        default=0,
        help_text="File size in bytes"
    )
    
    # Status and processing fields
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        db_index=True,
        help_text="Current processing status"
    )
    
    processing_notes = models.TextField(
        blank=True,
        help_text="Additional processing notes or error details"
    )
    
    # Timestamp fields
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When the resume was uploaded"
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="When the resume was last updated"
    )
    
    processed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When the resume processing was completed"
    )
    
    # Custom manager
    objects = ResumeManager()
    
    class Meta:
        """Meta options for Resume model."""
        ordering = ['-created_at']
        verbose_name = 'Resume'
        verbose_name_plural = 'Resumes'
        indexes = [
            models.Index(fields=['github_username']),
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['created_at']),
            models.Index(fields=['full_name']),
            models.Index(fields=['email']),
            # NEW: Additional indexes for enhanced features
            models.Index(fields=['text_extraction_success']),
            models.Index(fields=['github_sync_success']),
            models.Index(fields=['github_last_sync']),
        ]
        constraints = [
            models.CheckConstraint(
                check=models.Q(experience_years__gte=0),
                name='positive_experience_years'
            ),
        ]
    
    def __str__(self) -> str:
        """String representation of Resume instance."""
        return f"{self.github_username} - {self.get_status_display()}" # type: ignore
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"<Resume(github_username='{self.github_username}', "
            f"status='{self.status}', created_at='{self.created_at}')>"
        )
    
    def clean(self) -> None:
        """
        Additional model validation.
        
        Raises:
            ValidationError: If validation fails
        """
        super().clean()
        
        # Store original filename if not set
        if self.resume_file and not self.original_filename:
            self.original_filename = os.path.basename(self.resume_file.name)
        
        # Set file_path for compatibility
        if self.resume_file and not self.file_path:
            self.file_path = self.resume_file.name
        
        # Validate file extension matches allowed extensions
        if self.resume_file:
            file_ext = self.file_extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt']
            if file_ext not in allowed_extensions:
                raise ValidationError(
                    f"File extension '{file_ext}' not allowed. "
                    f"Allowed extensions: {', '.join(allowed_extensions)}"
                )
    
    def save(self, *args, **kwargs) -> None:
        """
        Override save method for additional processing.
        
        Args:
            *args: Variable arguments
            **kwargs: Keyword arguments
        """
        # Run clean validation
        self.full_clean()
        
        # Set file size from resume_file if available
        if self.resume_file and not self.file_size:
            try:
                self.file_size = self.resume_file.size
            except (ValueError, OSError):
                self.file_size = 0
        
        # Set file_path for compatibility
        if self.resume_file and not self.file_path:
            self.file_path = self.resume_file.name
        
        # Sync skills between text and JSON formats
        if self.skills and not self.skills_json:
            self.skills_json = [skill.strip() for skill in self.skills.split(',') if skill.strip()]
        elif self.skills_json and not self.skills:
            self.skills = ', '.join(self.skills_json)
        
        # Set processed_at timestamp when status changes to completed or failed
        if self.pk:  # Only for existing records
            try:
                old_instance = Resume.objects.get(pk=self.pk)
                if (old_instance.status != self.status and 
                    self.status in ['completed', 'failed'] and 
                    not self.processed_at):
                    self.processed_at = timezone.now()
            except Resume.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
    
    def delete(self, *args, **kwargs) -> None:
        """
        Override delete to remove file from storage.
        
        Args:
            *args: Variable arguments
            **kwargs: Keyword arguments
        """
        # Delete the physical file
        if self.resume_file:
            try:
                if os.path.isfile(self.resume_file.path):
                    os.remove(self.resume_file.path)
            except (ValueError, OSError) as e:
                # Log the error but don't prevent deletion
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Could not delete file {self.resume_file.name}: {e}")
        
        super().delete(*args, **kwargs)
    
    # Properties for file information (keeping your original methods)
    def get_file_size(self) -> int:
        """
        Get file size in bytes.
        
        Returns:
            int: File size in bytes, 0 if no file
        """
        if self.file_size:
            return self.file_size
        elif self.resume_file:
            try:
                return self.resume_file.size
            except (ValueError, OSError):
                return 0
        return 0
    
    @property
    def file_size_mb(self) -> float:
        """
        Get file size in megabytes.
        
        Returns:
            float: File size in MB rounded to 2 decimal places
        """
        size = self.get_file_size()
        return round(size / (1024 * 1024), 2)
    
    @property
    def file_size_human(self) -> str:
        """
        Get human-readable file size.
        
        Returns:
            str: Formatted file size (e.g., "2.5 MB")
        """
        return filesizeformat(self.get_file_size())
    
    @property
    def file_extension(self) -> str:
        """
        Get file extension.
        
        Returns:
            str: File extension with dot (e.g., '.pdf'), empty string if no file
        """
        if self.resume_file:
            try:
                return os.path.splitext(self.resume_file.name)[1].lower()
            except (ValueError, AttributeError):
                return ''
        return ''
    
    @property
    def is_processing_complete(self) -> bool:
        """
        Check if processing is complete (either succeeded or failed).
        
        Returns:
            bool: True if processing is complete
        """
        return self.status in ['completed', 'failed']
    
    @property
    def processing_duration(self) -> Optional[str]:
        """
        Get processing duration if completed.
        
        Returns:
            Optional[str]: Human-readable duration or None
        """
        if self.processed_at and self.created_at:
            duration = self.processed_at - self.created_at
            total_seconds = int(duration.total_seconds())
            
            if total_seconds < 60:
                return f"{total_seconds} seconds"
            elif total_seconds < 3600:
                minutes = total_seconds // 60
                return f"{minutes} minutes"
            else:
                hours = total_seconds // 3600
                minutes = (total_seconds % 3600) // 60
                return f"{hours} hours, {minutes} minutes"
        return None
    
    # NEW: GitHub-related properties
    @property
    def github_profile(self) -> dict:
        """Get GitHub profile data."""
        return self.github_data.get('profile', {}) if self.github_data else {}
    
    @property
    def github_repositories(self) -> list:
        """Get GitHub repositories data."""
        return self.github_data.get('repositories', []) if self.github_data else []
    
    @property
    def has_github_data(self) -> bool:
        """Check if GitHub data is available."""
        return bool(self.github_data and self.github_data.get('profile'))
    
    # NEW: Text extraction properties
    @property
    def has_extracted_text(self) -> bool:
        """Check if text extraction was successful."""
        return bool(self.extracted_text and self.text_extraction_success)
    
    @property
    def word_count(self) -> int:
        """Get word count of extracted text."""
        return len(self.extracted_text.split()) if self.extracted_text else 0
    
    @property
    def text_preview(self) -> str:
        """Get a preview of the extracted text (first 200 chars)."""
        if self.extracted_text:
            preview = self.extracted_text[:200]
            return preview + "..." if len(self.extracted_text) > 200 else preview
        return ""
    
    # Utility methods (keeping your original methods)
    def mark_processing(self, notes: str = '') -> None:
        """
        Mark resume as processing.
        
        Args:
            notes: Optional processing notes
        """
        self.status = 'processing'
        self.processing_notes = notes
        self.save(update_fields=['status', 'processing_notes', 'updated_at'])
    
    def mark_completed(self, notes: str = '') -> None:
        """
        Mark resume as completed.
        
        Args:
            notes: Optional completion notes
        """
        self.status = 'completed'
        self.processing_notes = notes
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processing_notes', 'processed_at', 'updated_at'])
    
    def mark_failed(self, error_message: str) -> None:
        """
        Mark resume as failed.
        
        Args:
            error_message: Error description
        """
        self.status = 'failed'
        self.processing_notes = error_message
        self.processed_at = timezone.now()
        self.save(update_fields=['status', 'processing_notes', 'processed_at', 'updated_at'])

# Keep your excellent ProcessingLog model exactly as is!
class ResumeProcessingLog(models.Model):
    """
    Model for storing detailed processing logs for resume processing steps.
    
    This model tracks each step of the resume processing pipeline
    for debugging and monitoring purposes.
    """
    
    # Log status choices
    LOG_STATUS_CHOICES = [
        ('started', 'Started'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('warning', 'Warning'),
        ('info', 'Information'),
    ]
    
    # Fields
    resume = models.ForeignKey(
        Resume,
        on_delete=models.CASCADE,
        related_name='processing_logs',
        help_text="Associated resume"
    )
    
    step = models.CharField(
        max_length=100,
        db_index=True,
        help_text="Processing step name (e.g., 'file_upload', 'text_extraction')"
    )
    
    status = models.CharField(
        max_length=20,
        choices=LOG_STATUS_CHOICES,
        db_index=True,
        help_text="Status of this processing step"
    )
    
    message = models.TextField(
        blank=True,
        help_text="Detailed log message or error description"
    )
    
    execution_time_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Execution time in milliseconds"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        help_text="When this log entry was created"
    )
    
    class Meta:
        """Meta options for ResumeProcessingLog model."""
        ordering = ['-created_at']
        verbose_name = 'Resume Processing Log'
        verbose_name_plural = 'Resume Processing Logs'
        indexes = [
            models.Index(fields=['resume', 'step']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self) -> str:
        """String representation of ResumeProcessingLog instance."""
        return f"{self.resume.github_username} - {self.step} - {self.get_status_display()}" # type: ignore
    
    def __repr__(self) -> str:
        """Developer-friendly representation."""
        return (
            f"<ResumeProcessingLog(resume='{self.resume.github_username}', "
            f"step='{self.step}', status='{self.status}')>"
        )
    
    @property
    def execution_time_human(self) -> str:
        """
        Get human-readable execution time.
        
        Returns:
            str: Formatted execution time
        """
        if self.execution_time_ms is None:
            return "N/A"
        
        if self.execution_time_ms < 1000:
            return f"{self.execution_time_ms} ms"
        else:
            seconds = self.execution_time_ms / 1000
            return f"{seconds:.2f} seconds"
