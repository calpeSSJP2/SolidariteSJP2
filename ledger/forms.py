from django import forms
from .models import AccountStatement
from accounts.models import MemberAccount

class AccountStatementForm(forms.ModelForm):
    class Meta:
        model = AccountStatement
        fields = [
            'account',
            'transaction_type',
            'debit',
            'credit',
            'reference'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Ensure account dropdown shows all accounts
        self.fields['account'].queryset = MemberAccount.objects.all()

