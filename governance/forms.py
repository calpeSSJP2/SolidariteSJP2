from django import forms
from accounts.models import User
from .models import Election, Role

class ElectionForm(forms.ModelForm):
    class Meta:
        model = Election
        fields = ["name", "election_date", "description"]
        widgets = {
            "election_date": forms.DateInput(attrs={"type": "date"}),
            "description": forms.Textarea(attrs={"rows": 2}),
        }
        
class LeaderFilterForm(forms.Form):
    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        required=False,
        empty_label="All Roles"    )

class ElectLeaderForm(forms.Form):
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        label="Select User"
    )

    role = forms.ModelChoiceField(
        queryset=Role.objects.all(),
        label="Leadership Role"
    )

    election = forms.ModelChoiceField(
        queryset=Election.objects.all(),
        required=False,
        label="Election Event"
    )