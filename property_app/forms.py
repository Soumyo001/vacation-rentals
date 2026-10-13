from django import forms

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