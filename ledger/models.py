from django.db import models
from django.db.models import Sum
# Create your models here.
from decimal import Decimal
from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError



class AccountStatement(models.Model):   ##This is for Individual lelvel

    class TransactionType(models.TextChoices):
        DEPOSIT = 'deposit', 'Deposit'
        WITHDRAW = 'withdraw', 'Withdraw'
        LOAN_ISSUED = 'loan_issued', 'Loan Issued'
        LOAN_INTEREST = 'loan_interest', 'loan-interest'
        TOP_UP = 'top_up', 'Loan Top-Up'
        LOAN_PAYMENT = 'loan_payment', 'Loan Payment'
        PENALTY_LATE_PAYMENT = 'penalty_late_payment', 'Penalty - Late Payment'
        PENALTY_UNDERPAYMENT = 'penalty_underpayment', 'Penalty - Underpayment'
        BORROWING ='borrowing', 'Borrowing'
        LENDING= 'lending', 'Lending'
        # ✅ Add these
        PEER_LOAN_ISSUED = 'peer_loan_issued', 'Peer Loan Issued'
        PEER_LOAN_RECEIVED = 'peer_loan_received', 'Peer Loan Received'
        PEER_LOAN_PAYMENT = 'peer_loan_payment', 'Peer Loan Payment'
        EXCESS_PAYMENT='excess_payment','excess_payment'
        TRANSFER = 'transfer', 'Transfer'

    account = models.ForeignKey(  'accounts.MemberAccount', on_delete=models.CASCADE,
        related_name='statements' )

    date = models.DateTimeField(default=timezone.now)

    transaction_type = models.CharField( max_length=30, choices=TransactionType.choices)

    debit = models.DecimalField(max_digits=12,decimal_places=2, default=Decimal('0.00'))

    credit = models.DecimalField(max_digits=12,decimal_places=2, default=Decimal('0.00')    )

    balance_after = models.DecimalField(  max_digits=12,  decimal_places=2 )

    reference = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['date', 'id']

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("Only one of debit or credit can be set.")
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("Either debit or credit must be provided.")

    def __str__(self):
        return f"{self.account.account_number} | {self.transaction_type}"


# ledger/models.py


class SystemAccountStatement(models.Model):
    account = models.ForeignKey('accounts.SJP2_Account', on_delete=models.CASCADE, related_name='statements')
    date = models.DateTimeField(default=timezone.now)
    transaction_type = models.CharField(max_length=30)
    debit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    credit = models.DecimalField(max_digits=15, decimal_places=2, default=Decimal('0.00'))
    balance_after = models.DecimalField(max_digits=15, decimal_places=2)
    reference = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        ordering = ['date', 'id']

    def clean(self):
        if self.debit > 0 and self.credit > 0:
            raise ValidationError("Only one of debit or credit can be set.")
        if self.debit == 0 and self.credit == 0:
            raise ValidationError("Either debit or credit must be provided.")

    def __str__(self):
        return f"{self.account.account_nbr} | {self.transaction_type}"

    @property
    def available_balance(self):
        totals = self.statements.aggregate(
            debit=Sum('debit'),
            credit=Sum('credit'))

        debit = totals['debit'] or Decimal('0.00')
        credit = totals['credit'] or Decimal('0.00')

        return credit - debit