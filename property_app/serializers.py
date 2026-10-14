from rest_framework import serializers
from property_app.models import Location

class LocationAutocompleteQuerySerializer(serializers.Serializer):
    q = serializers.CharField(
        min_length=2,
        max_length=150,
        trim_whitespace=True,
    )
    limit = serializers.IntegerField(
        required=False,
        default=5,
        min_value=1,
        max_value=10,
    )

    def validate_q(self, value):
        if not any(character.isalpha() for character in value):
            raise serializers.ValidationError("Enter a valid location name.")
        return value

class LocationSuggestionSerializer(serializers.ModelSerializer):
    distance = serializers.FloatField(read_only=True)

    class Meta:
        model = Location
        fields = [
            "id",
            "name",
            "city",
            "state",
            "country",
            "distance",
        ]
        read_only_fields = fields