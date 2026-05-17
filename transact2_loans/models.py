from datetime import date
from decimal import Decimal, ROUND_DOWN
from calendar import monthrange
from django.db.models import Q ##This is built in function that has OR, AND,..
from django.core.exceptions import ValidationError
from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from accounts.mixins import ActiveAccountMixin

from django.db import models
from django.conf import settings
from django.utils import timezone
###from dateutil.relativedelta import relativedelta
##
from django.contrib.auth import get_user_model



# -----------------------------
# Helper
# -----------------------------
def add_months(start_date: date, months: int) -> date:
    """Safely add months to a date (replacement for dateutil.relativedelta)."""
    year = start_date.year + (start_date.month - 1 + months) // 12
    month = (start_date.month - 1 + months) % 12 + 1
    day = start_date.day

    last_day = monthrange(year, month)[1]
    if day > last_day:
        day = last_day

    return date(year, month, day)



User = get_user_model()



    
class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('request', 'Loan Requested'),
        ('approve', 'Loan Approved'),
        ('reject', 'Loan Rejected'),
        ('disburse', 'Loan Disbursed'),
    ]
    loan = models.ForeignKey('Loan', on_delete=models.CASCADE, related_name='audit_logs')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

# -----------------------------
# Manager
# -----------------------------
class LoanManager(models.Manager):

    def open_loans_for_account(self, account):
        return self.filter(
            account=account,
            status__in=Loan.OPEN_STATUSES
        )

    def has_open_loan(self, account, exclude_loan_id=None):
        qs = self.open_loans_for_account(account)
        if exclude_loan_id:
            qs = qs.exclude(pk=exclude_loan_id)
        return qs.exists()

    def active_with_balance(self, account):
        """
        Returns active loan with remaining balance > 0
        """
        loans = self.filter(  account=account, status=Loan.LoanStatus.ACTIVE )
        for loan in loans:
            if loan.balance > 0:
                return loan
        return None

    def has_duplicate_regular(self, account, loan_type, exclude_loan_id=None):
        """
        Block duplicate regular loans ONLY if there is
        an open loan WITH balance > 0 (excluding top-ups).
        """
        qs = self.open_loans_for_account(account).filter(
            loan_type=loan_type,
            top_up_of__isnull=True
        )

        if exclude_loan_id:
            qs = qs.exclude(pk=exclude_loan_id)

        for loan in qs:
            if loan.balance > 0:
                return True

        return False


# -----------------------------
# Loan Model
# -----------------------------
class Loan(ActiveAccountMixin, models.Model):
    # -----------------------------
    # Choices
    # -----------------------------
    class LoanStatus(models.TextChoices):
        PENDING = 'pending', 'Pending Approval'
        APPROVED = 'approved', 'Approved'
        ACTIVE = 'active', 'Active'  ##Partially Paid
        PAID = 'paid', 'Fully Paid'
        REJECTED = 'rejected', 'Rejected'

    OPEN_STATUSES = (  LoanStatus.PENDING,   LoanStatus.APPROVED,   LoanStatus.ACTIVE,  )

    class LoanType(models.TextChoices):
        REGULAR = 'regular', 'Regular'
        EMERGENCY = 'emergency', 'Emergency'

    class TermChoices(models.IntegerChoices):
        THREE_MONTHS = 3, '3 Months (Emergency)'
        ONE_YEAR = 12, '1 Year (Regular)'
        TWO_YEARS = 24, '2 Years (Regular)'

    # -----------------------------
    # Fields
    # -----------------------------
    account = models.ForeignKey("accounts.MemberAccount", on_delete=models.CASCADE, related_name="loans")
    loan_type = models.CharField(max_length=20, choices=LoanType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    term_months = models.PositiveIntegerField(choices=TermChoices.choices)
    interest_rate = models.DecimalField(max_digits=5, decimal_places=2, editable=False)
    interest_amount = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    status = models.CharField(max_length=20, choices=LoanStatus.choices, default=LoanStatus.PENDING)
    issued_on = models.DateField(default=timezone.now)
    performed_by = models.ForeignKey(  settings.AUTH_USER_MODEL,  on_delete=models.SET_NULL,    null=True,
        blank=True,  related_name="processed_loans"  )


    top_up_of = models.ForeignKey("self", null=True, blank=True, on_delete=models.SET_NULL, related_name="topups")
    rejected_reason = models.TextField(blank=True, null=True, help_text="Reason for rejecting the loan")
    performed_on = models.DateTimeField(blank=True, null=True)
    objects = LoanManager()
    #requested_on = models.DateTimeField(auto_now_add=True) I uses Issued on
    approved_on = models.DateTimeField(null=True, blank=True)

    # =========================================================
    # NEW ADDITION: WORKFLOW TRACKING (NO CHANGE TO YOUR LOGIC)
    # =========================================================

    class Meta:
        ordering = ["-issued_on"]

    def __str__(self):
        return f"Loan #{self.pk} for {self.account}"

     # Validation
    # -----------------------------
    def clean(self):
        super().clean()

        # --------------------------------------------------
        # 🔹 BASIC VALIDATION
        # --------------------------------------------------
        if not self.account_id:
            raise ValidationError("Loan must be linked to an account.")

        self.check_active_accounts()

        # --------------------------------------------------
        # 🔒 BLOCK DUPLICATE STANDALONE REGULAR LOANS ONLY
        # --------------------------------------------------
        if (
                self._state.adding
                and self.loan_type == self.LoanType.REGULAR
                and self.top_up_of_id is None  # 🔥 Only block if NOT a top-up
        ):
            if Loan.objects.has_duplicate_regular(
                    self.account,
                    self.loan_type
            ):
                raise ValidationError(
                    "You already have an active regular loan with a balance. "
                    "You can request a top-up instead."
                )

        # --------------------------------------------------
        # 🔹 TERM VALIDATION
        # --------------------------------------------------
        if self.loan_type == self.LoanType.REGULAR:
            if self.term_months not in (
                    self.TermChoices.ONE_YEAR,
                    self.TermChoices.TWO_YEARS,
            ):
                raise ValidationError(
                    "Invalid term for regular loan. Choose 1 year or 2 years."
                )

        if self.loan_type == self.LoanType.EMERGENCY:
            if self.term_months != self.TermChoices.THREE_MONTHS:
                raise ValidationError(
                    "Emergency loans must be for 3 months only."
                )

        # --------------------------------------------------
        # 🔹 NORMALIZE & CALCULATE INTEREST
        # --------------------------------------------------
        self.amount = Decimal(self.amount).quantize(Decimal("0.01"))

        if self.loan_type == self.LoanType.REGULAR:
            self.interest_rate = (
                Decimal("5.0")
                if self.term_months == self.TermChoices.ONE_YEAR
                else Decimal("7.0")
            )
        else:
            self.interest_rate = Decimal("1.5")

        self.interest_rate = self.interest_rate.quantize(Decimal("0.01"))

        self.interest_amount = (
                self.amount * self.interest_rate / Decimal("100")
        ).quantize(Decimal("0.01"))

    # -----------------------------
    # Computed properties
    # -----------------------------
    @property
    def total_payable1(self): ##This is used only where you work on flat laon
        # ❌ Improvement: quantize total_payable to avoid float precision issues
        return (self.amount + self.interest_amount).quantize(Decimal("0.01"))

    @property
    def total_payable(self):
        return self.amount.quantize(Decimal("0.01"))

    @property
    def net_disbursed(self):
        return (self.amount - self.interest_amount).quantize(Decimal("0.01"))
    @property
    def total_paid(self):
        # ❌ Improvement: use ORM aggregate for efficiency instead of Python sum
        from django.db.models import Sum
        total = self.payments.aggregate(total=Sum('amount'))['total'] or Decimal("0.00")
        return total.quantize(Decimal("0.01"))

    @property
    def balance(self):
        # ❌ Improvement: quantize balance to avoid float precision issues
        return (self.total_payable - self.total_paid).quantize(Decimal("0.01"))

    @property
    def due_date(self):
        return add_months(self.issued_on, self.term_months)

    @property
    def monthly_payment(self):
        if self.term_months > 0:
            return (self.total_payable / Decimal(self.term_months)).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        return Decimal('0.00')

    @property
    def is_current1(self):  ##This is critize to work on only one Original loan with no top-ups, Original loan with one top-up,
        """
        Return True if this loan is the most recent active/top-up for the account.
        """
        # If this is a top-up, check the latest top-up in the chain
        if self.top_up_of:
            latest_topup = self.top_up_of.topups.order_by('-issued_on').first()
            return latest_topup == self
        # If this is a regular loan without top-ups, it's current if no top-ups exist
        return not self.topups.exists()

    def is_current(self):
        """
        Return True if this loan is the most recent active/top-up for the account.
        """

        # Find the root loan (original)
        root = self
        while root.top_up_of:
            root = root.top_up_of

        # Get latest loan in the chain (original + all top-ups)
        latest = (Loan.objects
            .filter(Q(pk=root.pk) | Q(top_up_of=root))
            .order_by('-issued_on')
            .first())

        return latest == self

    from datetime import timedelta

    def approval_sla(self):
        if self.approved_on:
            return self.approved_on - self.issued_on
        elif self.rejected_on:
            return self.rejected_on - self.issued_on
        return None

    @staticmethod
    def get_active_loan(member):
        return Loan.objects.filter(
            account__member=member,status=Loan.LoanStatus.ACTIVE ).first()

    # -----------------------------
    # ✅ TOP-UP ELIGIBILITY  Only ACTIVE regular loans with some repayment can be topped up. Emergency loans cannot be topped up.
    # -----------------------------
    @property
    def can_be_topped_up(self):
        if self.loan_type != self.LoanType.REGULAR:
            return False
        if self.status != self.LoanStatus.ACTIVE:
            return False
        if self.total_payable <= 0:
            return False
        # ❌ Improvement: quantize ratio to maintain consistency
        ratio = (self.total_paid / self.total_payable).quantize(Decimal("0.01"))
        return ratio >= Decimal("0.10")

    # -----------------------------
    def refresh_status(self):
        if self.total_paid >= self.total_payable:
            self.status = self.LoanStatus.PAID
        elif self.total_paid > 0:
            self.status = self.LoanStatus.ACTIVE
        else:
            self.status = self.LoanStatus.PENDING   ##we can remove this , because
        self.save(update_fields=["status"])

    # ✅ TOP-UP CREATION
    # -----------------------------
    def top_up(self, new_amount: Decimal, new_term_months: int):
        from .services import LoanLimitService
        if not self.can_be_topped_up:
            raise ValidationError("At least 10% of the loan must be paid before top-up.")
        if Loan.objects.has_open_loan(self.account, exclude_loan_id=self.pk):
            raise ValidationError(  "Another active loan exists for this account."   )

        if not LoanLimitService.can_request_Member_loan(self.account, new_amount):
            raise ValidationError("Top-up amount exceeds your allowable loan limit.")

        with transaction.atomic():
            new_total_amount = self.balance + new_amount
            topup_loan = Loan.objects.create(
                account=self.account,
                loan_type=self.loan_type,
                amount=new_total_amount,
                term_months=new_term_months,
                status=Loan.LoanStatus.ACTIVE,
                top_up_of=self,
                issued_on=timezone.now().date(),
            )
            # ❌ Mark the old loan as inactive for payments
            self.refresh_status()  # existing method will update status to ACTIVE/PAID
            return topup_loan

    def amount_remaining(self):
        # ❌ Improvement: quantize result for template consistency
        return max(self.total_payable - self.total_paid, Decimal('0.00')).quantize(Decimal("0.01"))

    # -----------------------------
    # Save
    # -----------------------------
    def save(self, *args, **kwargs):
        self.full_clean()
        # ❌ Improvement: wrap save in transaction.atomic() for safety
        with transaction.atomic():
            super().save(*args, **kwargs)

            # 🔹 Activation side-effects
class LoanWorkflow(models.Model):
    class Stage(models.TextChoices):
        SUBMITTED = "submitted", "Submitted"
        OFFICER_REVIEW = "officer_review", "Officer Review"
        MANAGER_REVIEW = "manager_review", "Manager Review"
        DISBURSED = "disbursed", "Disbursed"
        CLOSED = "closed", "Closed"
    loan = models.ForeignKey(  "Loan",  on_delete=models.CASCADE,  related_name="workflow_history" )
    stage = models.CharField( max_length=30,  choices=Stage.choices  )
    handler = models.ForeignKey( settings.AUTH_USER_MODEL,  null=True,   blank=True,  on_delete=models.SET_NULL  )
    moved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    from django.utils import timezone

    def move_stage(self, new_stage, user=None, notes=None):
        old_stage = self.stage

        self.stage = new_stage

        if user:
            self.handler = user

        self.moved_at = timezone.now()

        if notes is not None:
            self.notes = notes

        self.save()

        LoanWorkflowHistory.objects.create(
            workflow=self,
            stage=new_stage,
            previous_stage=old_stage,
            handler=user,
            notes=notes or ""  )
    @property
    def is_with_officer(self):
        return self.stage == self.Stage.OFFICER_REVIEW

    @property
    def is_with_manager(self):
        return self.stage == self.Stage.MANAGER_REVIEW

    @property
    def is_disbursed_stage(self):
        return self.stage == self.Stage.DISBURSED

    @property
    def days_in_current_stage(self):
        if not self.stage_entered_at:
            return 0

        return (timezone.now().date() - self.stage_entered_at.date()).days
    # -----------------------------
class LoanWorkflowHistory(models.Model):
    workflow = models.ForeignKey(  LoanWorkflow, on_delete=models.CASCADE,   related_name="history" )
    stage = models.CharField( max_length=30, choices=LoanWorkflow.Stage.choices   )
    previous_stage = models.CharField(  max_length=30, choices=LoanWorkflow.Stage.choices,  null=True,
        blank=True )
    handler = models.ForeignKey( settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL )
    moved_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-moved_at"]

    def __str__(self):
        return f"{self.workflow.loan} -> {self.stage}"

##Ledger in services
# -----------------------------
# Loan Payment paid_on, loanCount, names, amount paid, amount_due, delay time, penalities_applied
# -----------------------------
class LoanPayment(ActiveAccountMixin, models.Model):
    loan = models.ForeignKey(Loan, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'), editable=False)
    paid_on = models.DateField(null=True, blank=True)
    due_date = models.DateField(blank=True, null=True)
    receipt_ref_no = models.CharField(max_length=12, unique=True, blank=True, null=True)
    delay_time = models.PositiveIntegerField(default=0, editable=False)  # Delay in months
    penalty_applied = models.BooleanField(default=False)
    received_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    ledger_posted = models.BooleanField(default=False, editable=False)

    def clean(self):
        super().clean()

        # 1️⃣ Ensure loan is selected
        if not self.loan_id:
            raise ValidationError("Loan must be selected for this payment.")

        # 2️⃣ Check borrower account status (must be active)
        if self.loan.account.status_type != 'active':
            raise ValidationError("Cannot accept payment: borrower account is inactive.")

        # 🔴 Prevent fully paid loan
        if self.loan.balance <= 0:
            raise ValidationError("This loan is fully paid. No further payments are allowed.")

        # 🔴 Prevent overpayment
        if self.amount > self.loan.balance:
            raise ValidationError(
                f"Payment exceeds remaining loan balance ({self.loan.balance:.2f})."
            )

        # 3️⃣ Check for duplicate receipt reference number
        if self.receipt_ref_no:
            exists = LoanPayment.objects.filter(receipt_ref_no=self.receipt_ref_no).exclude(pk=self.pk).exists()
            if exists:
                raise ValidationError({'receipt_ref_no': "This receipt reference number has already been used."})

        # 4️⃣ Snapshot due date (if not already set)
        if not self.due_date:
            self.due_date = self.loan.next_monthly_due_date()

        # 5️⃣ Ensure `paid_on` is set if not provided
        if not self.paid_on:
            self.paid_on = timezone.now().date()

        # 6️⃣ Validate delay time (calculate based on `paid_on` vs `due_date`)
        if self.paid_on and self.due_date and self.paid_on > self.due_date:
            months_late = (
                    (self.paid_on.year - self.due_date.year) * 12 +
                    (self.paid_on.month - self.due_date.month))
            self.delay_time = max(months_late, 1)
        else:
            self.delay_time = 0

        # 7️⃣ Compute amount_due based on delay
        self.amount_due = (self.loan.monthly_payment * Decimal(self.delay_time)).quantize(Decimal("0.01"))

        # 8️⃣ Ensure payment amount is greater than zero
        if self.amount <= 0:
            raise ValidationError("Payment amount must be greater than zero.")

    def apply_penalty(self):
        """Apply penalty if the payment is late and update relevant accounts."""
        from .services import LoanPaymentService

        # Apply penalty via service
        penalty_amount = LoanPaymentService.apply_penalty(self)
        return penalty_amount

    @transaction.atomic
    def save(self, *args, **kwargs):
        is_new = self._state.adding

        self.full_clean()
        super().save(*args, **kwargs)

        # 🔐 Ledger must be written ONLY ONCE
        if is_new and not self.ledger_posted:
            self.record_repayment_in_ledger()
            self.ledger_posted = True
            super().save(update_fields=['ledger_posted'])

    def record_repayment_in_ledger(self):
        """Record the loan repayment in the ledger and update the loan status if needed."""
        from .services import LoanPaymentService

        # Handle loan repayment
        LoanPaymentService.process_payment(self)  ##This also has ledgers

        # Check if loan is fully paid and update status if needed
        if self.loan.balance <= 0:
            self.loan.status = Loan.LoanStatus.PAID
            self.loan.save()

    @property
    def repayment_progress_percent(self):
        """Returns the repayment progress percentage of the loan."""
        total_payable = self.loan.total_payable
        if total_payable == 0:
            return Decimal("0.00")
        return ((self.loan.total_paid / total_payable) * 100).quantize(Decimal("0.01"))

    def __str__(self):
        return f"Payment for Loan {self.loan.id} - {self.amount_due} due on {self.due_date}"


##Using weighted Graphs (Penalize coreelation /number of nodes)						
