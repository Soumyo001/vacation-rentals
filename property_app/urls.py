from django.urls import path
from property_app import views

urlpatterns = [
    path("", views.home, name="home"),
    path("properties/", views.property_list, name="property_list"),
    path(
        "properties/<slug:slug>/",
        views.property_detail,
        name="property_detail",
    ),
]