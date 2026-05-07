from django import forms
from .models import ShareIncrease, ShareDecrease
from accounts.models import MemberAccount

# -----------------------------
# Increase Share Form
# -----------------------------
class IncreaseShareForm(forms.ModelForm):
    class Meta:
        model = ShareIncrease
        fields = ['account', 'nbr_share', 'description']
        widgets = {
            'account': forms.Select(attrs={'class': 'form-control'}),
            'nbr_share': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of shares'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional note'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ❌ Only show ACTIVE accounts in dropdown
        self.fields['account'].queryset = MemberAccount.objects.filter(status_type='active')

# -----------------------------
# Decrease Share Form
# -----------------------------
class DecreaseShareForm(forms.ModelForm):
    class Meta:
        model = ShareDecrease
        fields = ['account', 'nbr_share', 'description']
        widgets = {
            'account': forms.Select(attrs={'class': 'form-control'}),
            'nbr_share': forms.NumberInput(attrs={'class': 'form-control', 'placeholder': 'Number of shares to remove'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Optional: Reason or note...'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # ❌ Only show ACTIVE accounts in dropdown
        self.fields['account'].queryset = MemberAccount.objects.filter(status_type='active')
