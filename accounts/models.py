from django.db.models import Sum
from datetime import date
from django.utils import timezone
from django.db import models, transaction
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from decimal import Decimal
#from ledger.services import LedgerService
from django.urls import reverse
##from ledger.models import AccountStatement
#from transact2_loans.models import Loan  # Make sure this import path is correct
SHARE_VALUE = Decimal('5000')

class Role(models.Model): ##The change can also perfromed in signals
    class RoleName(models.TextChoices):
        MANAGER = "manager", "Manager"
        AUDITOR = "auditor", "Auditor"
        ORDINARY_MEMBER = "ordinary_member", "Ordinary Member"
        OFFICER = "officer", "Officer"
        VERIFIER = "verifier", "Verifier"
        SECRETARY = "secretary", "Secretary"
        IT_ADMIN = "itadmin", "IT Admin"

    name = models.CharField(  max_length=20,  choices=RoleName.choices,
        unique=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.name

class User(AbstractUser):
    telephone = models.CharField(max_length=13, default='+000000000000')

    roles = models.ManyToManyField('Role', related_name='users')

    @property
    def account(self):
        try:
            return self.membersprofile.account
        except (MembersProfile.DoesNotExist, MemberAccount.DoesNotExist):
            return None

    def has_role(self, role_name):
        return self.roles.filter(name=role_name).exists()

    def has_any_role(self, *role_names):
        return self.roles.filter(name__in=role_names).exists()

    @property
    def is_ordinary_member(self):
        return self.has_role("ordinary_member")

    @property
    def is_staff_viewer(self):
        return self.has_any_role("officer", "manager", "itadmin")

    @property
    def dashboard_url(self):
        role_dashboard_map = {
            "manager": "accounts:manager-dashboard",
            "auditor": "accounts:auditor-dashboard",
            "ordinary_member": "accounts:customer-dashboard",
            "officer": "accounts:officer-dashboard",
            "verifier": "accounts:verifier-dashboard",
            "secretary": "accounts:secretary-dashboard",
            "itadmin": "accounts:itadmin-dashboard",
        }

        active_role = getattr(self, "_active_role", None)

        # fallback to session-style role (recommended)
        if active_role:
            return reverse(role_dashboard_map.get(active_role, "accounts:customer-dashboard"))

        user_roles = set(self.roles.values_list("name", flat=True))

        for role in role_dashboard_map:
            if role in user_roles:
                return reverse(role_dashboard_map[role])

        return reverse("accounts:customer-dashboard")

class MembersProfile(models.Model): ##Fname,Lname are in user model
    objects = models.Manager()   ##Adding objects = models.Manager() makes it clear to static analysis tools like the one in PyCharm or VS Code that the model has a .objects attribute
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    national_id = models.CharField(max_length=16)
    address = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name}" ##Use self.user, because they are not in MembersProfile


class SJP2_Profile(models.Model):
    objects = models.Manager()
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    location_address = models.CharField(max_length=255)  # e.g., "Gasabo/Jali"
    started_on = models.DateField(default=timezone.now)

    def __str__(self):
        return self.user.username  # Correct: Return a string don't return {self.user.username}


class MemberAccount(models.Model):
    """Member Account model (LEDGER-DERIVED BALANCE)"""

    class StatusType(models.TextChoices):
        ACTIVE = 'active', 'Active'
        SUSPENDED = 'suspended', 'Suspended'
        CLOSED = 'closed', 'Closed'
        DORMANT = 'dormant', 'Dormant'

    member = models.OneToOneField( 'MembersProfile',  on_delete=models.CASCADE,
        related_name='account'  )

    account_number = models.CharField(max_length=20, unique=True, blank=True)
    shares = models.PositiveIntegerField(default=1)

    initial_deposit = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    principal = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    balance = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))

    opened_on = models.DateTimeField(default=timezone.now)

    status_type = models.CharField(
        max_length=20,
        choices=StatusType.choices,
        default=StatusType.ACTIVE )

    closed_on = models.DateTimeField(null=True, blank=True)
    suspended_on = models.DateTimeField(null=True, blank=True)
    dormant_on = models.DateTimeField(null=True, blank=True)
    last_activity_on = models.DateTimeField(null=True, blank=True)

    objects = models.Manager()

    def __str__(self):
        return f"{self.member} - {self.account_number}"


    def Is_close_account(self):
        self.status_type = self.StatusType.CLOSED
        self.closed_on = timezone.now()
        self.save()

    def Is_dormant_account(self):
        self.status_type = self.StatusType.DORMANT
        self.closed_on = timezone.now()
        self.save()

    def Is_suspend_account(self):
        self.status_type = self.StatusType.SUSPENDED
        self.suspended_on = timezone.now()
        self.save()

    def Is_activate_account(self):
        self.status_type = self.StatusType.ACTIVE
        self.save()

    def update_activity(self):
        self.last_activity_on = timezone.now()
        # ❌ Pass _from_ledger=True so it doesn't trigger direct balance error
        self.save(update_fields=['last_activity_on'], _from_ledger=True)  # ❌

    @property
    def first_name(self):
        return self.member.user.first_name

    @property
    def last_name(self):
        return self.member.user.last_name

    @property
    def full_name(self):
        return f"{self.member.user.first_name} {self.member.user.last_name}"

    @property
    def display_name(self):
        return f"{self.full_name} ({self.account_number})"

    from datetime import date  # ✅ This is
    def get_total_months_since_opened(self):
        """
        Returns the number of full months since the account was opened.
        """
        if not self.opened_on:
            return 0
        opened_date = self.opened_on.date()
        today = date.today()
        months = (today.year - opened_date.year) * 12 + (today.month - opened_date.month)
        # If current day is earlier than opened day in the month, subtract one month
        if today.day < opened_date.day:
            months -= 1
        return max(months, 0)


    # =========================================================
    # STATUS MANAGEMENT
    # =========================================================
    @transaction.atomic
    def _change_status(self, new_status: str):
        if self.status_type == new_status:
            return

        from .models import AccountStatusHistory  # ✅ lazy import

        now = timezone.now()
        AccountStatusHistory.objects.create(
            account=self,
            status_type=new_status,
            started_on=now
        )

        self.status_type = new_status

        if new_status == self.StatusType.CLOSED:
            self.closed_on = now
        elif new_status == self.StatusType.SUSPENDED:
            self.suspended_on = now
        elif new_status == self.StatusType.DORMANT:
            self.dormant_on = now

        self.save(update_fields=[
            'status_type', 'closed_on', 'suspended_on', 'dormant_on'
        ])
    #===========================
    ## Generate account:
    #=========================
    # =========================================================
    # ACCOUNT NUMBER GENERATION (PER YEAR)
    # =========================================================
    def generate_next_account_number(self, year=None):
        """
        Generate the next account number for a given year.
        If no year is provided, defaults to the current year.

        Account number format: SSJP2-XXX-YYYY
        - XXX: sequence number for that year, zero-padded to 3 digits
        - YYYY: the year
        """
        prefix = "SSJP2"

        # Use provided year, or default to current year
        if year is None:
            year = timezone.now().year

        # Find the last account for this year
        last_account = (
            MemberAccount.objects
            .filter(account_number__endswith=f"-{year}")
            .order_by('-id')
            .first()
        )

        # Determine last sequence number
        last_seq = 0
        if last_account:
            try:
                # account_number format: SSJP2-XXX-YYYY
                last_seq = int(last_account.account_number.split('-')[1])
            except Exception:
                last_seq = 0

        # Return next account number
        return f"{prefix}-{last_seq + 1:03d}-{year}"

    # =========================================================
    # SHARES (LEDGER-BASED)
    # =========================================================
    def increase_shares(self, nbr: int):
        if nbr <= 0:
            raise ValueError("Number of shares must be positive")

        from ledger.services import LedgerService  # ✅ lazy import

        amount = Decimal(nbr) * SHARE_VALUE

        with transaction.atomic():
            self.shares += nbr
            self.principal += amount
            self.last_activity_on = timezone.now()
            self.save(update_fields=['shares', 'principal', 'last_activity_on'])

            LedgerService.create_statement(
                account=self,
                transaction_type='deposit',
                credit=amount,
                reference=f"Share purchase ({nbr})"
            )

    def decrease_shares(self, nbr: int):
        if nbr <= 0:
            raise ValueError("Number of shares must be positive")

        from ledger.services import LedgerService  # ✅ lazy import

        amount = Decimal(nbr) * SHARE_VALUE

        if self.balance < amount:
            raise ValueError("Insufficient balance")

        with transaction.atomic():
            self.shares -= nbr
            self.principal -= amount
            self.last_activity_on = timezone.now()
            self.save(update_fields=['shares', 'principal', 'last_activity_on'])

            LedgerService.create_statement(
                account=self,
                transaction_type='withdraw',
                debit=amount,
                reference=f"Share reduction ({nbr})"
            )

    # =========================================================
    # SAVE
    def save(self, *args, **kwargs):
        is_new = self.pk is None

        # ❌ Pop the custom ledger flag
        from_ledger = kwargs.pop('_from_ledger', False)  # ❌

        # Detect balance change
        if not is_new:
            old_balance = (MemberAccount.objects.filter(pk=self.pk)
                .values_list("balance", flat=True).first())

            # ❌ Only enforce ledger rule if _from_ledger=False, Prevent balance changes unless they are performed by the Ledger system.
            if old_balance != self.balance and not from_ledger:  # ❌
                raise RuntimeError(
                    "Check in accounts models. Direct balance updates are forbidden. "
                    "Use LedgerService to modify balances."  # ❌
                )

        # Existing logic preserved
        if is_new and not self.account_number:
            self.account_number = self.generate_next_account_number()
            self.initial_deposit = SHARE_VALUE
            self.principal = Decimal('0.00')

        super().save(*args, **kwargs)


# -----------------------------
# ACCOUNT STATUS HISTORY MODEL
# -----------------------------
class AccountStatusHistory(models.Model):
    """Track every status change of a MemberAccount"""
    account = models.ForeignKey(
        MemberAccount, on_delete=models.CASCADE, related_name='status_history'
    )
    status_type = models.CharField(max_length=20, choices=MemberAccount.StatusType.choices)
    started_on = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ['started_on']

    def __str__(self):
        return f"{self.account.account_number} - {self.status_type} ({self.started_on.date()})"



class AccountStatusSnapshot(models.Model):
    """
    One row per account per month per status
    """
    account = models.ForeignKey(MemberAccount, on_delete=models.CASCADE)
    year = models.PositiveIntegerField()
    month = models.PositiveIntegerField()

    status_type = models.CharField( max_length=20, choices=MemberAccount.StatusType.choices )

    days_in_status = models.PositiveIntegerField()
    months_fraction = models.DecimalField(max_digits=5,decimal_places=2 )

    class Meta:
        unique_together = ('account', 'year', 'month', 'status_type')


class SJP2_Account(models.Model):
    objects = models.Manager()

    Solid_info = models.ForeignKey('SJP2_Profile', on_delete=models.CASCADE, null=True, blank=True)
    account_nbr = models.CharField(max_length=20, unique=True)
    purpose = models.CharField(max_length=100, default='System Pool')  # Fixed default
    balance = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_penalized_amount = models.DecimalField(max_digits=15, decimal_places=2, default=0)  # New Field
    created_on = models.DateTimeField(default=timezone.now)
    last_activity_on = models.DateTimeField(default=timezone.now, blank=True, null=True)

    class Meta:
        ordering = ['id']  # or any field that makes sense

    def __str__(self):
        return f"{self.account_nbr} - {self.purpose}"

    def update_activity(self):
        self.last_activity_on = timezone.now()
        # ❌ Pass _from_ledger=True so it doesn't trigger direct balance error
        self.save(update_fields=['last_activity_on'], _from_ledger=True)  # ❌
    def save(self, *args, **kwargs):
        # Ensure there's only one account
        if not self.pk and SJP2_Account.objects.exists():
            raise ValidationError("Only one SJP2 system account is allowed.")

        # Auto-generate unique account number if not set
        if not self.account_nbr:
            self.account_nbr = "SJP2-SYSTEM"

        # Force purpose to be consistent
        self.purpose = "System Pool"

        # Handle '_from_ledger' explicitly
        from_ledger = kwargs.pop('_from_ledger', False)  # Extract '_from_ledger' if passed
        if from_ledger:
            # Perform necessary operations related to ledger updates (balance, etc.)
            self.total_penalized_amount += kwargs.get('penalty_amount', Decimal('0.00'))

        super().save(*args, **kwargs)  # Call the parent save method
        if from_ledger:
            # Additional logic for ledger-related operations can go here
            pass

    @staticmethod
    def get_main_account():
        return SJP2_Account.objects.first()


class IncomeSource(models.Model):##No reason for adding amount, because ssjp2transaction,has input amount, time,description)
    class SourceName(models.TextChoices):
        DONATION = 'Donation', 'Donation'
        GOVERNMENT_GRANT = 'Government Grant', 'Government Grant'
        MICROFINANCE_PROFIT= 'Microfinance Profit', 'Microfinance Profit'
        OTHER = 'Other', 'Other'

    name = models.CharField(max_length=100,choices=SourceName.choices,  help_text="Select the source of income" )
    description = models.TextField(blank=True)
     # linked_account = models.ForeignKey('SJP2_Account', on_delete=models.CASCADE, related_name='income_sources') is linked in transaction
    Receipt_ref_no = models.CharField(max_length=12,blank=True, null=True,help_text="type 12 ref_N0")
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class ExpensePurpose(models.Model):
    class OperationType(models.TextChoices):
        MACHINE_PURCHASE = 'Machine Purchase', 'Machine Purchase'
        WATER_BILL = 'Water Bill', 'Water Bill'
        IT_Service= 'IT Services', 'IT Services'
        Bonus_ = 'Bonus ', 'Bonus'
        OTHER = 'Other', 'Other'

    name = models.CharField(max_length=100, choices=OperationType.choices,
        help_text="Select the purpose of the expense")
    description = models.TextField(blank=True)
    receipt_ref_no = models.CharField(max_length=12, blank=True, null=True,
        help_text="Type 12-characters"    )
    is_active = models.BooleanField(default=True)
    created_on = models.DateTimeField(auto_now_add=True)



##shortcut to create a folder inside other folder:  New-Item -ItemType Directory accounts\management
##New-Item -ItemType Directory accounts\management\commands
##New-Item accounts\management\__init_
##New-Item accounts\management\commands\__init
##T#ransaction atomic, transaction.atomic makes sure everything succeeds or nothing is saved.
# ((Imenya ko buri step ikozwe, hagira imwe muri iba failed, nizindi zose , zisenyuka (rollback) ,Db ,ntihinguke
##History pollution = useless, duplicate, or misleading history records that make your timeline noisy or incorrect.