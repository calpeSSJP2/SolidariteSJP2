from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import CreateView
from django.db import models, transaction
from django.utils import timezone
from accounts.models import MemberAccount
from decimal import Decimal
from accounts.models import SHARE_VALUE  # ❌ Use the constant SHARE_VALUE instead of hardcoding 5000

# -----------------------------
# Base class for share transactions
# -----------------------------
class BaseTransaction(models.Model):
    nbr_share = models.PositiveIntegerField(default=0)
    timestamp = models.DateTimeField(default=timezone.now)
    description = models.TextField(blank=True)

    class Meta:
        abstract = True

# -----------------------------

# Share Increase
# -----------------------------
class ShareIncrease(BaseTransaction):
    account = models.ForeignKey( MemberAccount, on_delete=models.CASCADE, related_name='share_increase_transactions')

    def save(self, *args, **kwargs):
        # ❌ Prevent share increase on inactive accounts
        if self.account.status_type != MemberAccount.StatusType.ACTIVE:
            raise ValueError("❌ Cannot increase shares on inactive/suspended/dormant/closed account")

        with transaction.atomic():  # ❌ Ensure both transaction and account update succeed together
            super().save(*args, **kwargs)
            self.account.increase_shares(self.nbr_share)  # ❌ Uses the central increase_shares() method, keeping history and balance correct

    def __str__(self):
        return f"{self.account.account_number} increases {self.nbr_share} shares"

# -----------------------------
# Share Decrease
# -----------------------------
class ShareDecrease(BaseTransaction):
    account = models.ForeignKey(
        MemberAccount,
        on_delete=models.CASCADE,
        related_name='share_decrease_transactions' )

    def save(self, *args, **kwargs):
        # ❌ Prevent share decrease on inactive accounts
        if self.account.status_type != MemberAccount.StatusType.ACTIVE:
            raise ValueError("❌ Cannot decrease shares on inactive/suspended/dormant/closed account")

        with transaction.atomic():  # ❌ Atomic operation  (To control , ko biba saved, aruko account decrease_shares op yabase nayo saved
            super().save(*args, **kwargs)
            # ❌ Prevent decrease if account is inactive or not enough balance
            if self.account.balance < Decimal(self.nbr_share) * SHARE_VALUE:
                raise ValueError("❌ Not enough balance to remove these shares")
            self.account.decrease_shares(self.nbr_share)  # ❌ Central method handles principal, balance, and activity update

    def __str__(self):
        return f"{self.account.account_number} decreases {self.nbr_share} shares"

class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transact4_share_mngt/transaction_shares_form.html'
    title = ''
    button_label = 'Submit'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        account = getattr(self.request.user.membersprofile, 'memberaccount', None)

        recent_ops = []

        if account:
            increases = ShareIncrease.objects.filter(account=account)
            decreases = ShareDecrease.objects.filter(account=account)

            for tx in increases:
                recent_ops.append({
                    "type": "Increase",
                    "nbr_share": tx.nbr_share,
                    "timestamp": tx.timestamp,
                })

            for tx in decreases:
                recent_ops.append({
                    "type": "Decrease",
                    "nbr_share": tx.nbr_share,
                    "timestamp": tx.timestamp,
                })

            recent_ops.sort(key=lambda x: x["timestamp"], reverse=True)
            recent_ops = recent_ops[:5]

        context.update({
            "title": self.title,
            "button_label": self.button_label,
            "recent_ops": recent_ops,
        })

        return context