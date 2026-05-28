from django.db import models
from django.conf import settings
from decimal import Decimal
from accounts.models import MemberAccount, SJP2_Account
from django.db import models, transaction
from django.utils import timezone
from decimal import Decimal
from django.db.models import Sum
from django.core.exceptions import ValidationError
from accounts.models import MemberAccount
from django.db.models import Q


User = settings.AUTH_USER_MODEL


class YearlyInterestPool(models.Model):
    """
    Represents interest declared for a given year.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        DISTRIBUTED = "distributed", "Distributed"

    year = models.PositiveIntegerField(unique=True)

    # Planned interest (what officer inputs)
    total_interest = models.DecimalField(max_digits=15, decimal_places=2)

    # Actual distributed (after checking SJP2 balance)
    distributed_amount = models.DecimalField(    max_digits=15,    decimal_places=2, default=Decimal('0.00')   )
    total_not_distributed = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    source_account = models.ForeignKey(SJP2_Account, on_delete=models.PROTECT,    related_name="interest_pools"  )
    status = models.CharField(   max_length=20,    choices=Status.choices,     default=Status.PENDING )
    distributed_at = models.DateTimeField(null=True, blank=True)
    distributed_by = models.ForeignKey(  User,   on_delete=models.SET_NULL,  null=True,     blank=True  )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-year']

    def __str__(self):
        return f"Interest Pool {self.year}"
##Mmemeber distribution reccords

class MemberInterestShare(models.Model):
    """
    Stores how much each member received.
    This is your permanent audit record.
    """

    pool = models.ForeignKey( YearlyInterestPool, on_delete=models.CASCADE,  related_name="shares"  )

    account = models.ForeignKey( MemberAccount,  on_delete=models.PROTECT  )  ##Remeber not add on memebr account,

    # snapshot values at distribution time (IMPORTANT for audit)
    principal_snapshot = models.DecimalField(   max_digits=15,   decimal_places=2  )

    ratio = models.DecimalField( max_digits=12, decimal_places=8 )

    interest_earned = models.DecimalField( max_digits=15,   decimal_places=2 )
    distribute = models.DecimalField(max_digits=12, decimal_places=2,
                                     default=0)  ##We round, 0--400:000, while 500-900=500
    not_distributed = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('pool', 'account')  # prevent duplicates

    def __str__(self):
        return f"{self.account.account_number} → {self.interest_earned}"
