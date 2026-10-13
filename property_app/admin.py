from django.contrib import admin
from django.contrib.gis.admin import GISModelAdmin
from django.utils.html import format_html
from property_app.models import Location, Property, PropertyImage

class HasImagesFilter(admin.SimpleListFilter):
    title = "property images"
    parameter_name = "has_images"

    def lookups(self, request, model_admin):
        return [
            ("yes", "Has images"),
            ("no", "No images"),
        ]

    def queryset(self, request, queryset):
        if self.value() == "yes":
            return queryset.filter(
                images__isnull=False
            ).distinct()

        if self.value() == "no":
            return queryset.filter(
                images__isnull=True
            )

        return queryset

class PropertyImageInline(admin.TabularInline):
    model = PropertyImage
    extra = 1

    fields = [
        "image",
        "image_preview",
        "alt_text",
        "caption",
        "is_primary",
        "sort_order",
    ]

    readonly_fields = ["image_preview"]

    @admin.display(description="Preview")
    def image_preview(self, obj):
        if not obj.pk or not obj.image:
            return "No image uploaded"

        return format_html(
            '<img src="{}" width="110" '
            'style="height: 75px; object-fit: cover;" '
            'alt="Property image preview">',
            obj.image.url,
        )

@admin.register(Location)
class LocationAdmin(GISModelAdmin):
    list_display = [
        "name",
        "city",
        "state",
        "country",
        "is_active",
    ]

    list_filter = [
        "country",
        "is_active",
    ]

    search_fields = [
        "name",
        "city",
        "state",
        "country",
    ]

    exclude = ["embedding"]

@admin.register(Property)
class PropertyAdmin(GISModelAdmin):
    list_display = [
        "title",
        "location",
        "property_type",
        "status",
        "price",
        "is_active",
    ]

    list_filter = [
        "property_type",
        "status",
        "is_featured",
        "is_active",
        HasImagesFilter,
    ]

    search_fields = [
        "title",
        "address",
        "location__name",
        "location__city",
    ]

    list_select_related = ["location"]

    inlines = [PropertyImageInline]