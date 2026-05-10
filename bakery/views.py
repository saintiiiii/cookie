import csv
import shutil
from datetime import timedelta
from decimal import Decimal
from io import BytesIO

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth.views import LoginView, LogoutView
from django.core.exceptions import ValidationError
from django.db import connections, transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Q, Sum
from django.db.models.deletion import ProtectedError
from django.db.models.functions import TruncDate
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.views.generic import CreateView, DeleteView, FormView, ListView, TemplateView, UpdateView
from openpyxl import Workbook
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from .forms import (
    AdminPasswordResetForm,
    BackupRestoreForm,
    CategoryForm,
    EmployeeCreateForm,
    EmployeeUpdateForm,
    IngredientForm,
    IngredientPurchaseForm,
    LoginForm,
    OrderForm,
    ProductionBatchForm,
    ProductForm,
    RecipeForm,
    RestockIngredientForm,
    RestockProductForm,
    SupplierForm,
    VoidSaleForm,
)
from .models import ActivityLog, Category, Ingredient, IngredientPurchase, InventoryLog, LoginHistory, Order, Product, ProductionBatch, Recipe, Sale, Supplier
from .permissions import RoleRequiredMixin, user_has_role
from .services import (
    ROLE_ADMIN,
    ROLE_CASHIER,
    ROLE_INVENTORY,
    adjust_ingredient_stock,
    adjust_product_stock,
    bootstrap_default_categories,
    bootstrap_roles,
    create_sale,
    log_activity,
    reconcile_purchase_update,
    record_purchase,
    reverse_purchase_stock,
    void_sale,
)


STOCK_STATUS_CHOICES = [
    ("in", "In Stock"),
    ("low", "Low Stock"),
    ("out", "Out of Stock"),
]

PRODUCT_SORT_CHOICES = [
    ("name", "Name"),
    ("newest", "Newest"),
    ("oldest", "Oldest"),
    ("stock_low", "Lowest Stock"),
    ("stock_high", "Highest Stock"),
]

SALE_SORT_CHOICES = [
    ("newest", "Newest"),
    ("oldest", "Oldest"),
    ("total_high", "Highest Total"),
    ("total_low", "Lowest Total"),
]


def client_ip(request):
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def is_owner_account(user):
    if not user:
        return False
    if user.username == "admin":
        return True
    return user.is_superuser and User.objects.filter(is_superuser=True, is_active=True).count() <= 1


def filter_products_by_status(queryset, status):
    if status == "in":
        return queryset.filter(stock_quantity__gt=F("low_stock_threshold"))
    if status == "low":
        return queryset.filter(stock_quantity__gt=0, stock_quantity__lte=F("low_stock_threshold"))
    if status == "out":
        return queryset.filter(stock_quantity=0)
    return queryset


def filter_ingredients_by_status(queryset, status):
    if status == "in":
        return queryset.filter(quantity_in_stock__gt=F("reorder_level"))
    if status == "low":
        return queryset.filter(quantity_in_stock__gt=0, quantity_in_stock__lte=F("reorder_level"))
    if status == "out":
        return queryset.filter(quantity_in_stock__lte=0)
    return queryset


class BakeryLoginView(LoginView):
    template_name = "bakery/login.html"
    authentication_form = LoginForm

    def dispatch(self, request, *args, **kwargs):
        bootstrap_roles()
        bootstrap_default_categories()
        return super().dispatch(request, *args, **kwargs)


class BakeryLogoutView(LogoutView):
    pass


class DashboardView(RoleRequiredMixin, TemplateView):
    template_name = "bakery/dashboard.html"
    allowed_roles = (ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        today = timezone.localdate()
        month_start = today.replace(day=1)
        sales_today = Sale.objects.filter(sold_at__date=today, status=Sale.STATUS_COMPLETED)
        sales_month = Sale.objects.filter(sold_at__date__gte=month_start, status=Sale.STATUS_COMPLETED)

        top_products = (
            Product.objects.filter(sale_items__sale__status=Sale.STATUS_COMPLETED)
            .annotate(total_sold=Sum("sale_items__quantity", filter=Q(sale_items__sale__status=Sale.STATUS_COMPLETED)))
            .order_by("-total_sold", "name")[:5]
        )
        recent_transactions = Sale.objects.select_related("cashier").prefetch_related("items__product")[:6]
        low_products = Product.objects.filter(stock_quantity__lte=F("low_stock_threshold"), is_active=True).order_by("stock_quantity")[:6]
        low_ingredients = Ingredient.objects.filter(quantity_in_stock__lte=F("reorder_level")).order_by("quantity_in_stock")[:6]
        active_products = Product.objects.filter(is_archived=False)
        sales_series = (
            Sale.objects.filter(sold_at__date__gte=today - timedelta(days=6), status=Sale.STATUS_COMPLETED)
            .annotate(day=TruncDate("sold_at"))
            .values("day")
            .annotate(total=Sum("total_amount"))
            .order_by("day")
        )

        context.update(
            {
                "daily_sales": sales_today.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00"),
                "monthly_sales": sales_month.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00"),
                "recent_transactions": recent_transactions,
                "top_products": top_products,
                "low_products": low_products,
                "low_ingredients": low_ingredients,
                "low_stock_count": low_products.count() + low_ingredients.count(),
                "chart_labels": [entry["day"].strftime("%b %d") for entry in sales_series],
                "chart_values": [float(entry["total"]) for entry in sales_series],
                "inventory_chart_labels": ["In Stock", "Low Stock", "Out of Stock"],
                "inventory_chart_values": [
                    filter_products_by_status(active_products, "in").count(),
                    filter_products_by_status(active_products, "low").count(),
                    filter_products_by_status(active_products, "out").count(),
                ],
            }
        )
        return context


class BaseListView(RoleRequiredMixin, ListView):
    paginate_by = 10
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)


class BaseCreateView(RoleRequiredMixin, CreateView):
    template_name = "bakery/form.html"
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            user=self.request.user,
            action=ActivityLog.ACTION_CREATE,
            instance=self.object,
            description=f"Created {self.object}.",
            ip_address=client_ip(self.request),
        )
        return response


class BaseUpdateView(RoleRequiredMixin, UpdateView):
    template_name = "bakery/form.html"
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            user=self.request.user,
            action=ActivityLog.ACTION_UPDATE,
            instance=self.object,
            description=f"Updated {self.object}.",
            ip_address=client_ip(self.request),
        )
        return response


class BaseDeleteView(RoleRequiredMixin, DeleteView):
    template_name = "bakery/confirm_delete.html"
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)

    def form_valid(self, form):
        log_activity(
            user=self.request.user,
            action=ActivityLog.ACTION_DELETE,
            instance=self.object,
            description=f"Deleted {self.object}.",
            ip_address=client_ip(self.request),
        )
        return super().form_valid(form)


class CategoryListView(BaseListView):
    model = Category
    template_name = "bakery/category_list.html"


class CategoryCreateView(BaseCreateView):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy("category-list")


class CategoryUpdateView(BaseUpdateView):
    model = Category
    form_class = CategoryForm
    success_url = reverse_lazy("category-list")


class CategoryDeleteView(BaseDeleteView):
    model = Category
    success_url = reverse_lazy("category-list")


class ProductListView(BaseListView):
    model = Product
    template_name = "bakery/product_list.html"
    paginate_by = 12
    category_form_class = CategoryForm

    def get_queryset(self):
        queryset = Product.objects.select_related("category", "supplier")
        search = self.request.GET.get("search", "").strip()
        category = self.request.GET.get("category", "")
        status = self.request.GET.get("status", "")
        sort = self.request.GET.get("sort", "name")
        archived = self.request.GET.get("archived", "")
        if not archived:
            queryset = queryset.filter(is_archived=False)
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(sku__icontains=search)
                | Q(barcode__icontains=search)
                | Q(item_id__icontains=search)
                | Q(category__name__icontains=search)
                | Q(supplier__name__icontains=search)
            )
        if category:
            queryset = queryset.filter(category_id=category)
        queryset = filter_products_by_status(queryset, status)
        if sort == "newest":
            queryset = queryset.order_by("-created_at", "name")
        elif sort == "oldest":
            queryset = queryset.order_by("created_at", "name")
        elif sort == "stock_low":
            queryset = queryset.order_by("stock_quantity", "name")
        elif sort == "stock_high":
            queryset = queryset.order_by("-stock_quantity", "name")
        else:
            queryset = queryset.order_by("name")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "categories": Category.objects.all(),
                "category_form": kwargs.get("category_form") or self.category_form_class(),
                "stock_status_choices": STOCK_STATUS_CHOICES,
                "sort_choices": PRODUCT_SORT_CHOICES,
                "show_category_modal": kwargs.get("show_category_modal", False),
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        form = self.category_form_class(request.POST)
        if form.is_valid():
            category = form.save()
            log_activity(
                user=request.user,
                action=ActivityLog.ACTION_CREATE,
                instance=category,
                description=f"Created category {category.name} from the product page.",
                ip_address=client_ip(request),
            )
            messages.success(request, f"Category {category.name} created successfully.")
            return redirect("product-list")

        self.object_list = self.get_queryset()
        messages.error(request, "Could not create category. Please check the details below.")
        return self.render_to_response(
            self.get_context_data(
                category_form=form,
                show_category_modal=True,
            )
        )


class ProductCreateView(BaseCreateView):
    model = Product
    form_class = ProductForm
    success_url = reverse_lazy("product-list")


class ProductUpdateView(BaseUpdateView):
    model = Product
    form_class = ProductForm
    success_url = reverse_lazy("product-list")


class ProductDeleteView(BaseDeleteView):
    model = Product
    success_url = reverse_lazy("product-list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            self.object.is_archived = True
            self.object.is_active = False
            self.object.save(update_fields=["is_archived", "is_active", "updated_at"])
            log_activity(
                user=request.user,
                action=ActivityLog.ACTION_ARCHIVE,
                instance=self.object,
                description=f"Archived {self.object} because it is referenced by transactions.",
                ip_address=client_ip(request),
            )
            messages.warning(request, "Product is used by transactions, so it was archived instead of deleted.")
            return redirect(self.success_url)


@login_required
@require_POST
def archive_product_view(request, pk):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_INVENTORY):
        return redirect("dashboard")
    product = get_object_or_404(Product, pk=pk)
    product.is_archived = True
    product.is_active = False
    product.save(update_fields=["is_archived", "is_active", "updated_at"])
    log_activity(
        user=request.user,
        action=ActivityLog.ACTION_ARCHIVE,
        instance=product,
        description=f"Archived product {product.name}.",
        ip_address=client_ip(request),
    )
    messages.success(request, f"{product.name} archived.")
    return redirect(request.POST.get("next") or "product-list")


class InventoryDashboardView(RoleRequiredMixin, TemplateView):
    template_name = "bakery/inventory_dashboard.html"
    allowed_roles = (ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = self.request.GET.get("search", "").strip()
        item_type = self.request.GET.get("type", "")
        category = self.request.GET.get("category", "")
        status = self.request.GET.get("status", "")

        products = Product.objects.select_related("category").order_by("name")
        ingredients = Ingredient.objects.select_related("supplier").order_by("name")

        if search:
            products = products.filter(Q(name__icontains=search) | Q(sku__icontains=search) | Q(category__name__icontains=search))
            ingredients = ingredients.filter(Q(name__icontains=search) | Q(unit__icontains=search) | Q(supplier__name__icontains=search))
        if category:
            products = products.filter(category_id=category)
            ingredients = Ingredient.objects.none()

        products = filter_products_by_status(products, status)
        ingredients = filter_ingredients_by_status(ingredients, status)

        if item_type == "products":
            ingredients = Ingredient.objects.none()
        elif item_type == "ingredients":
            products = Product.objects.none()

        inventory_rows = [
            {
                "kind": "Product",
                "name": product.name,
                "sku": product.sku,
                "item_id": product.item_id,
                "barcode": product.barcode,
                "category": product.category.name,
                "category_color": product.category.color,
                "available_stock": product.stock_quantity,
                "reserved_stock": product.reserved_stock,
                "sold_stock": product.sold_stock,
                "unit": "pcs",
                "cost_price": product.cost,
                "price": product.price,
                "supplier": product.supplier.name if product.supplier else "",
                "production_date": product.production_date,
                "expiration_date": product.expiry_date,
                "status": product.display_status,
                "stock_status": product.stock_status,
                "image": product.product_image,
                "object": product,
            }
            for product in products
        ]
        inventory_rows.extend(
            [
                {
                    "kind": "Stock Item",
                    "name": ingredient.name,
                    "sku": f"STK-{ingredient.pk:04d}",
                    "item_id": f"ING-{ingredient.pk:04d}",
                    "barcode": "",
                    "category": "Raw Material",
                    "category_color": "#64748b",
                    "available_stock": ingredient.quantity_in_stock,
                    "reserved_stock": 0,
                    "sold_stock": 0,
                    "unit": ingredient.unit,
                    "cost_price": ingredient.cost_per_unit,
                    "price": ingredient.cost_per_unit,
                    "supplier": ingredient.supplier.name if ingredient.supplier else "",
                    "production_date": None,
                    "expiration_date": ingredient.expiration_date,
                    "status": ingredient.stock_status,
                    "stock_status": ingredient.stock_status,
                    "image": None,
                    "object": ingredient,
                }
                for ingredient in ingredients
            ]
        )

        stock_issues = Product.objects.filter(stock_quantity__lte=F("low_stock_threshold"), is_active=True).count()
        stock_issues += Ingredient.objects.filter(quantity_in_stock__lte=F("reorder_level")).count()

        context.update(
            {
                "inventory_rows": inventory_rows,
                "categories": Category.objects.all(),
                "stock_status_choices": STOCK_STATUS_CHOICES,
                "sku_total": Product.objects.count() + Ingredient.objects.count(),
                "products_reserved": Order.objects.exclude(status=Order.STATUS_CLAIMED).aggregate(total=Sum("quantity"))["total"] or 0,
                "stock_issues": stock_issues,
                "featured_stock": inventory_rows[0] if inventory_rows else None,
                "can_manage_inventory": user_has_role(self.request.user, ROLE_ADMIN, ROLE_INVENTORY),
            }
        )
        return context


class IngredientListView(BaseListView):
    model = Ingredient
    template_name = "bakery/ingredient_list.html"

    def get_queryset(self):
        queryset = Ingredient.objects.select_related("supplier")
        search = self.request.GET.get("search", "").strip()
        supplier = self.request.GET.get("supplier", "")
        status = self.request.GET.get("status", "")
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(unit__icontains=search) | Q(supplier__name__icontains=search))
        if supplier:
            queryset = queryset.filter(supplier_id=supplier)
        queryset = filter_ingredients_by_status(queryset, status)
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "suppliers": Supplier.objects.all(),
                "stock_status_choices": STOCK_STATUS_CHOICES,
            }
        )
        return context


class IngredientCreateView(BaseCreateView):
    model = Ingredient
    form_class = IngredientForm
    success_url = reverse_lazy("ingredient-list")


class IngredientUpdateView(BaseUpdateView):
    model = Ingredient
    form_class = IngredientForm
    success_url = reverse_lazy("ingredient-list")


class IngredientDeleteView(BaseDeleteView):
    model = Ingredient
    success_url = reverse_lazy("ingredient-list")


class RecipeListView(BaseListView):
    model = Recipe
    template_name = "bakery/recipe_list.html"

    def get_queryset(self):
        return Recipe.objects.select_related("product", "ingredient")


class RecipeCreateView(BaseCreateView):
    model = Recipe
    form_class = RecipeForm
    success_url = reverse_lazy("recipe-list")


class RecipeUpdateView(BaseUpdateView):
    model = Recipe
    form_class = RecipeForm
    success_url = reverse_lazy("recipe-list")


class RecipeDeleteView(BaseDeleteView):
    model = Recipe
    success_url = reverse_lazy("recipe-list")


class SupplierListView(BaseListView):
    model = Supplier
    template_name = "bakery/supplier_list.html"


class SupplierCreateView(BaseCreateView):
    model = Supplier
    form_class = SupplierForm
    success_url = reverse_lazy("supplier-list")


class SupplierUpdateView(BaseUpdateView):
    model = Supplier
    form_class = SupplierForm
    success_url = reverse_lazy("supplier-list")


class SupplierDeleteView(BaseDeleteView):
    model = Supplier
    success_url = reverse_lazy("supplier-list")


class OrderListView(BaseListView):
    model = Order
    template_name = "bakery/order_list.html"
    allowed_roles = (ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY)


class OrderCreateView(BaseCreateView):
    model = Order
    form_class = OrderForm
    success_url = reverse_lazy("order-list")
    allowed_roles = (ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY)


class OrderUpdateView(BaseUpdateView):
    model = Order
    form_class = OrderForm
    success_url = reverse_lazy("order-list")
    allowed_roles = (ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY)


class OrderDeleteView(BaseDeleteView):
    model = Order
    success_url = reverse_lazy("order-list")
    allowed_roles = (ROLE_ADMIN, ROLE_CASHIER)


class ProductionBatchListView(BaseListView):
    model = ProductionBatch
    template_name = "bakery/production_batch_list.html"
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)

    def get_queryset(self):
        queryset = ProductionBatch.objects.select_related("product", "recorded_by")
        search = self.request.GET.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(product__name__icontains=search) | Q(batch_number__icontains=search))
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["today"] = timezone.localdate()
        return context


class ProductionBatchCreateView(BaseCreateView):
    model = ProductionBatch
    form_class = ProductionBatchForm
    success_url = reverse_lazy("production-batch-list")
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)

    def form_valid(self, form):
        try:
            with transaction.atomic():
                self.object = form.save(commit=False)
                self.object.recorded_by = self.request.user
                self.object.save()
                adjust_product_stock(
                    self.object.product,
                    self.object.quantity_produced,
                    self.request.user,
                    f"Production batch {self.object.batch_number}",
                    InventoryLog.ACTION_RESTOCK,
                    reason=InventoryLog.REASON_RESTOCK,
                )
                log_activity(
                    user=self.request.user,
                    action=ActivityLog.ACTION_CREATE,
                    instance=self.object,
                    description=f"Recorded production batch {self.object.batch_number}.",
                    ip_address=client_ip(self.request),
                )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Production batch recorded and stock updated.")
        return redirect(self.get_success_url())


class ProductionBatchUpdateView(BaseUpdateView):
    model = ProductionBatch
    form_class = ProductionBatchForm
    success_url = reverse_lazy("production-batch-list")
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)


class ProductionBatchDeleteView(BaseDeleteView):
    model = ProductionBatch
    success_url = reverse_lazy("production-batch-list")
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)


class PurchaseListView(BaseListView):
    model = IngredientPurchase
    template_name = "bakery/purchase_list.html"

    def get_queryset(self):
        return IngredientPurchase.objects.select_related("supplier", "ingredient")


class PurchaseCreateView(BaseCreateView):
    model = IngredientPurchase
    form_class = IngredientPurchaseForm
    success_url = reverse_lazy("purchase-list")

    def form_valid(self, form):
        with transaction.atomic():
            self.object = form.save()
            record_purchase(purchase=self.object, user=self.request.user)
        messages.success(self.request, "Ingredient purchase recorded and stock updated.")
        return redirect(self.get_success_url())


class PurchaseUpdateView(BaseUpdateView):
    model = IngredientPurchase
    form_class = IngredientPurchaseForm
    success_url = reverse_lazy("purchase-list")

    def form_valid(self, form):
        previous_purchase = IngredientPurchase.objects.select_related("ingredient", "supplier").get(pk=self.object.pk)
        try:
            with transaction.atomic():
                self.object = form.save()
                reconcile_purchase_update(
                    purchase=self.object,
                    previous_purchase=previous_purchase,
                    user=self.request.user,
                )
        except ValidationError as exc:
            form.add_error(None, exc)
            return self.form_invalid(form)
        messages.success(self.request, "Purchase updated and stock reconciled.")
        return redirect(self.get_success_url())


class PurchaseDeleteView(BaseDeleteView):
    model = IngredientPurchase
    success_url = reverse_lazy("purchase-list")

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        try:
            with transaction.atomic():
                reverse_purchase_stock(purchase=self.object, user=request.user)
                self.object.delete()
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
            return redirect(self.get_success_url())
        messages.success(request, "Purchase deleted and stock reconciled.")
        return redirect(self.get_success_url())


class InventoryLogListView(BaseListView):
    model = InventoryLog
    template_name = "bakery/inventory_log_list.html"
    paginate_by = 20

    def get_queryset(self):
        return InventoryLog.objects.select_related("product", "ingredient", "user", "sale", "purchase")


class ActivityLogListView(RoleRequiredMixin, ListView):
    model = ActivityLog
    template_name = "bakery/activity_log_list.html"
    paginate_by = 25
    allowed_roles = (ROLE_ADMIN,)

    def get_queryset(self):
        queryset = ActivityLog.objects.select_related("user")
        action = self.request.GET.get("action", "")
        search = self.request.GET.get("search", "").strip()
        if action:
            queryset = queryset.filter(action=action)
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search)
                | Q(model_name__icontains=search)
                | Q(object_repr__icontains=search)
                | Q(description__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["action_choices"] = ActivityLog.ACTION_CHOICES
        return context


class LoginHistoryListView(RoleRequiredMixin, ListView):
    model = LoginHistory
    template_name = "bakery/login_history_list.html"
    paginate_by = 25
    allowed_roles = (ROLE_ADMIN,)

    def get_queryset(self):
        queryset = LoginHistory.objects.select_related("user")
        search = self.request.GET.get("search", "").strip()
        if search:
            queryset = queryset.filter(Q(username__icontains=search) | Q(user__username__icontains=search) | Q(ip_address__icontains=search))
        return queryset


class EmployeeListView(RoleRequiredMixin, ListView):
    model = User
    template_name = "bakery/employee_list.html"
    paginate_by = 12
    allowed_roles = (ROLE_ADMIN,)

    def dispatch(self, request, *args, **kwargs):
        bootstrap_roles()
        return super().dispatch(request, *args, **kwargs)

    def get_queryset(self):
        queryset = User.objects.prefetch_related("groups").order_by("username")
        search = self.request.GET.get("search", "").strip()
        role = self.request.GET.get("role", "")
        status = self.request.GET.get("status", "")
        if search:
            queryset = queryset.filter(Q(username__icontains=search) | Q(first_name__icontains=search) | Q(last_name__icontains=search) | Q(email__icontains=search))
        if role:
            queryset = queryset.filter(groups__name=role)
        if status == "active":
            queryset = queryset.filter(is_active=True)
        elif status == "archived":
            queryset = queryset.filter(is_active=False)
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["roles"] = [ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY]
        context["protected_user_ids"] = [user.pk for user in User.objects.filter(username="admin")] + (
            [User.objects.filter(is_superuser=True, is_active=True).first().pk]
            if User.objects.filter(is_superuser=True, is_active=True).count() == 1
            else []
        )
        return context


class EmployeeCreateView(RoleRequiredMixin, CreateView):
    model = User
    form_class = EmployeeCreateForm
    template_name = "bakery/employee_form.html"
    success_url = reverse_lazy("employee-list")
    allowed_roles = (ROLE_ADMIN,)

    def dispatch(self, request, *args, **kwargs):
        bootstrap_roles()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        response = super().form_valid(form)
        log_activity(
            user=self.request.user,
            action=ActivityLog.ACTION_CREATE,
            instance=self.object,
            description=f"Created employee account {self.object.username}.",
            ip_address=client_ip(self.request),
        )
        messages.success(self.request, "Employee account created.")
        return response


class EmployeeUpdateView(RoleRequiredMixin, UpdateView):
    model = User
    form_class = EmployeeUpdateForm
    template_name = "bakery/form.html"
    success_url = reverse_lazy("employee-list")
    allowed_roles = (ROLE_ADMIN,)

    def dispatch(self, request, *args, **kwargs):
        bootstrap_roles()
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        if is_owner_account(self.object) and not form.cleaned_data.get("is_active", True):
            form.add_error("is_active", "The main owner/admin account cannot be archived.")
            return self.form_invalid(form)
        response = super().form_valid(form)
        log_activity(
            user=self.request.user,
            action=ActivityLog.ACTION_UPDATE,
            instance=self.object,
            description=f"Updated employee account {self.object.username}.",
            ip_address=client_ip(self.request),
        )
        messages.success(self.request, "Employee account updated.")
        return response


class EmployeeDeleteView(RoleRequiredMixin, DeleteView):
    model = User
    template_name = "bakery/confirm_delete.html"
    success_url = reverse_lazy("employee-list")
    allowed_roles = (ROLE_ADMIN,)

    def post(self, request, *args, **kwargs):
        self.object = self.get_object()
        if is_owner_account(self.object):
            messages.error(request, "The main owner/admin account cannot be deleted.")
            return redirect(self.success_url)
        log_activity(
            user=request.user,
            action=ActivityLog.ACTION_DELETE,
            instance=self.object,
            description=f"Deleted employee account {self.object.username}.",
            ip_address=client_ip(request),
        )
        return super().post(request, *args, **kwargs)


@login_required
@require_POST
def archive_employee_view(request, pk):
    if not user_has_role(request.user, ROLE_ADMIN):
        return redirect("dashboard")
    employee = get_object_or_404(User, pk=pk)
    if is_owner_account(employee):
        messages.error(request, "The main owner/admin account cannot be archived.")
        return redirect("employee-list")
    employee.is_active = False
    employee.save(update_fields=["is_active"])
    log_activity(
        user=request.user,
        action=ActivityLog.ACTION_ARCHIVE,
        instance=employee,
        description=f"Archived employee account {employee.username}.",
        ip_address=client_ip(request),
    )
    messages.success(request, f"{employee.username} archived.")
    return redirect("employee-list")


class EmployeePasswordResetView(RoleRequiredMixin, FormView):
    template_name = "bakery/employee_form.html"
    form_class = AdminPasswordResetForm
    success_url = reverse_lazy("employee-list")
    allowed_roles = (ROLE_ADMIN,)

    def dispatch(self, request, *args, **kwargs):
        self.employee = get_object_or_404(User, pk=kwargs["pk"])
        return super().dispatch(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["user"] = self.employee
        return kwargs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["form_title"] = f"Reset password for {self.employee.username}"
        return context

    def form_valid(self, form):
        form.save()
        log_activity(
            user=self.request.user,
            action=ActivityLog.ACTION_PASSWORD,
            instance=self.employee,
            description=f"Reset password for {self.employee.username}.",
            ip_address=client_ip(self.request),
        )
        messages.success(self.request, "Employee password reset.")
        return super().form_valid(form)


class SaleListView(RoleRequiredMixin, ListView):
    model = Sale
    template_name = "bakery/sale_list.html"
    paginate_by = 12
    allowed_roles = (ROLE_ADMIN, ROLE_CASHIER)

    def get_queryset(self):
        queryset = Sale.objects.select_related("cashier", "voided_by").prefetch_related("items__product")
        search = self.request.GET.get("search", "").strip()
        payment = self.request.GET.get("payment", "")
        status = self.request.GET.get("status", "")
        channel = self.request.GET.get("channel", "")
        sort = self.request.GET.get("sort", "newest")
        if search:
            queryset = queryset.filter(
                Q(receipt_number__icontains=search)
                | Q(cashier__username__icontains=search)
                | Q(items__product__name__icontains=search)
                | Q(items__product__barcode__icontains=search)
            ).distinct()
        if payment:
            queryset = queryset.filter(payment_type=payment)
        if status:
            queryset = queryset.filter(status=status)
        if channel:
            queryset = queryset.filter(sale_channel=channel)
        if sort == "oldest":
            queryset = queryset.order_by("sold_at", "id")
        elif sort == "total_high":
            queryset = queryset.order_by("-total_amount", "-sold_at")
        elif sort == "total_low":
            queryset = queryset.order_by("total_amount", "-sold_at")
        else:
            queryset = queryset.order_by("-sold_at", "-id")
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "payment_types": Sale.PAYMENT_CHOICES,
                "status_choices": Sale.STATUS_CHOICES,
                "channel_choices": Sale.CHANNEL_CHOICES,
                "sort_choices": SALE_SORT_CHOICES,
                "can_void_sales": user_has_role(self.request.user, ROLE_ADMIN),
            }
        )
        return context


@login_required
def sale_receipt_view(request, pk):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_CASHIER):
        return redirect("dashboard")
    sale = get_object_or_404(Sale.objects.select_related("cashier", "voided_by").prefetch_related("items__product", "voided_items__product"), pk=pk)
    return render(request, "bakery/receipt.html", {"sale": sale, "void_form": VoidSaleForm(), "can_void_sales": user_has_role(request.user, ROLE_ADMIN)})


@login_required
def pos_view(request):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_CASHIER):
        return redirect("dashboard")
    products = Product.objects.filter(is_active=True, is_archived=False).select_related("category").order_by("category__name", "name")
    if request.method == "POST":
        product_ids = request.POST.getlist("product_id")
        quantities = request.POST.getlist("quantity")
        items = [{"product_id": product_id, "quantity": quantity} for product_id, quantity in zip(product_ids, quantities) if product_id and quantity]
        try:
            sale = create_sale(
                cashier=request.user,
                payment_type=request.POST.get("payment_type", Sale.PAYMENT_CASH),
                payment_amount=request.POST.get("payment_amount", "0"),
                items=items,
                notes=request.POST.get("notes", ""),
                sale_channel=request.POST.get("sale_channel", Sale.CHANNEL_WALK_IN),
                discount_type=request.POST.get("discount_type", Sale.DISCOUNT_NONE),
                promo_discount_amount=request.POST.get("promo_discount_amount", "0"),
                tax_rate=request.POST.get("tax_rate", "0"),
            )
            messages.success(request, f"Transaction {sale.receipt_number} saved successfully.")
            return redirect("sale-receipt", pk=sale.pk)
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    return render(
        request,
        "bakery/pos.html",
        {
            "products": products,
            "payment_types": Sale.PAYMENT_CHOICES,
            "channel_choices": Sale.CHANNEL_CHOICES,
            "discount_choices": Sale.DISCOUNT_CHOICES,
        },
    )


@login_required
@require_POST
def void_sale_view(request, pk):
    if not user_has_role(request.user, ROLE_ADMIN):
        messages.error(request, "Only an admin can approve a void transaction.")
        return redirect("sale-receipt", pk=pk)
    sale = get_object_or_404(Sale, pk=pk)
    form = VoidSaleForm(request.POST)
    if form.is_valid():
        try:
            void_sale(sale=sale, approved_by=request.user, reason=form.cleaned_data["reason"])
            messages.success(request, f"{sale.receipt_number} voided and stock restored.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Void reason is required.")
    return redirect("sale-receipt", pk=pk)


@login_required
@require_POST
def restock_product_view(request, pk):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_INVENTORY):
        return redirect("dashboard")
    product = get_object_or_404(Product, pk=pk)
    form = RestockProductForm(request.POST)
    if form.is_valid():
        quantity_change = form.signed_quantity()
        reason = form.cleaned_data.get("reason") or ""
        note = form.cleaned_data["note"] or ("Manual product restock" if quantity_change > 0 else f"Manual product deduction: {dict(InventoryLog.REASON_CHOICES).get(reason, reason)}")
        try:
            adjust_product_stock(
                product,
                quantity_change,
                request.user,
                note,
                InventoryLog.ACTION_RESTOCK if quantity_change > 0 else InventoryLog.ACTION_ADJUSTMENT,
                reason=reason,
            )
            movement = "increased" if quantity_change > 0 else "decreased"
            messages.success(request, f"{product.name} stock {movement} successfully.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Could not update product stock. Check the quantity and deduction reason.")
    return redirect(request.POST.get("next") or "product-list")


@login_required
@require_POST
def restock_ingredient_view(request, pk):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_INVENTORY):
        return redirect("dashboard")
    ingredient = get_object_or_404(Ingredient, pk=pk)
    form = RestockIngredientForm(request.POST)
    if form.is_valid():
        quantity_change = form.signed_quantity()
        reason = form.cleaned_data.get("reason") or ""
        note = form.cleaned_data["note"] or ("Manual stock restock" if quantity_change > 0 else f"Manual stock deduction: {dict(InventoryLog.REASON_CHOICES).get(reason, reason)}")
        try:
            adjust_ingredient_stock(
                ingredient,
                quantity_change,
                request.user,
                note,
                action=InventoryLog.ACTION_RESTOCK if quantity_change > 0 else InventoryLog.ACTION_ADJUSTMENT,
                reason=reason,
            )
            movement = "increased" if quantity_change > 0 else "decreased"
            messages.success(request, f"{ingredient.name} stock {movement} successfully.")
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
    else:
        messages.error(request, "Could not update ingredient stock. Check the quantity and deduction reason.")
    return redirect(request.POST.get("next") or "ingredient-list")


class ReportsView(RoleRequiredMixin, TemplateView):
    template_name = "bakery/reports.html"
    allowed_roles = (ROLE_ADMIN, ROLE_INVENTORY)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        sales = Sale.objects.exclude(status=Sale.STATUS_VOIDED).prefetch_related("items__product")
        total_sales = sales.aggregate(total=Sum("total_amount"))["total"] or Decimal("0.00")
        total_profit = sum(sale.total_profit for sale in sales)
        product_profits = Product.objects.annotate(
            total_sold=Sum("sale_items__quantity", filter=Q(sale_items__sale__status=Sale.STATUS_COMPLETED)),
            profit_value=Sum(
                ExpressionWrapper(
                    (F("sale_items__unit_price") - F("sale_items__unit_cost")) * F("sale_items__quantity"),
                    output_field=DecimalField(max_digits=12, decimal_places=2),
                ),
                filter=Q(sale_items__sale__status=Sale.STATUS_COMPLETED),
            ),
        ).order_by("-profit_value")
        context.update(
            {
                "sales": sales[:12],
                "total_sales": total_sales,
                "total_profit": total_profit,
                "product_profits": product_profits[:6],
                "low_products": Product.objects.filter(stock_quantity__lte=F("low_stock_threshold")),
                "low_ingredients": Ingredient.objects.filter(quantity_in_stock__lte=F("reorder_level")),
                "expired_products": Product.objects.filter(expiry_date__lt=timezone.localdate(), is_archived=False),
                "voided_sales": Sale.objects.filter(status=Sale.STATUS_VOIDED)[:8],
                "restore_form": BackupRestoreForm(),
            }
        )
        return context


@login_required
def sales_excel_export(request):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_INVENTORY):
        return redirect("dashboard")
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sales Report"
    sheet.append(["Receipt", "Cashier", "Date", "Payment Type", "Total Amount", "Profit"])
    for sale in Sale.objects.exclude(status=Sale.STATUS_VOIDED).select_related("cashier"):
        sheet.append(
            [
                sale.receipt_number,
                sale.cashier.username,
                timezone.localtime(sale.sold_at).strftime("%Y-%m-%d %H:%M"),
                sale.get_payment_type_display(),
                float(sale.total_amount),
                float(sale.total_profit),
            ]
        )
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    response = HttpResponse(
        output.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = 'attachment; filename="bakery-sales-report.xlsx"'
    return response


@login_required
def sales_pdf_export(request):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_INVENTORY):
        return redirect("dashboard")
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(30, height - 40, "Bakery Sales Report")
    pdf.setFont("Helvetica", 10)
    y = height - 80
    headers = ["Receipt", "Cashier", "Date", "Total", "Profit"]
    x_positions = [30, 130, 230, 360, 450]
    for index, header in enumerate(headers):
        pdf.drawString(x_positions[index], y, header)
    y -= 18
    for sale in Sale.objects.exclude(status=Sale.STATUS_VOIDED).select_related("cashier")[:30]:
        row = [
            sale.receipt_number,
            sale.cashier.username,
            timezone.localtime(sale.sold_at).strftime("%Y-%m-%d"),
            f"PHP {sale.total_amount:,.2f}",
            f"PHP {sale.total_profit:,.2f}",
        ]
        for index, value in enumerate(row):
            pdf.drawString(x_positions[index], y, str(value))
        y -= 16
        if y < 50:
            pdf.showPage()
            y = height - 40
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = 'attachment; filename="bakery-sales-report.pdf"'
    return response


@login_required
def sales_csv_export(request):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_INVENTORY):
        return redirect("dashboard")
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="bakery-sales-report.csv"'
    writer = csv.writer(response)
    writer.writerow(["Receipt", "Cashier", "Date", "Channel", "Payment Type", "Subtotal", "Discount", "Tax", "Total", "Status"])
    for sale in Sale.objects.select_related("cashier"):
        writer.writerow(
            [
                sale.receipt_number,
                sale.cashier.username,
                timezone.localtime(sale.sold_at).strftime("%Y-%m-%d %H:%M"),
                sale.get_sale_channel_display(),
                sale.get_payment_type_display(),
                sale.subtotal,
                sale.discount_amount,
                sale.tax_amount,
                sale.total_amount,
                sale.get_status_display(),
            ]
        )
    log_activity(
        user=request.user,
        action=ActivityLog.ACTION_BACKUP,
        description="Exported sales CSV report.",
        ip_address=client_ip(request),
    )
    return response


@login_required
def backup_database_view(request):
    if not user_has_role(request.user, ROLE_ADMIN):
        return redirect("dashboard")
    from django.conf import settings

    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        messages.warning(request, "Database backup download is only available for SQLite in this build.")
        return redirect("reports")
    db_path = settings.DATABASES["default"]["NAME"]
    with open(db_path, "rb") as file_handle:
        response = HttpResponse(file_handle.read(), content_type="application/octet-stream")
        response["Content-Disposition"] = 'attachment; filename="bakery-backup.sqlite3"'
        log_activity(
            user=request.user,
            action=ActivityLog.ACTION_BACKUP,
            description="Downloaded SQLite database backup.",
            ip_address=client_ip(request),
        )
        return response


@login_required
@require_POST
def restore_database_view(request):
    if not user_has_role(request.user, ROLE_ADMIN):
        return redirect("dashboard")
    if settings.DATABASES["default"]["ENGINE"] != "django.db.backends.sqlite3":
        messages.warning(request, "Database restore upload is only available for SQLite in this build.")
        return redirect("reports")
    form = BackupRestoreForm(request.POST, request.FILES)
    if not form.is_valid():
        messages.error(request, "Could not restore backup. Please upload a valid SQLite backup file.")
        return redirect("reports")

    db_path = settings.DATABASES["default"]["NAME"]
    uploaded = form.cleaned_data["backup_file"]
    current_backup_path = settings.BASE_DIR / f"db-before-restore-{timezone.now().strftime('%Y%m%d%H%M%S')}.sqlite3"
    connections.close_all()
    shutil.copy2(db_path, current_backup_path)
    with open(db_path, "wb") as destination:
        for chunk in uploaded.chunks():
            destination.write(chunk)
    log_activity(
        user=request.user,
        action=ActivityLog.ACTION_RESTORE,
        description=f"Restored SQLite database from uploaded backup. Previous copy: {current_backup_path.name}",
        ip_address=client_ip(request),
    )
    messages.success(request, f"Database restored. Previous database was saved as {current_backup_path.name}.")
    return redirect("reports")


@login_required
def printable_receipt_pdf(request, pk):
    if not user_has_role(request.user, ROLE_ADMIN, ROLE_CASHIER):
        return redirect("dashboard")
    sale = get_object_or_404(Sale.objects.prefetch_related("items__product"), pk=pk)
    buffer = BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=(80 * mm, 200 * mm))
    y = 520
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawCentredString(113, y, "Sweet Crumbs Bakery")
    y -= 20
    pdf.setFont("Helvetica", 9)
    pdf.drawString(20, y, f"Receipt: {sale.receipt_number}")
    y -= 14
    pdf.drawString(20, y, f"Date: {timezone.localtime(sale.sold_at).strftime('%Y-%m-%d %H:%M')}")
    y -= 20
    pdf.setStrokeColor(colors.grey)
    pdf.line(15, y, 210, y)
    y -= 14
    for item in sale.items.all():
        pdf.drawString(20, y, f"{item.product.name} x{item.quantity}")
        pdf.drawRightString(200, y, f"{item.line_total:,.2f}")
        y -= 14
    pdf.line(15, y, 210, y)
    y -= 16
    pdf.drawString(20, y, "Subtotal")
    pdf.drawRightString(200, y, f"{sale.subtotal:,.2f}")
    y -= 14
    pdf.drawString(20, y, "Discount")
    pdf.drawRightString(200, y, f"-{sale.discount_amount:,.2f}")
    y -= 14
    pdf.drawString(20, y, "Tax")
    pdf.drawRightString(200, y, f"{sale.tax_amount:,.2f}")
    y -= 14
    pdf.drawString(20, y, "Total")
    pdf.drawRightString(200, y, f"{sale.total_amount:,.2f}")
    y -= 14
    pdf.drawString(20, y, "Payment")
    pdf.drawRightString(200, y, f"{sale.payment_amount:,.2f}")
    y -= 14
    pdf.drawString(20, y, "Change")
    pdf.drawRightString(200, y, f"{sale.change_amount:,.2f}")
    if sale.is_voided:
        y -= 14
        pdf.drawString(20, y, "Status")
        pdf.drawRightString(200, y, "VOIDED")
    y -= 24
    pdf.drawCentredString(113, y, "Thank you for your order!")
    pdf.save()
    buffer.seek(0)
    response = HttpResponse(buffer.getvalue(), content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="{sale.receipt_number}.pdf"'
    return response
