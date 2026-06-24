from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register_view, name="register"),
    path("login/", views.login_view,  name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("verify-otp/", views.verify_otp_view, name="verify_otp"),  # full impl Day 3

]

