from django.urls import path
from django.contrib.auth.decorators import login_required
from django.shortcuts import render

app_name = "dashboard"

# Temporary stub — full dashboard built on Day 13
@login_required
def home(request):
    return render(request, "dashboard/home_stub.html")

urlpatterns = [
    path("", home, name="home"),
]

