import logging

from dateutil.relativedelta import relativedelta

logger = logging.getLogger(__name__)
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from django.core.exceptions import ValidationError
from accounts.models import MemberAccount, SJP2_Account,AccountStatusHistory,IncomeSource, ExpensePurpose
from ledger.services import LedgerService
from django.db import transaction
from django.utils import timezone
from ledger.models import AccountStatement

class DepositDueTransactionService:
    FLAT_PENALTY_PER_MONTH = Decimal("500.00")
    UNDERPAYMENT_PENALTY_RATE = Decimal("0.01")
    TWO_PLACES = Decimal("0.01")
    DUE_DAY = 10

    from datetime import date

    @staticmethod
    def due_date_for_month(year, month):
        return date(year, month, 10)  ##10th each month

    @classmethod
    def generate_due_records(cls, account):
        from .models import DepositDueTransaction
        today = timezone.now().date()

        first_due = date(
            account.created_on.year,
            account.created_on.month,
            cls.DUE_DAY
        )

        if account.created_on.day > cls.DUE_DAY:
            first_due += relativedelta(months=1)

        current = first_due

        while current <= today:
            from .models import DepositDueTransaction
            DepositDueTransaction.objects.get_or_create(
                account=account,
                due_date=current,
                defaults={
                    "monthly_due":
                        (account.shares or 0)
                        * DepositDueTransaction.BASE_AMOUNT_PER_SHARE
                }  )

            current += relativedelta(months=1)



    @staticmethod
    def get_oldest_unpaid_due(account):
        from .models import DepositDueTransaction
        return (DepositDueTransaction.objects
            .filter(
                account=account,
                is_paid=False ).order_by("due_date").first())

    @staticmethod   ##For a fixed due day (10th),
    def calculate_months_delay(due_date, paid_on):
        if not due_date or not paid_on or paid_on <= due_date:
            return 0
        months = ((paid_on.year - due_date.year) * 12
                + (paid_on.month - due_date.month))
        return max(months, 1)



    @classmethod
    def calculate_transaction(cls, txn):
        """
        Calculate penalties and update the linked DepositDueTransaction.each DepositDueTransaction represents one month's due
        """
        due = txn.deposit_due

        if not due:
            raise ValidationError("Deposit transaction must be linked to a due record.")

        delay_months = cls.calculate_months_delay(
            due.due_date,
            txn.paid_on
        )

        due.delay_time = delay_months

        shares = Decimal(due.account.shares or 0)

        # -------------------------
        # Late-payment penalty
        # -------------------------
        flat_penalty = Decimal("0.00")

        if delay_months > 0:
            flat_penalty = sum(
                cls.FLAT_PENALTY_PER_MONTH * Decimal(month) * shares
                for month in range(1, delay_months + 1))

        # -------------------------
        # Underpayment penalty
        # -------------------------
        expected_amount = due.monthly_due
        unpaid_amount = max(expected_amount - txn.amount, Decimal("0.00"))
        percent_penalty = (unpaid_amount * cls.UNDERPAYMENT_PENALTY_RATE   * Decimal(delay_months)     )
        # -------------------------
        # Round values
        # -------------------------
        due.flat_penalty = flat_penalty.quantize(  cls.TWO_PLACES,  ROUND_HALF_UP )
        due.percent_penalty = percent_penalty.quantize( cls.TWO_PLACES, ROUND_HALF_UP )
        due.penalty_unpaid = ( due.flat_penalty   + due.percent_penalty  ).quantize(  cls.TWO_PLACES, ROUND_HALF_UP      )
        total_required = expected_amount + due.penalty_unpaid
        due.is_paid = txn.amount >= total_required

        due.save(  update_fields=[
                "delay_time",
                "flat_penalty",
                "percent_penalty",
                "penalty_unpaid",
                "is_paid",
            ]
        )

        return due.penalty_unpaid, due.percent_penalty
    @classmethod
    @transaction.atomic
    def calculate_and_save(cls, txn):
        """
        Calculate penalties and apply them once.
        """
        logger.info(f"[calculate_and_save] Processing transaction ID {txn.id}")

        cls.calculate_transaction(txn)

        # FIX: Apply penalties using DepositDueTransaction (not DepositTransaction)
        cls.apply_penalties(txn.deposit_due)

        return txn

    @classmethod
    @transaction.atomic
    def apply_penalties(cls, deposit_due_txn):
        """
        Create ledger entries for penalties.
        """
        from ledger.services import LedgerService
        from ledger.models import AccountStatement
        from .models import SJP2Transaction
        from accounts.models import SJP2_Account

        # Lock row to avoid race conditions
        deposit_due_txn = type(deposit_due_txn).objects.select_for_update().get(pk=deposit_due_txn.pk)

        if deposit_due_txn.penalty_applied:
            return

        member_account = deposit_due_txn.account
        system_account = SJP2_Account.get_main_account()

        # -------------------------
        # UNDERPAYMENT PENALTY
        # -------------------------
        if deposit_due_txn.percent_penalty > 0:

            SJP2Transaction.objects.create(
                from_member_account=member_account,
                to_sjp2_account=system_account,
                amount=deposit_due_txn.percent_penalty,
                transaction_type=SJP2Transaction.TransactionType.Penality_Underpay_deposit,
                reference_transaction=deposit_due_txn,
                description=f"Underpayment penalty for DepositDueTransaction {deposit_due_txn.id}"
            )

        # -------------------------
        # LATE PENALTY
        # -------------------------
        if deposit_due_txn.flat_penalty > 0:


            SJP2Transaction.objects.create(
                from_member_account=member_account,
                to_sjp2_account=system_account,
                amount=deposit_due_txn.flat_penalty,
                transaction_type=SJP2Transaction.TransactionType.Penality_Late_deposit,
                reference_transaction=deposit_due_txn,
                description=f"Late penalty for DepositDueTransaction {deposit_due_txn.id}"
            )

        # Mark penalty applied
        deposit_due_txn.penalty_applied = True
        deposit_due_txn.save(update_fields=["penalty_applied"])

    @classmethod
    @transaction.atomic
    def process(cls, txn):
        """
        Process deposit transaction and update account balance.
        """
        from ledger.services import LedgerService
        from ledger.models import AccountStatement

        account = txn.account
        amount = txn.amount

        if amount <= 0:
            raise ValidationError("Deposit amount must be positive.")

        # Lock account row
        account = type(account).objects.select_for_update().get(pk=account.pk)

        account.principal += amount
        account.update_activity()

        account.save(update_fields=["principal", "last_activity_on"])

        txn.save()

        # Ledger entry for deposit
        LedgerService.create_statement(
            account=account,
            transaction_type=AccountStatement.TransactionType.DEPOSIT,
            debit=Decimal("0.00"),
            credit=amount,
            reference=f"Deposit:{txn.id}"
        )

        # Calculate penalties
        cls.calculate_and_save(txn)

        return txn

 #if txn.deposit_due:
         #  cls.calculate_and_save(txn.deposit_due)


class WithdrawalTransactionService:

    WITHDRAWAL_PERCENTAGE = Decimal("0.25")  # 25%

    @classmethod
    @transaction.atomic
    def process(cls, txn):
        from decimal import Decimal

        account = txn.account

        # -----------------------------
        # Basic validations
        # -----------------------------
        if txn.amount <= 0:
            raise ValidationError("Withdrawal amount must be positive.")

        if account.balance <= 0:
            raise ValidationError("No balace available for withdrawal.")

        # -----------------------------
        # 25% principal rule
        # -----------------------------
        max_withdrawable = account.principal * cls.WITHDRAWAL_PERCENTAGE
        if txn.amount > max_withdrawable:
            raise ValidationError(
                f"Withdrawal exceeds 25% of principal. "
                f"Maximum allowed: {max_withdrawable}"
            )

        # -----------------------------
        # Balance check
        # -----------------------------
        if account.balance < txn.amount:
            raise ValidationError("Insufficient balance.")

        # -----------------------------
        # Reduce principal , unacceptible.
        # -----------------------------
        #if txn.amount > account.principal:
         #   raise ValidationError("Withdrawal exceeds available principal.")

        #account.principal -= txn.amount
        #account.save(update_fields=["principal"])

        # -----------------------------
        # Save transaction
        # -----------------------------
        txn.save()

        # -----------------------------
        # Ledger entries
        # -----------------------------
        LedgerService.create_statement(
            account=account,
            transaction_type="withdrawal",
            debit=txn.amount,
            credit=Decimal('0.00'),
            reference=f"Withdrawal:{txn.id}"
        )

        system_account = SJP2_Account.get_main_account()
        LedgerService.create_statement(
            account=system_account,
            transaction_type="system_withdrawal",
            debit=Decimal('0.00'),
            credit=txn.amount,
            reference=f"System Withdrawal:{txn.id}"
        )

        return txn


class TransferTransactionService:

    @classmethod
    @transaction.atomic
    def process(cls, txn):
        # 🔴 Local import to avoid circular import
        from .models import TransferTransaction
        src = txn.source_account
        dst = txn.destination_account

        if src == dst:
            raise ValidationError("Cannot transfer to same account.")
        if txn.amount <= 0:
            raise ValidationError("Transfer amount must be positive.")
        if src.balance < txn.amount:
            raise ValidationError("Insufficient balance.")

        # Save the transaction first (to ensure its ID is set)
        txn.save()

        # Record the transfer in the ledger
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
        from .models import SJP2Transaction
        txn = SJP2Transaction.objects.create(
            to_sjp2_account=to_account,
            income_source=source,
            transaction_type=SJP2Transaction.TransactionType.External_Income,
            amount=amount,
            description=description)

        ledger_stmt = LedgerService.create_statement(
            account=to_account,
            transaction_type="external_income",
            debit=Decimal('0.00'),
            credit=amount,
            reference=f"SJP2:{txn.id}")
        return txn

    @classmethod
    @transaction.atomic
    def expense(cls, from_sjp2_account, amount, purpose: ExpensePurpose, description=""):##They at input form
        if amount <= 0:
            raise ValidationError("Amount must be positive.")

        from .models import SJP2Transaction

        return SJP2Transaction.objects.create(
            from_sjp2_account=from_sjp2_account,
            expense_purpose=purpose,
            transaction_type=SJP2Transaction.TransactionType.Expense,
            amount=amount,
            description=description  )




class LegacyAccountUpdateService:

    @staticmethod
    @transaction.atomic
    def update_account(data):

        account = data["account_obj"]

        # ----------------------------
        # SAFETY CHECK
        # ----------------------------
        if account is None:
            raise ValueError("Invalid account")

        # ----------------------------
        # LOCK ACCOUNT
        # ----------------------------
        account = (
            account.__class__.objects
            .select_for_update()
            .get(pk=account.pk)
        )

        # ----------------------------
        # NEW VALUES
        # ----------------------------
        new_balance = Decimal(data["balance"])
        new_principal = Decimal(data["principal"])
        new_shares = Decimal(data["shares"])
        opened_on = data["opened_on"]

        # ----------------------------
        # CURRENT LEDGER BALANCE
        # ----------------------------
        last_stmt = (
            AccountStatement.objects
            .filter(account=account)
            .order_by("-date", "-id")
            .first()
        )

        current_ledger_balance = (
            last_stmt.balance_after
            if last_stmt
            else Decimal("0.00")
        )

        # ----------------------------
        # CALCULATE DIFFERENCE
        # ----------------------------
        delta = new_balance - current_ledger_balance

        # ----------------------------
        # UPDATE ACCOUNT
        # ----------------------------
        account.shares = new_shares
        account.principal = new_principal
        account.balance = new_balance
        account.opened_on = opened_on
        account.last_activity_on = timezone.now()

        account.save(
            update_fields=[
                "shares",
                "principal",
                "balance",
                "opened_on",
                "last_activity_on",
            ],
            _from_ledger=True
        )

        # ----------------------------
        # LEGACY ACTIVE MONTHS
        # ----------------------------
        legacy_months = int(
            data.get("legacy_active_months", 0)
        )

        if (
            legacy_months > 0
            and not account.status_history.exists()
        ):

            from datetime import timedelta

            # approximate backdate
            started_date = (
                timezone.now()
                - timedelta(days=legacy_months * 30)
            )

            # create historical ACTIVE status
            AccountStatusHistory.objects.create(
                account=account,
                status_type=MemberAccount.StatusType.ACTIVE,
                started_on=started_date,
                ended_on=None
            )

        # ----------------------------
        # CREATE RECONCILIATION LEDGER ENTRY
        # ----------------------------
        if delta != Decimal("0.00"):

            AccountStatement.objects.create(
                account=account,
                transaction_type="legacy_import",

                debit=(
                    abs(delta)
                    if delta < 0
                    else Decimal("0.00")
                ),

                credit=(
                    delta
                    if delta > 0
                    else Decimal("0.00")
                ),

                balance_after=new_balance,

                reference=(
                    "Legacy account reconciliation import"
                ),
            )

        return account