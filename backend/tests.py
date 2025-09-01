"""
Test cases for Resume Upload Service models.

This module contains comprehensive tests for the Resume and ResumeProcessingLog models,
including validation, file handling, and business logic tests.
"""

from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.utils import timezone
from unittest.mock import patch, MagicMock
import os
import tempfile
from datetime import datetime, timedelta
from .models import Resume, ResumeProcessingLog


class ResumeModelTest(TestCase):
    """Test cases for the Resume model."""
    
    @classmethod
    def setUpTestData(cls):
        """Set up test data that won't be modified by test methods."""
        cls.valid_pdf_content = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>endobj"
        cls.valid_txt_content = b"This is a test resume content with skills and experience."
        cls.valid_doc_content = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"  # DOC file header
        cls.valid_docx_content = b"PK\x03\x04"  # DOCX file header (ZIP)
        
    def setUp(self):
        """Set up test data that may be modified by test methods."""
        self.test_username = "testuser123"
        
    def test_resume_creation_success(self):
        """Test successful resume creation with all fields."""
        resume_file = SimpleUploadedFile(
            "test_resume.pdf", 
            self.valid_pdf_content,
            content_type="application/pdf"
        )

        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file,
            summary="This is a test summary.",
            full_name="Test User",
            email="test@example.com",
            phone="+1234567890",
            skills="Python, Django, JavaScript",
            experience_years=5
        )

        self.assertEqual(resume.github_username, self.test_username)
        self.assertIn(f"{self.test_username}_", resume.resume_file.name)
        self.assertEqual(resume.summary, "This is a test summary.")
        self.assertEqual(resume.full_name, "Test User")
        self.assertEqual(resume.email, "test@example.com")
        self.assertEqual(resume.phone, "+1234567890")
        self.assertEqual(resume.skills, "Python, Django, JavaScript")
        self.assertEqual(resume.experience_years, 5)
        self.assertEqual(resume.status, "pending")
        self.assertIsNotNone(resume.created_at)
        self.assertIsNotNone(resume.updated_at)
        self.assertIsNone(resume.processed_at)

    def test_resume_str_method(self):
        """Test string representation of Resume model."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        expected_str = f"{self.test_username} - Pending Processing"
        self.assertEqual(str(resume), expected_str)

    def test_resume_repr_method(self):
        """Test developer-friendly representation of Resume model."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        repr_str = repr(resume)
        self.assertIn(f"github_username='{self.test_username}'", repr_str)
        self.assertIn("status='pending'", repr_str)

    def test_github_username_validation_valid(self):
        """Test valid GitHub usernames pass validation."""
        valid_usernames = [
            "testuser", 
            "test-user", 
            "test123", 
            "a", 
            "a1b2c3",
            "user-name-123",
            "z" * 39  # Maximum length
        ]
        
        for i, username in enumerate(valid_usernames):
            with self.subTest(username=username):
                resume_file = SimpleUploadedFile(f"test{i}.pdf", self.valid_pdf_content)
                resume = Resume(
                    github_username=username,
                    resume_file=resume_file
                )
                try:
                    resume.full_clean()
                    self.assertTrue(True)  # Validation passed
                except ValidationError:
                    self.fail(f"Valid username '{username}' failed validation")

    def test_github_username_validation_invalid(self):
        """Test invalid GitHub usernames fail validation."""
        invalid_usernames = [
            ("-testuser", "starts with hyphen"),
            ("testuser-", "ends with hyphen"),
            ("test--user", "consecutive hyphens"),
            ("test@user", "invalid character"),
            ("test user", "contains space"),
            ("test.user", "contains dot"),
            ("a" * 40, "too long (40 chars)"),
            ("", "empty string"),
            ("-", "single hyphen"),
        ]
        
        for username, reason in invalid_usernames:
            with self.subTest(username=username, reason=reason):
                resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
                resume = Resume(
                    github_username=username,
                    resume_file=resume_file
                )
                with self.assertRaises(ValidationError):
                    resume.full_clean()

    def test_github_username_unique_constraint(self):
        """Test that GitHub username must be unique across all resumes."""
        resume_file1 = SimpleUploadedFile("test1.pdf", self.valid_pdf_content)
        resume_file2 = SimpleUploadedFile("test2.pdf", self.valid_pdf_content)
        
        # Create first resume
        Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file1
        )
        
        # Try to create second resume with same username
        with self.assertRaises(IntegrityError):
            Resume.objects.create(
                github_username=self.test_username,
                resume_file=resume_file2
            )

    def test_file_extension_validation_valid(self):
        """Test that valid file extensions are accepted."""
        valid_files = [
            ("test.pdf", self.valid_pdf_content, "application/pdf"),
            ("test.doc", self.valid_doc_content, "application/msword"),
            ("test.docx", self.valid_docx_content, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            ("test.txt", self.valid_txt_content, "text/plain"),
        ]
        
        for i, (filename, content, content_type) in enumerate(valid_files):
            with self.subTest(filename=filename):
                resume_file = SimpleUploadedFile(filename, content, content_type=content_type)
                resume = Resume(
                    github_username=f"user{i}",
                    resume_file=resume_file
                )
                try:
                    resume.full_clean()
                    self.assertTrue(True)  # Validation passed
                except ValidationError as e:
                    self.fail(f"Valid file '{filename}' failed validation: {e}")

    def test_file_extension_validation_invalid(self):
        """Test that invalid file extensions are rejected."""
        invalid_files = [
            ("test.jpg", b"\xff\xd8\xff\xe0", "JPEG image"),
            ("test.exe", b"MZ", "executable file"),
            ("test.py", b"print('hello')", "Python script"),
            ("test.html", b"<html></html>", "HTML file"),
            ("test.zip", b"PK\x03\x04", "ZIP archive"),
        ]
        
        for i, (filename, content, description) in enumerate(invalid_files):
            with self.subTest(filename=filename, description=description):
                resume_file = SimpleUploadedFile(filename, content)
                resume = Resume(
                    github_username=f"user{filename.replace('.', '')}{i}",
                    resume_file=resume_file
                )
                with self.assertRaises(ValidationError):
                    resume.full_clean()

    def test_file_size_validation_success(self):
        """Test that files within size limit are accepted."""
        # Create a file just under 5MB
        content_size = 4 * 1024 * 1024  # 4MB
        valid_content = b"x" * content_size
        
        resume_file = SimpleUploadedFile("valid_size.pdf", valid_content)
        resume = Resume(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        try:
            resume.full_clean()
            self.assertTrue(True)  # Should pass validation
        except ValidationError:
            self.fail("Valid file size should not raise ValidationError")

    def test_file_size_validation_failure(self):
        """Test that files exceeding size limit are rejected."""
        # Create a file larger than 5MB
        large_content = b"x" * (6 * 1024 * 1024)  # 6MB
        large_file = SimpleUploadedFile("large.pdf", large_content)
        
        resume = Resume(
            github_username=self.test_username,
            resume_file=large_file
        )
        
        with self.assertRaises(ValidationError) as context:
            resume.full_clean()
        
        error_message = str(context.exception)
        self.assertIn("File size cannot exceed", error_message)
        self.assertIn("5.0 MB", error_message)

    def test_file_properties(self):
        """Test file-related property methods."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        # Test file size properties
        self.assertEqual(resume.file_size, len(self.valid_pdf_content))
        self.assertGreater(resume.file_size_mb, 0)
        self.assertIn("bytes", resume.file_size_human)
        
        # Test file extension
        self.assertEqual(resume.file_extension, '.pdf')
        
        # Test processing status
        self.assertFalse(resume.is_processing_complete)
        self.assertIsNone(resume.processing_duration)

    def test_original_filename_preservation(self):
        """Test that original filename is stored correctly."""
        original_filename = "my_awesome_resume_v2.pdf"
        resume_file = SimpleUploadedFile(original_filename, self.valid_pdf_content)
        
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        # Original filename should be stored
        self.assertEqual(resume.original_filename, original_filename)
        
        # Actual stored file should have unique name
        self.assertIn(f"{self.test_username}_", resume.resume_file.name)
        self.assertNotEqual(resume.resume_file.name, original_filename)

    def test_status_choices_validation(self):
        """Test that only valid status choices are accepted."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        # Test default status
        self.assertEqual(resume.status, "pending")
        
        # Test valid status changes
        valid_statuses = ["pending", "processing", "completed", "failed"]
        for status in valid_statuses:
            resume.status = status
            resume.save()
            resume.refresh_from_db()
            self.assertEqual(resume.status, status)
        
        # Test invalid status
        resume.status = "invalid_status"
        with self.assertRaises(ValidationError):
            resume.full_clean()

    def test_experience_years_validation(self):
        """Test experience years field validation."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        
        # Test valid experience values
        valid_values = [0, 1, 10, 50]
        for i, years in enumerate(valid_values):
            with self.subTest(years=years):
                resume = Resume.objects.create(
                    github_username=f"user{i}",
                    resume_file=SimpleUploadedFile(f"test{i}.pdf", self.valid_pdf_content),
                    experience_years=years
                )
                self.assertEqual(resume.experience_years, years)
        
        # Test negative experience years (should fail due to PositiveIntegerField)
        with self.assertRaises(ValidationError):
            resume = Resume(
                github_username="negative_user",
                resume_file=resume_file,
                experience_years=-1
            )
            resume.full_clean()

    def test_status_utility_methods(self):
        """Test utility methods for status management."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        # Test mark_processing
        resume.mark_processing("Starting text extraction")
        resume.refresh_from_db()
        self.assertEqual(resume.status, "processing")
        self.assertEqual(resume.processing_notes, "Starting text extraction")
        
        # Test mark_completed
        resume.mark_completed("Processing completed successfully")
        resume.refresh_from_db()
        self.assertEqual(resume.status, "completed")
        self.assertEqual(resume.processing_notes, "Processing completed successfully")
        self.assertIsNotNone(resume.processed_at)
        self.assertTrue(resume.is_processing_complete)
        
        # Test processing duration
        self.assertIsNotNone(resume.processing_duration)

    def test_mark_failed_method(self):
        """Test mark_failed utility method."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        error_message = "Failed to extract text from PDF"
        resume.mark_failed(error_message)
        resume.refresh_from_db()
        
        self.assertEqual(resume.status, "failed")
        self.assertEqual(resume.processing_notes, error_message)
        self.assertIsNotNone(resume.processed_at)
        self.assertTrue(resume.is_processing_complete)

    @patch('os.remove')
    @patch('os.path.isfile')
    def test_file_deletion_on_model_delete(self, mock_isfile, mock_remove):
        """Test that physical file is deleted when model instance is deleted."""
        mock_isfile.return_value = True
        
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        # Store the file path before deletion
        file_path = resume.resume_file.path
        
        # Delete the resume
        resume.delete()
        
        # Verify file deletion was attempted
        mock_isfile.assert_called_once_with(file_path)
        mock_remove.assert_called_once_with(file_path)

    @patch('os.remove', side_effect=OSError("File not found"))
    @patch('os.path.isfile', return_value=True)
    def test_file_deletion_error_handling(self, mock_isfile, mock_remove):
        """Test graceful handling of file deletion errors."""
        resume_file = SimpleUploadedFile("test.pdf", self.valid_pdf_content)
        resume = Resume.objects.create(
            github_username=self.test_username,
            resume_file=resume_file
        )
        
        # Should not raise exception even if file deletion fails
        try:
            resume.delete()
            self.assertTrue(True)  # Deletion should complete successfully
        except Exception as e:
            self.fail(f"Model deletion should not fail due to file deletion error: {e}")

    def test_model_ordering(self):
        """Test that resumes are ordered by creation date (newest first)."""
        resumes = []
        
        # Create multiple resumes with slight time delays
        for i in range(3):
            resume_file = SimpleUploadedFile(f"test{i}.pdf", self.valid_pdf_content)
            resume = Resume.objects.create(
                github_username=f"user{i}",
                resume_file=resume_file
            )
            resumes.append(resume)
        
        # Get all resumes from database
        db_resumes = list(Resume.objects.all())
        
        # Should be ordered by created_at descending (newest first)
        for i in range(len(db_resumes) - 1):
            self.assertGreaterEqual(
                db_resumes[i].created_at, 
                db_resumes[i + 1].created_at
            )

    def test_resume_manager_methods(self):
        """Test custom manager methods."""
        # Create resumes with different statuses
        statuses = ['pending', 'processing', 'completed', 'failed']
        for i, status in enumerate(statuses):
            resume_file = SimpleUploadedFile(f"test{i}.pdf", self.valid_pdf_content)
            Resume.objects.create(
                github_username=f"user{i}",
                resume_file=resume_file,
                status=status
            )
        
        # Test manager methods
        self.assertEqual(Resume.objects.pending().count(), 1)
        self.assertEqual(Resume.objects.completed().count(), 1)
        self.assertEqual(Resume.objects.failed().count(), 1)
        self.assertEqual(Resume.objects.by_status('processing').count(), 1)
        
        # Test recent method
        recent_resumes = Resume.objects.recent(days=1)
        self.assertEqual(recent_resumes.count(), 4)  # All should be recent


class ResumeProcessingLogTest(TestCase):
    """Test cases for the ResumeProcessingLog model."""
    
    def setUp(self):
        """Set up test data for each test method."""
        resume_file = SimpleUploadedFile("test.pdf", b"dummy pdf content")
        self.resume = Resume.objects.create(
            github_username="testuser",
            resume_file=resume_file
        )

    def test_processing_log_creation(self):
        """Test creating a processing log with all fields."""
        log = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="text_extraction",
            status="completed",
            message="Successfully extracted text from PDF",
            execution_time_ms=1500
        )
        
        self.assertEqual(log.resume, self.resume)
        self.assertEqual(log.step, "text_extraction")
        self.assertEqual(log.status, "completed")
        self.assertEqual(log.message, "Successfully extracted text from PDF")
        self.assertEqual(log.execution_time_ms, 1500)
        self.assertIsNotNone(log.created_at)

    def test_processing_log_str_method(self):
        """Test string representation of processing log."""
        log = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="parsing",
            status="failed",
            message="Failed to parse resume content"
        )
        
        expected_str = "testuser - parsing - Failed"
        self.assertEqual(str(log), expected_str)

    def test_processing_log_repr_method(self):
        """Test developer-friendly representation of processing log."""
        log = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="validation",
            status="started"
        )
        
        repr_str = repr(log)
        self.assertIn("resume='testuser'", repr_str)
        self.assertIn("step='validation'", repr_str)
        self.assertIn("status='started'", repr_str)

    def test_processing_log_relationship(self):
        """Test one-to-many relationship between Resume and ProcessingLog."""
        # Create multiple logs for the same resume
        log1 = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="file_upload",
            status="completed"
        )
        log2 = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="text_extraction",
            status="started"
        )
        log3 = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="parsing",
            status="failed"
        )
        
        # Test reverse relationship
        logs = self.resume.processing_logs.all()
        self.assertEqual(logs.count(), 3)
        self.assertIn(log1, logs)
        self.assertIn(log2, logs)
        self.assertIn(log3, logs)
        
        # Test ordering (should be newest first)
        ordered_logs = list(logs)
        for i in range(len(ordered_logs) - 1):
            self.assertGreaterEqual(
                ordered_logs[i].created_at,
                ordered_logs[i + 1].created_at
            )

    def test_processing_log_cascade_delete(self):
        """Test that logs are deleted when associated resume is deleted."""
        # Create logs for the resume
        ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="test_step_1",
            status="completed"
        )
        ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="test_step_2",
            status="started"
        )
        
        # Verify logs exist
        self.assertEqual(ResumeProcessingLog.objects.filter(resume=self.resume).count(), 2)
        
        # Delete the resume
        self.resume.delete()
        
        # All associated logs should be deleted
        self.assertEqual(ResumeProcessingLog.objects.count(), 0)

    def test_execution_time_human_property(self):
        """Test human-readable execution time property."""
        # Test milliseconds
        log_ms = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="quick_task",
            status="completed",
            execution_time_ms=500
        )
        self.assertEqual(log_ms.execution_time_human, "500 ms")
        
        # Test seconds
        log_seconds = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="slow_task",
            status="completed",
            execution_time_ms=2500
        )
        self.assertEqual(log_seconds.execution_time_human, "2.50 seconds")
        
        # Test None execution time
        log_none = ResumeProcessingLog.objects.create(
            resume=self.resume,
            step="unknown_task",
            status="started"
        )
        self.assertEqual(log_none.execution_time_human, "N/A")

    def test_log_status_choices(self):
        """Test that log status field accepts only valid choices."""
        valid_statuses = ['started', 'completed', 'failed', 'warning', 'info']
        
        for i, status in enumerate(valid_statuses):
            with self.subTest(status=status):
                log = ResumeProcessingLog.objects.create(
                    resume=self.resume,
                    step=f"test_step_{i}",
                    status=status
                )
                self.assertEqual(log.status, status)
        
        # Test invalid status
        log = ResumeProcessingLog(
            resume=self.resume,
            step="invalid_status_test",
            status="invalid_status"
        )
        with self.assertRaises(ValidationError):
            log.full_clean()
