from django.db.models import F


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


def filter_products_by_status(queryset, status):
    if status == "in":
        return queryset.filter(stock_quantity__gt=F("low_stock_threshold"))
    if status == "low":
        return queryset.filter(stock_quantity__gt=0, stock_quantity__lte=F("low_stock_threshold"))
    if status == "out":
        return queryset.filter(stock_quantity=0)
    return queryset
