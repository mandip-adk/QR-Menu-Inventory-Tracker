from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods, require_POST
from django.core.exceptions import ValidationError

from shops.models import Shop
from .models import Category
from .forms import CategoryForm


def _get_owned_shop_or_404(request, shop_slug):
    """
    Same pattern as shops/views.py: a shop owned by someone else 404s,
    rather than 403ing, so as not to confirm a slug's existence to a
    user who isn't its owner.
    """
    return get_object_or_404(Shop, slug=shop_slug, owner=request.user)


def _get_owned_category_or_404(request, shop_slug, category_id):
    """
    Two-hop ownership check: the category must belong to THIS shop,
    AND this shop must belong to the requesting user. Filtering on
    both shop__slug and shop__owner in one query means a category ID
    that's real but attached to someone else's shop returns 404 just
    as cleanly as a category ID that doesn't exist at all — neither
    case leaks which one it was.
    """
    return get_object_or_404(
        Category,
        pk=category_id,
        shop__slug=shop_slug,
        shop__owner=request.user,
    )


@login_required
def category_list_view(request, shop_slug):
    shop = _get_owned_shop_or_404(request, shop_slug)
    categories = shop.categories.all()  # Meta.ordering handles created_at sort
    return render(request, "categories/category_list.html", {
        "shop": shop,
        "categories": categories,
    })


@login_required
@require_http_methods(["GET", "POST"])
def category_create_view(request, shop_slug):
    shop = _get_owned_shop_or_404(request, shop_slug)
    form = CategoryForm(request.POST or None, shop=shop)

    if request.method == "POST":
        if form.is_valid():
            try:
                form.instance.full_clean()  # runs Category.clean() duplicate check
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field if field in form.fields else None, error)
            else:
                form.save()
                messages.success(request, f'Category "{form.instance.name}" created.')
                return redirect("categories:list", shop_slug=shop.slug)

        if form.errors:
            messages.error(request, "Please correct the errors below.")

    return render(request, "categories/category_form.html", {
        "form": form,
        "shop": shop,
        "is_edit": False,
    })


@login_required
@require_http_methods(["GET", "POST"])
def category_edit_view(request, shop_slug, category_id):
    shop = _get_owned_shop_or_404(request, shop_slug)
    category = _get_owned_category_or_404(request, shop_slug, category_id)
    form = CategoryForm(request.POST or None, instance=category, shop=shop)

    if request.method == "POST":
        if form.is_valid():
            try:
                form.instance.full_clean()
            except ValidationError as e:
                for field, errors in e.message_dict.items():
                    for error in errors:
                        form.add_error(field if field in form.fields else None, error)
            else:
                form.save()
                messages.success(request, "Category updated.")
                return redirect("categories:list", shop_slug=shop.slug)

        if form.errors:
            messages.error(request, "Please correct the errors below.")

    return render(request, "categories/category_form.html", {
        "form": form,
        "shop": shop,
        "category": category,
        "is_edit": True,
    })


@login_required
@require_POST
def category_delete_view(request, shop_slug, category_id):
    """
    POST-only (no GET delete — a GET request should never have a
    destructive side effect, otherwise link previews, browser
    prefetching, or a stray <a> tag could delete data unintentionally).

    Deletion cascades to Products in this category once Day 6 builds
    that FK with on_delete=CASCADE — worth being aware of before this
    button exists in a UI a real owner can click.
    """
    category = _get_owned_category_or_404(request, shop_slug, category_id)
    name = category.name
    category.delete()
    messages.success(request, f'Category "{name}" deleted.')
    return redirect("categories:list", shop_slug=shop_slug)


