from django import forms
from decimal import Decimal

class LocationSearchForm(forms.Form):
    location = forms.CharField(
        label="Location",
        max_length=150,
        widget=forms.TextInput(
            attrs={
                "placeholder": "Search city, state or country",
                "autocomplete": "off",
            }
        ),
    )

    def clean_location(self):
        location = self.cleaned_data["location"].strip()

        if len(location) < 2:
            raise forms.ValidationError("Enter at least two characters")

        if not any(character.isalpha() for character in location):
            raise forms.ValidationError("Enter a valid location name")

        return location

class SpatialFilterForm(forms.Form):
    radius_km = forms.DecimalField(
        label="Search radius (km)",
        required=False,
        initial=Decimal("5.0"),
        min_value=Decimal("0.5"),
        max_value=Decimal("100.0"),
        max_digits=5,
        decimal_places=1,
        widget=forms.NumberInput(
            attrs={
                "step": "0.5",
                "min": "0.5",
                "max": "100",
            }
        ),
    )

    within_boundary = forms.BooleanField(
        label="Property footprint intersects location boundary",
        required=False,
    )