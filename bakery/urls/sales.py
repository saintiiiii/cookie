from django.urls import path

from bakery.views.sales import (
    SaleListView,
    pos_view,
    printable_receipt_pdf,
    sale_receipt_view,
    void_sale_view,
)

urlpatterns = [
    path("sales/pos/", pos_view, name="pos"),
    path("sales/", SaleListView.as_view(), name="sale-list"),
    path("sales/<int:pk>/receipt/", sale_receipt_view, name="sale-receipt"),
    path("sales/<int:pk>/void/", void_sale_view, name="sale-void"),
    path("sales/<int:pk>/receipt.pdf", printable_receipt_pdf, name="sale-receipt-pdf"),
]
