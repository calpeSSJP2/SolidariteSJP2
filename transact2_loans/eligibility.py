from decimal import Decimal
from datetime import date
from accounts.models import MemberAccount
from transact1_regular_deposit.models import DepositDueTransaction
from transact2_loans.models import Loan as Loan

def is_member_eligible_for_loan(member_account: MemberAccount) -> bool:
    if not member_account or not member_account.opened_on:
        return False

    today = date.today()
    # Allow loan if member has contributed at least 1 month recently
    recent_months = {(today.year, today.month)}  # Just the current month for eligibility check

    dues = DepositDueTransaction.objects.filter(
        account=member_account,
        is_paid=True,
        paid_on__isnull=False
    )
    paid_months = {(d.paid_on.year, d.paid_on.month) for d in dues}

    return bool(recent_months.intersection(paid_months))


def get_loan_limit_by_type(member_account: MemberAccount, loan_type: str) -> Decimal:
    principal = member_account.principal or Decimal('0.00')

    if loan_type == Loan.LoanType.REGULAR:
        return principal * Decimal('3')
    elif loan_type == Loan.LoanType.EMERGENCY:
        return principal * Decimal('0.2')

    return Decimal('0.00')
