from .audit import urlpatterns as audit_urlpatterns
from .auth import urlpatterns as auth_urlpatterns
from .catalog import urlpatterns as catalog_urlpatterns
from .dashboard import urlpatterns as dashboard_urlpatterns
from .inventory import urlpatterns as inventory_urlpatterns
from .orders import urlpatterns as order_urlpatterns
from .reports import urlpatterns as report_urlpatterns
from .sales import urlpatterns as sales_urlpatterns

urlpatterns = (
    auth_urlpatterns
    + dashboard_urlpatterns
    + catalog_urlpatterns
    + inventory_urlpatterns
    + order_urlpatterns
    + sales_urlpatterns
    + audit_urlpatterns
    + report_urlpatterns
)
