import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import F, Sum
from django.utils import timezone


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class Note(TimeStampedModel):
    title = models.CharField(max_length=150)
    content = models.TextField()
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.title


class Category(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    barcode_prefix = models.CharField(max_length=12, blank=True)
    color = models.CharField(max_length=20, default="#f59e0b")

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.barcode_prefix:
            letters = "".join(character for character in self.name.upper() if character.isalnum())
            self.barcode_prefix = (letters[:3] or "CAT")
        if not self.color:
            self.color = "#f59e0b"
        super().save(*args, **kwargs)


class Product(TimeStampedModel):
    STATUS_AVAILABLE = "Available"
    STATUS_OUT_OF_STOCK = "Out of Stock"
    STATUS_EXPIRED = "Expired"
    STATUS_ARCHIVED = "Archived"

    item_id = models.CharField(max_length=30, unique=True, blank=True, null=True)
    barcode = models.CharField(max_length=80, unique=True, blank=True, null=True)
    name = models.CharField(max_length=150)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT, related_name="products")
    supplier = models.ForeignKey("Supplier", on_delete=models.SET_NULL, null=True, blank=True, related_name="products")
    sku = models.CharField(max_length=50, unique=True)
    price = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    cost = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    stock_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=10)
    production_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    theme_color = models.CharField(max_length=20, default="#f59e0b")
    storage_location = models.CharField(max_length=100, blank=True)
    product_image = models.ImageField(upload_to="products/", blank=True, null=True)
    is_active = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    archived_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="archived_products",
    )

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["is_active", "is_archived"], name="product_active_archive_idx"),
            models.Index(fields=["expiry_date"], name="product_expiry_idx"),
            models.Index(fields=["stock_quantity"], name="product_stock_idx"),
            models.Index(fields=["category", "is_active"], name="product_category_active_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gte=0), name="product_price_non_negative"),
            models.CheckConstraint(condition=models.Q(cost__gte=0), name="product_cost_non_negative"),
            models.CheckConstraint(condition=models.Q(stock_quantity__gte=0), name="product_stock_non_negative"),
            models.CheckConstraint(condition=models.Q(low_stock_threshold__gte=0), name="product_low_stock_non_negative"),
        ]

    def __str__(self):
        return f"{self.name} ({self.sku})"

    @staticmethod
    def _unique_code(prefix, field_name):
        while True:
            code = f"{prefix}-{uuid.uuid4().hex[:8].upper()}"
            if not Product.objects.filter(**{field_name: code}).exists():
                return code

    def save(self, *args, **kwargs):
        if not self.item_id:
            self.item_id = self._unique_code("ITM", "item_id")
        if not self.barcode:
            self.barcode = self._unique_code("BAR", "barcode")
        if not self.theme_color and self.category_id:
            self.theme_color = self.category.color
        super().save(*args, **kwargs)

    def archive(self, *, user=None):
        self.is_archived = True
        self.is_active = False
        self.is_deleted = True
        self.archived_at = timezone.now()
        self.archived_by = user if getattr(user, "is_authenticated", False) else None
        self.save(update_fields=["is_archived", "is_active", "is_deleted", "archived_at", "archived_by", "updated_at"])

    def clean(self):
        super().clean()
        if self.production_date and self.expiry_date and self.expiry_date < self.production_date:
            raise ValidationError({"expiry_date": "Expiry date cannot be earlier than production date."})
        if self.is_archived and self.is_active:
            raise ValidationError({"is_active": "Archived products cannot remain active."})

    @property
    def profit_per_unit(self):
        return self.price - self.cost

    @property
    def is_low_stock(self):
        return self.stock_quantity <= self.low_stock_threshold

    @property
    def stock_status(self):
        if self.stock_quantity <= 0:
            return "Out of Stock"
        if self.is_low_stock:
            return "Low Stock"
        return "In Stock"

    @property
    def display_status(self):
        if self.is_archived or not self.is_active:
            return self.STATUS_ARCHIVED
        if self.expiry_date and self.expiry_date < timezone.localdate():
            return self.STATUS_EXPIRED
        if self.stock_quantity <= 0:
            return self.STATUS_OUT_OF_STOCK
        return self.STATUS_AVAILABLE

    @property
    def is_expired(self):
        return self.expiry_date is not None and self.expiry_date < timezone.localdate()

    @property
    def reserved_stock(self):
        return self.orders.exclude(status=Order.STATUS_CLAIMED).aggregate(total=Sum("quantity"))["total"] or 0

    @property
    def sold_stock(self):
        return self.sale_items.exclude(sale__status=Sale.STATUS_VOIDED).aggregate(total=Sum("quantity"))["total"] or 0


class Supplier(TimeStampedModel):
    name = models.CharField(max_length=150)
    contact_person = models.CharField(max_length=150, blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Sale(TimeStampedModel):
    PAYMENT_CASH = "cash"
    PAYMENT_GCASH = "gcash"
    PAYMENT_MAYA = "maya"
    PAYMENT_CARD = "card"
    PAYMENT_CHOICES = [
        (PAYMENT_CASH, "Cash"),
        (PAYMENT_GCASH, "GCash"),
        (PAYMENT_MAYA, "Maya"),
        (PAYMENT_CARD, "Credit/Debit Card"),
    ]

    CHANNEL_WALK_IN = "walk_in"
    CHANNEL_ONLINE = "online"
    CHANNEL_CHOICES = [
        (CHANNEL_WALK_IN, "Walk-in"),
        (CHANNEL_ONLINE, "Online"),
    ]

    DISCOUNT_NONE = "none"
    DISCOUNT_SENIOR = "senior"
    DISCOUNT_PWD = "pwd"
    DISCOUNT_PROMO = "promo"
    DISCOUNT_CHOICES = [
        (DISCOUNT_NONE, "No Discount"),
        (DISCOUNT_SENIOR, "Senior Citizen"),
        (DISCOUNT_PWD, "PWD"),
        (DISCOUNT_PROMO, "Promo Discount"),
    ]

    STATUS_COMPLETED = "completed"
    STATUS_VOIDED = "voided"
    STATUS_CHOICES = [
        (STATUS_COMPLETED, "Completed"),
        (STATUS_VOIDED, "Voided"),
    ]

    receipt_number = models.CharField(max_length=30, unique=True)
    cashier = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="sales")
    sale_channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES, default=CHANNEL_WALK_IN)
    payment_type = models.CharField(max_length=20, choices=PAYMENT_CHOICES)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_type = models.CharField(max_length=20, choices=DISCOUNT_CHOICES, default=DISCOUNT_NONE)
    discount_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=4, default=0)
    tax_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    payment_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    change_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_COMPLETED)
    void_reason = models.TextField(blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="voided_sales",
    )
    voided_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    sold_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-sold_at", "-id"]
        indexes = [
            models.Index(fields=["sold_at"], name="sale_sold_at_idx"),
            models.Index(fields=["status", "sold_at"], name="sale_status_sold_idx"),
            models.Index(fields=["payment_type", "sold_at"], name="sale_payment_sold_idx"),
            models.Index(fields=["sale_channel", "sold_at"], name="sale_channel_sold_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(subtotal__gte=0), name="sale_subtotal_non_negative"),
            models.CheckConstraint(condition=models.Q(discount_amount__gte=0), name="sale_discount_non_negative"),
            models.CheckConstraint(condition=models.Q(tax_rate__gte=0, tax_rate__lte=1), name="sale_tax_rate_valid"),
            models.CheckConstraint(condition=models.Q(tax_amount__gte=0), name="sale_tax_non_negative"),
            models.CheckConstraint(condition=models.Q(total_amount__gte=0), name="sale_total_non_negative"),
            models.CheckConstraint(condition=models.Q(payment_amount__gte=0), name="sale_payment_non_negative"),
            models.CheckConstraint(condition=models.Q(change_amount__gte=0), name="sale_change_non_negative"),
            models.CheckConstraint(
                condition=(
                    models.Q(payment_type="cash")
                    | models.Q(payment_type="gcash")
                    | models.Q(payment_type="maya")
                    | models.Q(payment_type="card")
                ),
                name="sale_payment_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(sale_channel="walk_in") | models.Q(sale_channel="online"),
                name="sale_channel_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(discount_type="none")
                    | models.Q(discount_type="senior")
                    | models.Q(discount_type="pwd")
                    | models.Q(discount_type="promo")
                ),
                name="sale_discount_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status="completed") | models.Q(status="voided"),
                name="sale_status_valid",
            ),
        ]

    def __str__(self):
        return self.receipt_number

    @property
    def total_profit(self):
        if self.status == self.STATUS_VOIDED:
            return Decimal("0.00")
        result = self.items.aggregate(
            total=Sum(
                models.ExpressionWrapper(
                    (F("unit_price") - F("unit_cost")) * F("quantity"),
                    output_field=models.DecimalField(max_digits=12, decimal_places=2),
                )
            )
        )["total"]
        return result or Decimal("0.00")

    @property
    def is_voided(self):
        return self.status == self.STATUS_VOIDED

    def clean(self):
        super().clean()
        choice_checks = {
            "payment_type": (self.payment_type, self.PAYMENT_CHOICES),
            "sale_channel": (self.sale_channel, self.CHANNEL_CHOICES),
            "discount_type": (self.discount_type, self.DISCOUNT_CHOICES),
            "status": (self.status, self.STATUS_CHOICES),
        }
        errors = {}
        for field_name, (value, choices) in choice_checks.items():
            if value not in {choice_value for choice_value, _label in choices}:
                errors[field_name] = "Select a valid choice."
        if self.tax_rate is not None and (self.tax_rate < 0 or self.tax_rate > Decimal("1.0000")):
            errors["tax_rate"] = "Tax rate must be between 0 and 1."
        if errors:
            raise ValidationError(errors)


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="saleitem_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="saleitem_unit_price_non_negative"),
            models.CheckConstraint(condition=models.Q(unit_cost__gte=0), name="saleitem_unit_cost_non_negative"),
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="saleitem_line_total_non_negative"),
        ]

    def __str__(self):
        return f"{self.product.name} x {self.quantity}"


class VoidedSaleItem(TimeStampedModel):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="voided_items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="voided_sale_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    reason = models.CharField(max_length=255)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="voided_saleitem_quantity_positive"),
            models.CheckConstraint(condition=models.Q(unit_price__gte=0), name="voided_saleitem_unit_price_non_negative"),
            models.CheckConstraint(condition=models.Q(line_total__gte=0), name="voided_saleitem_line_total_non_negative"),
        ]

    def __str__(self):
        return f"Voided {self.product.name} x {self.quantity}"


class Order(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CLAIMED = "claimed"
    STATUS_CANCELLED = "cancelled"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CLAIMED, "Claimed"),
        (STATUS_CANCELLED, "Cancelled"),
    ]
    ALLOWED_STATUS_TRANSITIONS = {
        STATUS_PENDING: {STATUS_PENDING, STATUS_IN_PROGRESS, STATUS_CANCELLED},
        STATUS_IN_PROGRESS: {STATUS_IN_PROGRESS, STATUS_COMPLETED, STATUS_CANCELLED},
        STATUS_COMPLETED: {STATUS_COMPLETED, STATUS_CLAIMED, STATUS_CANCELLED},
        STATUS_CLAIMED: {STATUS_CLAIMED},
        STATUS_CANCELLED: {STATUS_CANCELLED},
    }

    customer_name = models.CharField(max_length=150)
    contact = models.CharField(max_length=100)
    product = models.ForeignKey(Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="orders")
    order_date = models.DateField(default=timezone.localdate)
    pickup_date = models.DateField()
    quantity = models.PositiveIntegerField(default=1)
    estimated_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)

    class Meta:
        ordering = ["pickup_date", "customer_name"]
        indexes = [
            models.Index(fields=["status", "pickup_date"], name="order_status_pickup_idx"),
            models.Index(fields=["product", "status"], name="order_product_status_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="order_quantity_positive"),
            models.CheckConstraint(condition=models.Q(estimated_total__gte=0), name="order_estimated_total_non_negative"),
            models.CheckConstraint(condition=models.Q(pickup_date__gte=F("order_date")), name="order_pickup_not_before_order"),
        ]

    def __str__(self):
        return f"{self.customer_name} - {self.pickup_date}"

    def clean(self):
        super().clean()
        if self.pickup_date and self.order_date and self.pickup_date < self.order_date:
            raise ValidationError({"pickup_date": "Pickup date cannot be earlier than order date."})
        if self.product and (not self.product.is_active or self.product.is_archived or self.product.is_deleted):
            raise ValidationError({"product": "Unavailable or archived products cannot be ordered."})
        if self.pk:
            previous_status = type(self).objects.filter(pk=self.pk).values_list("status", flat=True).first()
            if previous_status and self.status not in self.ALLOWED_STATUS_TRANSITIONS.get(previous_status, {previous_status}):
                raise ValidationError({"status": f"Cannot change order status from {previous_status} to {self.status}."})


class InventoryLog(TimeStampedModel):
    ITEM_PRODUCT = "product"
    ITEM_CHOICES = [
        (ITEM_PRODUCT, "Product"),
    ]
    ACTION_RESTOCK = "restock"
    ACTION_SALE = "sale"
    ACTION_ADJUSTMENT = "adjustment"
    ACTION_VOID = "void"
    ACTION_CHOICES = [
        (ACTION_RESTOCK, "Restock"),
        (ACTION_SALE, "Sale"),
        (ACTION_ADJUSTMENT, "Adjustment"),
        (ACTION_VOID, "Void"),
    ]
    REASON_RESTOCK = "restock"
    REASON_DAMAGED = "damaged"
    REASON_EXPIRED = "expired"
    REASON_RETURNED = "returned"
    REASON_SAMPLING = "sampling"
    REASON_STAFF = "staff_consumption"
    REASON_CHOICES = [
        (REASON_RESTOCK, "Restock"),
        (REASON_DAMAGED, "Damaged"),
        (REASON_EXPIRED, "Expired"),
        (REASON_RETURNED, "Returned"),
        (REASON_SAMPLING, "Used for sampling"),
        (REASON_STAFF, "Staff consumption"),
    ]

    item_type = models.CharField(max_length=20, choices=ITEM_CHOICES)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    reason = models.CharField(max_length=30, choices=REASON_CHOICES, blank=True)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, null=True, blank=True, related_name="inventory_logs")
    quantity_before = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_change = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_logs")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["product", "created_at"], name="inventory_product_created_idx"),
            models.Index(fields=["action", "created_at"], name="inventory_action_created_idx"),
            models.Index(fields=["sale", "created_at"], name="inventory_sale_created_idx"),
        ]

    def __str__(self):
        return f"{self.product or 'Inventory'} - {self.action}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Inventory logs are append-only and cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Inventory logs are append-only and cannot be deleted.")


class ProductionBatch(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="production_batches")
    batch_number = models.CharField(max_length=50)
    production_date = models.DateField(default=timezone.localdate)
    expiry_date = models.DateField(null=True, blank=True)
    quantity_produced = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    quantity_remaining = models.PositiveIntegerField(default=0)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-production_date", "-created_at"]
        unique_together = ("product", "batch_number")
        indexes = [
            models.Index(fields=["product", "expiry_date", "production_date"], name="batch_fifo_idx"),
            models.Index(fields=["product", "quantity_remaining"], name="batch_product_remaining_idx"),
            models.Index(fields=["expiry_date"], name="batch_expiry_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_produced__gte=1), name="batch_quantity_produced_positive"),
            models.CheckConstraint(condition=models.Q(quantity_remaining__gte=0), name="batch_quantity_remaining_non_negative"),
            models.CheckConstraint(condition=models.Q(quantity_remaining__lte=F("quantity_produced")), name="batch_remaining_not_over_produced"),
        ]

    def __str__(self):
        return f"{self.product.name} batch {self.batch_number}"

    def save(self, *args, **kwargs):
        if self._state.adding and not self.quantity_remaining:
            self.quantity_remaining = self.quantity_produced
        super().save(*args, **kwargs)

    def clean(self):
        super().clean()
        if self.expiry_date and self.production_date and self.expiry_date < self.production_date:
            raise ValidationError({"expiry_date": "Expiry date cannot be earlier than production date."})
        if self.product and (self.product.is_archived or self.product.is_deleted):
            raise ValidationError({"product": "Production batches cannot be added to archived products."})
        if self.quantity_remaining and self.quantity_produced and self.quantity_remaining > self.quantity_produced:
            raise ValidationError({"quantity_remaining": "Remaining quantity cannot exceed produced quantity."})


class BatchAllocation(TimeStampedModel):
    sale_item = models.ForeignKey(SaleItem, on_delete=models.CASCADE, related_name="batch_allocations")
    batch = models.ForeignKey(ProductionBatch, on_delete=models.PROTECT, related_name="sale_allocations")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    restored_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["batch", "created_at"], name="allocation_batch_created_idx"),
            models.Index(fields=["sale_item", "batch"], name="allocation_item_batch_idx"),
        ]
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gte=1), name="allocation_quantity_positive"),
        ]


class ActivityLog(TimeStampedModel):
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"
    ACTION_CREATE = "create"
    ACTION_UPDATE = "update"
    ACTION_DELETE = "delete"
    ACTION_ARCHIVE = "archive"
    ACTION_STOCK = "stock"
    ACTION_SALE = "sale"
    ACTION_VOID = "void"
    ACTION_BACKUP = "backup"
    ACTION_RESTORE = "restore"
    ACTION_PASSWORD = "password"
    ACTION_CHOICES = [
        (ACTION_LOGIN, "Login"),
        (ACTION_LOGOUT, "Logout"),
        (ACTION_CREATE, "Create"),
        (ACTION_UPDATE, "Update"),
        (ACTION_DELETE, "Delete"),
        (ACTION_ARCHIVE, "Archive"),
        (ACTION_STOCK, "Stock"),
        (ACTION_SALE, "Sale"),
        (ACTION_VOID, "Void"),
        (ACTION_BACKUP, "Backup"),
        (ACTION_RESTORE, "Restore"),
        (ACTION_PASSWORD, "Password"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100, blank=True)
    object_id = models.CharField(max_length=50, blank=True)
    object_repr = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="activity_action_created_idx"),
            models.Index(fields=["user", "created_at"], name="activity_user_created_idx"),
            models.Index(fields=["model_name", "object_id"], name="activity_object_idx"),
        ]

    def __str__(self):
        return f"{self.get_action_display()} - {self.object_repr or self.model_name or 'System'}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Activity logs are append-only and cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Activity logs are append-only and cannot be deleted.")


class LoginHistory(TimeStampedModel):
    ACTION_LOGIN = "login"
    ACTION_LOGOUT = "logout"
    ACTION_FAILED = "failed"
    ACTION_CHOICES = [
        (ACTION_LOGIN, "Login"),
        (ACTION_LOGOUT, "Logout"),
        (ACTION_FAILED, "Failed Login"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="login_history")
    username = models.CharField(max_length=150, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "login histories"
        indexes = [
            models.Index(fields=["action", "created_at"], name="login_action_created_idx"),
            models.Index(fields=["user", "created_at"], name="login_user_created_idx"),
            models.Index(fields=["username", "created_at"], name="login_username_created_idx"),
        ]

    def __str__(self):
        return f"{self.username or self.user} - {self.get_action_display()}"

    def save(self, *args, **kwargs):
        if self.pk:
            raise ValidationError("Login history records are append-only and cannot be edited.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError("Login history records are append-only and cannot be deleted.")


class EmployeeSecurity(TimeStampedModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="security")
    must_change_password = models.BooleanField(default=False)
    temporary_password_created_at = models.DateTimeField(null=True, blank=True)
    temporary_password_set_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="temporary_passwords_set",
    )

    class Meta:
        verbose_name_plural = "employee security settings"

    def __str__(self):
        return f"{self.user} security"
