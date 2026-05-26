from decimal import Decimal
from django.core import mail
from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from bakery.models import ActivityLog, BatchAllocation, Category, EmployeeSecurity, InventoryLog, Product, ProductionBatch, Sale
from bakery.services import ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY, bootstrap_roles, create_sale, void_sale


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

    def test_sale_deducts_product_stock(self):
        sale = create_sale(
            cashier=self.user,
            payment_type="cash",
            payment_amount=Decimal("1000.00"),
            items=[{"product_id": self.product.id, "quantity": 2}],
            notes="Test sale",
        )

        self.product.refresh_from_db()

        self.assertEqual(sale.total_amount, Decimal("1000.00"))
        self.assertEqual(self.product.stock_quantity, 8)
        self.assertEqual(sale.items.count(), 1)
        self.assertRegex(sale.receipt_number, r"^OR-\d{14}-[A-F0-9]{8}$")

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

        self.assertEqual(sale.status, Sale.STATUS_VOIDED)
        self.assertEqual(self.product.stock_quantity, 10)
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

    def test_sale_rejects_tampered_choice_fields(self):
        invalid_kwargs = [
            {"payment_type": "crypto"},
            {"sale_channel": "marketplace"},
            {"discount_type": "manager_override"},
        ]

        for overrides in invalid_kwargs:
            with self.subTest(overrides=overrides):
                kwargs = {
                    "cashier": self.user,
                    "payment_type": Sale.PAYMENT_CASH,
                    "payment_amount": Decimal("1000.00"),
                    "items": [{"product_id": self.product.id, "quantity": 1}],
                    "sale_channel": Sale.CHANNEL_WALK_IN,
                    "discount_type": Sale.DISCOUNT_NONE,
                }
                kwargs.update(overrides)
                with self.assertRaises(ValidationError):
                    create_sale(**kwargs)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

    def test_sale_rejects_invalid_tax_rates(self):
        for tax_rate in ("invalid", "-0.01", "1.0001"):
            with self.subTest(tax_rate=tax_rate):
                with self.assertRaises(ValidationError):
                    create_sale(
                        cashier=self.user,
                        payment_type=Sale.PAYMENT_CASH,
                        payment_amount=Decimal("1000.00"),
                        items=[{"product_id": self.product.id, "quantity": 1}],
                        tax_rate=tax_rate,
                    )

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 10)

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

    def test_sale_allocates_stock_from_batches_fifo_by_expiry(self):
        self.product.stock_quantity = 5
        self.product.save(update_fields=["stock_quantity"])
        newer_batch = ProductionBatch.objects.create(
            product=self.product,
            batch_number="NEW",
            production_date="2026-01-02",
            expiry_date="2026-01-20",
            quantity_produced=3,
            quantity_remaining=3,
        )
        older_expiry_batch = ProductionBatch.objects.create(
            product=self.product,
            batch_number="OLD",
            production_date="2026-01-01",
            expiry_date="2026-01-10",
            quantity_produced=2,
            quantity_remaining=2,
        )

        sale = create_sale(
            cashier=self.user,
            payment_type="cash",
            payment_amount=Decimal("1500.00"),
            items=[{"product_id": self.product.id, "quantity": 3}],
        )

        older_expiry_batch.refresh_from_db()
        newer_batch.refresh_from_db()
        self.product.refresh_from_db()

        self.assertEqual(older_expiry_batch.quantity_remaining, 0)
        self.assertEqual(newer_batch.quantity_remaining, 2)
        self.assertEqual(self.product.stock_quantity, 2)
        self.assertEqual(BatchAllocation.objects.filter(sale_item__sale=sale).count(), 2)

    def test_void_sale_restores_original_batch_allocations(self):
        self.product.stock_quantity = 2
        self.product.save(update_fields=["stock_quantity"])
        batch = ProductionBatch.objects.create(
            product=self.product,
            batch_number="BATCH-1",
            quantity_produced=2,
            quantity_remaining=2,
        )
        sale = create_sale(
            cashier=self.user,
            payment_type="cash",
            payment_amount=Decimal("1000.00"),
            items=[{"product_id": self.product.id, "quantity": 2}],
        )
        batch.refresh_from_db()
        self.assertEqual(batch.quantity_remaining, 0)

        void_sale(sale=sale, approved_by=self.user, reason="Customer cancellation")

        batch.refresh_from_db()
        self.product.refresh_from_db()
        self.assertEqual(batch.quantity_remaining, 2)
        self.assertEqual(self.product.stock_quantity, 2)

    def test_activity_and_inventory_logs_are_append_only(self):
        activity = ActivityLog.objects.create(action=ActivityLog.ACTION_CREATE, description="Created")
        inventory_log = InventoryLog.objects.create(
            item_type=InventoryLog.ITEM_PRODUCT,
            action=InventoryLog.ACTION_ADJUSTMENT,
            product=self.product,
            quantity_before=Decimal("1.00"),
            quantity_change=Decimal("1.00"),
            quantity_after=Decimal("2.00"),
        )

        activity.description = "Tampered"
        inventory_log.note = "Tampered"

        with self.assertRaises(ValidationError):
            activity.save()
        with self.assertRaises(ValidationError):
            inventory_log.save()
        with self.assertRaises(ValidationError):
            activity.delete()
        with self.assertRaises(ValidationError):
            inventory_log.delete()

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

    def test_production_batch_increases_stock_without_duplicate_batch(self):
        category = Category.objects.create(name="Bread")
        product = Product.objects.create(
            name="Sourdough",
            category=category,
            sku="BRD-001",
            price=Decimal("120.00"),
            cost=Decimal("60.00"),
            stock_quantity=0,
        )

        response = self.client.post(
            reverse("production-batch-add"),
            {
                "product": product.pk,
                "batch_number": "BREAD-001",
                "production_date": "2026-05-26",
                "expiry_date": "2026-05-30",
                "quantity_produced": 12,
                "quantity_remaining": 12,
                "notes": "",
            },
        )

        product.refresh_from_db()
        self.assertRedirects(response, reverse("production-batch-list"))
        self.assertEqual(product.stock_quantity, 12)
        self.assertEqual(ProductionBatch.objects.filter(product=product).count(), 1)


class EmployeeAccountTests(TestCase):
    def setUp(self):
        bootstrap_roles()
        self.admin = User.objects.create_user(username="manager", password="RolePass#123", is_staff=True)
        self.admin.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.client.force_login(self.admin)

    def test_employee_creation_hashes_password_and_assigns_role(self):
        response = self.client.post(
            reverse("employee-add"),
            {
                "username": "newcashier",
                "first_name": "New",
                "last_name": "Cashier",
                "email": "newcashier@example.com",
                "role": "Cashier",
                "is_active": "on",
                "password1": "OvenShift#789",
                "password2": "OvenShift#789",
            },
        )

        self.assertRedirects(response, reverse("employee-list"))
        employee = User.objects.get(username="newcashier")
        self.assertTrue(employee.is_active)
        self.assertNotEqual(employee.password, "OvenShift#789")
        self.assertTrue(employee.check_password("OvenShift#789"))
        self.assertTrue(employee.groups.filter(name=ROLE_CASHIER).exists())

    def test_admin_can_assign_roles_to_other_accounts(self):
        employee = User.objects.create_user(username="stocker", password="Stocker#123", is_staff=True)
        employee.groups.add(Group.objects.get(name=ROLE_CASHIER))

        response = self.client.post(
            reverse("employee-edit", args=[employee.pk]),
            {
                "username": "stocker",
                "first_name": "",
                "last_name": "",
                "email": "",
                "role": ROLE_INVENTORY,
                "is_active": "on",
            },
        )

        employee.refresh_from_db()
        self.assertRedirects(response, reverse("employee-list"))
        self.assertTrue(employee.is_active)
        self.assertTrue(employee.groups.filter(name=ROLE_INVENTORY).exists())

    def test_admin_generates_temporary_password_and_employee_must_change_it(self):
        employee = User.objects.create_user(username="cashier", password="Original#123", is_staff=True)
        employee.groups.add(Group.objects.get(name=ROLE_CASHIER))

        response = self.client.post(
            reverse("employee-password-reset", args=[employee.pk]),
            {"confirm": "on"},
        )

        employee.refresh_from_db()
        security = EmployeeSecurity.objects.get(user=employee)
        temporary_password = self.client.session["temporary_password_popup"]["password"]

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], reverse("employee-list"))
        self.assertFalse(employee.check_password("Original#123"))
        self.assertTrue(employee.check_password(temporary_password))
        self.assertTrue(security.must_change_password)

        popup_response = self.client.get(reverse("employee-list"))
        self.assertContains(popup_response, 'id="temporaryPasswordModal"')
        self.assertContains(popup_response, temporary_password)
        self.assertNotIn("temporary_password_popup", self.client.session)

        self.client.logout()
        login_response = self.client.post(
            reverse("login"),
            {"username": "cashier", "password": temporary_password},
        )
        self.assertRedirects(login_response, reverse("force-password-change"))

        dashboard_response = self.client.get(reverse("dashboard"))
        self.assertRedirects(dashboard_response, reverse("force-password-change"))

        change_response = self.client.post(
            reverse("force-password-change"),
            {"new_password1": "FreshPass#456", "new_password2": "FreshPass#456"},
        )
        employee.refresh_from_db()
        security.refresh_from_db()

        self.assertRedirects(change_response, reverse("dashboard"))
        self.assertTrue(employee.check_password("FreshPass#456"))
        self.assertFalse(security.must_change_password)

    @override_settings(EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend")
    def test_forgot_password_emails_temporary_password_to_employee_email(self):
        employee = User.objects.create_user(
            username="cashier",
            password="Original#123",
            email="cashier@example.com",
            is_staff=True,
        )
        employee.groups.add(Group.objects.get(name=ROLE_CASHIER))

        response = self.client.post(reverse("password-reset"), {"email": "cashier@example.com"})

        employee.refresh_from_db()
        security = EmployeeSecurity.objects.get(user=employee)
        temporary_password = mail.outbox[0].body.split("Your Sweet Crumbs Bakery temporary password is:\n", 1)[1].split("\n", 1)[0]

        self.assertRedirects(response, reverse("password-reset-done"))
        self.assertEqual(mail.outbox[0].to, ["cashier@example.com"])
        self.assertFalse(employee.check_password("Original#123"))
        self.assertTrue(employee.check_password(temporary_password))
        self.assertTrue(security.must_change_password)

        self.client.logout()
        login_response = self.client.post(
            reverse("login"),
            {"username": "cashier", "password": temporary_password},
        )
        self.assertRedirects(login_response, reverse("force-password-change"))

    def test_last_active_admin_cannot_be_deleted_archived_or_stripped(self):
        archive_response = self.client.post(reverse("employee-archive", args=[self.admin.pk]))
        self.assertRedirects(archive_response, reverse("employee-list"))
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)

        update_response = self.client.post(
            reverse("employee-edit", args=[self.admin.pk]),
            {
                "username": "manager",
                "first_name": "",
                "last_name": "",
                "email": "",
                "role": ROLE_CASHIER,
                "is_active": "on",
            },
        )
        self.assertEqual(update_response.status_code, 200)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.groups.filter(name=ROLE_ADMIN).exists())

        delete_response = self.client.post(reverse("employee-delete", args=[self.admin.pk]))
        self.assertRedirects(delete_response, reverse("employee-list"))
        self.assertTrue(User.objects.filter(pk=self.admin.pk).exists())


class BackupRestoreSafetyTests(TestCase):
    def setUp(self):
        bootstrap_roles()
        self.admin = User.objects.create_user(username="manager", password="RolePass#123", is_staff=True)
        self.admin.groups.add(Group.objects.get(name=ROLE_ADMIN))
        self.client.force_login(self.admin)

    @override_settings(DEBUG=False)
    def test_backup_download_is_disabled_outside_debug(self):
        response = self.client.get(reverse("backup-database"))

        self.assertRedirects(response, reverse("reports"))

    @override_settings(DEBUG=False)
    def test_restore_upload_is_disabled_outside_debug(self):
        response = self.client.post(reverse("restore-database"))

        self.assertRedirects(response, reverse("reports"))
