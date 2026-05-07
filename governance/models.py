from django.db import models
from django.utils import timezone

from accounts.models import User, Role


class Election(models.Model):
    name = models.CharField(max_length=150)
    election_date = models.DateField()
    description = models.TextField(blank=True)
    created_on = models.DateField(default=timezone.now)

    def __str__(self):
        return f"{self.name} ({self.election_date})"


class LeadershipTerm(models.Model):
    user = models.ForeignKey(User, on_delete=models.PROTECT)

    # ✅ FIX: Use Role model instead of CharField enum
    role = models.ForeignKey(Role, on_delete=models.PROTECT)

    election = models.ForeignKey(
        Election,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    started_on = models.DateField()
    ended_on = models.DateField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_on = models.DateField(default=timezone.now)

    class Meta:
        ordering = ['-started_on']

        constraints = [
            models.UniqueConstraint(
                fields=['role'],
                condition=models.Q(is_active=True),
                name='only_one_active_role'
            )
        ]

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.role.name}"