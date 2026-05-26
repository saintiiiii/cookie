from django.urls import path

from bakery.views.reports import (
    ReportsView,
    backup_database_view,
    restore_database_view,
    sales_csv_export,
    sales_excel_export,
    sales_pdf_export,
)

urlpatterns = [
    path("reports/", ReportsView.as_view(), name="reports"),
    path("reports/sales.xlsx", sales_excel_export, name="sales-excel"),
    path("reports/sales.pdf", sales_pdf_export, name="sales-pdf"),
    path("reports/sales.csv", sales_csv_export, name="sales-csv"),
    path("backup/database/", backup_database_view, name="backup-database"),
    path("backup/restore/", restore_database_view, name="restore-database"),
]
