from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError

from .models import PeerToPeerLoan, PeerLoanRepayment
from accounts.models import User, MemberAccount  # Correct import
from transact2_loans.models import Loan

class PeerToPeerLoanForm(forms.ModelForm):
    class Meta:
        model = PeerToPeerLoan
        fields = ['lender', 'borrower', 'contract', 'amount', 'date']
        widgets = {
            'date': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Show readable names for lender and borrower dropdowns
        self.fields['lender'].queryset = MemberAccount.objects.select_related(
            'member__user'
        ).order_by('member__user__first_name')
        self.fields['borrower'].queryset = MemberAccount.objects.select_related(
            'member__user'
        ).order_by('member__user__first_name')

        # Optional: Add placeholders
        self.fields['amount'].widget.attrs.update({'placeholder': 'Enter loan amount'})
        self.fields['contract'].widget.attrs.update({'accept': '.pdf,.doc,.docx'})

    def clean(self):
        cleaned_data = super().clean()
        lender = cleaned_data.get('lender')
        borrower = cleaned_data.get('borrower')
        amount = cleaned_data.get('amount')

        if lender and borrower:
            if lender == borrower:
                raise forms.ValidationError("Lender and borrower cannot be the same account.")

        if lender and amount:
            if amount > (lender.principal * Decimal('2')):
                raise forms.ValidationError("Lending amount exceeds 2x lender’s principal.")

        return cleaned_data


from django import forms
from decimal import Decimal
from .models import PeerLoanRepayment

class PeerLoanRepaymentForm(forms.ModelForm):
    class Meta:
        model = PeerLoanRepayment
        fields = ['amount']

    def __init__(self, *args, peer_loan=None, user=None, **kwargs):
        super().__init__(*args, **kwargs)

        self.peer_loan = peer_loan
        self.user = user

        if peer_loan:
            self.instance.peer_loan = peer_loan
            self.fields['amount'].required = False
            self.fields['amount'].help_text = (
                f"Remaining balance: {peer_loan.remaining_balance}"
            )

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')

        if amount is None:
            return None

        if amount <= 0:
            raise forms.ValidationError("Amount must be greater than zero.")

        if amount > self.peer_loan.remaining_balance:
            raise forms.ValidationError(
                f"Exceeds remaining balance ({self.peer_loan.remaining_balance})"
            )

        return amount

    def save(self, commit=True):
        amount = self.cleaned_data.get('amount')

        if amount is None:
            return None

        instance = super().save(commit=False)
        instance.paid_by = self.user

        if commit:
            instance.save()

        return instance



from django import forms

class LoanSearchForm(forms.Form):
    search_query = forms.CharField(
        required=False,
        label="Search for a Borrower/Lender",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter account number or name'}),)


# forms.py
from django import forms

class AccountSearchForm(forms.Form):
    query = forms.CharField(
        label="Search (Account No or First Name)",
        required=False
    )
