from django.urls import path
from property_app import views

urlpatterns = [
    path("", views.home, name="home")
]