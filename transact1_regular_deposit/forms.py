from django import forms
from django import forms
from .models import  WithdrawalTransaction, TransferTransaction,DepositTransaction, DepositDueTransaction

from decimal import Decimal
from accounts.models import SJP2_Account,IncomeSource,MemberAccount
from django import forms
from .models import DepositDueTransaction

class MemberAccountSearchForm(forms.Form):
    q = forms.CharField(
        required=False,
        label="Search Member Account",
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'placeholder': 'Account number, first name, or last name'
            }
        ),
    )


class DepositForm_dynamic(forms.ModelForm):

    DATE_INPUT_FORMATS = ['%d/%m/%Y', '%Y-%m-%d']

    readonly_widget = forms.TextInput(attrs={
        "class": "form-control",
        "readonly": "readonly"
    })

    due_date = forms.DateField(
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={
            "class": "form-control datepicker",
            "placeholder": "dd/mm/yyyy"
        })
    )

    paid_on = forms.DateField(
        required=False,
        input_formats=DATE_INPUT_FORMATS,
        widget=forms.TextInput(attrs={
            "class": "form-control datepicker",
            "placeholder": "dd/mm/yyyy"
        })
    )
    account = forms.ModelChoiceField(
        queryset=MemberAccount.objects.all(),
        label="Member Account",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    flat_penalty = forms.DecimalField(required=False, widget=readonly_widget)
    percent_penalty = forms.DecimalField(required=False, widget=readonly_widget)
    total_penalty = forms.DecimalField(required=False, widget=readonly_widget)
    total_due = forms.DecimalField(required=False, widget=readonly_widget)

    class Meta:
        model = DepositDueTransaction
        fields = [     ]

        widgets = {
            "account": forms.Select(attrs={"class": "form-control"}),
            "amount": forms.NumberInput(attrs={"class": "form-control"}),
            "receipt_ref_no": forms.TextInput(attrs={"class": "form-control"}),
            "description": forms.Textarea(attrs={
                "class": "form-control",
                "rows": 2
            }),
        }

    # ---------------------------------------------------
    # Accept account passed from the view
    # ---------------------------------------------------

    def __init__(self, *args, **kwargs):

        self.account = kwargs.pop("account", None)

        super().__init__(*args, **kwargs)

        # If account is provided from URL
        if self.account:
            self.fields["account"].initial = self.account
            self.fields["account"].widget = forms.HiddenInput()

        # Add shares to dropdown for JS penalty calculation
        if "account" in self.fields:
            for account in self.fields["account"].queryset:
                account.shares_attr = account.shares


class DepositForm(forms.ModelForm):

    account = forms.ModelChoiceField(
        queryset=MemberAccount.objects.none(),
        label="Member Account"
    )

    due_date = forms.DateField(
        required=True,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            attrs={
                'class': 'form-control datepicker',
                'placeholder': 'YYYY-MM-DD'
            },
            format='%Y-%m-%d'
        )
    )

    paid_on = forms.DateField(
        required=True,
        input_formats=['%Y-%m-%d'],
        widget=forms.DateInput(
            attrs={
                'class': 'form-control datepicker',
                'placeholder': 'YYYY-MM-DD'
            },
            format='%Y-%m-%d'
        )
    )

    class Meta:
        model = DepositTransaction
        fields = [
            "account",
            "amount",
            "due_date",
            "paid_on",
            "receipt_ref_no",
            "description",
        ]

        widgets = {
            "description": forms.Textarea(attrs={
                "rows": 2,
                "cols": 5,
                "class": "form-control",
                "placeholder": "Enter description..."
            })
        }

    def __init__(self, *args, **kwargs):
        account = kwargs.pop("account", None)
        super().__init__(*args, **kwargs)

        if account:
            self.fields["account"].queryset = MemberAccount.objects.filter(pk=account.pk)
            self.initial["account"] = account
        else:
            self.fields["account"].queryset = MemberAccount.objects.all()


        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def clean(self):
        cleaned_data = super().clean()

        account = cleaned_data.get("account")
        due_date = cleaned_data.get("due_date")

        if account and due_date:

            due, created = DepositDueTransaction.objects.get_or_create(
                account=account,
                due_date=due_date,
                defaults={
                    "monthly_due": (account.shares or 0) *
                    DepositDueTransaction.BASE_AMOUNT_PER_SHARE
                }
            )

            cleaned_data["deposit_due"] = due

        return cleaned_data

    def save(self, commit=True):

        instance = super().save(commit=False)

        instance.deposit_due = self.cleaned_data["deposit_due"]

        if commit:
            instance.save()

        return instance


class WithdrawalForm(forms.ModelForm):
    account = forms.ModelChoiceField(
        queryset=MemberAccount.objects.none(),
        label="Member Account"
    )

    def __init__(self, *args, **kwargs):
        account = kwargs.pop('account', None)
        super().__init__(*args, **kwargs)

        if account:
            # Limit account choices to the selected member
            self.fields['account'].queryset = MemberAccount.objects.filter(pk=account.pk)
            self.initial['account'] = account

        # Widgets
        self.fields['amount'].widget.attrs.update({'class': 'form-control'})
        self.fields['account'].widget.attrs.update({'class': 'form-control'})
        self.fields['description'].widget.attrs.update({'class': 'form-control', 'placeholder': 'Enter description...',"rows": 2,
                    "cols": 5})

    class Meta:
        model = WithdrawalTransaction  # ⚡ MUST specify the model
        fields = ['account', 'amount', 'description']

class TransferForm(forms.ModelForm):
    source_account = forms.ModelChoiceField(
        queryset=MemberAccount.objects.none(),
        label="Source Account"
    )

    destination_account = forms.ModelChoiceField(
        queryset=MemberAccount.objects.filter(status_type='active'),
        label="Destination Account"
    )

    def __init__(self, *args, **kwargs):
        source_account = kwargs.pop('account', None)  # account passed from URL
        super().__init__(*args, **kwargs)

        if source_account:
            # Limit source_account to the selected member
            self.fields['source_account'].queryset = MemberAccount.objects.filter(pk=source_account.pk)
            self.initial['source_account'] = source_account

        # Add form-control classes
        self.fields['source_account'].widget.attrs.update({'class': 'form-control'})
        self.fields['destination_account'].widget.attrs.update({'class': 'form-control'})
        self.fields['amount'].widget.attrs.update({'class': 'form-control'})
        self.fields['description'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Enter description...',   "rows": 2,      "cols": 5 })

    class Meta:
        model = TransferTransaction
        fields = ['source_account', 'destination_account', 'amount', 'description']

from accounts.models import MemberAccount  ##    🔁 Replace your_app_name with the actual name of the Django app where the Account model is defined.
##If you want users to filter history by date range, account, or transaction type:
class TransactionHistoryFilterForm(forms.Form):
    TRANSACTION_TYPES = [
        ('Deposit', 'Deposit'),
        ('Withdrawal', 'Withdrawal'),
        ('Transfer', 'Transfer'),
    ]

    account = forms.ModelChoiceField(queryset=MemberAccount.objects.all(), required=False)  #The system filters all Deposit, Withdrawal, and Transfer transactions related to that account
    transaction_type = forms.ChoiceField(choices=[('', 'All')] + TRANSACTION_TYPES, required=False)
    start_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))
    end_date = forms.DateField(required=False, widget=forms.DateInput(attrs={'type': 'date'}))

class ExternalIncomeForm(forms.Form):
    account = forms.ModelChoiceField( queryset=SJP2_Account.objects.all(),label="Target Account"  )

    income_source = forms.ChoiceField(
        choices=IncomeSource.SourceName.choices,
        label="Income Source")

    amount = forms.DecimalField( max_digits=10, decimal_places=2,  min_value=Decimal('0.01'), label="Amount" )

    description = forms.CharField(  required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'cols': 30,
            'placeholder': 'Optional short description...'   }),   label="Description"  )

    receipt_ref_no = forms.CharField( max_length=12,   required=False,
        widget=forms.TextInput(attrs={  'placeholder': '12-char ref no (optional)'
        }),  label="Receipt Ref No"
    )


from django import forms
from decimal import Decimal
from accounts.models import SJP2_Account, ExpensePurpose

class ExpenseForm(forms.Form):
    account = forms.ModelChoiceField(queryset=SJP2_Account.objects.all(), label="Target Account")
    expense_purpose = forms.ChoiceField(choices=ExpensePurpose.OperationType.choices, label="Expense Purpose")
    amount = forms.DecimalField(max_digits=12, decimal_places=2, min_value=Decimal('0.01'), label="Amount")
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional description...'}),
        label="Description" )
    receipt_ref_no = forms.CharField(
        max_length=12,
        required=False,
        widget=forms.TextInput(attrs={'placeholder': '12-char ref no (optional)'}),
        label="Receipt Ref No")
