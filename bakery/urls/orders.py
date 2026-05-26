from django.urls import path

from bakery.views.orders import OrderCreateView, OrderDeleteView, OrderListView, OrderUpdateView

urlpatterns = [
    path("orders/", OrderListView.as_view(), name="order-list"),
    path("orders/add/", OrderCreateView.as_view(), name="order-add"),
    path("orders/<int:pk>/edit/", OrderUpdateView.as_view(), name="order-edit"),
    path("orders/<int:pk>/delete/", OrderDeleteView.as_view(), name="order-delete"),
]
