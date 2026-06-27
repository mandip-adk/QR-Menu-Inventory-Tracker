"""
Automated QA tests for Sajilo Pasal — Shops app (Day 4).

Covers checklist sections:
  2. Restaurant/Shop  — create, edit, verify changes saved
  7. Permissions       — User B cannot access User A's shop (THE critical test)
  8. Forms             — empty/invalid/long/duplicate input
  9. URLs              — no 500s, even for cross-owner access attempts

Run with:
    python manage.py test shops -v 2
"""

from django.test import TestCase, Client
from django.urls import reverse

from accounts.models import User
from .models import Shop


VALID_PASSWORD = "StrongPass123!"


def make_verified_user(email):
    user = User.objects.create_user(email=email, password=VALID_PASSWORD)
    user.is_active = True
    user.is_verified = True
    user.save()
    return user


class ShopSlugGenerationTests(TestCase):
    """Checklist section 2 (implicitly) + the core Day 4 feature."""

    def setUp(self):
        self.owner = make_verified_user("slugowner@example.com")

    def test_slug_generated_from_name(self):
        shop = Shop.objects.create(owner=self.owner, name="Sharma Kirana Pasal")
        self.assertEqual(shop.slug, "sharma-kirana-pasal")

    def test_duplicate_name_gets_unique_suffixed_slug(self):
        shop1 = Shop.objects.create(owner=self.owner, name="Annapurna Restaurant")
        owner2 = make_verified_user("slugowner2@example.com")
        shop2 = Shop.objects.create(owner=owner2, name="Annapurna Restaurant")

        self.assertEqual(shop1.slug, "annapurna-restaurant")
        self.assertEqual(shop2.slug, "annapurna-restaurant-2")
        self.assertNotEqual(shop1.slug, shop2.slug)

    def test_three_way_duplicate_name_collision(self):
        names = ["Same Name Shop"] * 3
        slugs = []
        for i, name in enumerate(names):
            owner = make_verified_user(f"collision{i}@example.com")
            shop = Shop.objects.create(owner=owner, name=name)
            slugs.append(shop.slug)
        self.assertEqual(len(slugs), len(set(slugs)))  # all unique
        self.assertEqual(slugs[0], "same-name-shop")
        self.assertEqual(slugs[1], "same-name-shop-2")
        self.assertEqual(slugs[2], "same-name-shop-3")

    def test_slug_does_not_change_on_rename(self):
        """
        Critical: a shop's slug must survive a name change, since it
        may already be printed on a QR code handed to customers.
        """
        shop = Shop.objects.create(owner=self.owner, name="Original Name")
        original_slug = shop.slug

        shop.name = "Completely Different Name"
        shop.save()

        self.assertEqual(shop.slug, original_slug)

    def test_empty_name_still_produces_a_slug(self):
        """Defensive: slugify('') is '', should fall back to 'shop' rather than crash."""
        shop = Shop(owner=self.owner, name="")
        shop.save()
        self.assertTrue(shop.slug)  # non-empty

    def test_nepali_or_unicode_name_does_not_crash(self):
        """SDD requires bilingual support — shop names may contain
        Nepali/Devanagari text. slugify must not error on this, even
        if the resulting slug ends up empty/numeric-fallback."""
        shop = Shop(owner=self.owner, name="शर्मा किराना पसल")
        shop.save()  # must not raise
        self.assertTrue(shop.slug)


class ShopCRUDTests(TestCase):
    """Checklist section 2: create, edit, verify changes saved."""

    def setUp(self):
        self.client = Client()
        self.owner = make_verified_user("cruduser@example.com")
        self.client.login(username=self.owner.email, password=VALID_PASSWORD)

    def test_create_shop_via_view(self):
        resp = self.client.post(reverse("shops:create"), {
            "name": "Test Kirana",
            "shop_type": "kirana",
            "phone": "9800000000",
            "address": "Test Address",
            "description": "A test shop",
        })
        self.assertEqual(Shop.objects.filter(owner=self.owner).count(), 1)
        shop = Shop.objects.get(owner=self.owner)
        self.assertRedirects(resp, reverse("shops:detail", args=[shop.slug]))

    def test_created_shop_is_owned_by_creator(self):
        self.client.post(reverse("shops:create"), {
            "name": "Ownership Test Shop",
            "shop_type": "restaurant",
        })
        shop = Shop.objects.get(name="Ownership Test Shop")
        self.assertEqual(shop.owner, self.owner)

    def test_edit_shop_saves_changes(self):
        shop = Shop.objects.create(owner=self.owner, name="Before Edit", shop_type="kirana")
        resp = self.client.post(reverse("shops:edit", args=[shop.slug]), {
            "name": "Before Edit",  # name unchanged on purpose, slug shouldn't move
            "shop_type": "restaurant",
            "phone": "9811111111",
            "address": "New Address",
            "description": "Updated description",
        })
        shop.refresh_from_db()
        self.assertEqual(shop.shop_type, "restaurant")
        self.assertEqual(shop.phone, "9811111111")
        self.assertEqual(shop.address, "New Address")
        self.assertEqual(shop.description, "Updated description")
        self.assertRedirects(resp, reverse("shops:detail", args=[shop.slug]))

    def test_shop_list_shows_only_own_shops(self):
        Shop.objects.create(owner=self.owner, name="My Shop One")
        Shop.objects.create(owner=self.owner, name="My Shop Two")
        other_owner = make_verified_user("otherowner@example.com")
        Shop.objects.create(owner=other_owner, name="Someone Else's Shop")

        resp = self.client.get(reverse("shops:list"))
        shop_names = [s.name for s in resp.context["shops"]]

        self.assertIn("My Shop One", shop_names)
        self.assertIn("My Shop Two", shop_names)
        self.assertNotIn("Someone Else's Shop", shop_names)


class ShopFormValidationTests(TestCase):
    """Checklist section 8: empty fields, invalid data, long text."""

    def setUp(self):
        self.client = Client()
        self.owner = make_verified_user("formuser@example.com")
        self.client.login(username=self.owner.email, password=VALID_PASSWORD)

    def test_empty_name_rejected(self):
        resp = self.client.post(reverse("shops:create"), {
            "name": "",
            "shop_type": "kirana",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Shop.objects.count(), 0)

    def test_single_character_name_rejected(self):
        resp = self.client.post(reverse("shops:create"), {
            "name": "A",
            "shop_type": "kirana",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Shop.objects.count(), 0)

    def test_invalid_shop_type_rejected(self):
        resp = self.client.post(reverse("shops:create"), {
            "name": "Valid Name",
            "shop_type": "not_a_real_choice",
        })
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(Shop.objects.count(), 0)

    def test_very_long_name_does_not_crash(self):
        resp = self.client.post(reverse("shops:create"), {
            "name": "A" * 5000,
            "shop_type": "kirana",
        })
        self.assertIn(resp.status_code, (200, 302))  # never a 500

    def test_very_long_description_does_not_crash(self):
        resp = self.client.post(reverse("shops:create"), {
            "name": "Valid Shop Name",
            "shop_type": "kirana",
            "description": "B" * 50000,
        })
        self.assertIn(resp.status_code, (200, 302))

    def test_duplicate_shop_name_across_different_owners_is_allowed(self):
        """
        Unlike emails, shop names are NOT required to be globally
        unique — two different owners can both run a "Kirana Pasal".
        The slug collision logic (tested above) is what keeps URLs
        unique, not a uniqueness constraint on the name itself.
        """
        Shop.objects.create(owner=self.owner, name="Common Shop Name")
        other_owner = make_verified_user("formuser2@example.com")
        client2 = Client()
        client2.login(username=other_owner.email, password=VALID_PASSWORD)

        resp = client2.post(reverse("shops:create"), {
            "name": "Common Shop Name",
            "shop_type": "kirana",
        })
        self.assertEqual(Shop.objects.filter(name="Common Shop Name").count(), 2)


class ShopOwnershipPermissionTests(TestCase):
    """
    Checklist section 7 — THE critical test.
    User A creates a shop; User B must not be able to view or edit it
    by guessing/typing the URL directly.
    """

    def setUp(self):
        self.user_a = make_verified_user("ownera@example.com")
        self.user_b = make_verified_user("ownerb@example.com")
        self.shop = Shop.objects.create(owner=self.user_a, name="User A's Private Shop")

        self.client_a = Client()
        self.client_a.login(username=self.user_a.email, password=VALID_PASSWORD)

        self.client_b = Client()
        self.client_b.login(username=self.user_b.email, password=VALID_PASSWORD)

    def test_owner_can_view_own_shop(self):
        resp = self.client_a.get(reverse("shops:detail", args=[self.shop.slug]))
        self.assertEqual(resp.status_code, 200)

    def test_other_user_cannot_view_shop_via_direct_url(self):
        resp = self.client_b.get(reverse("shops:detail", args=[self.shop.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_other_user_cannot_edit_shop_via_direct_url_get(self):
        resp = self.client_b.get(reverse("shops:edit", args=[self.shop.slug]))
        self.assertEqual(resp.status_code, 404)

    def test_other_user_cannot_edit_shop_via_direct_url_post(self):
        """
        The real attack: User B POSTing directly to User A's edit URL,
        attempting to overwrite A's shop data.
        """
        resp = self.client_b.post(reverse("shops:edit", args=[self.shop.slug]), {
            "name": "HIJACKED BY USER B",
            "shop_type": "other",
        })
        self.assertEqual(resp.status_code, 404)

        self.shop.refresh_from_db()
        self.assertEqual(self.shop.name, "User A's Private Shop")  # unchanged
        self.assertNotEqual(self.shop.name, "HIJACKED BY USER B")

    def test_other_users_shop_list_does_not_include_this_shop(self):
        resp = self.client_b.get(reverse("shops:list"))
        shop_names = [s.name for s in resp.context["shops"]]
        self.assertNotIn("User A's Private Shop", shop_names)

    def test_anonymous_user_cannot_view_owner_dashboard_shop_detail(self):
        anon_client = Client()
        resp = anon_client.get(reverse("shops:detail", args=[self.shop.slug]))
        self.assertEqual(resp.status_code, 302)  # redirected to login
        self.assertIn(reverse("accounts:login"), resp.url)

    def test_nonexistent_slug_returns_404_not_500(self):
        resp = self.client_a.get(reverse("shops:detail", args=["this-slug-does-not-exist"]))
        self.assertEqual(resp.status_code, 404)

        