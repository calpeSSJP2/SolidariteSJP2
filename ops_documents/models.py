from django.db import models
from accounts.models import User

class UploadedDocument(models.Model):
    objects = models.Manager()  ##Adding objects = models.Manager() makes it clear to static analysis tools like the one in PyCharm or VS Code that the model has a .objects attribute

    DOC_TYPE_CHOICES = [
        ('loan_request', 'Loan Request'),
        ('loan_topup', 'Loan Top-Up'),
        ('emergency', 'Emergency Request'),
        ('meeting_permission', 'Meeting Absence Permission'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    doc_type = models.CharField(max_length=50, choices=DOC_TYPE_CHOICES)
    file = models.FileField(upload_to='documents/')
    note = models.TextField(blank=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_doc_type_display()} ({self.uploaded_at.date()})"
