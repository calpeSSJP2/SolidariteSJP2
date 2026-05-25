from django.db import models
from accounts.models import User

class Meeting(models.Model):
    objects = models.Manager()

    topic = models.CharField(max_length=255)
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_meetings')
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.topic} - {self.date} {self.start_time}"

class MeetingAttendance(models.Model):
    objects = models.Manager()

    class AttendanceStatus(models.TextChoices):
        PRESENT = 'present', 'Present'
        LATE = 'late', 'Late'
        ABSENT = 'absent', 'Absent'

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='attendances')
    member = models.ForeignKey(User, on_delete=models.CASCADE)
    check_in_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=10, choices=AttendanceStatus.choices, default=AttendanceStatus.ABSENT)
    penalty_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.0)
    remarks = models.TextField(blank=True)

    def calculate_penalty(self):
        if self.status == self.AttendanceStatus.LATE:
            self.penalty_amount = 500
        elif self.status == self.AttendanceStatus.ABSENT:
            self.penalty_amount = 1000
        else:
            self.penalty_amount = 0

    def save(self, *args, **kwargs):
        self.calculate_penalty()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.member.firstname} {self.member.lastname} - {self.meeting.topic} ({self.status})"

class MeetingDecision(models.Model):
    objects = models.Manager()

    meeting = models.ForeignKey(Meeting, on_delete=models.CASCADE, related_name='decisions')
    decision_text = models.TextField()
    assigned_to = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    deadline = models.DateField(null=True, blank=True)
    implemented = models.BooleanField(default=False)

    def __str__(self):
        return f"Decision for {self.meeting.topic}: {self.decision_text[:30]}..."
