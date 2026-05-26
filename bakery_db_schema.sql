-- Bakery database schema dump
-- Generated from active Django MySQL database: bakery_db
CREATE DATABASE IF NOT EXISTS `bakery_db` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE `bakery_db`;
CREATE TABLE `auth_group` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `auth_group_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `group_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_group_permissions_group_id_permission_id_0cd325b0_uniq` (`group_id`,`permission_id`),
  KEY `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_group_permissio_permission_id_84c5c92e_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_group_permissions_group_id_b120cbf9_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `auth_permission` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type_id` int NOT NULL,
  `codename` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_permission_content_type_id_codename_01ab375a_uniq` (`content_type_id`,`codename`),
  CONSTRAINT `auth_permission_content_type_id_2f476e4b_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=85 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `auth_user` (
  `id` int NOT NULL AUTO_INCREMENT,
  `password` varchar(128) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_login` datetime(6) DEFAULT NULL,
  `is_superuser` tinyint(1) NOT NULL,
  `username` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `first_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `last_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(254) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_staff` tinyint(1) NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  `date_joined` datetime(6) NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `auth_user_groups` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `group_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_groups_user_id_group_id_94350c0c_uniq` (`user_id`,`group_id`),
  KEY `auth_user_groups_group_id_97559544_fk_auth_group_id` (`group_id`),
  CONSTRAINT `auth_user_groups_group_id_97559544_fk_auth_group_id` FOREIGN KEY (`group_id`) REFERENCES `auth_group` (`id`),
  CONSTRAINT `auth_user_groups_user_id_6a12ed8b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `auth_user_user_permissions` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `user_id` int NOT NULL,
  `permission_id` int NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `auth_user_user_permissions_user_id_permission_id_14a6b632_uniq` (`user_id`,`permission_id`),
  KEY `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` (`permission_id`),
  CONSTRAINT `auth_user_user_permi_permission_id_1fbb5f2c_fk_auth_perm` FOREIGN KEY (`permission_id`) REFERENCES `auth_permission` (`id`),
  CONSTRAINT `auth_user_user_permissions_user_id_a95ead1b_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_activitylog` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `action` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model_name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `object_id` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `object_repr` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `ip_address` char(39) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `metadata` json NOT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `bakery_activitylog_user_id_119aab98_fk_auth_user_id` (`user_id`),
  CONSTRAINT `bakery_activitylog_user_id_119aab98_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=14 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_category` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `name` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `barcode_prefix` varchar(12) COLLATE utf8mb4_unicode_ci NOT NULL,
  `color` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `name` (`name`)
) ENGINE=InnoDB AUTO_INCREMENT=11 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_inventorylog` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `item_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `quantity_before` decimal(12,2) NOT NULL,
  `quantity_change` decimal(12,2) NOT NULL,
  `quantity_after` decimal(12,2) NOT NULL,
  `note` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int DEFAULT NULL,
  `product_id` bigint DEFAULT NULL,
  `sale_id` bigint DEFAULT NULL,
  `reason` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  KEY `bakery_inventorylog_user_id_47dd1a22_fk_auth_user_id` (`user_id`),
  KEY `bakery_inventorylog_product_id_8b2c1652_fk_bakery_product_id` (`product_id`),
  KEY `bakery_inventorylog_sale_id_fb6c00a0_fk_bakery_sale_id` (`sale_id`),
  CONSTRAINT `bakery_inventorylog_product_id_8b2c1652_fk_bakery_product_id` FOREIGN KEY (`product_id`) REFERENCES `bakery_product` (`id`),
  CONSTRAINT `bakery_inventorylog_sale_id_fb6c00a0_fk_bakery_sale_id` FOREIGN KEY (`sale_id`) REFERENCES `bakery_sale` (`id`),
  CONSTRAINT `bakery_inventorylog_user_id_47dd1a22_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_loginhistory` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `username` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ip_address` char(39) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_agent` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `user_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `bakery_loginhistory_user_id_58d22984_fk_auth_user_id` (`user_id`),
  CONSTRAINT `bakery_loginhistory_user_id_58d22984_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=18 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_note` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `title` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `content` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_active` tinyint(1) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_order` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `customer_name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `order_date` date NOT NULL,
  `pickup_date` date NOT NULL,
  `quantity` int unsigned NOT NULL,
  `estimated_total` decimal(12,2) NOT NULL,
  `notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `product_id` bigint DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `bakery_order_product_id_37b2a5a0_fk_bakery_product_id` (`product_id`),
  CONSTRAINT `bakery_order_product_id_37b2a5a0_fk_bakery_product_id` FOREIGN KEY (`product_id`) REFERENCES `bakery_product` (`id`),
  CONSTRAINT `bakery_order_chk_1` CHECK ((`quantity` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_product` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sku` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `price` decimal(10,2) NOT NULL,
  `cost` decimal(10,2) NOT NULL,
  `stock_quantity` int unsigned NOT NULL,
  `low_stock_threshold` int unsigned NOT NULL,
  `product_image` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_active` tinyint(1) NOT NULL,
  `category_id` bigint NOT NULL,
  `barcode` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `expiry_date` date DEFAULT NULL,
  `is_archived` tinyint(1) NOT NULL,
  `item_id` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `production_date` date DEFAULT NULL,
  `storage_location` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `supplier_id` bigint DEFAULT NULL,
  `theme_color` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `sku` (`sku`),
  UNIQUE KEY `barcode` (`barcode`),
  UNIQUE KEY `item_id` (`item_id`),
  KEY `bakery_product_category_id_26ba2cd9_fk_bakery_category_id` (`category_id`),
  KEY `bakery_product_supplier_id_f7543b26_fk_bakery_supplier_id` (`supplier_id`),
  CONSTRAINT `bakery_product_category_id_26ba2cd9_fk_bakery_category_id` FOREIGN KEY (`category_id`) REFERENCES `bakery_category` (`id`),
  CONSTRAINT `bakery_product_supplier_id_f7543b26_fk_bakery_supplier_id` FOREIGN KEY (`supplier_id`) REFERENCES `bakery_supplier` (`id`),
  CONSTRAINT `bakery_product_chk_1` CHECK ((`stock_quantity` >= 0)),
  CONSTRAINT `bakery_product_chk_2` CHECK ((`low_stock_threshold` >= 0))
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_productionbatch` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `batch_number` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `production_date` date NOT NULL,
  `expiry_date` date DEFAULT NULL,
  `quantity_produced` int unsigned NOT NULL,
  `quantity_remaining` int unsigned NOT NULL,
  `notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `product_id` bigint NOT NULL,
  `recorded_by_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `bakery_productionbatch_product_id_batch_number_8d59bba0_uniq` (`product_id`,`batch_number`),
  KEY `bakery_productionbatch_recorded_by_id_74af255f_fk_auth_user_id` (`recorded_by_id`),
  CONSTRAINT `bakery_productionbatch_product_id_3ec7817b_fk_bakery_product_id` FOREIGN KEY (`product_id`) REFERENCES `bakery_product` (`id`),
  CONSTRAINT `bakery_productionbatch_recorded_by_id_74af255f_fk_auth_user_id` FOREIGN KEY (`recorded_by_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `bakery_productionbatch_chk_1` CHECK ((`quantity_produced` >= 0)),
  CONSTRAINT `bakery_productionbatch_chk_2` CHECK ((`quantity_remaining` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_sale` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `receipt_number` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `payment_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `subtotal` decimal(12,2) NOT NULL,
  `total_amount` decimal(12,2) NOT NULL,
  `payment_amount` decimal(12,2) NOT NULL,
  `change_amount` decimal(12,2) NOT NULL,
  `notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `sold_at` datetime(6) NOT NULL,
  `cashier_id` int NOT NULL,
  `discount_amount` decimal(12,2) NOT NULL,
  `discount_type` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sale_channel` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci NOT NULL,
  `tax_amount` decimal(12,2) NOT NULL,
  `tax_rate` decimal(5,4) NOT NULL,
  `void_reason` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `voided_at` datetime(6) DEFAULT NULL,
  `voided_by_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `receipt_number` (`receipt_number`),
  KEY `bakery_sale_cashier_id_408036e6_fk_auth_user_id` (`cashier_id`),
  KEY `bakery_sale_voided_by_id_f3591a64_fk_auth_user_id` (`voided_by_id`),
  CONSTRAINT `bakery_sale_cashier_id_408036e6_fk_auth_user_id` FOREIGN KEY (`cashier_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `bakery_sale_voided_by_id_f3591a64_fk_auth_user_id` FOREIGN KEY (`voided_by_id`) REFERENCES `auth_user` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_saleitem` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `quantity` int unsigned NOT NULL,
  `unit_price` decimal(10,2) NOT NULL,
  `unit_cost` decimal(10,2) NOT NULL,
  `line_total` decimal(12,2) NOT NULL,
  `product_id` bigint NOT NULL,
  `sale_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `bakery_saleitem_product_id_1516b635_fk_bakery_product_id` (`product_id`),
  KEY `bakery_saleitem_sale_id_0fe32d12_fk_bakery_sale_id` (`sale_id`),
  CONSTRAINT `bakery_saleitem_product_id_1516b635_fk_bakery_product_id` FOREIGN KEY (`product_id`) REFERENCES `bakery_product` (`id`),
  CONSTRAINT `bakery_saleitem_sale_id_0fe32d12_fk_bakery_sale_id` FOREIGN KEY (`sale_id`) REFERENCES `bakery_sale` (`id`),
  CONSTRAINT `bakery_saleitem_chk_1` CHECK ((`quantity` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_supplier` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `name` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `contact_person` varchar(150) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `email` varchar(254) COLLATE utf8mb4_unicode_ci NOT NULL,
  `address` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `notes` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `bakery_voidedsaleitem` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `created_at` datetime(6) NOT NULL,
  `updated_at` datetime(6) NOT NULL,
  `quantity` int unsigned NOT NULL,
  `unit_price` decimal(10,2) NOT NULL,
  `line_total` decimal(12,2) NOT NULL,
  `reason` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `product_id` bigint NOT NULL,
  `sale_id` bigint NOT NULL,
  PRIMARY KEY (`id`),
  KEY `bakery_voidedsaleitem_product_id_9ff9824a_fk_bakery_product_id` (`product_id`),
  KEY `bakery_voidedsaleitem_sale_id_a6ac7f23_fk_bakery_sale_id` (`sale_id`),
  CONSTRAINT `bakery_voidedsaleitem_product_id_9ff9824a_fk_bakery_product_id` FOREIGN KEY (`product_id`) REFERENCES `bakery_product` (`id`),
  CONSTRAINT `bakery_voidedsaleitem_sale_id_a6ac7f23_fk_bakery_sale_id` FOREIGN KEY (`sale_id`) REFERENCES `bakery_sale` (`id`),
  CONSTRAINT `bakery_voidedsaleitem_chk_1` CHECK ((`quantity` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `django_admin_log` (
  `id` int NOT NULL AUTO_INCREMENT,
  `action_time` datetime(6) NOT NULL,
  `object_id` longtext COLLATE utf8mb4_unicode_ci,
  `object_repr` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `action_flag` smallint unsigned NOT NULL,
  `change_message` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `content_type_id` int DEFAULT NULL,
  `user_id` int NOT NULL,
  PRIMARY KEY (`id`),
  KEY `django_admin_log_content_type_id_c4bce8eb_fk_django_co` (`content_type_id`),
  KEY `django_admin_log_user_id_c564eba6_fk_auth_user_id` (`user_id`),
  CONSTRAINT `django_admin_log_content_type_id_c4bce8eb_fk_django_co` FOREIGN KEY (`content_type_id`) REFERENCES `django_content_type` (`id`),
  CONSTRAINT `django_admin_log_user_id_c564eba6_fk_auth_user_id` FOREIGN KEY (`user_id`) REFERENCES `auth_user` (`id`),
  CONSTRAINT `django_admin_log_chk_1` CHECK ((`action_flag` >= 0))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `django_content_type` (
  `id` int NOT NULL AUTO_INCREMENT,
  `app_label` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `model` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `django_content_type_app_label_model_76bd3d3b_uniq` (`app_label`,`model`)
) ENGINE=InnoDB AUTO_INCREMENT=22 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `django_migrations` (
  `id` bigint NOT NULL AUTO_INCREMENT,
  `app` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `name` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `applied` datetime(6) NOT NULL,
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=23 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE `django_session` (
  `session_key` varchar(40) COLLATE utf8mb4_unicode_ci NOT NULL,
  `session_data` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `expire_date` datetime(6) NOT NULL,
  PRIMARY KEY (`session_key`),
  KEY `django_session_expire_date_a5c62663` (`expire_date`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

