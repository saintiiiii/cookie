from django.urls import path

from bakery.views.catalog import (
    CategoryCreateView,
    CategoryDeleteView,
    CategoryListView,
    CategoryUpdateView,
    ProductCreateView,
    ProductDeleteView,
    ProductListView,
    ProductUpdateView,
    SupplierCreateView,
    SupplierDeleteView,
    SupplierListView,
    SupplierUpdateView,
    archive_product_view,
)

urlpatterns = [
    path("categories/", CategoryListView.as_view(), name="category-list"),
    path("categories/add/", CategoryCreateView.as_view(), name="category-add"),
    path("categories/<int:pk>/edit/", CategoryUpdateView.as_view(), name="category-edit"),
    path("categories/<int:pk>/delete/", CategoryDeleteView.as_view(), name="category-delete"),
    path("products/", ProductListView.as_view(), name="product-list"),
    path("products/add/", ProductCreateView.as_view(), name="product-add"),
    path("products/<int:pk>/edit/", ProductUpdateView.as_view(), name="product-edit"),
    path("products/<int:pk>/delete/", ProductDeleteView.as_view(), name="product-delete"),
    path("products/<int:pk>/archive/", archive_product_view, name="product-archive"),
    path("suppliers/", SupplierListView.as_view(), name="supplier-list"),
    path("suppliers/add/", SupplierCreateView.as_view(), name="supplier-add"),
    path("suppliers/<int:pk>/edit/", SupplierUpdateView.as_view(), name="supplier-edit"),
    path("suppliers/<int:pk>/delete/", SupplierDeleteView.as_view(), name="supplier-delete"),
]
