from decimal import Decimal
from django.db import transaction

class PeerLoanRepaymentService:
    @staticmethod
    @transaction.atomic
    def repay_borrower_loans(borrower_account, total_amount, paid_by_user):
        # Lazy import to avoid circular import
        from transact3_lending.models import PeerToPeerLoan, PeerLoanRepayment, PeerLendingStatus, PeerBorrowingStatus

        total_amount = Decimal(total_amount)
        if total_amount <= 0:
            raise ValueError("Repayment amount must be greater than zero.")

        remaining_amount = total_amount

        # Get all unpaid loans for borrower, largest first
        unpaid_loans = PeerToPeerLoan.objects.filter(
            borrower=borrower_account,
            is_fully_paid=False
        ).order_by('-amount')

        lenders_to_update = set()

        for loan in unpaid_loans:
            if remaining_amount <= 0:
                break

            remaining_loan_amount = loan.amount - loan.total_paid
            if remaining_loan_amount <= 0:
                continue  # skip fully paid loans

            pay_amount = min(remaining_amount, remaining_loan_amount)

            # Create repayment record; balances handled in model save()
            PeerLoanRepayment.objects.create(
                loan=loan,
                amount=pay_amount,
                paid_by=paid_by_user
            )

            remaining_amount -= pay_amount

            # Refresh loan to get updated total_paid
            loan.refresh_from_db()
            if loan.total_paid >= loan.amount:
                loan.is_fully_paid = True
                loan.save(update_fields=['is_fully_paid'])

            lenders_to_update.add(loan.lender)

        used_amount = total_amount - remaining_amount

        # Update aggregate statuses
        PeerBorrowingStatus.update_total_borrowed(borrower_account)
        for lender in lenders_to_update:
            PeerLendingStatus.update_total_lender_loan(lender)

        return used_amount, remaining_amount
