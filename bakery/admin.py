from django.contrib import admin

from .models import (
    ActivityLog,
    BatchAllocation,
    Category,
    EmployeeSecurity,
    InventoryLog,
    LoginHistory,
    Order,
    Product,
    ProductionBatch,
    Sale,
    SaleItem,
    Supplier,
    VoidedSaleItem,
)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "barcode", "category", "price", "cost", "stock_quantity", "display_status", "is_active", "is_archived")
    list_filter = ("category", "is_active", "is_archived", "expiry_date")
    search_fields = ("name", "sku", "barcode", "item_id")


class SaleItemInline(admin.TabularInline):
    model = SaleItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "line_total")


class BatchAllocationInline(admin.TabularInline):
    model = BatchAllocation
    extra = 0
    readonly_fields = ("batch", "quantity", "restored_at")
    can_delete = False


class VoidedSaleItemInline(admin.TabularInline):
    model = VoidedSaleItem
    extra = 0
    readonly_fields = ("product", "quantity", "unit_price", "line_total", "reason")


@admin.register(Sale)
class SaleAdmin(admin.ModelAdmin):
    list_display = ("receipt_number", "cashier", "sale_channel", "payment_type", "total_amount", "status", "sold_at")
    list_filter = ("payment_type", "sale_channel", "status", "sold_at")
    search_fields = ("receipt_number", "cashier__username")
    inlines = [SaleItemInline, VoidedSaleItemInline]


admin.site.register(Category)
admin.site.register(Order)
admin.site.register(Supplier)

@admin.register(InventoryLog)
class InventoryLogAdmin(admin.ModelAdmin):
    list_display = ("product", "action", "quantity_change", "quantity_after", "user", "created_at")
    readonly_fields = [field.name for field in InventoryLog._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("action", "model_name", "object_repr", "user", "created_at")
    readonly_fields = [field.name for field in ActivityLog._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(LoginHistory)
class LoginHistoryAdmin(admin.ModelAdmin):
    list_display = ("username", "action", "ip_address", "created_at")
    readonly_fields = [field.name for field in LoginHistory._meta.fields]

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(EmployeeSecurity)
class EmployeeSecurityAdmin(admin.ModelAdmin):
    list_display = ("user", "must_change_password", "temporary_password_created_at", "temporary_password_set_by")
    readonly_fields = ("created_at", "updated_at")


admin.site.register(ProductionBatch)
admin.site.register(BatchAllocation)
