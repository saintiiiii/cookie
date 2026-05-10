# Bakery Sales and Inventory System

A Django-based bakery management app for point-of-sale, inventory, ingredients, orders, suppliers, and reporting.

## Features

- Role-aware dashboard for Admin, Cashier, and Inventory Staff
- Product, ingredient, recipe, supplier, employee, production batch, and order management
- Product images, unique SKU/item ID/barcode values, supplier/date metadata, archive support, and category colors
- POS workflow with barcode lookup, walk-in/online sale type, discounts, tax, and automatic product and ingredient deduction
- Admin-approved sale voids with automatic stock restoration and voided-item records
- Inventory history logs and low-stock alerts
- Activity audit trail and login history
- Sales reporting with PDF, Excel, and CSV exports
- Printable browser receipt and PDF receipt output
- SQLite for development with MySQL and PostgreSQL environment support
- Backup download and restore upload for the SQLite database

## Setup

```bash
python -m pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py seed_bakery_demo
python manage.py runserver
```

## Demo Accounts

- `admin` / `Admin@123`
- `cashier` / `Cashier@123`
- `inventory` / `Inventory@123`

## Database Configuration

Set these environment variables to switch from SQLite to MySQL:

- `MYSQL_DB`
- `MYSQL_USER`
- `MYSQL_PASSWORD`
- `MYSQL_HOST`
- `MYSQL_PORT`

If `MYSQL_DB` is not set, you can still switch to PostgreSQL with:

- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `POSTGRES_HOST`
- `POSTGRES_PORT`

## Notes

- The seed command creates user roles, default employee accounts, and starter product categories. Products, stock items, suppliers, and transactions should be created through the app.
- Uploaded product images are stored in `media/products/`.
- The backup download route is intended for SQLite backups in development or small deployments.
- Passwords must be at least 8 characters and include uppercase, lowercase, number, and special character, such as `Example@123`.
