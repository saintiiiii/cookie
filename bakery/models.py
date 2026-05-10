import uuid
from decimal import Decimal

from django.conf import settings
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

    class Meta:
        ordering = ["name"]

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


class Ingredient(TimeStampedModel):
    name = models.CharField(max_length=150, unique=True)
    unit = models.CharField(max_length=30, default="pcs")
    quantity_in_stock = models.DecimalField(max_digits=12, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0.00"))])
    reorder_level = models.DecimalField(max_digits=12, decimal_places=2, default=5, validators=[MinValueValidator(Decimal("0.00"))])
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0, validators=[MinValueValidator(Decimal("0.00"))])
    supplier = models.ForeignKey("Supplier", on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_items")
    expiration_date = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name

    @property
    def is_low_stock(self):
        return self.quantity_in_stock <= self.reorder_level

    @property
    def stock_status(self):
        if self.quantity_in_stock <= 0:
            return "Out of Stock"
        if self.is_low_stock:
            return "Low Stock"
        return "In Stock"


class Recipe(TimeStampedModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="recipe_items")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, related_name="recipe_items")
    quantity_required = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    unit = models.CharField(max_length=30, blank=True)

    class Meta:
        unique_together = ("product", "ingredient")
        ordering = ["product__name", "ingredient__name"]

    def __str__(self):
        unit = self.unit or self.ingredient.unit
        return f"{self.product.name}: {self.quantity_required} {unit} {self.ingredient.name}"


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


class IngredientPurchase(TimeStampedModel):
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name="purchases")
    ingredient = models.ForeignKey(Ingredient, on_delete=models.PROTECT, related_name="purchases")
    quantity = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.01"))])
    unit = models.CharField(max_length=30, blank=True)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    expiration_date = models.DateField(null=True, blank=True)
    purchased_at = models.DateField(default=timezone.localdate)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ["-purchased_at", "-created_at"]

    def __str__(self):
        return f"{self.ingredient.name} from {self.supplier.name}"

    def save(self, *args, **kwargs):
        if not self.unit and self.ingredient_id:
            self.unit = self.ingredient.unit
        super().save(*args, **kwargs)

    @property
    def total_cost(self):
        return self.quantity * self.unit_cost

    @property
    def display_unit(self):
        return self.unit or self.ingredient.unit


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


class SaleItem(models.Model):
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="sale_items")
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    unit_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    line_total = models.DecimalField(max_digits=12, decimal_places=2)

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

    def __str__(self):
        return f"Voided {self.product.name} x {self.quantity}"


class Order(TimeStampedModel):
    STATUS_PENDING = "pending"
    STATUS_IN_PROGRESS = "in_progress"
    STATUS_COMPLETED = "completed"
    STATUS_CLAIMED = "claimed"
    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_IN_PROGRESS, "In Progress"),
        (STATUS_COMPLETED, "Completed"),
        (STATUS_CLAIMED, "Claimed"),
    ]

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

    def __str__(self):
        return f"{self.customer_name} - {self.pickup_date}"


class InventoryLog(TimeStampedModel):
    ITEM_PRODUCT = "product"
    ITEM_INGREDIENT = "ingredient"
    ITEM_CHOICES = [
        (ITEM_PRODUCT, "Product"),
        (ITEM_INGREDIENT, "Ingredient"),
    ]
    ACTION_RESTOCK = "restock"
    ACTION_SALE = "sale"
    ACTION_PURCHASE = "purchase"
    ACTION_ADJUSTMENT = "adjustment"
    ACTION_VOID = "void"
    ACTION_CHOICES = [
        (ACTION_RESTOCK, "Restock"),
        (ACTION_SALE, "Sale"),
        (ACTION_PURCHASE, "Purchase"),
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
    ingredient = models.ForeignKey(Ingredient, on_delete=models.CASCADE, null=True, blank=True, related_name="inventory_logs")
    quantity_before = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_change = models.DecimalField(max_digits=12, decimal_places=2)
    quantity_after = models.DecimalField(max_digits=12, decimal_places=2)
    note = models.CharField(max_length=255, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    sale = models.ForeignKey(Sale, on_delete=models.SET_NULL, null=True, blank=True, related_name="inventory_logs")
    purchase = models.ForeignKey(
        IngredientPurchase,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inventory_logs",
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        target = self.product or self.ingredient
        return f"{target} - {self.action}"


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

    def __str__(self):
        return f"{self.product.name} batch {self.batch_number}"

    def save(self, *args, **kwargs):
        if not self.quantity_remaining:
            self.quantity_remaining = self.quantity_produced
        super().save(*args, **kwargs)


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

    def __str__(self):
        return f"{self.get_action_display()} - {self.object_repr or self.model_name or 'System'}"


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

    def __str__(self):
        return f"{self.username or self.user} - {self.get_action_display()}"
