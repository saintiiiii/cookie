from decimal import Decimal
from datetime import date

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from .models import Category, Ingredient, IngredientPurchase, Product, Recipe, Sale, Supplier
from .services import ROLE_INVENTORY, bootstrap_roles, create_sale, reconcile_purchase_update, record_purchase, reverse_purchase_stock, void_sale


class SaleServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="cashier", password="testpass123")
        self.category = Category.objects.create(name="Cake")
        self.product = Product.objects.create(
            name="Chocolate Cake",
            category=self.category,
            sku="CK-001",
            price=Decimal("500.00"),
            cost=Decimal("300.00"),
            stock_quantity=10,
        )
        self.flour = Ingredient.objects.create(name="Flour", unit="cups", quantity_in_stock=50, reorder_level=5, cost_per_unit=Decimal("20.00"))
        Recipe.objects.create(product=self.product, ingredient=self.flour, quantity_required=Decimal("2.00"), unit="cups")
        self.supplier = Supplier.objects.create(name="Golden Grain Supplies")

    def test_sale_deducts_product_and_ingredient_stock(self):
        sale = create_sale(
            cashier=self.user,
            payment_type="cash",
            payment_amount=Decimal("1000.00"),
            items=[{"product_id": self.product.id, "quantity": 2}],
            notes="Test sale",
        )

        self.product.refresh_from_db()
        self.flour.refresh_from_db()

        self.assertEqual(sale.total_amount, Decimal("1000.00"))
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertEqual(self.flour.quantity_in_stock, Decimal("46.00"))
        self.assertEqual(sale.items.count(), 1)

    def test_void_sale_restores_stock_and_records_voided_items(self):
        sale = create_sale(
            cashier=self.user,
            payment_type="cash",
            payment_amount=Decimal("1000.00"),
            items=[{"product_id": self.product.id, "quantity": 2}],
            notes="Test sale",
        )

        void_sale(sale=sale, approved_by=self.user, reason="Customer cancellation")

        sale.refresh_from_db()
        self.product.refresh_from_db()
        self.flour.refresh_from_db()

        self.assertEqual(sale.status, Sale.STATUS_VOIDED)
        self.assertEqual(self.product.stock_quantity, 10)
        self.assertEqual(self.flour.quantity_in_stock, Decimal("50.00"))
        self.assertEqual(sale.voided_items.count(), 1)
        self.assertEqual(sale.total_profit, Decimal("0.00"))

    def test_sale_rejects_when_payment_is_insufficient(self):
        with self.assertRaises(ValidationError):
            create_sale(
                cashier=self.user,
                payment_type="cash",
                payment_amount=Decimal("100.00"),
                items=[{"product_id": self.product.id, "quantity": 1}],
            )

    def test_sale_rejects_duplicate_lines_that_exceed_product_stock(self):
        self.product.stock_quantity = 3
        self.product.save(update_fields=["stock_quantity"])

        with self.assertRaises(ValidationError):
            create_sale(
                cashier=self.user,
                payment_type="cash",
                payment_amount=Decimal("2000.00"),
                items=[
                    {"product_id": self.product.id, "quantity": 2},
                    {"product_id": self.product.id, "quantity": 2},
                ],
            )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 3)

    def test_sale_rejects_shared_ingredient_shortage(self):
        second_product = Product.objects.create(
            name="Vanilla Cake",
            category=self.category,
            sku="CK-002",
            price=Decimal("500.00"),
            cost=Decimal("250.00"),
            stock_quantity=10,
        )
        Recipe.objects.create(product=second_product, ingredient=self.flour, quantity_required=Decimal("49.00"), unit="cups")

        with self.assertRaises(ValidationError):
            create_sale(
                cashier=self.user,
                payment_type="cash",
                payment_amount=Decimal("1000.00"),
                items=[
                    {"product_id": self.product.id, "quantity": 1},
                    {"product_id": second_product.id, "quantity": 1},
                ],
            )

        self.flour.refresh_from_db()
        self.assertEqual(self.flour.quantity_in_stock, Decimal("50.00"))

    def test_record_purchase_updates_stock_and_metadata(self):
        purchase = IngredientPurchase.objects.create(
            supplier=self.supplier,
            ingredient=self.flour,
            quantity=Decimal("10.00"),
            unit_cost=Decimal("22.00"),
            expiration_date=date(2026, 8, 31),
        )

        record_purchase(purchase=purchase, user=self.user)

        purchase.refresh_from_db()
        self.flour.refresh_from_db()
        self.assertEqual(purchase.unit, "cups")
        self.assertEqual(self.flour.quantity_in_stock, Decimal("60.00"))
        self.assertEqual(self.flour.cost_per_unit, Decimal("22.00"))
        self.assertEqual(self.flour.supplier, self.supplier)
        self.assertEqual(self.flour.expiration_date, date(2026, 8, 31))

    def test_purchase_update_reconciles_stock_delta(self):
        purchase = IngredientPurchase.objects.create(
            supplier=self.supplier,
            ingredient=self.flour,
            quantity=Decimal("10.00"),
            unit_cost=Decimal("22.00"),
        )
        record_purchase(purchase=purchase, user=self.user)
        previous_purchase = IngredientPurchase.objects.get(pk=purchase.pk)

        purchase.quantity = Decimal("4.00")
        purchase.save(update_fields=["quantity"])
        reconcile_purchase_update(purchase=purchase, previous_purchase=previous_purchase, user=self.user)

        self.flour.refresh_from_db()
        self.assertEqual(self.flour.quantity_in_stock, Decimal("54.00"))

    def test_purchase_delete_rejects_negative_stock(self):
        purchase = IngredientPurchase.objects.create(
            supplier=self.supplier,
            ingredient=self.flour,
            quantity=Decimal("60.00"),
            unit_cost=Decimal("22.00"),
        )

        with self.assertRaises(ValidationError):
            reverse_purchase_stock(purchase=purchase, user=self.user)


class ProductCategoryWorkflowTests(TestCase):
    def setUp(self):
        bootstrap_roles()
        self.user = User.objects.create_user(username="inventory", password="testpass123")
        self.user.groups.add(Group.objects.get(name=ROLE_INVENTORY))
        self.client.force_login(self.user)

    def test_product_page_creates_category_visible_in_products_and_categories(self):
        response = self.client.post(
            reverse("product-list"),
            {
                "name": "Pastries",
                "description": "Freshly baked pastry items.",
            },
        )

        self.assertRedirects(response, reverse("product-list"))
        self.assertTrue(Category.objects.filter(name="Pastries").exists())

        product_response = self.client.get(reverse("product-list"))
        self.assertContains(product_response, "Pastries")

        category_response = self.client.get(reverse("category-list"))
        self.assertContains(category_response, "Pastries")
