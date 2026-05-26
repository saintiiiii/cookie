import uuid
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from secrets import choice, randbelow

from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Sum
from django.utils import timezone

from bakery.models import ActivityLog, BatchAllocation, Category, InventoryLog, Product, ProductionBatch, Sale, SaleItem, VoidedSaleItem

ROLE_ADMIN = "Admin"
ROLE_CASHIER = "Cashier"
ROLE_INVENTORY = "Inventory Staff"

DEFAULT_CATEGORIES = [
    ("Bread", "BRD", "#f59e0b"),
    ("Cakes", "CKE", "#ec4899"),
    ("Pastries", "PAS", "#8b5cf6"),
    ("Cookies", "COOKIE", "#a16207"),
    ("Drinks", "DRINK", "#0ea5e9"),
    ("Custom Orders", "CUSTOM", "#10b981"),
]

TEMP_PASSWORD_LENGTH = 12
TEMP_PASSWORD_SPECIALS = "!@#$%^&*"
TEMP_PASSWORD_CHARS = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789" + TEMP_PASSWORD_SPECIALS


def bootstrap_roles():
    for role in (ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY):
        Group.objects.get_or_create(name=role)


def bootstrap_default_categories():
    for name, prefix, color in DEFAULT_CATEGORIES:
        Category.objects.get_or_create(
            name=name,
            defaults={
                "description": f"{name} category",
                "barcode_prefix": prefix,
                "color": color,
            },
        )


def generate_temporary_password():
    required_characters = [
        choice("ABCDEFGHJKLMNPQRSTUVWXYZ"),
        choice("abcdefghijkmnopqrstuvwxyz"),
        choice("23456789"),
        choice(TEMP_PASSWORD_SPECIALS),
    ]
    remaining = [choice(TEMP_PASSWORD_CHARS) for _ in range(TEMP_PASSWORD_LENGTH - len(required_characters))]
    password_characters = required_characters + remaining
    for index in range(len(password_characters) - 1, 0, -1):
        swap_index = randbelow(index + 1)
        password_characters[index], password_characters[swap_index] = password_characters[swap_index], password_characters[index]
    return "".join(password_characters)


def log_activity(*, user=None, action, instance=None, description="", ip_address=None, metadata=None):
    ActivityLog.objects.create(
        user=user if getattr(user, "is_authenticated", False) else None,
        action=action,
        model_name=instance.__class__.__name__ if instance is not None else "",
        object_id=str(instance.pk) if getattr(instance, "pk", None) else "",
        object_repr=str(instance)[:255] if instance is not None else "",
        description=description,
        ip_address=ip_address,
        metadata=metadata or {},
    )


def _money(value, *, field_name="Amount"):
    try:
        return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError(f"{field_name} must be a valid amount.")


def _choice_values(choices):
    return {value for value, _label in choices}


def _validate_choice(value, *, allowed_values, field_name):
    value = (value or "").strip()
    if value not in allowed_values:
        raise ValidationError(f"Invalid {field_name}.")
    return value


def _tax_rate(value):
    try:
        rate = Decimal(value or "0").quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, TypeError, ValueError):
        raise ValidationError("Tax rate must be a valid decimal rate.")
    if rate < 0 or rate > Decimal("1.0000"):
        raise ValidationError("Tax rate must be between 0 and 1.")
    return rate


def _next_category_code(*, category, field_name):
    prefix = category.barcode_prefix or category.name[:3].upper()
    prefix = "".join(character for character in prefix.upper() if character.isalnum()) or "PRD"
    next_number = Product.objects.filter(**{f"{field_name}__startswith": f"{prefix}-"}).count() + 1
    while True:
        code = f"{prefix}-{next_number:04d}"
        if not Product.objects.filter(**{field_name: code}).exists():
            return code
        next_number += 1


def generate_product_sku(category):
    return _next_category_code(category=category, field_name="sku")


def generate_product_barcode(category):
    return _next_category_code(category=category, field_name="barcode")


def create_inventory_log(
    *,
    item_type,
    action,
    quantity_before,
    quantity_change,
    quantity_after,
    user=None,
    note="",
    reason="",
    product=None,
    sale=None,
):
    InventoryLog.objects.create(
        item_type=item_type,
        action=action,
        quantity_before=quantity_before,
        quantity_change=quantity_change,
        quantity_after=quantity_after,
        user=user,
        note=note,
        reason=reason,
        product=product,
        sale=sale,
    )


def _available_batch_stock(product):
    return (
        ProductionBatch.objects.filter(product=product, quantity_remaining__gt=0)
        .aggregate(total=Sum("quantity_remaining"))["total"]
        or 0
    )


def _ensure_legacy_batch(product):
    if ProductionBatch.objects.filter(product=product).exists() or product.stock_quantity <= 0:
        return
    ProductionBatch.objects.create(
        product=product,
        batch_number=f"LEGACY-{product.pk}",
        production_date=product.production_date or timezone.localdate(),
        expiry_date=product.expiry_date,
        quantity_produced=product.stock_quantity,
        quantity_remaining=product.stock_quantity,
    )


def _fifo_batches_for_update(product):
    return (
        ProductionBatch.objects.select_for_update()
        .filter(product=product, quantity_remaining__gt=0)
        .order_by(F("expiry_date").asc(nulls_last=True), "production_date", "created_at", "pk")
    )


def allocate_product_stock(*, product, quantity, sale_item=None):
    quantity = int(quantity)
    if quantity <= 0:
        raise ValidationError("Quantity must be positive.")

    product = Product.objects.select_for_update().get(pk=product.pk)
    _ensure_legacy_batch(product)
    if product.stock_quantity < quantity or _available_batch_stock(product) < quantity:
        raise ValidationError(f"Not enough stock for {product.name}.")

    remaining = quantity
    allocations = []
    for batch in _fifo_batches_for_update(product):
        if remaining <= 0:
            break
        allocated = min(batch.quantity_remaining, remaining)
        before = batch.quantity_remaining
        batch.quantity_remaining = before - allocated
        batch.save(update_fields=["quantity_remaining", "updated_at"])
        if sale_item is not None:
            allocations.append(BatchAllocation.objects.create(sale_item=sale_item, batch=batch, quantity=allocated))
        remaining -= allocated

    if remaining:
        raise ValidationError(f"Not enough batch stock for {product.name}.")

    Product.objects.filter(pk=product.pk).update(stock_quantity=F("stock_quantity") - quantity)
    product.refresh_from_db()
    return product, allocations


def restore_sale_item_allocations(*, sale_item):
    restored_quantity = 0
    for allocation in sale_item.batch_allocations.select_related("batch").filter(restored_at__isnull=True):
        batch = ProductionBatch.objects.select_for_update().get(pk=allocation.batch_id)
        batch.quantity_remaining = F("quantity_remaining") + allocation.quantity
        batch.save(update_fields=["quantity_remaining", "updated_at"])
        allocation.restored_at = timezone.now()
        allocation.save(update_fields=["restored_at", "updated_at"])
        restored_quantity += allocation.quantity
    return restored_quantity


def _format_stock_quantity(value):
    value = Decimal(value)
    if value == value.to_integral_value():
        return str(value.quantize(Decimal("1")))
    return str(value)


@transaction.atomic
def increase_product_balance_for_batch(product, quantity, user=None, note="", reason=InventoryLog.REASON_RESTOCK):
    quantity = int(quantity)
    if quantity <= 0:
        raise ValidationError("Quantity must be positive.")
    product = Product.objects.select_for_update().get(pk=product.pk)
    before = Decimal(product.stock_quantity)
    Product.objects.filter(pk=product.pk).update(stock_quantity=F("stock_quantity") + quantity)
    product.refresh_from_db()
    create_inventory_log(
        item_type=InventoryLog.ITEM_PRODUCT,
        action=InventoryLog.ACTION_RESTOCK,
        quantity_before=before,
        quantity_change=Decimal(quantity),
        quantity_after=Decimal(product.stock_quantity),
        user=user,
        note=note,
        reason=reason,
        product=product,
    )
    log_activity(
        user=user,
        action=ActivityLog.ACTION_STOCK,
        instance=product,
        description=note or f"Product stock changed by {_format_stock_quantity(quantity)}.",
        metadata={"before": str(before), "change": str(quantity), "after": str(product.stock_quantity), "reason": reason},
    )
    return product


@transaction.atomic
def adjust_product_stock(product, quantity_change, user=None, note="", action=InventoryLog.ACTION_ADJUSTMENT, reason=""):
    quantity_change = int(quantity_change)
    product = Product.objects.select_for_update().get(pk=product.pk)
    before = Decimal(product.stock_quantity)
    after = before + Decimal(quantity_change)
    if after < 0:
        raise ValidationError(f"Stock for {product.name} cannot go below zero.")
    if quantity_change > 0:
        ProductionBatch.objects.create(
            product=product,
            batch_number=f"ADJ-{timezone.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6].upper()}",
            production_date=timezone.localdate(),
            quantity_produced=quantity_change,
            quantity_remaining=quantity_change,
            recorded_by=user if getattr(user, "is_authenticated", False) else None,
            notes=note,
        )
        Product.objects.filter(pk=product.pk).update(stock_quantity=F("stock_quantity") + quantity_change)
        product.refresh_from_db()
    elif quantity_change < 0:
        product, _allocations = allocate_product_stock(product=product, quantity=abs(quantity_change))
    create_inventory_log(
        item_type=InventoryLog.ITEM_PRODUCT,
        action=action,
        quantity_before=before,
        quantity_change=Decimal(quantity_change),
        quantity_after=Decimal(product.stock_quantity),
        user=user,
        note=note,
        reason=reason,
        product=product,
    )
    log_activity(
        user=user,
        action=ActivityLog.ACTION_STOCK,
        instance=product,
        description=note or f"Product stock changed by {_format_stock_quantity(quantity_change)}.",
        metadata={"before": str(before), "change": str(quantity_change), "after": str(product.stock_quantity), "reason": reason},
    )
    return product


@transaction.atomic
def restock_product(product, quantity, user=None, note="", reason=InventoryLog.REASON_RESTOCK):
    return adjust_product_stock(
        product=product,
        quantity_change=quantity,
        user=user,
        note=note,
        action=InventoryLog.ACTION_RESTOCK,
        reason=reason,
    )


def _generate_receipt_number():
    stamp = timezone.localtime().strftime("%Y%m%d%H%M%S")
    return f"OR-{stamp}-{uuid.uuid4().hex[:8].upper()}"


def _discount_amount(subtotal, discount_type, promo_discount_amount):
    if discount_type in (Sale.DISCOUNT_SENIOR, Sale.DISCOUNT_PWD):
        return _money(subtotal * Decimal("0.20"))
    if discount_type == Sale.DISCOUNT_PROMO:
        promo_discount_amount = _money(promo_discount_amount or "0", field_name="Promo discount amount")
        if promo_discount_amount < 0:
            raise ValidationError("Promo discount amount cannot be negative.")
        return min(promo_discount_amount, subtotal)
    return Decimal("0.00")


@transaction.atomic
def create_sale(
    *,
    cashier,
    payment_type,
    payment_amount,
    items,
    notes="",
    sale_channel=Sale.CHANNEL_WALK_IN,
    discount_type=Sale.DISCOUNT_NONE,
    promo_discount_amount="0",
    tax_rate="0",
):
    if not items:
        raise ValidationError("At least one item is required to complete the sale.")

    payment_type = _validate_choice(
        payment_type,
        allowed_values=_choice_values(Sale.PAYMENT_CHOICES),
        field_name="payment type",
    )
    sale_channel = _validate_choice(
        sale_channel,
        allowed_values=_choice_values(Sale.CHANNEL_CHOICES),
        field_name="sale channel",
    )
    discount_type = _validate_choice(
        discount_type,
        allowed_values=_choice_values(Sale.DISCOUNT_CHOICES),
        field_name="discount type",
    )
    payment_amount = _money(payment_amount, field_name="Payment amount")
    tax_rate = _tax_rate(tax_rate)
    subtotal = Decimal("0.00")
    normalized_items = []
    requested_quantities = {}

    for item in items:
        try:
            product_id = int(item["product_id"])
            quantity = int(item["quantity"])
        except (KeyError, TypeError, ValueError):
            raise ValidationError("Invalid product or quantity in sale items.")
        if quantity <= 0:
            raise ValidationError("Invalid product or quantity in sale items.")
        requested_quantities[product_id] = requested_quantities.get(product_id, 0) + quantity

    products = {
        product.id: product
        for product in Product.objects.select_for_update().filter(id__in=requested_quantities.keys(), is_active=True, is_archived=False, is_deleted=False)
    }
    if len(products) != len(requested_quantities):
        raise ValidationError("Invalid product or quantity in sale items.")

    for product_id, quantity in requested_quantities.items():
        product = products[product_id]
        if product.stock_quantity < quantity:
            raise ValidationError(f"Not enough stock for {product.name}.")

        line_total = product.price * quantity
        subtotal += line_total
        normalized_items.append(
            {
                "product": product,
                "quantity": quantity,
                "unit_price": product.price,
                "unit_cost": product.cost,
                "line_total": line_total,
            }
        )

    discount_amount = _discount_amount(subtotal, discount_type, promo_discount_amount)
    taxable_amount = subtotal - discount_amount
    tax_amount = _money(taxable_amount * tax_rate)
    total_amount = _money(taxable_amount + tax_amount)

    if payment_amount < total_amount:
        raise ValidationError("Payment amount must cover the total sale amount.")

    sale = Sale.objects.create(
        receipt_number=_generate_receipt_number(),
        cashier=cashier,
        sale_channel=sale_channel,
        payment_type=payment_type,
        subtotal=subtotal,
        discount_type=discount_type,
        discount_amount=discount_amount,
        tax_rate=tax_rate,
        tax_amount=tax_amount,
        total_amount=total_amount,
        payment_amount=payment_amount,
        change_amount=payment_amount - total_amount,
        notes=notes,
    )

    for item in normalized_items:
        product = item["product"]
        quantity = item["quantity"]
        before = Decimal(product.stock_quantity)
        sale_item = SaleItem.objects.create(sale=sale, **item)
        product, _allocations = allocate_product_stock(product=product, quantity=quantity, sale_item=sale_item)
        create_inventory_log(
            item_type=InventoryLog.ITEM_PRODUCT,
            action=InventoryLog.ACTION_SALE,
            quantity_before=before,
            quantity_change=Decimal(-quantity),
            quantity_after=Decimal(product.stock_quantity),
            user=cashier,
            note=f"Sold via {sale.receipt_number}",
            product=product,
            sale=sale,
        )
    log_activity(
        user=cashier,
        action=ActivityLog.ACTION_SALE,
        instance=sale,
        description=f"Completed sale {sale.receipt_number}.",
        metadata={"total": str(sale.total_amount), "discount": str(sale.discount_amount), "tax": str(sale.tax_amount)},
    )
    return sale


@transaction.atomic
def void_sale(*, sale, approved_by, reason):
    reason = (reason or "").strip()
    if not reason:
        raise ValidationError("Void reason is required.")

    sale = Sale.objects.select_for_update().prefetch_related("items__product").get(pk=sale.pk)
    if sale.status == Sale.STATUS_VOIDED:
        raise ValidationError("This sale is already voided.")

    for item in sale.items.select_related("product"):
        product = Product.objects.select_for_update().get(pk=item.product_id)
        before = Decimal(product.stock_quantity)
        restore_sale_item_allocations(sale_item=item)
        Product.objects.filter(pk=product.pk).update(stock_quantity=F("stock_quantity") + item.quantity)
        product.refresh_from_db()
        create_inventory_log(
            item_type=InventoryLog.ITEM_PRODUCT,
            action=InventoryLog.ACTION_VOID,
            quantity_before=before,
            quantity_change=Decimal(item.quantity),
            quantity_after=Decimal(product.stock_quantity),
            user=approved_by,
            note=f"Voided sale {sale.receipt_number}: {reason}",
            reason=InventoryLog.REASON_RETURNED,
            product=product,
            sale=sale,
        )
        VoidedSaleItem.objects.create(
            sale=sale,
            product=product,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
            reason=reason,
        )
    sale.status = Sale.STATUS_VOIDED
    sale.void_reason = reason
    sale.voided_by = approved_by
    sale.voided_at = timezone.now()
    sale.save(update_fields=["status", "void_reason", "voided_by", "voided_at", "updated_at"])
    log_activity(
        user=approved_by,
        action=ActivityLog.ACTION_VOID,
        instance=sale,
        description=f"Voided sale {sale.receipt_number}.",
        metadata={"reason": reason},
    )
    return sale

