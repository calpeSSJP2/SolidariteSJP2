
from django.db import models
# transact2_loans/services.py

from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime
import logging

from django.db import transaction, models
from django.core.exceptions import ValidationError

from ledger.services import LedgerService
from ledger.models import AccountStatement
from transact1_regular_deposit.models import SJP2Transaction
from accounts.models import SJP2_Account
from transact2_loans.models import AuditLog

logger = logging.getLogger(__name__)

from django.db import transaction
from decimal import Decimal
from django.core.exceptions import ValidationError

import logging
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class DepositDueTransactionService:

    FLAT_PENALTY_PER_MONTH = Decimal("500.00")
    UNDERPAYMENT_PENALTY_RATE = Decimal("0.01")
    TWO_PLACES = Decimal("0.01")

    # ------------------------------------------------
    # MONTH DELAY CALCULATION
    # ------------------------------------------------
    @staticmethod
    def calculate_months_delay(due_date, paid_on) -> int:
        if not due_date or not paid_on or paid_on <= due_date:
            return 0

        return (paid_on.year - due_date.year) * 12 + (paid_on.month - due_date.month)

    # ------------------------------------------------
    # PENALTY CALCULATION
    # ------------------------------------------------
    @classmethod
    def calculate_transaction(cls, txn):

        delay_months = cls.calculate_months_delay(txn.due_date, txn.paid_on)
        txn.delay_time = delay_months

        shares = Decimal(txn.account.shares or 0)

        flat_penalty = Decimal("0.00")

        for month in range(1, delay_months + 1):
            flat_penalty += cls.FLAT_PENALTY_PER_MONTH * month * shares

        unpaid_amount = max(txn.amount_due - txn.amount_paid, Decimal("0.00"))

        percent_penalty = (
            unpaid_amount
            * cls.UNDERPAYMENT_PENALTY_RATE
            * Decimal(delay_months)
        )

        txn.flat_penalty = flat_penalty.quantize(cls.TWO_PLACES, ROUND_HALF_UP)

        txn.percent_penalty = percent_penalty.quantize(
            cls.TWO_PLACES, ROUND_HALF_UP
        )

        txn.penalty_unpaid = (
            txn.flat_penalty + txn.percent_penalty
        ).quantize(cls.TWO_PLACES, ROUND_HALF_UP)

        txn.is_paid = txn.amount_paid >= (
            txn.amount_due + txn.penalty_unpaid
        )

        return txn.penalty_unpaid, txn.percent_penalty

    # ------------------------------------------------
    # CALCULATE + SAVE
    # ------------------------------------------------
    @classmethod
    @transaction.atomic
    def calculate_and_save(cls, txn):

        logger.info(f"Processing penalty calculation for txn {txn.id}")

        cls.calculate_transaction(txn)

        txn.save(
            update_fields=[
                "delay_time",
                "flat_penalty",
                "percent_penalty",
                "penalty_unpaid",
                "is_paid",
            ]
        )

        cls.apply_penalties(txn)

        return txn

    # ------------------------------------------------
    # APPLY PENALTIES
    # ------------------------------------------------
    @classmethod
    @transaction.atomic
    def apply_penalties(cls, deposit_due_txn):

        from ledger.services import LedgerService
        from ledger.models import AccountStatement
        from transact1_regular_deposit.models import SJP2Transaction
        from accounts.models import SJP2_Account

        # 🔒 LOCK transaction row
        deposit_due_txn = type(deposit_due_txn).objects.select_for_update().get(
            pk=deposit_due_txn.pk
        )

        # HARD STOP
        if deposit_due_txn.penalty_applied:
            return

        member_account = deposit_due_txn.account
        system_account = SJP2_Account.get_main_account()

        # -------------------------
        # UNDERPAYMENT PENALTY
        # -------------------------
        if deposit_due_txn.percent_penalty > 0:

            LedgerService.create_statement(
                account=member_account,
                transaction_type=AccountStatement.TransactionType.PENALTY_UNDERPAYMENT,
                debit=deposit_due_txn.percent_penalty,
                credit=Decimal("0.00"),
                reference=f"DDT-{deposit_due_txn.id}-UNDERPAYMENT",
            )

            SJP2Transaction.objects.create(
                from_member_account=member_account,
                to_sjp2_account=system_account,
                amount=deposit_due_txn.percent_penalty,
                transaction_type=SJP2Transaction.TransactionType.Penality_Underpay_deposit,
                reference_transaction=deposit_due_txn,
                description=f"Underpayment penalty for DepositDueTransaction {deposit_due_txn.id}",
            )

        # -------------------------
        # LATE PENALTY
        # -------------------------
        if deposit_due_txn.flat_penalty > 0:

            LedgerService.create_statement(
                account=member_account,
                transaction_type=AccountStatement.TransactionType.PENALTY_LATE_PAYMENT,
                debit=deposit_due_txn.flat_penalty,
                credit=Decimal("0.00"),
                reference=f"DDT-{deposit_due_txn.id}-LATE",
            )

            SJP2Transaction.objects.create(
                from_member_account=member_account,
                to_sjp2_account=system_account,
                amount=deposit_due_txn.flat_penalty,
                transaction_type=SJP2Transaction.TransactionType.Penality_Late_deposit,
                reference_transaction=deposit_due_txn,
                description=f"Late penalty for DepositDueTransaction {deposit_due_txn.id}",
            )

        deposit_due_txn.penalty_applied = True
        deposit_due_txn.save(update_fields=["penalty_applied"])

    # ------------------------------------------------
    # PENALTY COMPATIBILITY
    # ------------------------------------------------
    @staticmethod
    def calculate_penalty(deposit_due_txn):

        return deposit_due_txn.penalty_unpaid or Decimal("0.00")

    # ------------------------------------------------
    # PENALTY TYPE
    # ------------------------------------------------
    @staticmethod
    def get_penalty_type(deposit_due_txn):

        from transact1_regular_deposit.models import SJP2Transaction

        if deposit_due_txn.delay_time <= 0:
            return None

        if deposit_due_txn.amount_paid < deposit_due_txn.amount_due:
            return SJP2Transaction.TransactionType.Penality_Underpay_deposit

        return SJP2Transaction.TransactionType.Penality_Late_deposit

    # ------------------------------------------------
    # PROCESS TRANSACTION
    # ------------------------------------------------
    @classmethod
    @transaction.atomic
    def process(cls, txn):

        account = txn.account
        amount = txn.amount

        if amount <= 0:
            raise ValidationError("Deposit amount must be positive.")

        # 🔒 LOCK ACCOUNT ROW
        account = type(account).objects.select_for_update().get(pk=account.pk)

        account.principal += amount
        account.update_activity()

        account.save(
            update_fields=["principal", "last_activity_on"])

        txn.save()

        from ledger.services import LedgerService
        from ledger.models import AccountStatement

        LedgerService.create_statement(
            account=account,
            transaction_type=AccountStatement.TransactionType.DEPOSIT,
            debit=Decimal("0.00"),
            credit=amount,
            reference=f"Deposit:{txn.id}",
        )

        # apply penalties
        cls.calculate_and_save(txn)

        return txn

class LoanRequestService1:
    """
    SINGLE source of truth for loan creation.
    Only creates a loan in PENDING state.
    Disbursement (ledger + SJP2 transactions) happens later during approval.
    """

    @classmethod
    @transaction.atomic
    def request_loan(
        cls,
        *,
        account,
        loan_type,
        amount: Decimal,
        term_months: int,
        requested_by
    ):
        # 1️⃣ Validate account is active
        if account.status_type != 'active':
            raise ValidationError("Member account is inactive.")

        # 2️⃣ Validate loan amount does not exceed limit
        if not LoanLimitService.can_request_Member_loan(account, amount):
            raise ValidationError("Loan exceeds allowable limit.")

        # 3️⃣ Create the loan in PENDING state
        from .models import Loan  # lazy import to avoid circular dependencies
        loan = Loan.objects.create(
            account=account,
            loan_type=loan_type,  # from form
            amount=amount,
            term_months=term_months,
            status=Loan.LoanStatus.PENDING,
            created_by=requested_by
        )
        # 4️⃣ Return the loan instance
        return loan



##LoanRequestService is linked to the Loan model by calling
# Loan.objects.create(), which automatically invokes Loan.save() and Loan.clean(),
class LoanPaymentService:
    """
    SINGLE source of truth for loan penalty calculation & application.
    """

    PENALTY_RATE = Decimal('0.02')  # 2% penalty rate
    TWO_PLACES = Decimal('0.01')  # Decimal precision for rounding

    # -----------------------------
    # Helpers
    # -----------------------------
    @staticmethod
    def calculate_months_delay(due_date, paid_on) -> int:
        """Calculate the number of months between the due date and the paid date."""
        if not due_date or not paid_on:
            return 0

        # Convert paid_on to a date (removes time part)
        if isinstance(paid_on, datetime):
            paid_on = paid_on.date()

        # Ensure both due_date and paid_on are datetime.date objects for comparison
        if paid_on <= due_date:
            return 0

        return max((paid_on.year - due_date.year) * 12 +
            (paid_on.month - due_date.month),  1   )

    # -----------------------------
    # Core penalty calculation
    # -----------------------------
    @classmethod
    def calculate_penalty(cls, payment):
        """
        Calculates cumulative penalty based on delayed months.
        """
        delay_months = cls.calculate_months_delay(payment.due_date, payment.paid_on)
        payment.delay_time = delay_months

        if delay_months <= 0:
            return Decimal('0.00')

        monthly_payment = payment.loan.monthly_payment

        total_penalty = Decimal('0.00')
        for month in range(1, delay_months + 1):
            total_penalty += monthly_payment * cls.PENALTY_RATE * Decimal(month)

        return total_penalty.quantize(cls.TWO_PLACES, ROUND_HALF_UP)

    # -----------------------------
    # Apply penalty (idempotent)
    # -----------------------------
    @classmethod
    @transaction.atomic
    def apply_penalty(cls, loan_payment):
        """
        Applies penalties to the ledger & transaction layer.
        This is idempotent and safe to call multiple times.
        """
        if loan_payment.penalty_applied:
            logger.info(f"[LoanPenaltyService] Penalty already applied for payment {loan_payment.id}")
            return Decimal('0.00')

        penalty_amount =cls.calculate_penalty(loan_payment)

        if penalty_amount <= 0:
            return Decimal('0.00')

        # Fetch the system account (where the penalty will be credited)
        system_account = SJP2_Account.get_main_account()
        if not system_account:
            raise ValidationError("Missing system account: 'System Pool'.")

        # Create a transaction for the penalty
        txn = SJP2Transaction.objects.create(
            transaction_type=SJP2Transaction.TransactionType.Penality_Late_Loan,
            from_member_account=loan_payment.loan.account,
            to_sjp2_account=system_account,
            amount=penalty_amount,
            reference_transaction=loan_payment,        )

        reference = f"SJP2Transaction ID {txn.pk}"

        # Create ledger entries to reflect the penalty movement
       # LedgerService.create_statement(
         #   account=loan_payment.loan.account,
         #   transaction_type=AccountStatement.TransactionType.PENALTY_LATE_PAYMENT,
         #   debit=penalty_amount,
         #   credit=Decimal('0.00'),
         #   reference=reference,  )  ##This duplicate , because it is recorded  in ssjp2transaction
        ##Legder for laon Pyment,, it increase balace =credit
       # LedgerService.create_statement(
         #   account=system_account,
         #   transaction_type=AccountStatement.TransactionType.LOAN_PAYMENT,
        #    debit=Decimal('0.00'),
         #   credit=amount,
         #   reference=reference, )

        # Mark penalty as applied to avoid re-applying the same penalty
        loan_payment.penalty_applied = True
        loan_payment.save(update_fields=['penalty_applied'])

        logger.info(f"[LoanPenaltyService] Applied penalty {penalty_amount} for payment {loan_payment.id}")

        return penalty_amount

    # -----------------------------
    # Penalty retrieval (compatibility)
    # -----------------------------
    @staticmethod
    def calculate_total_penalty(loan_payment):
        """Returns the total penalty for compatibility purposes."""
        return loan_payment.penalty_unpaid or Decimal("0.00")

    @staticmethod
    def get_penalty_type(loan_payment):
        """Returns the type of penalty applied based on payment details."""
        from transact1_regular_deposit.models import SJP2Transaction
        if loan_payment.delay_time <= 0:
            return None
        if loan_payment.amount < loan_payment.amount_due:
            return SJP2Transaction.TransactionType.Penality_Underpay_deposit
        return SJP2Transaction.TransactionType.Penality_Late_deposit

    # -----------------------------
    # Process loan repayment (with penalties)
    # -----------------------------
    @classmethod
    @transaction.atomic
    def process_payment(cls, loan_payment):
        if not loan_payment.loan:
            raise ValidationError("Loan must be specified for payment.")

        borrower_account = loan_payment.loan.account

        # 🔐 HARD RULE: ensure no unpaid peer loans block main loan
        LoanRepaymentEligibilityService.ensure_can_repay_loan(borrower_account)

        payment_amount = loan_payment.amount

        # --------------------------
        # Apply penalty
        # --------------------------
        penalty_amount = cls.apply_penalty(loan_payment)
        remaining_amount = max(payment_amount - penalty_amount, Decimal('0.00'))

        # --------------------------
        # Repay peer loans first Remove Because peer loans are already paid via the form.
        # --------------------------
        #repaid_peers, remaining_amount = PeerLoanRepaymentService.repay_borrower_loans(
        #    borrower_account,
        #    remaining_amount,
        #    paid_by_user=loan_payment.received_by        )

        # --------------------------
        # Repay cooperative loan
        # --------------------------
        loan = loan_payment.loan
        payable_remaining = loan.total_payable - loan.total_paid
        loan_repayment_amount = min(remaining_amount, payable_remaining)

        if loan_repayment_amount > 0:
            LedgerService.create_statement(
                account=borrower_account,
                transaction_type=AccountStatement.TransactionType.LOAN_PAYMENT,
                debit=Decimal("0.00"),
                credit=loan_repayment_amount,
                reference=f"Loan ID {loan.pk}",
            )

        remaining_amount -= loan_repayment_amount

        # --------------------------
        # Record any excess as account credit
        # --------------------------
        if remaining_amount > 0:
            LedgerService.create_statement(
                account=borrower_account,
                transaction_type=AccountStatement.TransactionType.EXCESS_PAYMENT,
                debit=Decimal("0.00"),
                credit=remaining_amount,
                reference=f"Loan ID {loan.pk} - excess",
            )

        # --------------------------
        # Update loan status
        # --------------------------
        loan.refresh_status()

        return {
            "penalty": penalty_amount,
           # "peer_repayment": repaid_peers,
            "loan_repayment": loan_repayment_amount,
            "excess": remaining_amount,
        }
# services.py
#class LoanRepaymentEligibilityService:

  #  @staticmethod
  #  def can_repay_loan(member_account) -> bool:
   #     from transact3_lending.models import PeerToPeerLoan
    #    return not PeerToPeerLoan.objects.filter(
    #        borrower=member_account,
     #       is_fully_paid=False ).exists()

    #@staticmethod
    #def ensure_can_repay_loan(member_account):
     #   if not LoanRepaymentEligibilityService.can_repay_loan(member_account):
     #       raise ValidationError(
     #           "Borrower has unpaid peer-to-peer loans."
      #      )

##Process payment, 1.get amount,it goes to account(yours or lender), save these fields,+balance, -laon balance. seconday
##1.Check penality, [[see process in deposit:1st deposit amount, save, 2.check and save penalities
                #SJP2Transaction.objects.create(
               # from_member_account=member_account,
               # to_sjp2_account=system_account,
               # amount=deposit_due_txn.flat_penalty,(Put interest amount)
                #transaction_type=SJP2Transaction.TransactionType.loan interest,
              #  reference_transaction=deposit_due_txn,
              #  description=f"Late penalty for DepositDueTransaction {deposit_due_txn.id}" )
# =====================================================

class LoanLimitService:

    @staticmethod
    def can_request_Member_loan(account, requested_amount):
        from transact2_loans.models import Loan

        principal_balance = account.principal or Decimal('0.00')
        allowed_limit = principal_balance * Decimal('3')

        # ❌➡️✅ RED CROSS: canonical OPEN_STATUSES
        current_loans = Loan.objects.filter(
            account=account,
            status__in=Loan.OPEN_STATUSES
        )

        # exposure-based (ledger-safe)
        total_exposure = sum(
            (loan.amount + loan.interest_amount) for loan in current_loans
        )

        return (total_exposure + requested_amount) <= allowed_limit

    @staticmethod
    def validate_loan_limit(account, amount):
        if not LoanLimitService.can_request_Member_loan(account, amount):
            raise ValidationError(
                "Loan exceeds allowable limit. Request less or negotiate."
            )
##we also need process:Request amount save lanace-amount , save. interest to ssjp2 account save.//We need laonrequsetServices+loanPymentservices
# =====================================================
# Peer Loan Check Service
# =====================================================

class PeerLoanCheckService:

    @staticmethod
    def borrower_has_unpaid_peer_loans(member_account):
        from transact3_lending.models import PeerToPeerLoan
        return PeerToPeerLoan.objects.filter(
            borrower=member_account,
            is_fully_paid=False
        ).exists()

    @staticmethod
    def total_unpaid_peer_loans(member_account):
        from transact3_lending.models import PeerToPeerLoan
        loans = PeerToPeerLoan.objects.filter(
            borrower=member_account,
            is_fully_paid=False
        )
        return sum((loan.amount for loan in loans), Decimal('0.00'))


# =====================================================
# Loan Repayment Eligibility Service
# =====================================================

class LoanRepaymentEligibilityService1:

    @staticmethod
    def can_repay_loan(member_account) -> bool:
        from transact3_lending.models import PeerToPeerLoan
        return not PeerToPeerLoan.objects.filter(
            borrower=member_account,
            is_fully_paid=False
        ).exists()

    @staticmethod
    def ensure_can_repay_loan(member_account):
        if not LoanRepaymentEligibilityService.can_repay_loan(member_account):
            raise ValidationError(
                "You still have unpaid peer-to-peer loans. "
                "Please clear all peer loans before repaying this cooperative loan."
            )

    @staticmethod
    def check_peer_loans_status(member_account):
        from transact3_lending.models import PeerToPeerLoan
        return list(
            PeerToPeerLoan.objects.filter(
                borrower=member_account,
                is_fully_paid=False
            ).values('id', 'amount', 'lender__member_id')
        )


# =====================================================

class LoanRepaymentEligibilityService: #We are using the same form

    @staticmethod
    def can_repay_loan(member_account) -> bool:
        # OLD LOGIC REMOVED
        return True

    @staticmethod
    def ensure_can_repay_loan(member_account):
        return  # do nothing
# Peer Loan Repayment Service
# =====================================================

class PeerLoanRepaymentService1:

    @staticmethod
    @transaction.atomic
    def repay_borrower_loans(borrower_account, total_amount, paid_by_user):
        from transact3_lending.models import PeerToPeerLoan, PeerLoanRepayment
        from transact1_regular_deposit.models import SJP2Transaction
        from ledger.services import LedgerService

        remaining_amount = Decimal(total_amount)
        unpaid_loans = PeerToPeerLoan.objects.select_for_update().filter(
            borrower=borrower_account,
            is_fully_paid=False
        ).order_by('-amount')

        total_repaid = Decimal('0.00')

        for loan in unpaid_loans:
            if remaining_amount <= 0:
                break

            already_paid = loan.repayments.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')

            remaining_loan_amount = loan.amount - already_paid
            pay_amount = min(remaining_amount, remaining_loan_amount)

            txn= PeerLoanRepayment.objects.create(
                peer_loan=loan,
                amount=pay_amount,
                paid_by=paid_by_user )

            #txn = SJP2Transaction.objects.create(
            #    transaction_type=SJP2Transaction.TransactionType.Transfer,
             #   from_member_account=borrower_account,
             #   to_member_account=loan.lender,
            #    amount=pay_amount,   ) #SSJP2 does not need this

           # reference = f"SJP2Transaction ID {txn.pk}"

            LedgerService.create_statement(
                account=borrower_account,
                transaction_type='peer_loan_repayment',
                debit=pay_amount,
                credit=Decimal('0.00'),
                reference=f"PeerLoanPyt ID {txn.pk}",
            )

            LedgerService.create_statement(
                account=loan.lender,
                transaction_type='peer_loan_repayment',
                debit=Decimal('0.00'),
                credit=pay_amount,
                reference=f"PeerLoanPyt ID {txn.pk}",
            )

            if pay_amount == remaining_loan_amount:
                loan.is_fully_paid = True
                loan.save(update_fields=['is_fully_paid'])

            total_repaid += pay_amount
            remaining_amount -= pay_amount

        return total_repaid, remaining_amount
# transact2_loans/services.py
from django.core.mail import send_mail
from django.conf import settings


class LoanNotification:
    from .models import Loan, AuditLog
    """
    Service class to handle loan-related actions like notifications and audit logging.
    """

    @staticmethod
    def notify_manager(loan: Loan):
        """
        Send an email notification to the manager for approval.
        """
        manager_email = getattr(settings, "MANAGER_EMAIL", None)
        if not manager_email:
            return  # optionally log warning

        send_mail(
            subject=f"Loan Approval Needed: {loan.pk}",
            message=f"Loan #{loan.pk} for {loan.account} needs manager approval.",
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[manager_email],
        )

    @staticmethod
    def log_audit(loan: Loan, action: str, user):
        """
        Record an audit entry for the loan.
        """
        AuditLog.objects.create(
            loan=loan,
            action=action,
            performed_by=user )
#SO THAT WE REUSE IT LAONPAYMENT, AND PEER TO PEER LOAN
class LoanDelayService:

    @staticmethod
    def calculate_delay(paid_on, due_date):
        if paid_on <= due_date:
            return 0

        months_late = (
            (paid_on.year - due_date.year) * 12 +
            (paid_on.month - due_date.month)
        )
        return max(months_late, 1)


class PeerLoanRepaymentService:

    @staticmethod
    @transaction.atomic
    def repay_borrower_loans(borrower_account, total_amount, paid_by_user):
        from transact3_lending.models import PeerToPeerLoan, PeerLoanRepayment
        from ledger.services import LedgerService

        remaining_amount = Decimal(total_amount)
        unpaid_loans = PeerToPeerLoan.objects.select_for_update().filter(
            borrower=borrower_account,
            is_fully_paid=False
        ).order_by('-amount')

        total_repaid = Decimal('0.00')

        for loan in unpaid_loans:
            if remaining_amount <= 0:
                break

            already_paid = loan.repayments.aggregate(
                total=models.Sum('amount')
            )['total'] or Decimal('0.00')

            remaining_loan_amount = loan.amount - already_paid
            pay_amount = min(remaining_amount, remaining_loan_amount)

            # 🔹 Save repayment
            repayment = PeerLoanRepayment.objects.create(
                peer_loan=loan,
                amount=pay_amount,
                paid_by=paid_by_user,
            )

            # 🔹 Ledger entries for borrower and lender
            LedgerService.create_statement(
                account=borrower_account,
                transaction_type='peer_loan_repayment',
                debit=pay_amount,
                credit=Decimal('0.00'),
                reference=f"PeerLoanPyt ID {repayment.pk}",
            )

            LedgerService.create_statement(
                account=loan.lender,
                transaction_type='peer_loan_repayment',
                debit=Decimal('0.00'),
                credit=pay_amount,
                reference=f"PeerLoanPyt ID {repayment.pk}",
            )

            # 🔹 Mark fully paid if completed
            if pay_amount == remaining_loan_amount:
                loan.is_fully_paid = True
                loan.save(update_fields=['is_fully_paid'])

            total_repaid += pay_amount
            remaining_amount -= pay_amount

        return total_repaid, remaining_amount

