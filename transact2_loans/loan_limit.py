from decimal import Decimal
from django.db import models
from accounts.models import MemberAccount

class LoanLimitService:

    @staticmethod
    def get_total_outstanding(account: MemberAccount) -> Decimal:
        from transact2_loans.models import Loan as BankLoan
        from transact3_lending.models import PeerToPeerLoan

        bank_loans = BankLoan.objects.filter(account=account, status__in=['approved', 'active']).aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')
        peer_loans = PeerToPeerLoan.objects.filter(borrower=account, is_fully_paid=False).aggregate(s=models.Sum('amount'))['s'] or Decimal('0.00')
        return bank_loans + peer_loans

    @staticmethod
    def can_request_bank_loan(account: MemberAccount, amount: Decimal) -> bool:
        max_allowed = account.Principal * Decimal('3')
        return LoanLimitService.get_total_outstanding(account) + amount <= max_allowed

    @staticmethod
    def can_request_peer_loan(account: MemberAccount, amount: Decimal) -> bool:
        max_allowed = account.Principal * Decimal('2')
        return LoanLimitService.get_total_outstanding(account) + amount <= max_allowed
