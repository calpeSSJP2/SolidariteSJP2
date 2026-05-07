from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
import re
import re

from django import forms
from django.db import transaction
from django.core.exceptions import ValidationError
import re

from .models import User, Role, MembersProfile
from .models import MembersProfile, Role, SJP2_Account, SJP2_Profile

User = get_user_model()

# ---------------------------------------------------
# 🔵 REGISTRATION FORM (MULTI-ROLE SUPPORT)
# ---------------------------------------------------
from django import forms
from accounts.models import User, Role
from django.core.exceptions import ValidationError



class RegistrationForm(forms.ModelForm):
    first_name = forms.CharField(required=True)
    last_name = forms.CharField(required=True)
    email = forms.EmailField(required=False)

    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.none(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    telephone = forms.CharField(required=True)
    national_id = forms.CharField(required=False, max_length=16)
    address = forms.CharField(required=False)

    password1 = forms.CharField(widget=forms.PasswordInput)
    password2 = forms.CharField(widget=forms.PasswordInput)

    class Meta:
        model = User
        fields = [
            "username",
            "first_name",
            "last_name",
            "telephone",
            "email",
            "roles",
            "national_id",
            "address",
            "password1",
            "password2",
        ]

    # ✅ Load roles dynamically
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["roles"].queryset = Role.objects.all()

    # ✅ Telephone normalization
    def clean_telephone(self):
        phone = re.sub(r"[^\d+]", "", self.cleaned_data["telephone"])

        if phone.startswith("07"):
            phone = "+250" + phone[1:]
        elif phone.startswith("250") and not phone.startswith("+"):
            phone = "+" + phone

        if not re.match(r'^\+[1-9]\d{7,14}$', phone):
            raise ValidationError("Invalid phone number")

        return phone

    # ✅ ALL validation in one place
    def clean(self):
        cleaned = super().clean()

        password1 = cleaned.get("password1")
        password2 = cleaned.get("password2")

        # ✔ Fix missing password validation
        if password1 and password2 and password1 != password2:
            self.add_error("password2", "Passwords do not match")

        roles = cleaned.get("roles")

        if roles:
            role_names = [r.name for r in roles]

            # ✔ Conditional validation
            if "ordinary_member" in role_names:
                if not cleaned.get("national_id"):
                    self.add_error("national_id", "Required for member")
                if not cleaned.get("address"):
                    self.add_error("address", "Required for member")

        return cleaned

    # ✅ Safe + atomic save
    def save(self, commit=True):
        with transaction.atomic():
            user = super().save(commit=False)

            user.first_name = self.cleaned_data["first_name"]
            user.last_name = self.cleaned_data["last_name"]
            user.email = self.cleaned_data.get("email")
            user.telephone = self.cleaned_data["telephone"]
            user.set_password(self.cleaned_data["password1"])

            if commit:
                user.save()

                # ✔ assign roles
                roles = self.cleaned_data["roles"]
                user.roles.set(roles)

                # ✔ create profile ONLY if needed
                if any(r.name == "ordinary_member" for r in roles):
                    MembersProfile.objects.create(
                        user=user,
                        national_id=self.cleaned_data.get("national_id"),
                        address=self.cleaned_data.get("address"),
                    )

            return user


class UserUpdateForm(forms.ModelForm):
    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple )

    class Meta:
        model = User
        fields = ["username", "first_name", "last_name", "email", "telephone", "roles"]
# ---------------------------------------------------
# 🔵 PROFILE UPDATE FORM
# ---------------------------------------------------
class MembersProfileUpdateForm(forms.ModelForm):
    username = forms.CharField(max_length=150)
    first_name = forms.CharField(max_length=150)
    last_name = forms.CharField(max_length=150)
    telephone = forms.CharField(max_length=13)

    roles = forms.ModelMultipleChoiceField(
        queryset=Role.objects.all(),
        widget=forms.CheckboxSelectMultiple,
        required=True
    )

    class Meta:
        model = MembersProfile
        fields = [
            'username',
            'first_name',
            'last_name',
            'telephone',
            'roles',
            'national_id',
            'address',
        ]

    # ---------------------------------------------------
    # 🔵 INIT (populate user fields)
    # ---------------------------------------------------
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.user:
            user = self.instance.user

            self.fields['username'].initial = user.username
            self.fields['first_name'].initial = user.first_name
            self.fields['last_name'].initial = user.last_name
            self.fields['telephone'].initial = user.telephone
            self.fields['roles'].initial = user.roles.all()

    # ---------------------------------------------------
    # 🔵 VALIDATE USERNAME
    # ---------------------------------------------------
    def clean_username(self):
        username = self.cleaned_data['username']

        qs = User.objects.filter(username=username)
        if self.instance and self.instance.user:
            qs = qs.exclude(pk=self.instance.user.pk)

        if qs.exists():
            raise ValidationError("Username already exists.")

        return username

    # ---------------------------------------------------
    # 🔵 SAVE UPDATE
    # ---------------------------------------------------
    def save(self, commit=True):
        profile = super().save(commit=False)
        user = profile.user

        user.username = self.cleaned_data['username']
        user.first_name = self.cleaned_data['first_name']
        user.last_name = self.cleaned_data['last_name']
        user.telephone = self.cleaned_data['telephone']

        if commit:
            user.save()

            # update roles (replace old ones)
            user.roles.set(self.cleaned_data['roles'])

            profile.save()

        return profile


# ---------------------------------------------------
# 🔵 SJP2 ACCOUNT FORM
# ---------------------------------------------------
class SJP2AccountForm(forms.ModelForm):
    class Meta:
        model = SJP2_Account
        fields = ['account_nbr', 'purpose', 'balance']

        widgets = {
            'account_nbr': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Account number'
            }),
            'purpose': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Purpose'
            }),
            'balance': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def clean_account_nbr(self):
        account_nbr = self.cleaned_data.get('account_nbr')

        if SJP2_Account.objects.filter(account_nbr=account_nbr).exists():
            raise ValidationError("Account already exists.")

        return account_nbr

    def clean(self):
        cleaned_data = super().clean()

        if not self.instance.pk and SJP2_Account.objects.exists():
            raise ValidationError("Only one SJP2 account is allowed.")

        return cleaned_data


# ---------------------------------------------------
# 🔵 SJP2 PROFILE FORM
# ---------------------------------------------------
class SJP2_ProfileForm(forms.ModelForm):
    class Meta:
        model = SJP2_Profile
        fields = ['location_address', 'started_on']

        widgets = {
            'started_on': forms.DateInput(attrs={'type': 'date'}),
        }


# ---------------------------------------------------
# 🔵 PASSWORD RESET FORM
# ---------------------------------------------------
class PasswordResetDirectForm(forms.Form):
    username = forms.CharField(max_length=150)
    new_password1 = forms.CharField(widget=forms.PasswordInput)
    new_password2 = forms.CharField(widget=forms.PasswordInput)

    def clean_username(self):
        username = self.cleaned_data['username']

        if not User.objects.filter(username=username).exists():
            raise ValidationError("User does not exist.")

        return username

    def clean(self):
        cleaned_data = super().clean()

        if cleaned_data.get("new_password1") != cleaned_data.get("new_password2"):
            raise ValidationError("Passwords do not match.")

        return cleaned_data