from django.db.models import F

from .models import Ingredient, Product
from .permissions import user_has_role
from .services import ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY


def bakery_context(request):
    if not request.user.is_authenticated:
        return {}
    can_manage_inventory = user_has_role(request.user, ROLE_ADMIN, ROLE_INVENTORY)
    can_manage_sales = user_has_role(request.user, ROLE_ADMIN, ROLE_CASHIER)
    return {
        "sidebar_low_products": Product.objects.filter(stock_quantity__lte=F("low_stock_threshold"), is_active=True).count(),
        "sidebar_low_ingredients": Ingredient.objects.filter(quantity_in_stock__lte=F("reorder_level")).count(),
        "can_manage_inventory": can_manage_inventory,
        "can_manage_sales": can_manage_sales,
        "can_manage_users": user_has_role(request.user, ROLE_ADMIN),
        "can_view_inventory": user_has_role(request.user, ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY),
        "can_view_orders": user_has_role(request.user, ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY),
        "can_view_reports": can_manage_inventory,
    }
