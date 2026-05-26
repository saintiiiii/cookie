from django.urls import path

from bakery.views.inventory import (
    InventoryDashboardView,
    InventoryLogListView,
    ProductionBatchCreateView,
    ProductionBatchDeleteView,
    ProductionBatchListView,
    ProductionBatchUpdateView,
    restock_product_view,
)

urlpatterns = [
    path("inventory/", InventoryDashboardView.as_view(), name="inventory-dashboard"),
    path("products/<int:pk>/restock/", restock_product_view, name="product-restock"),
    path("production/", ProductionBatchListView.as_view(), name="production-batch-list"),
    path("production/add/", ProductionBatchCreateView.as_view(), name="production-batch-add"),
    path("production/<int:pk>/edit/", ProductionBatchUpdateView.as_view(), name="production-batch-edit"),
    path("production/<int:pk>/delete/", ProductionBatchDeleteView.as_view(), name="production-batch-delete"),
    path("inventory/logs/", InventoryLogListView.as_view(), name="inventory-logs"),
]
