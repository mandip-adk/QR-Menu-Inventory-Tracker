from django.urls import path
from . import views

app_name = "products"

urlpatterns = [
    path("<slug:shop_slug>/categories/<int:category_id>/products/",
         views.product_list_view, name="list"),
    path("<slug:shop_slug>/categories/<int:category_id>/products/create/",
         views.product_create_view, name="create"),
    path("<slug:shop_slug>/categories/<int:category_id>/products/<int:product_id>/edit/",
         views.product_edit_view, name="edit"),
    path("<slug:shop_slug>/categories/<int:category_id>/products/<int:product_id>/delete/",
         views.product_delete_view, name="delete"),
    path("<slug:shop_slug>/categories/<int:category_id>/products/<int:product_id>/toggle/",
         views.product_toggle_availability_view, name="toggle_availability"),
]

