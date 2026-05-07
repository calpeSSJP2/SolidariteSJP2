from decimal import Decimal
from django.db import models, transaction
from django.core.exceptions import ValidationError
from django.utils import timezone
from accounts.mixins import ActiveAccountMixin

# -----------------------------
# Base Transaction
# -----------------------------
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
        return account.status_type in self.SUSPEND_STATUSES


# ##CREATE LEDEGER DEPOSIT HERE??, PENALITIES LEDGER
# Deposit Due Transaction
# -----------------------------
class DepositDueTransaction(PenaltyMixin, ActiveAccountMixin, BaseTransaction):
    account = models.ForeignKey(
        'accounts.MemberAccount',
        on_delete=models.CASCADE,
        related_name='deposit_due_transactions',
        null=True,
        blank=True,
    )
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_on = models.DateField(null=True, blank=True)
    receipt_ref_no = models.CharField(max_length=12, blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    delay_time = models.PositiveIntegerField(default=0)

    BASE_AMOUNT_PER_SHARE = Decimal('5000.00')

    def clean(self):
        """
        Validation for date logic:
        - Allow early payments (paid_on before due_date).
        - If paid_on < due_date, mark delay_time = 0 (no penalty).
        - Ensure both dates are valid if provided.
        """
        super().clean()

        if not self.due_date:
            raise ValidationError({'due_date': "A due date must be specified."})

        if self.paid_on:
            # Early payment → no penalty
            if self.paid_on < self.due_date:
                self.delay_time = 0
            else:
                # Normal delay calculation (difference in months)
                self.delay_time = ((self.paid_on.year - self.due_date.year) * 12
                    + (self.paid_on.month - self.due_date.month))

    def save(self, *args, **kwargs):
        # Run clean() to apply date logic
        self.full_clean()

        # Auto-calculate amount_due if not set
        if not self.amount_due or self.amount_due == Decimal('0.00'):
            shares = self.account.shares or 0
            self.amount_due = shares * self.BASE_AMOUNT_PER_SHARE

        super().save(*args, **kwargs)

    @property
    def amount_paid(self):
        return self.amount

    def process_and_save(self):
        from transact1_regular_deposit.services import DepositDueTransactionService
        DepositDueTransactionService.calculate_and_save(self)

class DepositTransaction(ActiveAccountMixin, BaseTransaction):
    deposit_due = models.ForeignKey('DepositDueTransaction', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='deposit_transactions')
    account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE, related_name='deposit_transactions',
                                editable=False, null=True)

    class Meta(BaseTransaction.Meta):
        verbose_name = "Deposit Transaction"
        verbose_name_plural = "Deposit Transactions"

    def clean(self):
        super().clean()
        self.check_active_accounts()

        if self.amount <= 0:
            raise ValidationError({'amount': "Deposit amount must be positive."})

        if self.deposit_due and self.deposit_due.account != self.account:  ##Check deposit_due.account
            raise ValidationError("DepositDue account mismatch.")

    def __str__(self):
        return f"Deposit {self.amount} → {self.account}"
#no save override, no ledger entry here it will be in services



# -----------------------------
# Withdrawal Transaction
# -----------------------------
class WithdrawalTransaction(ActiveAccountMixin, BaseTransaction):
    account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
        related_name='withdrawal_transactions' )

    def clean(self):
        super().clean()
        self.check_active_accounts()  # ✅ Ensure account is active

    def save(self, *args, **kwargs):
        # Ensure validations
        self.full_clean()

        is_new = self.pk is None

        super().save(*args, **kwargs)

        # Only create ledger entry for new withdrawals
        if is_new:
            self._create_ledger_entry()

    def _create_ledger_entry(self):
        """
        Create a ledger statement for this withdrawal transaction
        (debiting the member account)
        """
        from ledger.services import LedgerService

        if self.account:
            LedgerService.create_statement(
                account=self.account,
                transaction_type='withdrawal',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=f"WithdrawalTransaction ID {self.pk}" )



# -----------------------------
# Transfer Transaction
# -----------------------------
class TransferTransaction(ActiveAccountMixin, BaseTransaction):
    source_account = models.ForeignKey(
        'accounts.MemberAccount', on_delete=models.CASCADE,
        related_name='transfers_sent'
    )
    destination_account = models.ForeignKey(
        'accounts.MemberAccount', on_delete=models.CASCADE,
        related_name='transfers_received'
    )

    def clean(self):
        super().clean()
        self.check_active_accounts()
        if self.source_account == self.destination_account:
            raise ValidationError("Cannot transfer to the same account.")

    def save(self, *args, **kwargs):
        # Run validations
        self.full_clean()

        is_new = self.pk is None

        super().save(*args, **kwargs)

        # Only create ledger entries for new transfers
        if is_new:
            self._create_ledger_entries()

    def _create_ledger_entries(self):
        """
        Ledger entries for a transfer:
        - Debit source account
        - Credit destination account
        """
        from ledger.services import LedgerService

        reference = f"TransferTransaction ID {self.pk}"

        if self.source_account:
            LedgerService.create_statement(
                account=self.source_account,
                transaction_type='transfer_out',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )

        if self.destination_account:
            LedgerService.create_statement(
                account=self.destination_account,
                transaction_type='transfer_in',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference )



# -----------------------------
# SJP2 Transaction
# -----------------------------
class SJP2Transaction(ActiveAccountMixin,BaseTransaction):
    # -----------------------------
    # Transaction Type Enum
    # -----------------------------
    class TransactionType(models.TextChoices):
        INITIAL_DEPOSIT = 'initial_deposit', 'Initial Deposit'  ##capital contibution
        Loan_Interest = 'loan_interest', 'loan-interest'
        Deposit = 'Deposit', 'Deposit'  # fixed syntax (was 'Deposit, Deposit')
        Withdrawal = 'withdrawal', 'Withdrawal'
        Transfer = 'transfer', 'Transfer'
        External_Income = 'external_income', 'External Income Source'
        Expense = 'Expense', 'Expense'
        Penality_Late_deposit = 'penalty_late', 'Penalty - Late Payment'
        Penality_Underpay_deposit = 'penalty_underpayment', 'Penalty - Underpayment'
        Penality_Late_Loan = 'penalty_late_loan', 'Penalty - Late Payment - Loan'
        Penality_Underpay_Loan = 'penalty_underpayment_loan', 'Penalty - Underpayment - Loan'
    income_source = models.ForeignKey( 'accounts.IncomeSource',
        on_delete=models.SET_NULL, null=True, blank=True,  related_name='income_transactions'  )
    expense_purpose = models.ForeignKey('accounts.ExpensePurpose',on_delete=models.SET_NULL,
        null=True, blank=True, related_name='transactions',help_text="Purpose of the expense"  )
    from_member_account = models.ForeignKey('accounts.MemberAccount',  on_delete=models.SET_NULL,
        null=True, blank=True,related_name='sent_transactions'  )
    from_sjp2_account = models.ForeignKey('accounts.SJP2_Account', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='sjp2_sent_transactions' )
    to_member_account = models.ForeignKey('accounts.MemberAccount', on_delete=models.SET_NULL,
        null=True, blank=True,related_name='received_transactions'  )
    to_sjp2_account = models.ForeignKey('accounts.SJP2_Account',on_delete=models.SET_NULL,
        null=True, blank=True,related_name='sjp2_received_transactions')

    transaction_type = models.CharField(max_length=30, choices=TransactionType.choices)
    reference_transaction = models.ForeignKey('transact1_regular_deposit.DepositDueTransaction',
        on_delete=models.CASCADE, null=True,  blank=True, related_name='penalty_transactions',
        help_text="Reference to the original deposit due transaction (used for penalties)."  )
    # -----------------------------
    def __str__(self):
        return f"{self.transaction_type} - {self.amount} on {self.timestamp}"
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
        # 2️⃣a Deposit (Credit to member)
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
        # 3️⃣ Withdrawal (Debit from member)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Withdrawal:
            LedgerService.create_statement(
                account=self.from_member_account,
                transaction_type='withdrawal',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )

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
        # 5️⃣ Loan Interest (Debit from SJP2, credit member)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Loan_Interest:
            LedgerService.create_statement(
                account=self.to_member_account,
                transaction_type='loan_interest',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference    )

        # -----------------------------
        # 6️⃣ Expense (Debit member)
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Expense:
            LedgerService.create_statement(
                account=self.from_member_account,
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
                credit=self.amount,
                reference=reference)

    def clean(self):
        from django.core.exceptions import ValidationError

        # ✅ 0️⃣ Check account status (from mixin)
        self.check_active_accounts()

        # -----------------------------
        # 1️⃣ Penalty Transactions
        # -----------------------------
        if self.transaction_type.startswith('penalty_'):
            if not self.from_member_account:
                raise ValidationError({
                    'from_member_account': "Penalty transactions must have a member account."
                })
            if not self.to_sjp2_account:
                raise ValidationError({
                    'to_sjp2_account': f"{self.transaction_type} must have a to_sjp2_account."
                })
            # Optional: must reference a deposit/loan
            if getattr(self, 'reference_transaction', None) is None:
                raise ValidationError({
                    'reference_transaction': "Penalty transactions must reference a valid deposit or loan."
                })

        # -----------------------------
        # 2️⃣ Expense or Withdrawal
        # -----------------------------
        elif self.transaction_type in [self.TransactionType.Expense, self.TransactionType.Withdrawal]:
            if not self.from_member_account or not self.from_sjp2_account or not self.to_sjp2_account:
                raise ValidationError(
                    "Expense/Withdrawal must have from_member_account, from_sjp2_account, and to_sjp2_account."
                )

            available_balance = getattr(self.from_sjp2_account, "balance", Decimal('0.00'))
            if self.amount > available_balance:
                raise ValidationError({
                    'amount': f"Insufficient balance: {available_balance}. You cannot spend {self.amount}."
                })

        # -----------------------------
        # 3️⃣ External Income
        # -----------------------------
        elif self.transaction_type == self.TransactionType.External_Income:
            if not self.income_source:
                raise ValidationError({'income_source': "External income must have a valid income_source."})
            if not self.to_sjp2_account:
                raise ValidationError({'to_sjp2_account': "External income must have a to_sjp2_account."})

        # -----------------------------
        # 4️⃣ Transfers
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Transfer:
            if not self.from_member_account or not self.to_member_account:
                raise ValidationError("Transfer must have both from_member_account and to_member_account.")
            if self.from_member_account == self.to_member_account:
                raise ValidationError("Cannot transfer to the same account.")

        # -----------------------------
        # 5️⃣ Deposits
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Deposit:
            if not self.to_member_account:
                raise ValidationError("Deposit must have a to_member_account.")
            if not self.to_sjp2_account:
                raise ValidationError("Deposit must have a to_sjp2_account.")

        # -----------------------------
        # 6️⃣ Loan Interest
        # -----------------------------
        elif self.transaction_type == self.TransactionType.Loan_Interest:
            if not self.from_sjp2_account:
                raise ValidationError({'from_sjp2_account': "Loan interest must have a from_sjp2_account."})
            if not self.to_member_account:
                raise ValidationError({'to_member_account': "Loan interest must have a to_member_account."})
            if self.amount <= 0:
                raise ValidationError({'amount': "Loan interest amount must be greater than zero."})
        elif self.transaction_type == self.TransactionType.INITIAL_DEPOSIT:
            if not self.from_member_account:
                raise ValidationError("Initial deposit must have from_member_account")

            if not self.to_sjp2_account:
                raise ValidationError("Initial deposit must have to_sjp2_account")

            if self.amount <= 0:
                raise ValidationError("Initial deposit amount must be positive")

        # -----------------------------
        # Call parent clean for any additional validations
        # -----------------------------
        super().clean()


class DailyOperation(ActiveAccountMixin, models.Model):
    class OperationType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        TRANSFER = 'transfer', 'Transfer'
        PENALTY = 'penalty', 'Penalty'

    operation_type = models.CharField(max_length=20, choices=OperationType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    description = models.TextField(blank=True)

    member_account = models.ForeignKey('accounts.MemberAccount',  on_delete=models.SET_NULL,
        null=True, blank=True, related_name='daily_operations' )
    source_account = models.ForeignKey('accounts.MemberAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='operations_as_source'  )
    destination_account = models.ForeignKey('accounts.MemberAccount',   on_delete=models.SET_NULL,  null=True, blank=True,
        related_name='operations_as_destination' )
    related_due = models.ForeignKey('DepositDueTransaction', on_delete=models.SET_NULL, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.operation_type} {self.amount} on {self.timestamp:%Y-%m-%d}"

    # -----------------------------
    # Validation
    # -----------------------------
    def clean(self):
        # Ensure all involved accounts are active
        self.check_active_accounts()

        if self.operation_type == self.OperationType.TRANSFER:
            if not self.source_account or not self.destination_account:
                raise ValidationError("Transfer requires source and destination accounts.")
        if self.operation_type in {self.OperationType.DEPOSIT, self.OperationType.WITHDRAWAL, self.OperationType.PENALTY}:
            if not self.member_account:
                raise ValidationError("This operation requires a member account.")

    # -----------------------------
    # Save (Immutable + Ledger)
    # -----------------------------
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("DailyOperation entries are immutable and cannot be edited.")

        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)
            self._create_ledger_entry()

    # -----------------------------
    # Ledger Writing
    # -----------------------------
    def _create_ledger_entry(self):
        from ledger.services import LedgerService
        reference = f"DailyOperation ID {self.pk}"

        if self.operation_type == self.OperationType.DEPOSIT:
            LedgerService.create_statement(
                account=self.member_account,
                transaction_type='deposit',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference
            )

        elif self.operation_type == self.OperationType.WITHDRAWAL:
            LedgerService.create_statement(
                account=self.member_account,
                transaction_type='withdrawal',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )

        elif self.operation_type == self.OperationType.TRANSFER:
            LedgerService.create_statement(
                account=self.source_account,
                transaction_type='transfer_out',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )
            LedgerService.create_statement(
                account=self.destination_account,
                transaction_type='transfer_in',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference
            )

        elif self.operation_type == self.OperationType.PENALTY:
            LedgerService.create_statement(
                account=self.member_account,
                transaction_type='penalty',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )
from decimal import Decimal, ROUND_HALF_UP
import logging

from django.db import transaction
from django.core.exceptions import ValidationError

from ledger.services import LedgerService
from accounts.models import SJP2_Account, MemberAccount, IncomeSource, ExpensePurpose
from .models import (SJP2Transaction, DepositDueTransaction, DepositTransaction,
    WithdrawalTransaction, TransferTransaction)

logger = logging.getLogger(__name__)
from decimal import Decimal, ROUND_HALF_UP
import logging



logger = logging.getLogger(__name__)

class DepositDueTransactionService:
    FLAT_PENALTY_PER_MONTH = Decimal("500.00")
    UNDERPAYMENT_PENALTY_RATE = Decimal("0.01")
    TWO_PLACES = Decimal('0.01')

    @staticmethod
    def calculate_months_delay(due_date, paid_on) -> int:
        if not due_date or not paid_on or paid_on <= due_date:
            return 0
        return (paid_on.year - due_date.year) * 12 + (paid_on.month - due_date.month)

    @classmethod
    def calculate_transaction(cls, txn: DepositDueTransaction):
        delay = cls.calculate_months_delay(txn.due_date, txn.paid_on)
        shares = Decimal(txn.account.shares or 0)
        delay = Decimal(delay)
        flat_penalty = (cls.FLAT_PENALTY_PER_MONTH * shares * delay
                        if delay > 0 else Decimal("0.00"))

        unpaid = max(txn.amount_due - txn.amount_paid, Decimal("0.00"))
        percent_penalty = unpaid * cls.UNDERPAYMENT_PENALTY_RATE * delay
        flat_penalty = flat_penalty.quantize(cls.TWO_PLACES, ROUND_HALF_UP)
        percent_penalty = percent_penalty.quantize(cls.TWO_PLACES, ROUND_HALF_UP)
        total = (flat_penalty + percent_penalty).quantize(cls.TWO_PLACES, ROUND_HALF_UP)

        txn.delay_time = delay
        txn.flat_penalty = flat_penalty
        txn.percent_penalty = percent_penalty
        txn.penalty_unpaid = total
        txn.is_paid = txn.amount_paid >= (txn.amount_due + total)

        return flat_penalty, percent_penalty

    @staticmethod
    def log_penalty_transaction(from_member, to_system, amount, tx_type, description, reference_transaction):
        """
        Log a penalty transaction if it doesn't already exist.
        Idempotent: avoids duplicate SJP2Transactions.
        """
        if amount <= 0:
            return

        exists = SJP2Transaction.objects.filter(
            from_member_account=from_member,
            to_sjp2_account=to_system,
            transaction_type=tx_type,
            reference_transaction=reference_transaction        ).exists()

        if not exists:
            SJP2Transaction.objects.create(
                from_member_account=from_member,
                to_sjp2_account=to_system,
                amount=amount,
                transaction_type=tx_type,
                description=description,
                reference_transaction=reference_transaction  )

    @classmethod
    @transaction.atomic
    def calculate_and_save(cls, txn: DepositDueTransaction):
        """
        Alias for apply_penalties. Calculates penalties, saves transaction,
        and transfers penalties to the system account.
        """
        logger.info(f"[calculate_and_save] Processing transaction ID {txn.id}")
        return cls.apply_penalties(txn)

    @classmethod
    @transaction.atomic
    def apply_penalties(cls, txn: DepositDueTransaction):
        """
        Calculates penalties and transfers them from member account to system account.
        Idempotent: skips if penalties already applied.
        """
        # Prevent double application
        if txn.penalty_unpaid > 0 and getattr(txn, 'penalty_applied', False):
            logger.info(f"[apply_penalties] Penalties already applied for transaction {txn.id}")
            return

        flat, percent = cls.calculate_transaction(txn)
        total = flat + percent
        txn.save()

        if total <= 0:
            return

        member = txn.account
        system = SJP2_Account.get_main_account()

        if member.balance < total:
            raise ValidationError("Insufficient balance to cover penalties.")

        # Update balances
        member.balance -= total
        member.save(update_fields=["balance"])

        system.balance += total
        system.total_penalized_amount += total
        system.save(update_fields=["balance", "total_penalized_amount"])

        # Log penalty transactions
        cls.log_penalty_transaction(
            from_member=member,
            to_system=system,
            amount=flat,
            tx_type=SJP2Transaction.TransactionType.Penality_Late_deposit,
            description=f"Late payment penalty for due {txn.due_date}",
            reference_transaction=txn )

        cls.log_penalty_transaction(
            from_member=member,
            to_system=system,
            amount=percent,
            tx_type=SJP2Transaction.TransactionType.Penality_Underpay_deposit,
            description=f"Underpayment penalty for due {txn.due_date}",
            reference_transaction=txn   )

        # Mark penalties as applied to avoid double application
        txn.penalty_applied = True
        txn.save(update_fields=["penalty_applied"])

class WithdrawalTransactionService:
    WITHDRAWAL_LIMIT = Decimal("100000.00")

    @classmethod
    @transaction.atomic
    def process(cls, txn: WithdrawalTransaction):
        account = txn.account

        if txn.amount <= 0:
            raise ValidationError("Withdrawal amount must be positive.")
        if txn.amount > cls.WITHDRAWAL_LIMIT:
            raise ValidationError("Withdrawal limit exceeded.")
        if account.balance < txn.amount:
            raise ValidationError("Insufficient balance.")

        account.balance -= txn.amount
        account.save(update_fields=["balance"])
        txn.save()

        system = SJP2_Account.get_main_account()

        LedgerService.create_statement(
            account=account,
            transaction_type="withdrawal",
            debit=txn.amount,
            credit=Decimal('0.00'),
            reference=f"Withdrawal:{txn.id}"
        )
        LedgerService.create_statement(
            account=system,
            transaction_type="system_withdrawal",
            debit=Decimal('0.00'),
            credit=txn.amount,
            reference=f"Withdrawal:{txn.id}"
        )

        return txn
class TransferTransactionService:

    @classmethod
    @transaction.atomic
    def process(cls, txn: TransferTransaction):
        src = txn.source_account
        dst = txn.destination_account

        if src == dst:
            raise ValidationError("Cannot transfer to same account.")
        if txn.amount <= 0:
            raise ValidationError("Transfer amount must be positive.")
        if src.balance < txn.amount:
            raise ValidationError("Insufficient balance.")

        src.balance -= txn.amount
        dst.balance += txn.amount
        src.save(update_fields=["balance"])
        dst.save(update_fields=["balance"])
        txn.save()

        LedgerService.create_statement(
            account=src,
            transaction_type="transfer_out",
            debit=txn.amount,
            credit=Decimal('0.00'),
            reference=f"Transfer:{txn.id}"
        )
        LedgerService.create_statement(
            account=dst,
            transaction_type="transfer_in",
            debit=Decimal('0.00'),
            credit=txn.amount,
            reference=f"Transfer:{txn.id}"
        )

        return txn
class SJP2TransactionService:

    @classmethod
    @transaction.atomic
    def external_income(cls, to_account, amount, source: IncomeSource, description=""):
        if amount <= 0:
            raise ValidationError("Amount must be positive.")

        to_account.balance += amount
        to_account.save(update_fields=["balance"])

        txn = SJP2Transaction.objects.create(
            to_sjp2_account=to_account,
            income_source=source,
            transaction_type=SJP2Transaction.TransactionType.External_Income,
            amount=amount,
            description=description
        )

        LedgerService.create_statement(
            account=to_account,
            transaction_type="external_income",
            debit=Decimal('0.00'),
            credit=amount,
            reference=f"SJP2:{txn.id}"
        )

        return txn

    @classmethod
    @transaction.atomic
    def expense(cls, from_account, amount, purpose: ExpensePurpose, description=""):
        if amount <= 0:
            raise ValidationError("Amount must be positive.")
        if from_account.balance < amount:
            raise ValidationError("Insufficient balance.")

        from_account.balance -= amount
        from_account.save(update_fields=["balance"])

        txn = SJP2Transaction.objects.create(
            from_sjp2_account=from_account,
            expense_purpose=purpose,
            transaction_type=SJP2Transaction.TransactionType.Expense,
            amount=amount,
            description=description
        )

        LedgerService.create_statement(
            account=from_account,
            transaction_type="expense",
            debit=amount,
            credit=Decimal('0.00'),
            reference=f"SJP2:{txn.id}"
        )




##Model
class DailyOperation(ActiveAccountMixin, models.Model):
    class OperationType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAWAL = 'withdrawal', 'Withdrawal'
        TRANSFER = 'transfer', 'Transfer'
        PENALTY = 'penalty', 'Penalty'

    operation_type = models.CharField(max_length=20, choices=OperationType.choices)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    timestamp = models.DateTimeField(default=timezone.now, db_index=True)
    description = models.TextField(blank=True)

    member_account = models.ForeignKey('accounts.MemberAccount',  on_delete=models.SET_NULL,
        null=True, blank=True, related_name='daily_operations' )
    source_account = models.ForeignKey('accounts.MemberAccount', on_delete=models.SET_NULL, null=True, blank=True,
        related_name='operations_as_source'  )
    destination_account = models.ForeignKey('accounts.MemberAccount',   on_delete=models.SET_NULL,  null=True, blank=True,
        related_name='operations_as_destination' )
    related_due = models.ForeignKey('DepositDueTransaction', on_delete=models.SET_NULL, null=True, blank=True)
    balance_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.operation_type} {self.amount} on {self.timestamp:%Y-%m-%d}"

    # -----------------------------
    # Validation
    # -----------------------------
    def clean(self):
        # Ensure all involved accounts are active
        self.check_active_accounts()

        if self.operation_type == self.OperationType.TRANSFER:
            if not self.source_account or not self.destination_account:
                raise ValidationError("Transfer requires source and destination accounts.")
        if self.operation_type in {self.OperationType.DEPOSIT, self.OperationType.WITHDRAWAL, self.OperationType.PENALTY}:
            if not self.member_account:
                raise ValidationError("This operation requires a member account.")

    # -----------------------------
    # Save (Immutable + Ledger)
    # -----------------------------
    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("DailyOperation entries are immutable and cannot be edited.")

        self.full_clean()

        with transaction.atomic():
            super().save(*args, **kwargs)
            self._create_ledger_entry()

    # -----------------------------
    # Ledger Writing
    # -----------------------------
    def _create_ledger_entry(self):
        from ledger.services import LedgerService
        reference = f"DailyOperation ID {self.pk}"

        if self.operation_type == self.OperationType.DEPOSIT:
            LedgerService.create_statement(
                account=self.member_account,
                transaction_type='deposit',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference
            )

        elif self.operation_type == self.OperationType.WITHDRAWAL:
            LedgerService.create_statement(
                account=self.member_account,
                transaction_type='withdrawal',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )

        elif self.operation_type == self.OperationType.TRANSFER:
            LedgerService.create_statement(
                account=self.source_account,
                transaction_type='transfer_out',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )
            LedgerService.create_statement(
                account=self.destination_account,
                transaction_type='transfer_in',
                debit=Decimal('0.00'),
                credit=self.amount,
                reference=reference
            )

        elif self.operation_type == self.OperationType.PENALTY:
            LedgerService.create_statement(
                account=self.member_account,
                transaction_type='penalty',
                debit=self.amount,
                credit=Decimal('0.00'),
                reference=reference
            )


see
my
deposit
model


# -----------------------------
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
        return account.status_type in self.SUSPEND_STATUSES


# ##CREATE LEDEGER DEPOSIT HERE??, PENALITIES LEDGER
# Deposit Due Transaction
# -----------------------------
class DepositDueTransaction(PenaltyMixin, ActiveAccountMixin, BaseTransaction):
    account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
                                related_name='deposit_due_transactions', null=True, blank=True, )
    due_date = models.DateField()
    amount_due = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_on = models.DateField(null=True, blank=True)
    receipt_ref_no = models.CharField(max_length=12, blank=True, null=True)
    is_paid = models.BooleanField(default=False)
    delay_time = models.PositiveIntegerField(default=0)

    BASE_AMOUNT_PER_SHARE = Decimal('5000.00')

    def clean(self):
        """
        Validation for date logic:
        - Allow early payments (paid_on before due_date).
        - If paid_on < due_date, mark delay_time = 0 (no penalty).
        - Ensure both dates are valid if provided.
        """
        super().clean()

        if not self.due_date:
            raise ValidationError({'due_date': "A due date must be specified."})

        if self.paid_on:
            # Early payment → no penalty
            if self.paid_on < self.due_date:
                self.delay_time = 0
            else:
                # Normal delay calculation (difference in months)
                self.delay_time = ((self.paid_on.year - self.due_date.year) * 12
                                   + (self.paid_on.month - self.due_date.month))

    def save(self, *args, **kwargs):
        # Run clean() to apply date logic
        self.full_clean()

        # Auto-calculate amount_due if not set
        if not self.amount_due or self.amount_due == Decimal('0.00'):
            shares = self.account.shares or 0
            self.amount_due = shares * self.BASE_AMOUNT_PER_SHARE

        super().save(*args, **kwargs)

    @property
    def amount_paid(self):
        return self.amount

    def process_and_save(self):
        from transact1_regular_deposit.services import DepositDueTransactionService
        DepositDueTransactionService.calculate_and_save(self)


class DepositTransaction(ActiveAccountMixin, BaseTransaction):
    deposit_due = models.ForeignKey('DepositDueTransaction', null=True, blank=True, on_delete=models.SET_NULL,
                                    related_name='deposit_transactions')
    account = models.ForeignKey('accounts.MemberAccount', on_delete=models.CASCADE,
                                related_name='deposit_transactions', editable=False, null=True)

    class Meta(BaseTransaction.Meta):
        verbose_name = "Deposit Transaction"
        verbose_name_plural = "Deposit Transactions"

    def clean(self):
        super().clean()
        self.check_active_accounts()
        if self.amount <= 0:
            raise ValidationError({'amount': "Deposit amount must be positive."})
        if self.deposit_due and self.deposit_due.account != self.account:
            raise ValidationError("DepositDue account mismatch.")

    def save(self, *args, **kwargs):
        self.full_clean()
        is_new = self.pk is None
        super().save(*args, **kwargs),


class DepositDueTransactionService:
    FLAT_PENALTY_PER_MONTH = Decimal("500.00")
    UNDERPAYMENT_PENALTY_RATE = Decimal("0.01")
    TWO_PLACES = Decimal('0.01')

    @staticmethod
    def calculate_months_delay(due_date, paid_on) -> int:
        if not due_date or not paid_on or paid_on <= due_date:
            return 0
        return (paid_on.year - due_date.year) * 12 + (paid_on.month - due_date.month)

    @classmethod
    def calculate_transaction(cls, txn: DepositDueTransaction):
        delay = cls.calculate_months_delay(txn.due_date, txn.paid_on)
        shares = Decimal(txn.account.shares or 0)
        delay = Decimal(delay)

        flat_penalty = (cls.FLAT_PENALTY_PER_MONTH * shares * delay) if delay > 0 else Decimal("0.00")
        unpaid = max(txn.amount_due - txn.amount_paid, Decimal("0.00"))
        percent_penalty = unpaid * cls.UNDERPAYMENT_PENALTY_RATE * delay

        flat_penalty = flat_penalty.quantize(cls.TWO_PLACES, ROUND_HALF_UP)
        percent_penalty = percent_penalty.quantize(cls.TWO_PLACES, ROUND_HALF_UP)

        txn.delay_time = delay
        txn.flat_penalty = flat_penalty
        txn.percent_penalty = percent_penalty
        txn.penalty_unpaid = (flat_penalty + percent_penalty).quantize(cls.TWO_PLACES, ROUND_HALF_UP)
        txn.is_paid = txn.amount_paid >= (txn.amount_due + txn.penalty_unpaid)

        return flat_penalty, percent_penalty

    @classmethod
    @transaction.atomic
    def calculate_and_save(cls, txn: DepositDueTransaction):
        """Wrapper to calculate and apply penalties safely"""
        logger.info(f"[calculate_and_save] Processing transaction ID {txn.id}")
        return cls.apply_penalties(txn)  # Call original method consistently

    @classmethod
    def apply_penalties(cls, deposit_due_txn):
        # Assuming `deposit_due_txn` is an instance of DepositDueTransaction
        penalty_amount = cls.calculate_penalty(deposit_due_txn)

        # Ensure there is a valid penalty to apply
        if penalty_amount > 0:
            # Determine the penalty type (based on logic or attributes of deposit_due_txn)
            penalty_type = cls.get_penalty_type(deposit_due_txn)

            # Now create the appropriate SJP2Transaction based on the type
            if penalty_type:
                system = SJP2_Account.get_main_account()
                SJP2Transaction.objects.create(
                    from_member_account=deposit_due_txn.account,
                    to_sjp2_account=system,
                    # Assuming you want to use the main SJP2 account
                    amount=penalty_amount,
                    transaction_type=penalty_type,  # Ensure correct enum is used here
                    reference_transaction=deposit_due_txn,
                    description=f"Penalty applied for DepositDueTransaction ID {deposit_due_txn.pk}"
                )

    @staticmethod
    def calculate_penalty(deposit_due_txn):
        if deposit_due_txn.delay_time > 0:
            penalty_rate = Decimal('0.05')
            penalty = deposit_due_txn.amount_due * penalty_rate

            return penalty.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

        return Decimal('0.00')

    @staticmethod
    def get_penalty_type(deposit_due_txn):
        """Determine which penalty type should be applied based on the transaction details."""
        # Example: based on the delay, we select the appropriate penalty type
        if deposit_due_txn.delay_time > 0:
            if deposit_due_txn.amount_due < deposit_due_txn.amount_paid:
                return SJP2Transaction.TransactionType.Penality_Underpay_deposit  # Underpayment penalty
            else:
                return SJP2Transaction.TransactionType.Penality_Late_deposit  # Late payment penalty
        return None  # No penalty if no delay or other conditions,


# -----------------------------
class TransactionCreateMixin(LoginRequiredMixin, CreateView):
    template_name = 'transact1_regular_deposit/transaction_form.html'
    title = ''
    button_label = 'Submit'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update({'account': self.request.user.account})
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({
            'title': self.title,
            'button_label': self.button_label,
        })
        return context


# -----------------------------
# 🔹 Deposit View
# -----------------------------
# -----------------------------
# 🔹 Deposit View
# -----------------------------
class DepositCreateView(TransactionCreateMixin):
    model = DepositTransaction
    form_class = DepositForm
    title = 'Make a Deposit'
    button_label = 'Deposit Funds'
    success_url = reverse_lazy('transact1_regular_deposit:transaction-success')

    def form_valid(self, form):
        # 1️⃣ Save txn first to generate primary key
        txn = form.save(commit=True)  # commit=True ensures it has PK

        account = txn.account
        amount = txn.amount

        try:
            with transaction.atomic():
                # 🔹 Record deposit in ledger (updates balance)
                LedgerService.create_statement(
                    account=account,
                    transaction_type="deposit",
                    debit=Decimal('0.00'),
                    credit=amount,
                    reference=f"Deposit:{txn.id}")

                # 🔹 Update last activity safely
                account.update_activity()
                account.principal += amount
                # 🔹 Update duration safely
                account.duration = account.get_total_months_since_opened()

                # 🔹 Apply any deposit penalties
                DepositDueTransactionService.apply_penalties(txn)  # txn has PK now

        except ValidationError as e:
            messages.error(self.request, str(e))
            return self.form_invalid(form)

        messages.success(self.request, "Deposit successful.")
        return super().form_valid(form)



