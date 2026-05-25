from decimal import Decimal
from math import ceil
from django.conf import settings
User = settings.AUTH_USER_MODEL
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.mixins import ActiveAccountMixin

# -----------------------------
# Base Transaction
# -----------------------------

from transact1_regular_deposit.services import DepositDueTransactionService



class BaseTransaction(models.Model):
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    description = models.TextField(blank=True)

    class Meta:
        abstract = True
        ordering = ['-timestamp']

# -----------------------------
# Penalty Mixin
# -----------------------------
class PenaltyMixin(models.Model):
    SUSPEND_STATUSES = ['dormant', 'inactive', 'suspended']

    flat_penalty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    percent_penalty = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    penalty_unpaid = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    penalty_applied = models.BooleanField(default=False)

    class Meta:
        abstract = True

    def is_penalty_suspended(self, account):
        if not account:
            return False
        return account and account.status_type in self.SUSPEND_STATUSES


# ##CREATE LEDEGER DEPOSIT HERE??, PENALITIES LEDGER
# Deposit Due Transaction
# -----------------------------
class DepositDueTransaction(PenaltyMixin, ActiveAccountMixin, BaseTransaction):
    account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
        related_name='deposit_due_transactions'  ) #null=True, blank=True,account should NOT be nullable, But every due must belong to an account.
    due_date = models.DateField(db_index=True)
    monthly_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))##Expected amount  to get
    is_paid = models.BooleanField(default=False)
    delay_time = models.PositiveIntegerField(default=0)
    ##penalty_applied = models.BooleanField(default=False)  # ✅ New field for tracking penalty application this is in penalityMixin
    BASE_AMOUNT_PER_SHARE = Decimal('5000.00')

    from math import ceil

    def clean(self):
        """
        Validation for date logic:
        - Allow early payments (paid_on before due_date) → no penalty.
        - Late payments → calculate delay in months (partial months rounded up).
        """
        super().clean()

        #if not self.due_date:
          #  raise ValidationError({'due_date': "A due date must be specified."}) ,But DateField() already enforces this.can not pass

    def save(self, *args, **kwargs):
        """
        Ensure monthly_due is calculated automatically.
        """

        if not self.monthly_due and self.account:
            shares = self.account.shares or 0
            self.monthly_due = shares * self.BASE_AMOUNT_PER_SHARE

        super().save(*args, **kwargs)

    @property
    def expected_due(self):
        """
        Total expected due depending on delay months.
        At least one month must be paid.
        """
        months = max(self.delay_time, 1)
        return self.monthly_due * months

    def unpaid_amount(self, paid_amount):
        if not paid_amount:
            paid_amount = Decimal("0.00")
        return max(self.expected_due - paid_amount, Decimal("0.00"))

class DepositTransaction(ActiveAccountMixin, BaseTransaction):
    deposit_due = models.ForeignKey('DepositDueTransaction', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='deposit_transactions')
    account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
                                related_name='deposit_transactions', editable=True, null=False)
    paid_on = models.DateField(null=True, blank=True)  ##The date could not be on duetransaction
    receipt_ref_no = models.CharField(max_length=12, blank=True, null=True)  #Because they belong to payment, not obligation.

    def clean(self):
        super().clean()

        if self.deposit_due and self.account:
            if self.deposit_due.account != self.account:
                raise ValidationError("Deposit account must match due account.")

    def save(self, *args, **kwargs):

        if self.deposit_due:
            self.account = self.deposit_due.account

            if self.paid_on and self.deposit_due.due_date:

                due = self.deposit_due.due_date
                paid = self.paid_on

                if paid > due:

                    months = (paid.year - due.year) * 12 + (paid.month - due.month)

                    if paid.day > due.day:
                        months += 1

                    self.deposit_due.delay_time = months
                else:
                    self.deposit_due.delay_time = 0

        self.full_clean()

        super().save(*args, **kwargs)

        if self.deposit_due:
            due = self.deposit_due

            total_due = due.expected_due + (due.penalty_unpaid or Decimal("0.00"))
            due.is_paid = self.amount_paid >= total_due

            due.save(update_fields=["delay_time", "is_paid"])

    @property   ##Property are not save in dabase , they help attributes to help calculations
    def amount_paid(self):
        return self.amount


# -----------------------------
# Withdrawal Transaction
# -----------------------------
class WithdrawalTransaction(ActiveAccountMixin, BaseTransaction):
    account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
                                related_name='withdrawal_transactions')

    def clean(self):
        super().clean()
        self.check_active_accounts()

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)


# Transfer Transaction, ##legers are in servises and called in Views
# -----------------------------
class TransferTransaction(ActiveAccountMixin, BaseTransaction):
    source_account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
                                       related_name='transfers_sent')
    destination_account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
                                            related_name='transfers_received')

    def clean(self):
        super().clean()
        self.check_active_accounts()
        if self.source_account == self.destination_account:
            raise ValidationError("Cannot transfer to the same account.")

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs)

##object_id: This stores the primary key of the related object (either a LoanPayment or DepositDueTransaction).
##content_type: This stores the primary key of the related object (either a LoanPayment or DepositDueTransaction).
##The GenericForeignKey ties the content_type and object_id together, making it a flexible field that can reference either LoanPayment or DepositDueTransaction.

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
# -----------------------------
# SJP2 Transaction
# -----------------------------
class SJP2Transaction(ActiveAccountMixin, BaseTransaction): #(Base transaction ,has amount, description,time)
    # -----------------------------
    # Transaction Type Enum
    # -----------------------------
    class TransactionType(models.TextChoices):
        INITIAL_DEPOSIT = 'initial_deposit', 'Initial Deposit'  # Capital contribution
        Loan_Interest = 'loan_interest', 'Loan Interest'
        Deposit = 'Deposit', 'Deposit'  # Fixed syntax (was 'Deposit, Deposit')
        Withdrawal = 'withdrawal', 'Withdrawal'
        Transfer = 'transfer', 'Transfer'
        External_Income = 'external_income', 'External Income Source'
        Expense = 'Expense', 'Expense'
        Interest_Distribution = 'interest_distribution', 'Interest Distribution'
        Penality_Late_deposit = 'penalty_late', 'Penalty - Late Payment'
        Penality_Underpay_deposit = 'penalty_underpayment', 'Penalty - Underpayment'
        Penality_Late_Loan = 'penalty_late_loan', 'Penalty - Late Payment - Loan'
        Penality_Underpay_Loan = 'penalty_underpayment_loan', 'Penalty - Underpayment - Loan'

    #class Status(models.TextChoices):
    #    PENDING = 'pending', 'Pending'
    #    POSTED = 'posted', 'Posted'
     #   REVERSED = 'reversed', 'Reversed'

    income_source = models.ForeignKey('accounts.IncomeSource', on_delete=models.SET_NULL, null=True, blank=True, related_name='income_transactions')
    expense_purpose = models.ForeignKey('accounts.ExpensePurpose', on_delete=models.SET_NULL, null=True, blank=True, related_name='transactions', help_text="Purpose of the expense")
    distribution_purpose = models.ForeignKey('transact5_share_distrib.MemberInterestShare', on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='sjp2_distribute_interest')
    interest_pool = models.ForeignKey(  'transact5_share_distrib.YearlyInterestPool',    on_delete=models.SET_NULL,    null=True,     blank=True,
        related_name='transactions'   )
    from_member_account = models.ForeignKey('accounts.MemberAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='sent_transactions')
    from_sjp2_account = models.ForeignKey('accounts.SJP2_Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='sjp2_sent_transactions')
    to_member_account = models.ForeignKey('accounts.MemberAccount', on_delete=models.SET_NULL, null=True, blank=True, related_name='received_transactions')
    to_sjp2_account = models.ForeignKey('accounts.SJP2_Account', on_delete=models.SET_NULL, null=True, blank=True, related_name='sjp2_received_transactions')

    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)

    # Generic Foreign Key for reference_transaction (either LoanPayment or DepositDueTransaction)
    content_type = models.ForeignKey(ContentType, on_delete=models.SET_NULL, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    reference_transaction = GenericForeignKey('content_type', 'object_id')
    #status = models.CharField( max_length=20,   choices=Status.choices,    default=Status.POSTED  )
    #reversal_of = models.ForeignKey( 'self',  on_delete=models.SET_NULL,    null=True,    blank=True,     related_name='reversed_by'
    #)
    performed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"{self.transaction_type} - {self.amount} on {self.timestamp}"

    def _ensure_sufficient_balance(self, account, amount, field_name):
        from django.core.exceptions import ValidationError
        from decimal import Decimal

        if not account:
            raise ValidationError({field_name: "Account is required."})

        balance = getattr(account, "balance", Decimal('0.00'))

        if amount <= 0:
            raise ValidationError({"amount": "Amount must be greater than zero."})

        if amount > balance:
            raise ValidationError({field_name: f"Insufficient balance. Available: {balance}" })
    # Save + Ledger
    # -----------------------------
    def save(self, *args, **kwargs):
        # Run all validations in one place
        self.full_clean()  # ✅ Will call our updated clean() method

        is_new = self.pk is None

        with transaction.atomic():
            super().save(*args, **kwargs)

            # Only create ledger entries for new transactions
            if is_new:
                self._create_ledger_entry()

    def _create_ledger_entry(self):
        from ledger.services import LedgerService
        reference = f"SJP2Transaction ID {self.pk}"

        # 1️⃣ Penalty transactions (Debit member, Credit SJP2)
        if self.transaction_type.startswith("penalty_"):
            # Debit member
            LedgerService.create_statement(
                account=self.from_member_account,
                transaction_type=self.transaction_type,
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference )

            # Credit SJP2 account
            LedgerService.create_statement(
                account=self.to_sjp2_account,
                transaction_type=self.transaction_type,
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference )

        # -----------------------------
        # 2️⃣a Deposit (Credit to member,UWHEN PROVID AID)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Deposit:
            LedgerService.create_statement(
                account=self.to_member_account,
                transaction_type='deposit',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference )
            ##capital contibution from new members
            # -----------------------------
            # 2️⃣b Deposit (initial deposit)
            # -
        elif self.transaction_type == self.TransactionType.INITIAL_DEPOSIT:
            LedgerService.create_statement(
                account=self.to_sjp2_account,
                transaction_type='initial_deposit',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference     )

        # -----------------------------
        # 3️⃣ Withdrawal (DEBit when you go to purchase)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Withdrawal:
            LedgerService.create_statement(
                account=self.from_member_account,
                transaction_type='withdrawal',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference )

        # -----------------------------
        # 4️⃣ Transfer
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Transfer:
            # Outgoing debit
            LedgerService.create_statement(
                account=self.from_member_account,
                transaction_type='transfer_out',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )
            # Incoming credit
            LedgerService.create_statement(
                account=self.to_member_account,
                transaction_type='transfer_in',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference )

        # -----------------------------
        # 5️⃣ Loan Interest (Debit from SJP2, credit member)  ##NO DOUBLE RECORDING , BECAUSE IT IS ALSO IN APPROAVL
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Loan_Interest:
            # Debit member (interest expense)
            LedgerService.create_statement(
                account=self.from_member_account,
                transaction_type='loan_interest',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference   )

            # Credit SJP2 (interest income)  CHECK SYSTEM LEGDER
            #LedgerService.create_statement(
            #    account=self.to_sjp2_account,
            #    transaction_type='loan_interest',
            #    debit=Decimal('0.00'),
            #    credit=self.amount,
             #   reference=reference            )


        # -----------------------------
        # 6️⃣ Expense (Debit ssjp2)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Expense:
            LedgerService.create_statement(
                account=self.from_sjp2_account,
                transaction_type='expense',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference)

        # -----------------------------
        # 7️⃣ External Income (Credit member/SJP2 account)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.External_Income:
            LedgerService.create_statement(
                account=self.to_sjp2_account,
                transaction_type='external_income',
                debit=Decimal('0.00'),
                credit=self.amount, ##It receives)
                reference=reference)
        elif self.transaction_type == self.TransactionType.Interest_Distribution:

            # 1️⃣ Debit main SJP2 source (money leaves main pool)
            LedgerService.create_statement(
                account=self.from_sjp2_account,
                transaction_type='interest_distribution',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference)

            # 2️⃣ Credit System Pool (temporary holding / payout bucket, acount to control montly distribution)
            #LedgerService.create_statement(   ,It works like expense
             #   account=self.to_sjp2_account,
             #   transaction_type='interest_distribution',
              #  debit=Decimal('0.00'),
              #  credit=self.amount,
              #  reference=reference )

            # 🧾 Audit-only record (NO member balance impact)
            # We do NOT credit member account in ledger system balance sense
            # because cash is already given physically

    def clean(self):
        from django.core.exceptions import ValidationError
        from decimal import Decimal
        from transact2_loans.models import LoanPayment


        # 0️⃣ Check account status (from mixin)
        self.check_active_accounts()

        # -----------------------------
        # 1️⃣ Penalty Transactions
        # -----------------------------
        # Penalty Transactions
        if self.transaction_type.startswith('penalty_'):
            if not self.from_member_account:
                raise ValidationError({'from_member_account': "Penalty transactions must have a member account."})
            if not self.to_sjp2_account:
                raise ValidationError({'to_sjp2_account': "Penalty transactions must have a to_sjp2_account."})
            if not self.reference_transaction:
                raise ValidationError(
                    {'reference_transaction': "Penalty transactions must reference a valid deposit or loan."})

            if not isinstance(self.reference_transaction, (LoanPayment, DepositDueTransaction)):
                raise ValidationError(
                    {'reference_transaction': "Reference transaction must be a LoanPayment or DepositDueTransaction."})

        # -----------------------------
        # 2️⃣ Expense (money leaves SJP2)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Expense:
            if not self.from_sjp2_account:
                raise ValidationError({
                    'from_sjp2_account': "Expense must have a source SJP2 account."
                })

            self._ensure_sufficient_balance(self.from_sjp2_account,  self.amount, "from_sjp2_account" )
            #if self.amount <= 0:
             #   raise ValidationError({
             #       'amount': "Expense amount must be greater than zero."
             #   })
            #if self.amount > available_balance:
            #    raise ValidationError({
             #       'amount': f"Insufficient balance: {available_balance}"
             #   })

        # -----------------------------
        # 3️⃣ Withdrawal (member cash out)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Withdrawal:
            if not self.from_member_account:
                raise ValidationError({
                    'from_member_account': "Withdrawal must have a member account." })

            if self.amount <= 0:
                raise ValidationError({'amount': "Withdrawal amount must be greater than zero." })

            self._ensure_sufficient_balance( self.from_member_account,    self.amount,       "from_member_account" )

        # -----------------------------
        # 4️⃣ External Income
        # -----------------------------
        elif self.transaction_type == self.TransactionType.External_Income:
            if not self.income_source:
                raise ValidationError({
                    'income_source': "External income must have a valid income source."
                })
            if not self.to_sjp2_account:
                raise ValidationError({
                    'to_sjp2_account': "External income must have a to_sjp2_account."
                })

        # -----------------------------
        # 5️⃣ Transfers
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Transfer:
            if not self.from_member_account or not self.to_member_account:
                raise ValidationError(
                    "Transfer must have both from_member_account and to_member_account."
                )

            if self.from_member_account == self.to_member_account:
                raise ValidationError("Cannot transfer to the same account." )

            if self.amount <= 0:  raise ValidationError({
                    'amount': "Transfer amount must be greater than zero." })

            self._ensure_sufficient_balance(   self.from_member_account,
                self.amount,  "from_member_account" )
        # -----------------------------
        # 6️⃣ Deposits
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Deposit:
            if not self.to_member_account:
                raise ValidationError({
                    'to_member_account': "Deposit must have a to_member_account."
                })
            if not self.to_sjp2_account:
                raise ValidationError({
                    'to_sjp2_account': "Deposit must have a to_sjp2_account."
                })
            if self.amount <= 0:
                raise ValidationError({
                    'amount': "Deposit amount must be greater than zero."
                })

        # -----------------------------
        # 7️⃣ Loan Interest
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Loan_Interest:
            if not self.from_member_account:
                raise ValidationError({
                    'from_member_account': "Loan interest must be paid by a member."
                })
            if not self.to_sjp2_account:
                raise ValidationError({
                    'to_sjp2_account': "Loan interest must be received by an SJP2 account."
                })
            if self.amount <= 0:
                raise ValidationError({
                    'amount': "Loan interest amount must be greater than zero."
                })


        # -----------------------------
        # 8️⃣ Initial Deposit
        # -----------------------------
        elif self.transaction_type == self.TransactionType.INITIAL_DEPOSIT:
            if not self.from_member_account:
                raise ValidationError({
                    'from_member_account': "Initial deposit must have from_member_account."
                })
            if not self.to_sjp2_account:
                raise ValidationError({
                    'to_sjp2_account': "Initial deposit must have to_sjp2_account."
                })
            if self.amount <= 0:
                raise ValidationError({
                    'amount': "Initial deposit amount must be positive."
                })
        elif self.transaction_type == self.TransactionType.Interest_Distribution:
            if not self.from_sjp2_account:
                raise ValidationError({
                    'from_sjp2_account': "Interest distribution must have source account."
                })

            if self.amount <= 0:
                raise ValidationError({'amount': "Amount must be greater than zero."     })

            self._ensure_sufficient_balance(  self.from_sjp2_account, self.amount,  "from_sjp2_account" )
        # -----------------------------
        # Call parent clean
        # -----------------------------
        super().clean()



#| Scenario                                        | Result               |
#| ----------------------------------------------- | -------------------- |
#| paid_on ≤ due_date AND amount_paid ≥ amount_due | No penalty           |
#| paid_on ≤ due_date AND amount_paid < amount_due | Underpayment penalty |
#| paid_on > due_date AND amount_paid ≥ amount_due | Late penalty         |
#| paid_on > due_date AND amount_paid < amount_due | Late + Underpayment  |
