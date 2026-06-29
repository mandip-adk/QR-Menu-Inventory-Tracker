from django.urls import path
from . import views

app_name = "categories"

urlpatterns = [
    path("<slug:shop_slug>/categories/", views.category_list_view,   name="list"),
    path("<slug:shop_slug>/categories/create/", views.category_create_view, name="create"),
    path("<slug:shop_slug>/categories/<int:category_id>/edit/", views.category_edit_view,   name="edit"),
    path("<slug:shop_slug>/categories/<int:category_id>/delete/", views.category_delete_view, name="delete"),
]

