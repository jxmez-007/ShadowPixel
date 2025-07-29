from django.db import models

class Resume(models.Model):
    github_username = models.CharField(max_length=100)
    resume_file = models.FileField(upload_to='resumes/')
    summary = models.TextField(blank=True)  # new field for AI summary

    def _str_(self):
        return self.github_username