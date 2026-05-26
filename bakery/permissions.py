from .services import ROLE_ADMIN, ROLE_CASHIER, ROLE_INVENTORY
from .mixins.views import RoleRequiredMixin


def user_has_role(user, *roles):
    if not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    return user.groups.filter(name__in=roles).exists()
