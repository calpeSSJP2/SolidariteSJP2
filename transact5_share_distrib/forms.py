# finance/forms.py


from django import forms
from .models import YearlyInterestPool


class InterestPoolForm(forms.ModelForm):
    class Meta:
        model = YearlyInterestPool
        fields = ['year', 'total_interest', 'source_account']

    def clean_year(self):
        year = self.cleaned_data['year']

        if YearlyInterestPool.objects.filter(year=year).exists():
            raise forms.ValidationError("This year already has an interest pool.")
        if year < 2026 or year > 2100:
            raise forms.ValidationError("Please enter a valid year.")
        return year



    def clean_total_interest(self):
        value = self.cleaned_data['total_interest']

        if value <= 0:
            raise forms.ValidationError("Interest must be greater than zero.")

        return value

