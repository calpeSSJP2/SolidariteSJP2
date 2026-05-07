from django import forms
from django.core.exceptions import ValidationError


from django.contrib.auth import get_user_model
User = get_user_model()
from .models import Loan,LoanPayment,LoanWorkflow
from .services import  LoanLimitService
from accounts.models import MemberAccount, User,MembersProfile

class LoanRequestForm(forms.ModelForm):

    class Meta:
        model = Loan
        fields = ['account', 'loan_type', 'amount', 'term_months']

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if self.account:
            self.fields['account'].queryset = MemberAccount.objects.filter(pk=self.account.pk)
            self.initial['account'] = self.account

        self.fields['loan_type'].choices = Loan.LoanType.choices
        self.fields['term_months'].choices = Loan.TermChoices.choices


    def clean(self):
        cleaned_data = super().clean()

        account = cleaned_data.get('account')
        loan_type = cleaned_data.get('loan_type')
        amount = cleaned_data.get('amount')
        term_months = cleaned_data.get('term_months')

        if not account:
            return cleaned_data

        # ---------------------------------------------------
        # 🔒 BLOCK MULTIPLE REGULAR LOANS
        # ---------------------------------------------------
        if loan_type == Loan.LoanType.REGULAR:

            existing_loan = (
                Loan.objects
                .filter(
                    account=account,
                    loan_type=Loan.LoanType.REGULAR,
                    status__in=[
                        Loan.LoanStatus.PENDING,
                        Loan.LoanStatus.ACTIVE
                    ]
                )
                .order_by('-issued_on')
                .first()
            )

            if existing_loan:

                # If pending → block
                if existing_loan.status == Loan.LoanStatus.PENDING:
                    raise forms.ValidationError(
                        "You already have a pending regular loan awaiting approval."
                    )

                # If active and not fully paid → block
                if (
                    existing_loan.status == Loan.LoanStatus.ACTIVE
                    and existing_loan.balance > 0
                ):
                    raise forms.ValidationError(
                        "You already have an active regular loan. "
                        "Please clear the balance or request a top-up."
                    )

        # ---------------------------------------------------
        # TERM VALIDATION
        # ---------------------------------------------------
        if loan_type == Loan.LoanType.REGULAR and term_months not in [
            Loan.TermChoices.ONE_YEAR,
            Loan.TermChoices.TWO_YEARS
        ]:
            raise forms.ValidationError(
                "Invalid term for regular loan. Choose 1 year or 2 years."
            )

        if loan_type == Loan.LoanType.EMERGENCY and term_months != Loan.TermChoices.THREE_MONTHS:
            raise forms.ValidationError(
                "Emergency loans must be for 3 months only."
            )

        # ---------------------------------------------------
        # LOAN LIMIT VALIDATION
        # ---------------------------------------------------
        if self.instance.pk is None and not self.instance.top_up_of:
            if not LoanLimitService.can_request_Member_loan(
                account,
                amount
            ):
                raise forms.ValidationError(
                    "Loan exceeds allowable limit. Please request a lower amount."
                )

        return cleaned_data


class TopUpLoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['account', 'loan_type', 'amount', 'term_months']

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)  # officer

        self.original_loan = kwargs.pop('loan', None)
        super().__init__(*args, **kwargs)

        if not self.original_loan:
            self.add_error(None, "Original loan not provided.")
            return

        # Set account field readonly
        self.fields['account'].queryset = MemberAccount.objects.filter(
            pk=self.original_loan.account.pk
        )
        self.initial['account'] = self.original_loan.account
        self.fields['term_months'].choices = [ (12, '1 Year (Regular)'),
            (24, '2 Years (Regular)') ]
        self.fields['account'].widget.attrs['readonly'] = True

        # Set loan_type readonly
        self.fields['loan_type'].choices = [
            (self.original_loan.loan_type, self.original_loan.get_loan_type_display())
        ]
        self.initial['loan_type'] = self.original_loan.loan_type
        self.fields['loan_type'].widget.attrs['readonly'] = True

        # Pre-fill term
        self.initial['term_months'] = self.original_loan.term_months
        self.fields['amount'].label = "Top-Up Amount"

        # Automatically attach top_up_of to the instance
        self.instance.top_up_of = self.original_loan
        self.instance.account = self.original_loan.account
        self.instance.loan_type = self.original_loan.loan_type

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount is None:
            return amount

        if not LoanLimitService.can_request_Member_loan(
            self.original_loan.account,
            amount
        ):
            raise forms.ValidationError(
                "Top-up amount exceeds allowable loan limit."
            )
        return amount

    def clean(self):
        cleaned_data = super().clean()

        if not self.original_loan:
            raise forms.ValidationError("Original loan is required for top-up.")

        # 🔒 ROLE VALIDATION (ADD THIS)
        if not self.user or not self.user.has_any_role('officer', 'itadmin'):
            raise forms.ValidationError("You are not authorized to perform a top-up.")

        # ✅ Business rule
        if not self.original_loan.can_be_topped_up:
            raise forms.ValidationError(
                "This loan cannot be topped up. At least 10% must be paid."
            )

        return cleaned_data



class EmergencyLoanRequestForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['account', 'amount']

    def __init__(self, *args, **kwargs):
        self.account = kwargs.pop('account', None)
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Lock account to selected member
        if self.account:
            self.fields['account'].queryset = MemberAccount.objects.filter(pk=self.account.pk)
            self.initial['account'] = self.account

        # Force emergency defaults (not editable)
        self.instance.loan_type = Loan.LoanType.EMERGENCY
        self.instance.term_months = Loan.TermChoices.THREE_MONTHS

    def clean(self):
        cleaned_data = super().clean()

        account = cleaned_data.get('account')
        amount = cleaned_data.get('amount')

        if not account:
            return cleaned_data

        # -----------------------------
        # 🔒 Loan limit validation
        # -----------------------------
        if amount and not LoanLimitService.can_request_Member_loan(account, amount):
            raise ValidationError(
                "Emergency loan exceeds your allowable loan limit."
            )

        #if not self.user or not self.user.has_any_role('officer', 'itadmin'):
         #   raise ValidationError("You are not authorized to request an emergency loan.")
        return cleaned_data

##Here we remove loans, and related logic.In View are selected
class AccountLookupForm(forms.Form):
    account_number = forms.CharField(
        label="Member Account Number",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter member account number'}),
    )
    account_name = forms.CharField(
        label="Member Name",
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter member first or last name'}),
    )

class LoanPaymentForm(forms.ModelForm):

    member_account = forms.ModelChoiceField(
        queryset=MemberAccount.objects.none(),
        label="Member"
    )

    loan = forms.ModelChoiceField(
        queryset=Loan.objects.none(),
        label="Loan"
    )

    class Meta:
        model = LoanPayment
        fields = [
            'member_account',
            'loan',
            'amount',
            'due_date',
            'paid_on',
            'receipt_ref_no'
        ]

        # =========================
        # UI WIDGETS (FLATPICKR READY)
        # =========================
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control'
            }),
            'receipt_ref_no': forms.TextInput(attrs={
                'class': 'form-control'
            }),

            # 🔥 Flatpickr fields
            'due_date': forms.DateInput(attrs={
                'class': 'form-control datepicker',
                'placeholder': 'YYYY-MM-DD'
            }),
            'paid_on': forms.DateInput(attrs={
                'class': 'form-control datepicker',
                'placeholder': 'YYYY-MM-DD'
            }),
        }

    # -------------------------
    # INIT (SAFE BINDING FIX)
    # -------------------------
    def __init__(self, *args, **kwargs):
        member_account = kwargs.pop('member_account', None)
        super().__init__(*args, **kwargs)

        self.fields['member_account'].queryset = MemberAccount.objects.none()
        self.fields['loan'].queryset = Loan.objects.none()

        # ✅ Force Django date format
        self.fields['due_date'].input_formats = ['%Y-%m-%d']
        self.fields['paid_on'].input_formats = ['%Y-%m-%d']

        if member_account:
            self.fields['member_account'].queryset = MemberAccount.objects.filter(
                pk=member_account.pk
            )
            self.initial['member_account'] = member_account

            loans = Loan.objects.filter(account=member_account)
            self.fields['loan'].queryset = loans

            if loans.exists():
                self.initial['loan'] = loans.first()

    # -------------------------
    # VALIDATION
    # -------------------------
    def clean_member_account(self):
        member = self.cleaned_data.get('member_account')
        if not member:
            raise ValidationError("Member account is required.")
        return member

    def clean_loan(self):
        loan = self.cleaned_data.get('loan')
        member = self.cleaned_data.get('member_account')

        if loan and member and loan.account_id != member.id:
            raise ValidationError("Selected loan does not belong to this member.")

        if not loan:
            raise ValidationError("Loan is required.")

        return loan
# forms.py


class MoveStageForm(forms.Form):
    stage = forms.ChoiceField(choices=LoanWorkflow.Stage.choices)
    notes = forms.CharField(widget=forms.Textarea, required=False)