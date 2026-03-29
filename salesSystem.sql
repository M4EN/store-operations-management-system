create database salesSystem;
USE salesSystem;

create table warehouse(
warehouse_id int auto_increment primary key,
warehouse_name varchar(32),
location varchar(32),
phone_number varchar (32)
);

create table branch(
branch_id int auto_increment primary key,
branch_name varchar(32),
location varchar(32),
phone_number varchar (32),
is_deleted int
);

create table employee(
employee_id int auto_increment primary key,
employee_name varchar(32),
phone_number varchar(32),
date_of_birth DATE,
position varchar (32),
salary decimal(10,2),
warehouse_id int NULL,
branch_id int NULL,
user_password varchar(32),
is_deleted int,
access_level varchar(32),
foreign key (warehouse_id) references warehouse(warehouse_id),
foreign key (branch_id) references branch(branch_id)
);

create table customer(
customer_id int auto_increment primary key,
customer_name varchar(32),
phone_number varchar(32),
date_of_birth DATE,
email varchar(100)
);

create table supplier(
supplier_id int auto_increment primary key,
supplier_name varchar(32),
location varchar(32),
phone_number varchar(32),
email varchar(100),
is_deleted int
);

create table product(
product_id int auto_increment primary key,
product_name varchar(32),
category varchar(32),
is_deleted int,
purchase_price_per_kg decimal(10,2),
sale_price_per_kg decimal(10,2)
);

create table purchase(
purchase_id int auto_increment primary key,
employee_id int NULL,
warehouse_id int,
supplier_id int,
purchase_date date,
is_deleted int,
foreign key (employee_id) references employee(employee_id),
foreign key (warehouse_id) references warehouse(warehouse_id),
foreign key (supplier_id) references supplier(supplier_id)
);

create table purchase_detail(
purchase_detail_id int auto_increment primary key,
purchase_id int,
product_id int,
quantity decimal(10,2),
kg_price_at_purchase_time decimal(10,2),
is_deleted int,
is_deleted_with_purchase int,
foreign key (purchase_id) references purchase(purchase_id),
foreign key (product_id) references product(product_id)
);

create table payment(
payment_id int auto_increment primary key,
purchase_id int,
employee_id int NULL,
payment_date date,
amount decimal(10,2),
method varchar(32),
is_deleted int,
is_deleted_with_purchase int,
foreign key (purchase_id) references purchase(purchase_id),
foreign key (employee_id) references employee(employee_id)
);

create table sale(
sale_id int auto_increment primary key,
customer_id int,
branch_id int,
employee_id int NULL,
sale_date date,
payment_method varchar(32),
is_deleted int,
foreign key (customer_id) references customer(customer_id) on delete SET NULL,
foreign key (branch_id) references branch(branch_id),
foreign key (employee_id) references employee(employee_id)
);

create table sale_detail(
sale_detail_id int auto_increment primary key,
sale_id int,
product_id int,
quantity decimal(10,2),
kg_price_at_sale_time decimal(10,2),
is_deleted int,
is_deleted_with_sale int,
foreign key (sale_id) references sale(sale_id),
foreign key (product_id) references product(product_id)
);

create table transfer(
transfer_id int auto_increment primary key,
warehouse_id int,
branch_id int,
employee_id int NULL,
transfer_date date,
foreign key (warehouse_id) references warehouse(warehouse_id),
foreign key (branch_id) references branch(branch_id),
foreign key (employee_id) references employee(employee_id)
);

create table transfer_detail(
transfer_detail_id int auto_increment primary key,
transfer_id int,
product_id int,
quantity decimal(10,2),
foreign key (transfer_id) references transfer(transfer_id),
foreign key (product_id) references product(product_id)
);

CREATE TABLE warehouse_stock (
    warehouse_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 0,
    is_deleted_with_warehouse int,
    PRIMARY KEY (warehouse_id, product_id),
    FOREIGN KEY (warehouse_id) REFERENCES warehouse(warehouse_id),
    FOREIGN KEY (product_id) REFERENCES product(product_id)
);

CREATE TABLE branch_stock (
    branch_id INT NOT NULL,
    product_id INT NOT NULL,
    quantity DECIMAL(10,2) NOT NULL DEFAULT 0,
    is_deleted_with_branch int,
    PRIMARY KEY (branch_id, product_id),
    FOREIGN KEY (branch_id) REFERENCES branch(branch_id),
    FOREIGN KEY (product_id) REFERENCES product(product_id)
);
-- Default warehouse for admin
INSERT INTO warehouse (warehouse_name, location, phone_number)
VALUES ('Main Warehouse', 'HQ', '0000000000');

-- Default admin employee
INSERT INTO employee (employee_name, phone_number, position, warehouse_id, branch_id, user_password, is_deleted, access_level)
VALUES ('Admin', '0000000000', 'Admin', 1, NULL, 'admin1234', NULL, 'admin');