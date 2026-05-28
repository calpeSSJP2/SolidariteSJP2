from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from transact2_loans.models import Loan  # Import your regular Loan mo
# ✅ Import centralized mixin
from accounts.mixins import ActiveAccountMixin

from decimal import Decimal
from django.db import models, transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db.models import Sum
from django.conf import settings
# -----------------------------
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models, transaction
from django.db.models import Sum
from django.utils import timezone

from ledger.services import LedgerService
from ledger.models import AccountStatement

from accounts.mixins import ActiveAccountMixin
from transact2_loans.models import Loan  # Import your regular Loan model
from ledger.services import LedgerService
from ledger.models import AccountStatement


# -----------------------------
# Peer-to-Peer Loan
# -----------------------------
class PeerToPeerLoan(ActiveAccountMixin, models.Model):
    lender = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE, related_name='given_peer_loans')
    borrower = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE, related_name='received_peer_loans')
    contract = models.FileField(upload_to='peer_contracts/')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(default=timezone.now)
    is_fully_paid = models.BooleanField(default=False)

    # -----------------------------
    # Validation
    # -----------------------------
    def clean(self):
        super().clean()
        ActiveAccountMixin.check_active_accounts(self.lender)
        ActiveAccountMixin.check_active_accounts(self.borrower)

        if self.lender == self.borrower:
            raise ValidationError("Lender and borrower cannot be the same account.")

        if self.amount > (self.lender.principal * 2):
            raise ValidationError("Lending amount exceeds 2x principal of the lender.")

    # -----------------------------
    # Save with transactional balance updates
    # -----------------------------
    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self._state.adding
        self.full_clean()
        super().save(*args, **kwargs)

        if is_new:
            from ledger.services import LedgerService
            from ledger.models import AccountStatement

            LedgerService.create_statement(
                account=self.borrower,
                transaction_type=AccountStatement.TransactionType.BORROWING,
                credit=self.amount,
                debit=Decimal('0.00'),
                reference=f"Peer-to-Peer Loan ID {self.pk} from Lender ID {self.lender.pk}"
            )

            LedgerService.create_statement(
                account=self.lender,
                transaction_type=AccountStatement.TransactionType.LENDING,
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=f"Peer-to-Peer Loan ID {self.pk} to Borrower ID {self.borrower.pk}"
            )

            from .models import PeerLendingStatus, PeerBorrowingStatus
            PeerLendingStatus.update_total_lender_loan(self.lender)
            PeerBorrowingStatus.update_total_borrowed(self.borrower)

    # -----------------------------
    # Total paid property
    # -----------------------------

    @property
    def total_paid(self):
        return self.repayments.aggregate(
            total=Sum('amount')
        )['total'] or 0

    # -----------------------------
    # Remaining balance property
    # -----------------------------
    #@property
    #def remaining_balance(self):
      #  return self.amount - self.total_paid

    @property
    def remaining_balance(self):
        total_paid = self.repayments.aggregate(total=Sum('amount'))['total'] or 0
        return max(self.amount - total_paid, 0)
# -----------------------------
# Peer Loan Repayment


class PeerLoanRepayment(ActiveAccountMixin, models.Model):
    """
    Handles repayment transactions for Peer-to-Peer loans.
    Automatically creates ledger entries and updates loan status.
    """

    peer_loan = models.ForeignKey( "PeerToPeerLoan", on_delete=models.CASCADE, null=True, blank=True, related_name="repayments", )
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    date = models.DateField(null=True, blank=True)
    paid_by = models.ForeignKey( settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,null=True, blank=True, )

    # -------------------------
    # Validation
    # -------------------------

    def clean(self):
        super().clean()

        if not self.peer_loan:
            raise ValidationError("Peer loan is required.")

        ActiveAccountMixin.check_active_accounts(self.peer_loan.borrower)
        ActiveAccountMixin.check_active_accounts(self.peer_loan.lender)

        if self.amount is None or self.amount <= 0:
            raise ValidationError("Repayment amount must be greater than zero.")

        if self.peer_loan.is_fully_paid:
            raise ValidationError("This loan is already fully paid.")

        # ✅ Calculate remaining balance properly
        total_paid = (
                self.peer_loan.repayments.aggregate(total=Sum("amount"))["total"] or 0
        )

        remaining_balance = self.peer_loan.amount - total_paid

        if self.amount > remaining_balance:
            raise ValidationError(
                f"Repayment exceeds remaining balance ({remaining_balance})."
            )

    # -------------------------
    # Save Override
    # -------------------------
    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self._state.adding

        # Always validate before saving
        self.full_clean()
        super().save(*args, **kwargs)

        if not is_new:
            return

        borrower = self.peer_loan.borrower
        lender = self.peer_loan.lender

        # -------------------------
        # Create Ledger Entries  ,,Check in services to make sure no double legers
        # -------------------------
        LedgerService.create_statement(
            account=borrower,
            transaction_type=AccountStatement.TransactionType.PEER_LOAN_PAYMENT,
            debit=self.amount,
            reference=f"Repayment for Peer-to-Peer Loan ID {self.peer_loan.pk}",
        )

        LedgerService.create_statement(
            account=lender,
            transaction_type=AccountStatement.TransactionType.PEER_LOAN_PAYMENT,
            credit=self.amount,
            reference=f"Received repayment for Peer-to-Peer Loan ID {self.peer_loan.pk}", )

        # -------------------------
        # Mark Loan Fully Paid, Exclude current  instance(data0, while you are updting.Otherwise you risk to use it while it not new
        # -------------------------
        #total_paid = (
          #      self.peer_loan.repayments.exclude(pk=self.pk).aggregate(total=Sum("amount"))["total"] or 0  )
        total_paid = (self.peer_loan.repayments.aggregate(total=Sum("amount"))["total"] or 0 )
        if total_paid >= self.peer_loan.amount:
            self.peer_loan.is_fully_paid = True
            self.peer_loan.save(update_fields=["is_fully_paid"])


# -----------------------------
# Peer Lending Status
# -----------------------------
class PeerLendingStatus(models.Model):
    lender = models.OneToOneField('accounts.MemberAccount', on_delete=models.CASCADE)
    total_lent = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @staticmethod
    def update_total_lender_loan(lender_account):
        from .models import PeerToPeerLoan
        total = PeerToPeerLoan.objects.filter(lender=lender_account, is_fully_paid=False).aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        status, _ = PeerLendingStatus.objects.get_or_create(lender=lender_account)
        status.total_lent = total
        status.save(update_fields=["total_lent"])


# -----------------------------
# Peer Borrowing Status
# -----------------------------
class PeerBorrowingStatus(models.Model):
    borrower = models.OneToOneField('accounts.MemberAccount', on_delete=models.CASCADE)
    total_borrowed = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    @staticmethod
    def update_total_borrowed(borrower_account):
        from .models import PeerToPeerLoan
        total = PeerToPeerLoan.objects.filter(borrower=borrower_account, is_fully_paid=False).aggregate(
            total=models.Sum('amount'))['total'] or Decimal('0.00')
        status, _ = PeerBorrowingStatus.objects.get_or_create(borrower=borrower_account)
        status.total_borrowed = total
        status.save(update_fields=["total_borrowed"])




##you want, I can also write the corresponding Django Form and View for Peer Loan payments, so users see amount due including penalties, exactly like LoanPaymentForm.