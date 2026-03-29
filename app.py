from datetime import datetime, date
from flask import Flask, render_template, request, redirect, session, url_for, flash
import mysql.connector

salesDB = mysql.connector.connect(  # Connect to the database
    host="localhost",
    user="your_username",
    passwd="your_password",
    database="salesSystem"
)
myCursor = salesDB.cursor()  # Cursor used to execute sql statements
myCursorDict = salesDB.cursor(dictionary=True)  # Cursor returns a dictionary

app = Flask(__name__)
app.secret_key = "122supersecret221"


@app.route('/')
@app.route('/login', methods=['GET', 'POST'])
def login():
    msg = ''
    if 'logged_in' in session:
        return redirect(url_for('home'))
    if request.method == 'POST' and 'user_id' in request.form and 'password' in request.form:
        try:
            user_id = int(request.form['user_id'])
        except ValueError:
            msg = 'Incorrect login information. Please try again.'
            return render_template('login.html', msg=msg)
        password = request.form['password']
        myCursor.execute("""
        SELECT employee_id, user_password, access_level,employee_name, warehouse_id, branch_id
        FROM employee
        WHERE employee_id = %s AND user_password = %s AND is_deleted is NULL
          """, (user_id, password))
        account = myCursor.fetchone()
        if account:
            session['logged_in'] = True
            session['user_id'] = account[0]
            session['access_level'] = account[2]
            session['user_name'] = account[3]
            session['branch_id'] = account[5]
            session['warehouse_id'] = account[4]
            return redirect(url_for('home'))
        else:
            msg = "Incorrect login information. Please try again."
    return render_template('login.html', msg=msg)


@app.route('/home')
def home():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('home.html')

# === Sales ===


def loadSalesData():
    myCursor.execute("""
        SELECT s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name,s.branch_id, b.branch_name, s.sale_date, s.payment_method, IFNULL(SUM(sd.quantity * sd.kg_price_at_sale_time),0) as total
        FROM sale s LEFT OUTER JOIN customer c ON s.customer_id = c.customer_id LEFT OUTER JOIN employee e ON s.employee_id = e.employee_id LEFT OUTER JOIN branch b ON s.branch_id = b.branch_id LEFT OUTER JOIN sale_detail sd ON s.sale_id = sd.sale_id AND sd.is_deleted is NULL
        WHERE s.is_deleted IS NULL
        GROUP BY s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name, s.branch_id, b.branch_name, s.sale_date, s.payment_method
        ORDER BY s.sale_date desc,s.sale_id desc

    """)
    salesData = myCursor.fetchall()
    '''
    [0] = Sale ID, [1] = Customer ID, [2] = Customer Name, [3] = Employee ID
    [4] = Employee Name, [5] = Branch ID, [6] = Branch Name, [7] = Sale Date
    [8] = Payment Method (Cash or Card), [9] = Total
    '''
    myCursor.execute("""
        SELECT s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name, s.branch_id, b.branch_name, s.sale_date, s.payment_method, IFNULL(SUM(sd.quantity * sd.kg_price_at_sale_time),0) as total
        FROM sale s LEFT OUTER JOIN customer c ON s.customer_id = c.customer_id LEFT OUTER JOIN employee e ON s.employee_id = e.employee_id LEFT OUTER JOIN branch b ON s.branch_id = b.branch_id LEFT OUTER JOIN sale_detail sd ON s.sale_id = sd.sale_id AND sd.is_deleted is NULL
        WHERE s.is_deleted = 1
        GROUP BY s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name, s.branch_id, b.branch_name, s.sale_date, s.payment_method
        ORDER BY s.sale_date desc,s.sale_id desc
    """)
    deletedSalesData = myCursor.fetchall()
    return salesData, deletedSalesData


def loadSalesDataByEmp(employee_id):
    myCursor.execute("""
    SELECT s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name,s.branch_id, b.branch_name, s.sale_date, s.payment_method, IFNULL(SUM(sd.quantity * sd.kg_price_at_sale_time),0) as total
        FROM sale s LEFT OUTER JOIN customer c ON s.customer_id = c.customer_id LEFT OUTER JOIN employee e ON s.employee_id = e.employee_id LEFT OUTER JOIN branch b ON s.branch_id = b.branch_id LEFT OUTER JOIN sale_detail sd ON s.sale_id = sd.sale_id AND sd.is_deleted is NULL
        WHERE s.is_deleted IS NULL AND s.employee_id=%s
        GROUP BY s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name,s.branch_id, b.branch_name, s.sale_date, s.payment_method
        ORDER BY s.sale_date desc,s.sale_id desc
    """, (employee_id,))
    salesDataForEmp = myCursor.fetchall()
    return salesDataForEmp


@app.route('/sales')
def sales():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:  # If this employee does not work at a branch
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':  # If employee has no admin access, he can only view his sales
        return render_template('sales.html', sales=loadSalesDataByEmp(session['user_id']))
    salesData, deletedSalesData = loadSalesData()
    return render_template('sales.html', sales=salesData)


@app.route('/sales/deleted')
def sales_deleted():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    salesData, deletedSalesData = loadSalesData()
    return render_template('sales_deleted.html', sales=deletedSalesData)


@app.route('/sales/add', methods=['GET', 'POST'])
def sales_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    myCursor.execute("SELECT customer_id, customer_name, phone_number FROM customer")
    customerData = myCursor.fetchall()
    myCursor.execute("""
    SELECT p.product_id, p.product_name, p.sale_price_per_kg, s.quantity
    FROM branch_stock s JOIN product p on s.product_id = p.product_id
    WHERE p.is_deleted IS NULL AND s.branch_id = %s AND s.quantity > 0
    """, (session['branch_id'],))
    productsData = myCursor.fetchall()
    today = date.today().strftime('%Y-%m-%d')
    if request.method == 'POST':
        customer_id = request.form.get('customer_id') or None
        sale_date = request.form.get('sale_date') or datetime.today().strftime('%Y-%m-%d')
        payment_method = request.form.get('payment_method')
        branch_id = session['branch_id']
        employee_id = session['user_id']
        myCursor.execute("""
            INSERT INTO sale (customer_id, branch_id, employee_id, sale_date, payment_method)
            VALUES (%s, %s, %s, %s, %s)
        """, (customer_id, branch_id, employee_id, sale_date, payment_method))
        myCursor.execute("SELECT LAST_INSERT_ID()")
        sale_id = myCursor.fetchone()[0]
        # Insert sale details to the new sale
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('kg_price[]')
        for pid, qty, price in zip(product_ids, quantities, prices):
            if pid and qty and price:
                myCursor.execute("""
                    INSERT INTO sale_detail (sale_id, product_id, quantity, kg_price_at_sale_time)
                    VALUES (%s, %s, %s, %s)
                """, (sale_id, pid, qty, price))
                myCursor.execute("""
                UPDATE branch_stock
                SET quantity = quantity - %s
                WHERE branch_id = %s AND product_id = %s
                """, (qty, branch_id, pid))
        salesDB.commit()
        return redirect(url_for('sales_add'))
    return render_template('sales_form.html', sale=None, sale_details=None, customers=customerData, products=productsData, currentDate=today)


@app.route('/sales/edit/<int:sale_id>', methods=['GET', 'POST'])
def sales_edit(sale_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    myCursor.execute("SELECT customer_id, customer_name, phone_number FROM customer")
    customerData = myCursor.fetchall()
    myCursor.execute("""
        SELECT p.product_id, p.product_name, p.sale_price_per_kg, s.quantity
        FROM branch_stock s JOIN product p on s.product_id = p.product_id
        WHERE p.is_deleted IS NULL AND s.branch_id = %s
        """, (session['branch_id'],))
    productsData = myCursor.fetchall()
    # Load sale
    myCursor.execute("""
        SELECT sale_id, customer_id, employee_id, branch_id,sale_date, payment_method
        FROM sale
        WHERE sale_id=%s AND is_deleted IS NULL
    """, (sale_id,))
    saleData = myCursor.fetchone()
    # Load sale details
    myCursor.execute("""
        SELECT sale_detail_id, sale_id, product_id, quantity, kg_price_at_sale_time
        FROM sale_detail
        WHERE sale_id=%s AND is_deleted IS NULL
    """, (sale_id,))
    saleDetails = myCursor.fetchall()
    editProductsData = []  # Products data with quantities accounting the ones in the sales details
    for p in productsData:
        availableQtyForEdit = float(p[3])
        for sd in saleDetails:
            if sd[2] == p[0]:  # If this sale detail has the product
                availableQtyForEdit = availableQtyForEdit + float(sd[3])
        editProductsData.append((p[0], p[1], p[2], availableQtyForEdit))
    if request.method == 'POST':
        customer_id = request.form.get('customer_id') or None
        sale_date = request.form.get('sale_date')
        payment_method = request.form.get('payment_method')
        branch_id = session['branch_id']
        for d in saleDetails:  # Return Quantities
            myCursor.execute("""
                        UPDATE branch_stock
                        SET quantity = quantity + %s
                        WHERE branch_id = %s AND product_id = %s
                    """, (d[3], branch_id, d[2]))
        # Update sale
        myCursor.execute(
            """
            UPDATE sale
            SET customer_id=%s, sale_date=%s, payment_method=%s
            WHERE sale_id=%s
        """, (customer_id, sale_date, payment_method, sale_id))
        # Set current details to deleted
        myCursor.execute("""
            UPDATE sale_detail
            SET is_deleted = 1
            WHERE sale_id = %s
        """, (sale_id,))
        # Add new updated details
        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('kg_price[]')
        for pid, qty, price in zip(product_ids, quantities, prices):
            if pid and qty and price:
                myCursor.execute("""
                    INSERT INTO sale_detail (sale_id, product_id, quantity, kg_price_at_sale_time)
                    VALUES (%s, %s, %s, %s)
                """, (sale_id, pid, qty, price))
                myCursor.execute("""
                                UPDATE branch_stock
                                SET quantity = quantity - %s
                                WHERE branch_id = %s AND product_id = %s
                                """, (qty, branch_id, pid))
        salesDB.commit()
        return redirect(url_for('sales'))
    return render_template('sales_form.html', sale=saleData, sale_details=saleDetails, customers=customerData, products=editProductsData, currentDate=saleData[4])


@app.route('/sales/delete/<int:sale_id>', methods=['GET', 'POST'])
def sales_delete(sale_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    branch_id = session['branch_id']
    myCursor.execute("SELECT product_id, quantity FROM sale_detail WHERE sale_id=%s AND is_deleted is NULL", (sale_id,))
    details = myCursor.fetchall()
    for item in details:
        myCursor.execute("""
            UPDATE branch_stock
            SET quantity = quantity + %s
            WHERE branch_id = %s AND product_id = %s
        """, (item[1], branch_id, item[0]))
    myCursor.execute(
        """
        UPDATE sale
        SET is_deleted = 1
        WHERE sale_id = %s
    """, (sale_id,))
    myCursor.execute(
        """
        UPDATE sale_detail
        SET is_deleted_with_sale = 1
        WHERE sale_id = %s AND is_deleted is NULL
    """, (sale_id,))
    salesDB.commit()
    return redirect(url_for('sales'))


@app.route('/sales/recover/<int:sale_id>', methods=['GET', 'POST'])
def sales_recover(sale_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    branch_id = session['branch_id']
    # Recover only the details that were deleted when the sale was deleted, not the ones deleted separately
    myCursor.execute("""
        SELECT product_id, quantity
        FROM sale_detail
        WHERE sale_id = %s AND is_deleted_with_sale = 1
    """, (sale_id,))
    sale_details = myCursor.fetchall()
    # Check if there is enough stock to recover the sale
    for item in sale_details:
        myCursor.execute("""
            SELECT quantity
            FROM branch_stock
            WHERE branch_id = %s AND product_id = %s
        """, (branch_id, item[0]))
        stockData = myCursor.fetchone()
        if not stockData or stockData[0] < item[1]:
            flash("Sale can't be recovered now: Stock is not enough")
            return redirect(url_for('sales'))
    try:  # If enough stock to recover
        for item in sale_details:
            myCursor.execute("""
                UPDATE branch_stock
                SET quantity = quantity - %s
                WHERE branch_id = %s AND product_id = %s
            """, (item[1], branch_id, item[0]))
        myCursor.execute("""
            UPDATE sale
            SET is_deleted = NULL
            WHERE sale_id = %s
        """, (sale_id,))
        myCursor.execute("""
            UPDATE sale_detail
            SET is_deleted_with_sale = NULL
            WHERE sale_id = %s AND is_deleted_with_sale = 1
        """, (sale_id,))
        salesDB.commit()
    except Exception as e:
        salesDB.rollback()
        flash("Error Recovering Sale")
    else:
        flash("Sale recovered successfully")
    return redirect(url_for('sales'))


@app.route('/sales/view/<int:sale_id>', methods=['GET', 'POST'])
def sales_view(sale_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    myCursor.execute("""
        SELECT s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name, s.branch_id, b.branch_name, s.sale_date, s.payment_method, IFNULL(SUM(sd.quantity * sd.kg_price_at_sale_time), 0) AS total
        FROM sale s LEFT OUTER JOIN customer c ON s.customer_id = c.customer_id LEFT OUTER JOIN employee e ON s.employee_id = e.employee_id LEFT OUTER JOIN branch b ON s.branch_id = b.branch_id
        LEFT OUTER JOIN sale_detail sd ON s.sale_id = sd.sale_id AND sd.is_deleted IS NULL
        WHERE s.sale_id = %s
        GROUP BY s.sale_id, s.customer_id, c.customer_name, s.employee_id, e.employee_name, s.branch_id, b.branch_name, s.sale_date, s.payment_method
    """, (sale_id,))
    saleData = myCursor.fetchone()
    # Load sale details
    myCursor.execute("""
        SELECT sd.sale_detail_id, sd.product_id, p.product_name, sd.quantity, sd.kg_price_at_sale_time, (sd.quantity * sd.kg_price_at_sale_time) AS line_total
        FROM sale_detail sd LEFT OUTER JOIN product p ON sd.product_id = p.product_id
        WHERE sd.sale_id = %s AND sd.is_deleted IS NULL
    """, (sale_id,))
    saleDetails = myCursor.fetchall()
    return render_template('sales_view.html', sale=saleData, sale_details=saleDetails)


# === Customers ===


def loadCustomersData():
    myCursor.execute("""
    SELECT *
    FROM customer
    """)
    data = myCursor.fetchall()
    customersData = []  # [0] = ID, [1] = Name, [2] = Phone Number, [3] = Date of Birth, [4] = Email
    for c in data:
        if c[3]:  # Format date of birth into YYYY-MM-DD if it exists
            dob = c[3].strftime('%Y-%m-%d')
        else:
            dob = ''
        customersData.append((c[0], c[1], c[2], dob, c[4]))
    return customersData


@app.route('/customers')
def customers():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    return render_template('customers.html', customers=loadCustomersData())


def getCustomerDataFromForm(form):  # Extracts Customer data from input form
    # Required fields
    name = form['customer_name'].strip()
    phone = form['phone_number'].strip()
    # Optional fields
    year = form.get('dob_year')
    month = form.get('dob_month')
    day = form.get('dob_day')
    if year and month and day:
        dob = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    else:
        dob = None
    email = form['email'] or None
    return (name, phone, dob, email)


@app.route('/customers/add', methods=['GET', 'POST'])
def customers_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    if request.method == 'GET':  # If the page is loading
        return render_template('customers_form.html', action=url_for('customers_add'), c=None)
    if request.method == 'POST':  # If the user is submitting a new customer
        customerForm = request.form  # Returns a dictionary with the added customer data
        try:
            customerData = getCustomerDataFromForm(customerForm)  # Gets the customer data from the form
            myCursor.execute("""
                    INSERT INTO customer (customer_name, phone_number, date_of_birth, email)
                    VALUES (%s,%s,%s,%s)
                """, customerData)
            salesDB.commit()
        except Exception as e:
            flash(f"Error adding customer: {e}")
    return redirect(url_for('customers'))


@app.route('/customers/edit/<int:c_id>', methods=['GET', 'POST'])
def customers_edit(c_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    customersData = loadCustomersData()
    if request.method == 'GET':
        c = None  # Look for the customer data, to edit
        for customer in customersData:  # Look in customers
            if customer[0] == c_id:
                c = customer
                break
        return render_template('customers_form.html', action=url_for('customers_edit', c_id=c_id), c=c)
    else:
        customerForm = request.form
        try:
            customerData = getCustomerDataFromForm(customerForm)
            myCursor.execute("""
                    UPDATE customer
                    SET customer_name=%s, phone_number=%s, date_of_birth=%s, email=%s
                    WHERE customer_id=%s
                """, customerData + (c_id,))
            salesDB.commit()
        except Exception as e:
            flash(f"Error updating customer: {e}")
    return redirect(url_for('customers'))


@app.route('/customers/delete/<int:c_id>', methods=['POST'])
def customers_delete(c_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('branch_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("DELETE FROM customer WHERE customer_id=%s", (c_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"Error Deleting Customer: {e}")
    return redirect(url_for('customers'))

# === purchases ===
@app.route('/purchases')
def purchases():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') == 'admin':
        purchasesData = loadPurchasesData()
        deletedPurchasesData = loadDeletedPurchasesData()
    else:
        wh_id = session.get('warehouse_id')
        if not wh_id:
            return "Access denied: Purchases are available for warehouse employees only."
        purchasesData = loadPurchasesData(warehouse_id=wh_id)
        deletedPurchasesData = loadDeletedPurchasesData(warehouse_id=wh_id)
    return render_template('purchases.html', purchases=purchasesData, deleted_purchases=deletedPurchasesData)

def loadPurchasesData(warehouse_id=None):
    if warehouse_id:
        myCursor.execute("""
            SELECT p.purchase_id,
                   p.purchase_date,
                   p.warehouse_id, w.warehouse_name,
                   p.supplier_id, s.supplier_name,
                   p.employee_id, e.employee_name,
                   IFNULL(SUM(pd.quantity * pd.kg_price_at_purchase_time), 0) AS total,
                   IFNULL((SELECT SUM(pay.amount) FROM payment pay
                           WHERE pay.purchase_id = p.purchase_id AND pay.is_deleted IS NULL), 0) AS paid
            FROM purchase p
            LEFT OUTER JOIN warehouse w ON p.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN supplier s ON p.supplier_id = s.supplier_id
            LEFT OUTER JOIN employee e ON p.employee_id = e.employee_id
            LEFT OUTER JOIN purchase_detail pd ON p.purchase_id = pd.purchase_id AND pd.is_deleted is NULL
            WHERE p.warehouse_id = %s AND p.is_deleted is NULL
            GROUP BY p.purchase_id
            ORDER BY p.purchase_id DESC
        """, (warehouse_id,))
    else:
        myCursor.execute("""
            SELECT p.purchase_id,
                   p.purchase_date,
                   p.warehouse_id, w.warehouse_name,
                   p.supplier_id, s.supplier_name,
                   p.employee_id, e.employee_name,
                   IFNULL(SUM(pd.quantity * pd.kg_price_at_purchase_time), 0) AS total,
                   IFNULL((SELECT SUM(pay.amount) FROM payment pay
                           WHERE pay.purchase_id = p.purchase_id AND pay.is_deleted IS NULL), 0) AS paid
            FROM purchase p
            LEFT OUTER JOIN warehouse w ON p.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN supplier s ON p.supplier_id = s.supplier_id
            LEFT OUTER JOIN employee e ON p.employee_id = e.employee_id
            LEFT OUTER JOIN purchase_detail pd ON p.purchase_id = pd.purchase_id AND pd.is_deleted is NULL
            WHERE p.is_deleted is NULL
            GROUP BY p.purchase_id
            ORDER BY p.purchase_id DESC
        """)
    return myCursor.fetchall()


def loadDeletedPurchasesData(warehouse_id=None):
    if warehouse_id:
        myCursor.execute("""
            SELECT p.purchase_id,
                   p.purchase_date,
                   p.warehouse_id, w.warehouse_name,
                   p.supplier_id, s.supplier_name,
                   p.employee_id, e.employee_name,
                   IFNULL(SUM(pd.quantity * pd.kg_price_at_purchase_time), 0) AS total,
                   IFNULL((SELECT SUM(pay.amount) FROM payment pay
                           WHERE pay.purchase_id = p.purchase_id AND pay.is_deleted IS NULL), 0) AS paid
            FROM purchase p
            LEFT OUTER JOIN warehouse w ON p.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN supplier s ON p.supplier_id = s.supplier_id
            LEFT OUTER JOIN employee e ON p.employee_id = e.employee_id
            LEFT OUTER JOIN purchase_detail pd ON p.purchase_id = pd.purchase_id AND pd.is_deleted is NULL
            WHERE p.warehouse_id = %s AND p.is_deleted = 1
            GROUP BY p.purchase_id
            ORDER BY p.purchase_id DESC
        """, (warehouse_id,))
    else:
        myCursor.execute("""
            SELECT p.purchase_id,
                   p.purchase_date,
                   p.warehouse_id, w.warehouse_name,
                   p.supplier_id, s.supplier_name,
                   p.employee_id, e.employee_name,
                   IFNULL(SUM(pd.quantity * pd.kg_price_at_purchase_time), 0) AS total,
                   IFNULL((SELECT SUM(pay.amount) FROM payment pay
                           WHERE pay.purchase_id = p.purchase_id AND pay.is_deleted IS NULL), 0) AS paid
            FROM purchase p
            LEFT OUTER JOIN warehouse w ON p.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN supplier s ON p.supplier_id = s.supplier_id
            LEFT OUTER JOIN employee e ON p.employee_id = e.employee_id
            LEFT OUTER JOIN purchase_detail pd ON p.purchase_id = pd.purchase_id AND pd.is_deleted is NULL
            WHERE p.is_deleted = 1
            GROUP BY p.purchase_id
            ORDER BY p.purchase_id DESC
        """)
    return myCursor.fetchall()


def loadPurchaseHeader(purchase_id):
    myCursor.execute("""
        SELECT p.purchase_id,
               p.purchase_date,
               p.warehouse_id, w.warehouse_name,
               p.supplier_id, s.supplier_name,
               p.employee_id, e.employee_name
        FROM purchase p
        LEFT OUTER JOIN warehouse w ON p.warehouse_id = w.warehouse_id
        LEFT OUTER JOIN supplier s ON p.supplier_id = s.supplier_id
        LEFT OUTER JOIN employee e ON p.employee_id = e.employee_id
        WHERE p.purchase_id = %s AND p.is_deleted is NULL
    """, (purchase_id,))
    return myCursor.fetchone()


def loadPurchaseDetails(purchase_id):
    myCursor.execute("""
        SELECT pd.purchase_detail_id,
               pd.purchase_id,
               pd.product_id, pr.product_name,
               pd.quantity,
               pd.kg_price_at_purchase_time
        FROM purchase_detail pd
        LEFT OUTER JOIN product pr ON pd.product_id = pr.product_id
        WHERE pd.purchase_id = %s AND pd.is_deleted is NULL
        ORDER BY pd.purchase_detail_id
    """, (purchase_id,))
    return myCursor.fetchall()


def loadPurchaseTotal(purchase_id):
    myCursor.execute("""
        SELECT IFNULL(SUM(pd.quantity * pd.kg_price_at_purchase_time), 0) AS total
        FROM purchase_detail pd
        WHERE pd.purchase_id = %s
          AND pd.is_deleted IS NULL
    """, (purchase_id,))
    row = myCursor.fetchone()
    return float(row[0]) if row and row[0] is not None else 0.0


def loadActiveProductsForPurchase():
    myCursor.execute("""
        SELECT product_id, product_name, purchase_price_per_kg, sale_price_per_kg
        FROM product
        WHERE is_deleted IS NULL
        ORDER BY product_id
    """)
    return myCursor.fetchall()


def loadSuppliersForSelect():
    myCursor.execute("""
        SELECT supplier_id, supplier_name
        FROM supplier
        WHERE is_deleted IS NULL
        ORDER BY supplier_id
    """)
    return myCursor.fetchall()


def loadWarehousesForSelect():
    myCursor.execute("""
        SELECT warehouse_id, warehouse_name
        FROM warehouse
        ORDER BY warehouse_id
    """)
    return myCursor.fetchall()


def upsertWarehouseStock(warehouse_id, product_id, delta_qty):
    myCursor.execute("""
        INSERT INTO warehouse_stock (warehouse_id, product_id, quantity)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
    """, (warehouse_id, product_id, delta_qty))


def getWarehouseStockQty(warehouse_id, product_id):
    myCursor.execute("""
        SELECT quantity
        FROM warehouse_stock
        WHERE warehouse_id = %s AND product_id = %s
    """, (warehouse_id, product_id))
    row = myCursor.fetchone()
    return float(row[0]) if row else 0.0


@app.route('/purchases/add', methods=['GET', 'POST'])
def purchases_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:  # If this employee does not work at a warehouse
        return redirect(url_for('home'))

    if request.method == 'GET':
        suppliersData = loadSuppliersForSelect()
        productsData = loadActiveProductsForPurchase()
        warehousesData = loadWarehousesForSelect() if session.get('access_level') == 'admin' else None
        return render_template('purchases_form.html',
                               mode='add',
                               purchase=None,
                               purchase_details=None,
                               suppliers=suppliersData,
                               products=productsData,
                               warehouses=warehousesData)

    try:
        supplier_id = request.form.get('supplier_id')
        purchase_date = request.form.get('purchase_date')
        if not purchase_date:
            purchase_date = date.today().isoformat()

        if session.get('access_level') == 'admin':
            warehouse_id = request.form.get('warehouse_id')
        else:
            warehouse_id = session.get('warehouse_id')

        if not warehouse_id:
            return "Error: warehouse_id is required."

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('kg_price_at_purchase_time[]')

        details = []
        for pid, qty, prc in zip(product_ids, quantities, prices):
            if not pid:
                continue
            q = float(qty) if qty else 0
            p = float(prc) if prc else 0
            if q <= 0:
                continue
            details.append((int(pid), q, p))

        if not supplier_id or len(details) == 0:
            return "Error: Please select a supplier and add at least one product line."

        myCursor.execute("""
            INSERT INTO purchase (employee_id, warehouse_id, supplier_id, purchase_date)
            VALUES (%s, %s, %s, %s)
        """, (session.get('user_id'), warehouse_id, supplier_id, purchase_date))
        purchase_id = myCursor.lastrowid

        for pid, qty, prc in details:
            myCursor.execute("""
                INSERT INTO purchase_detail (purchase_id, product_id, quantity, kg_price_at_purchase_time)
                VALUES (%s, %s, %s, %s)
            """, (purchase_id, pid, qty, prc))
            upsertWarehouseStock(warehouse_id, pid, qty)

        salesDB.commit()
        return redirect(url_for('purchases'))
    except Exception as e:
        try:
            salesDB.rollback()
        except Exception:
            pass
        return f"Error adding purchase: {e}"


@app.route('/purchases/view/<int:purchase_id>')
def purchases_view(purchase_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))

    header = loadPurchaseHeader(purchase_id)
    details = loadPurchaseDetails(purchase_id)
    if not header:
        return "Purchase not found."

    if session.get('access_level') != 'admin':
        if session.get('warehouse_id') != header[2]:
            return "Access denied."

    total = loadPurchaseTotal(purchase_id)

    return render_template('purchases_view.html',purchase=header,details=details,total=total)


@app.route('/purchases/edit/<int:purchase_id>', methods=['GET', 'POST'])
def purchases_edit(purchase_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:  # If this employee does not work at a warehouse
        return redirect(url_for('home'))

    if session.get('access_level') != 'admin':
        return "Access denied: only admin can edit purchases."

    header = loadPurchaseHeader(purchase_id)
    if not header:
        return "Purchase not found."

    if request.method == 'GET':
        suppliersData = loadSuppliersForSelect()
        productsData = loadActiveProductsForPurchase()
        warehousesData = loadWarehousesForSelect()
        details = loadPurchaseDetails(purchase_id)
        return render_template('purchases_form.html',
                               mode='edit',
                               purchase=header,
                               purchase_details=details,
                               suppliers=suppliersData,
                               products=productsData,
                               warehouses=warehousesData)

    try:
        supplier_id = request.form.get('supplier_id')
        purchase_date = request.form.get('purchase_date')
        warehouse_id_new = request.form.get('warehouse_id')

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')
        prices = request.form.getlist('kg_price_at_purchase_time[]')

        new_details = []
        for pid, qty, prc in zip(product_ids, quantities, prices):
            if not pid:
                continue
            q = float(qty) if qty else 0
            p = float(prc) if prc else 0
            if q <= 0:
                continue
            new_details.append((int(pid), q, p))

        if not supplier_id or not warehouse_id_new or len(new_details) == 0:
            return "Error: Please select supplier/warehouse and add at least one product line."

        warehouse_id_old = header[2]
        old_details = loadPurchaseDetails(purchase_id)

        for d in old_details:
            pid = d[2]
            old_qty = float(d[4])
            current_qty = getWarehouseStockQty(warehouse_id_old, pid)
            if current_qty < old_qty:
                return ("Cannot edit this purchase because some purchased quantities were already transferred/sold. "
                        f"(Warehouse {warehouse_id_old}, Product {pid} needs {old_qty} in stock, but has {current_qty}).")


        for d in old_details:
            pid = d[2]
            old_qty = float(d[4])
            upsertWarehouseStock(warehouse_id_old, pid, -old_qty)

        myCursor.execute("""
            UPDATE purchase
            SET supplier_id = %s,
                warehouse_id = %s,
                purchase_date = %s
            WHERE purchase_id = %s
        """, (supplier_id, warehouse_id_new, purchase_date, purchase_id))

        myCursor.execute("UPDATE purchase_detail SET is_deleted = 1 WHERE purchase_id = %s", (purchase_id,))

        for pid, qty, prc in new_details:
            myCursor.execute("""
                INSERT INTO purchase_detail (purchase_id, product_id, quantity, kg_price_at_purchase_time)
                VALUES (%s, %s, %s, %s)
            """, (purchase_id, pid, qty, prc))
            upsertWarehouseStock(warehouse_id_new, pid, qty)

        salesDB.commit()
        return redirect(url_for('purchases_view', purchase_id=purchase_id))
    except Exception as e:
        try:
            salesDB.rollback()
        except Exception:
            pass
        return f"Error editing purchase: {e}"


@app.route('/purchases/delete/<int:purchase_id>', methods=['POST'])
def purchases_delete(purchase_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:  # If this employee does not work at a warehouse
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return "Access denied: only admin can delete purchases."

    header = loadPurchaseHeader(purchase_id)
    if not header:
        return "Purchase not found."

    warehouse_id = header[2]
    details = loadPurchaseDetails(purchase_id)

    for d in details:
        pid = d[2]
        old_qty = float(d[4])
        current_qty = getWarehouseStockQty(warehouse_id, pid)
        if current_qty < old_qty:
            return ("Cannot delete this purchase because some quantities were already transferred/sold. "
                    f"(Warehouse {warehouse_id}, Product {pid} needs {old_qty} in stock, but has {current_qty}).")

    try:

        for d in details:
            pid = d[2]
            old_qty = float(d[4])
            upsertWarehouseStock(warehouse_id, pid, -old_qty)
        myCursor.execute("UPDATE payment SET is_deleted_with_purchase = 1 WHERE purchase_id = %s", (purchase_id,))
        myCursor.execute("UPDATE purchase_detail SET is_deleted_with_purchase = 1 WHERE purchase_id = %s", (purchase_id,))
        myCursor.execute("UPDATE purchase SET is_deleted = 1 WHERE purchase_id = %s", (purchase_id,))
        salesDB.commit()
        return redirect(url_for('purchases'))
    except Exception as e:
        try:
            salesDB.rollback()
        except Exception:
            pass
        return f"Error deleting purchase: {e}"

    
@app.route('/purchases/recover/<int:purchase_id>', methods=['POST'])
def purchases_recover(purchase_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return "Access denied: only admin can recover purchases."
    myCursor.execute("""
        SELECT p.purchase_id, p.warehouse_id, p.is_deleted
        FROM purchase p
        WHERE p.purchase_id = %s
    """, (purchase_id,))
    header = myCursor.fetchone()
    if not header:
        return "Purchase not found."
    warehouse_id = header[1]
    is_deleted_flag = header[2]
    if is_deleted_flag is None:
        return "This purchase is already active."
    myCursor.execute("""
        SELECT pd.product_id, pd.quantity
        FROM purchase_detail pd
        WHERE pd.purchase_id = %s
          AND pd.is_deleted_with_purchase = 1
          AND pd.is_deleted IS NULL
    """, (purchase_id,))
    details = myCursor.fetchall()
    if not details:
        return "No purchase details to recover."
    try:
        for pid, qty in details:
            upsertWarehouseStock(warehouse_id, int(pid), float(qty))
        myCursor.execute("""
            UPDATE payment
            SET is_deleted_with_purchase = NULL
            WHERE purchase_id = %s
        """, (purchase_id,))
        myCursor.execute("""
            UPDATE purchase_detail
            SET is_deleted_with_purchase = NULL
            WHERE purchase_id = %s
              AND is_deleted IS NULL
        """, (purchase_id,))
        myCursor.execute("""
            UPDATE purchase
            SET is_deleted = NULL
            WHERE purchase_id = %s
        """, (purchase_id,))
        salesDB.commit()
        return redirect(url_for('purchases'))
    except Exception as e:
        try:
            salesDB.rollback()
        except Exception:
            pass
        return f"Error recovering purchase: {e}"
    

# === Suppliers ===


def loadSupData():
    myCursor.execute("""
    SELECT *
    FROM supplier
    WHERE is_deleted is NULL
    """)
    data = myCursor.fetchall()  # [0] = ID, [1] = Name, [2] = Location , [3] Phone Number, [4] = Email, [5] is_deleted
    return data


def loadDeletedSupData():
    myCursor.execute("""
    SELECT *
    FROM supplier
    WHERE is_deleted = 1
    """)
    data = myCursor.fetchall()  # [0] = ID, [1] = Name, [2] = Location , [3] Phone Number, [4] = Email, [5] is_deleted
    return data


@app.route('/suppliers')
def suppliers():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    return render_template('suppliers.html', suppliers=loadSupData())


@app.route('/suppliers/deleted')
def suppliers_deleted():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    return render_template('suppliers_deleted.html', suppliers=loadDeletedSupData())


def getSupDataFromForm(form):
    name = form['supplier_name'].strip()
    location = form['supplier_location'].strip()
    phone = form['supplier_phone'].strip()
    email = form['supplier_email'].strip()
    return (name, location, phone, email)


@app.route('/suppliers/add', methods=['GET', 'POST'])
def suppliers_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if request.method == 'GET':  # If the page is loading
        return render_template('suppliers_form.html', action=url_for('suppliers_add'), s=None)
    if request.method == 'POST':  # If the user is submitting a new supplier
        suppliersForm = request.form  # Returns a dictionary with the added supplier data
        try:
            supData = getSupDataFromForm(suppliersForm)  # Gets the supplier data from the form
            myCursor.execute("""
                INSERT INTO supplier (supplier_name, location, phone_number, email, is_deleted)
                VALUES (%s,%s,%s,%s,NULL)
            """, supData)
            salesDB.commit()
        except Exception as e:
            flash(f"Error adding supplier: {e}")
    return redirect(url_for('suppliers'))


@app.route('/suppliers/edit/<int:sup_id>', methods=['GET', 'POST'])
def suppliers_edit(sup_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    suppliersData = loadSupData()
    sup = None  # Look for the supplier data, to edit
    for s in suppliersData:  # Look in supplier data
        if s[0] == sup_id:
            sup = s
            break
    if request.method == 'GET':  # If the page is loading
        return render_template('suppliers_form.html', action=url_for('suppliers_edit', sup_id=sup_id), s=sup)
    if request.method == 'POST':  # If the user is submitting a new supplier
        supplierForm = request.form  # Returns a dictionary with the added supplier data
        try:
            supData = getSupDataFromForm(supplierForm)  # Gets the supplier data from the form
            myCursor.execute("""
                UPDATE supplier
                SET supplier_name=%s, location=%s, phone_number=%s,email =%s
                WHERE supplier_id=%s
            """, supData + (sup_id,))
            salesDB.commit()
        except Exception as e:
            flash(f"Error updating supplier: {e}")
    return redirect(url_for('suppliers'))


@app.route('/suppliers/delete/<int:sup_id>', methods=['POST'])
def suppliers_delete(sup_id):  # Deletes a supplier, this sets the is_deleted to 1, but the supplier data is kept
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("UPDATE supplier SET is_deleted=1 WHERE supplier_id=%s", (sup_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"Error deleting supplier: {e}")
    return redirect(url_for('suppliers'))


@app.route('/suppliers/recover/<int:sup_id>', methods=['POST'])
def suppliers_recover(sup_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("UPDATE supplier SET is_deleted=NULL WHERE supplier_id=%s", (sup_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"Error recovering supplier: {e}")
    return redirect(url_for('suppliers'))


# === Payments ===


@app.route('/payments')
def payments():  # Show unpaid purchases with their info, payments are for admin access only
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:  # If this employee does not work at a warehouse
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    myCursor.execute("""
                    SELECT p.purchase_id, p.purchase_date, s.supplier_name,IFNULL(pd.total_amount, 0) AS total_amount,IFNULL(pay.paid_amount, 0) AS paid_amount
                    FROM purchase p JOIN supplier s ON s.supplier_id = p.supplier_id
                    LEFT OUTER JOIN (SELECT purchase_id, SUM(quantity*kg_price_at_purchase_time) AS total_amount
                                    FROM purchase_detail
                                    WHERE purchase_detail.is_deleted is NULL
                                    GROUP BY purchase_id) pd ON pd.purchase_id = p.purchase_id
                    LEFT OUTER JOIN (SELECT purchase_id, SUM(amount) AS paid_amount
                                    FROM payment
                                    WHERE is_deleted IS NULL
                                    GROUP BY purchase_id) pay ON pay.purchase_id = p.purchase_id
                    WHERE IFNULL(pay.paid_amount,0) < IFNULL(pd.total_amount,0) AND p.is_deleted is NULL
                    ORDER BY p.purchase_date DESC;
    """)
    data = myCursor.fetchall()
    show_completed = request.args.get('show_completed')
    completed_purchases = []
    if show_completed:
        myCursor.execute("""
                    SELECT p.purchase_id, p.purchase_date, s.supplier_name,IFNULL(pd.total_amount, 0) AS total_amount,IFNULL(pay.paid_amount, 0) AS paid_amount
                    FROM purchase p JOIN supplier s ON s.supplier_id = p.supplier_id
                    LEFT OUTER JOIN (SELECT purchase_id, SUM(quantity * kg_price_at_purchase_time) AS total_amount
                                    FROM purchase_detail
                                    WHERE purchase_detail.is_deleted is NULL
                                    GROUP BY purchase_id) pd ON pd.purchase_id = p.purchase_id
                    LEFT OUTER JOIN (SELECT purchase_id, SUM(amount) AS paid_amount
                                    FROM payment
                                    WHERE is_deleted IS NULL
                                    GROUP BY purchase_id) pay ON pay.purchase_id = p.purchase_id
                    WHERE IFNULL(pay.paid_amount,0) >= IFNULL(pd.total_amount,0) AND p.is_deleted is NULL
                    ORDER BY p.purchase_date DESC;
            """)
        completed_purchases = myCursor.fetchall()
    pid = request.args.get('pid')
    payAmountForPurchase = ()  # (Purchase ID, Remaining Amount)
    if pid:
        pid = int(pid)
        p = None
        for purchase in data:
            if purchase[0] == pid:
                p = purchase
                break
        remaining = p[3]-p[4]
        if remaining <= 0:  # If payment is already paid then we cant add more
            return redirect(url_for('payments'))
        payAmountForPurchase = p
    return render_template('payments.html', purchases=data, completed_purchases=completed_purchases, payAmountForPurchase=payAmountForPurchase)


def getPaymentDataFromForm(form):
    purchase_id = form['purchase_id'].strip()
    employee_id = session['user_id']
    current_date = datetime.today().strftime('%Y-%m-%d')
    amount = float(form['amount'].strip())
    method = form['method'].strip()
    return (purchase_id, employee_id, current_date, amount, method)


@app.route('/payments/add', methods=['POST'])
def payments_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    form = request.form
    paymentData = getPaymentDataFromForm(form)
    myCursor.execute("""
        INSERT INTO payment (purchase_id, employee_id, payment_date, amount, method, is_deleted)
        VALUES (%s,%s,%s,%s,%s,NULL)
    """, paymentData)
    salesDB.commit()
    return redirect(url_for('payments'))


@app.route('/payments/view/<int:purchase_id>')
def payment_view(purchase_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    myCursor.execute("""
        SELECT p.purchase_id,p.supplier_id,s.supplier_name,p.employee_id,e.employee_name,p.warehouse_id,w.warehouse_name,p.purchase_date,IFNULL(SUM(pd.quantity * pd.kg_price_at_purchase_time), 0) AS total
        FROM purchase p LEFT OUTER JOIN supplier s ON p.supplier_id = s.supplier_id LEFT OUTER JOIN employee e ON p.employee_id = e.employee_id LEFT OUTER JOIN warehouse w ON p.warehouse_id = w.warehouse_id LEFT OUTER JOIN purchase_detail pd ON p.purchase_id = pd.purchase_id
        WHERE p.purchase_id = %s
        GROUP BY p.purchase_id,p.supplier_id,s.supplier_name,p.employee_id,e.employee_name,p.warehouse_id,w.warehouse_name,p.purchase_date
    """, (purchase_id,))
    purchaseData = myCursor.fetchone()
    myCursor.execute("""
        SELECT pay.payment_id, pay.payment_date, pay.amount, pay.method, e.employee_name
        FROM payment pay LEFT OUTER JOIN employee e ON e.employee_id = pay.employee_id
        WHERE pay.purchase_id = %s AND pay.is_deleted IS NULL
        ORDER BY pay.payment_date, pay.payment_id
    """, (purchase_id,))
    paymentsData = myCursor.fetchall()
    total_paid = 0
    for payment in paymentsData:
        amount = float(payment[2] or 0)
        total_paid = total_paid + amount
    purchase_total = float(purchaseData[8] or 0)
    remaining = purchase_total - total_paid
    show_deleted = request.args.get('show_deleted')
    deleted_payments = []
    if show_deleted:
        myCursor.execute("""
            SELECT pay.payment_id, pay.payment_date, pay.amount, pay.method, e.employee_name
            FROM payment pay LEFT OUTER JOIN employee e ON e.employee_id = pay.employee_id
            WHERE pay.purchase_id = %s AND pay.is_deleted = 1
            ORDER BY pay.payment_date, pay.payment_id
        """, (purchase_id,))
        deleted_payments = myCursor.fetchall()
    return render_template('payment_view.html',purchase=purchaseData,payments=paymentsData,total_paid=total_paid,remaining=remaining,deleted_payments=deleted_payments)


@app.route('/payments/delete/<int:payment_id>', methods=['POST'])
def delete_payment(payment_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("""
            UPDATE payment
            SET is_deleted = 1
            WHERE payment_id = %s
        """, (payment_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"Error deleting payment: {e}")
    myCursor.execute("SELECT purchase_id FROM payment WHERE payment_id = %s", (payment_id,))
    pid = myCursor.fetchone()
    if pid:
        return redirect(url_for('payment_view', purchase_id=pid[0]))
    return redirect(url_for('purchases'))


# ====stock====


@app.route('/stock')
def stock():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    # Admin can view all others see their own branch or warehouse
    wh_filter = request.args.get('warehouse_id')
    br_filter = request.args.get('branch_id')

    if session.get('access_level') != 'admin':
        if session.get('warehouse_id'):
            wh_filter = session.get('warehouse_id')
        if session.get('branch_id'):
            br_filter = session.get('branch_id')

    # Warehouse stock
    if wh_filter:
        myCursor.execute("""
            SELECT ws.warehouse_id, w.warehouse_name, ws.product_id, p.product_name, ws.quantity
            FROM warehouse_stock ws
            LEFT OUTER JOIN warehouse w ON ws.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN product p ON ws.product_id = p.product_id
            WHERE ws.warehouse_id = %s
            ORDER BY ws.product_id
        """, (wh_filter,))
    else:
        myCursor.execute("""
            SELECT ws.warehouse_id, w.warehouse_name, ws.product_id, p.product_name, ws.quantity
            FROM warehouse_stock ws
            LEFT OUTER JOIN warehouse w ON ws.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN product p ON ws.product_id = p.product_id
            ORDER BY ws.warehouse_id, ws.product_id
        """)
    warehouseStock = myCursor.fetchall()

    # Branch stock
    if br_filter:
        myCursor.execute("""
            SELECT bs.branch_id, b.branch_name, bs.product_id, p.product_name, bs.quantity
            FROM branch_stock bs
            LEFT OUTER JOIN branch b ON bs.branch_id = b.branch_id
            LEFT OUTER JOIN product p ON bs.product_id = p.product_id
            WHERE bs.branch_id = %s
            ORDER BY bs.product_id
        """, (br_filter,))
    else:
        myCursor.execute("""
            SELECT bs.branch_id, b.branch_name, bs.product_id, p.product_name, bs.quantity
            FROM branch_stock bs
            LEFT OUTER JOIN branch b ON bs.branch_id = b.branch_id
            LEFT OUTER JOIN product p ON bs.product_id = p.product_id
            ORDER BY bs.branch_id, bs.product_id
        """)
    branchStock = myCursor.fetchall()

    warehousesData = loadWarehousesForSelect()
    branchesData = loadBranchesForSelect()

    return render_template('stock.html',
                           warehouse_stock=warehouseStock,
                           branch_stock=branchStock,
                           warehouses=warehousesData,
                           branches=branchesData,
                           wh_filter=wh_filter,
                           br_filter=br_filter)


# ====products====

@app.route('/products')
def products():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    productsData = loadProductsData(active_only=True)
    deletedProductsData = loadProductsData(active_only=False) if session.get('access_level') == 'admin' else None
    return render_template('products.html', products=productsData, deleted_products=deletedProductsData)


def loadProductsData(active_only=True):
    if active_only:
        myCursor.execute("""
            SELECT product_id, product_name, category, purchase_price_per_kg, sale_price_per_kg
            FROM product
            WHERE is_deleted IS NULL
            ORDER BY product_id
        """)
    else:
        myCursor.execute("""
            SELECT product_id, product_name, category, purchase_price_per_kg, sale_price_per_kg
            FROM product
            WHERE is_deleted = 1
            ORDER BY product_id
        """)
    return myCursor.fetchall()


@app.route('/products/add', methods=['GET', 'POST'])
def products_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if request.method == 'GET':
        return render_template('products_form.html', mode='add', product=None)

    try:
        form = request.form
        name = form.get('product_name')
        category = form.get('category')
        purchase_price = form.get('purchase_price_per_kg')
        sale_price = form.get('sale_price_per_kg')

        if not name or not category:
            return "Error: product name and category are required."

        myCursor.execute("""
            INSERT INTO product (product_name, category, is_deleted, purchase_price_per_kg, sale_price_per_kg)
            VALUES (%s, %s, NULL, %s, %s)
        """, (name, category, purchase_price, sale_price))
        salesDB.commit()
        return redirect(url_for('products'))
    except Exception as e:
        return f"Error adding product: {e}"


@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
def products_edit(product_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if session.get('access_level') != 'admin':
        return "Access denied: only admin can edit products."

    myCursor.execute("""
        SELECT product_id, product_name, category, purchase_price_per_kg, sale_price_per_kg
        FROM product
        WHERE product_id = %s
    """, (product_id,))
    product = myCursor.fetchone()
    if not product:
        return "Product not found."

    if request.method == 'GET':
        return render_template('products_form.html', mode='edit', product=product)

    try:
        form = request.form
        name = form.get('product_name')
        category = form.get('category')
        purchase_price = form.get('purchase_price_per_kg')
        sale_price = form.get('sale_price_per_kg')

        myCursor.execute("""
            UPDATE product
            SET product_name = %s,
                category = %s,
                purchase_price_per_kg = %s,
                sale_price_per_kg = %s
            WHERE product_id = %s
        """, (name, category, purchase_price, sale_price, product_id))
        salesDB.commit()
        return redirect(url_for('products'))
    except Exception as e:
        return f"Error editing product: {e}"


@app.route('/products/delete/<int:product_id>', methods=['POST'])
def products_delete(product_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if session.get('access_level') != 'admin':
        return "Access denied: only admin can delete products."

    try:
        myCursor.execute("UPDATE product SET is_deleted = 1 WHERE product_id = %s", (product_id,))
        salesDB.commit()
        return redirect(url_for('products'))
    except Exception as e:
        return f"Error deleting product: {e}"


@app.route('/products/recover/<int:product_id>', methods=['POST'])
def products_recover(product_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if session.get('access_level') != 'admin':
        return "Access denied: only admin can recover products."

    try:
        myCursor.execute("UPDATE product SET is_deleted = NULL WHERE product_id = %s", (product_id,))
        salesDB.commit()
        return redirect(url_for('products'))
    except Exception as e:
        return f"Error recovering product: {e}"


# ====transfer====
@app.route('/transfer')
def transfer():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if session.get('access_level') == 'admin':
        transfersData = loadTransfersData()
    else:
        wh_id = session.get('warehouse_id')
        if not wh_id:
            return "Access denied: Transfers are available for warehouse employees only."
        transfersData = loadTransfersData(warehouse_id=wh_id)

    return render_template('transfer.html', transfers=transfersData)


def loadTransfersData(warehouse_id=None):
    if warehouse_id:
        myCursor.execute("""
            SELECT t.transfer_id,
                   t.transfer_date,
                   t.warehouse_id, w.warehouse_name,
                   t.branch_id, b.branch_name,
                   t.employee_id, e.employee_name,
                   IFNULL(SUM(td.quantity), 0) AS total_qty
            FROM transfer t
            LEFT OUTER JOIN warehouse w ON t.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN branch b ON t.branch_id = b.branch_id
            LEFT OUTER JOIN employee e ON t.employee_id = e.employee_id
            LEFT OUTER JOIN transfer_detail td ON t.transfer_id = td.transfer_id
            WHERE t.warehouse_id = %s
            GROUP BY t.transfer_id
            ORDER BY t.transfer_id DESC
        """, (warehouse_id,))
    else:
        myCursor.execute("""
            SELECT t.transfer_id,
                   t.transfer_date,
                   t.warehouse_id, w.warehouse_name,
                   t.branch_id, b.branch_name,
                   t.employee_id, e.employee_name,
                   IFNULL(SUM(td.quantity), 0) AS total_qty
            FROM transfer t
            LEFT OUTER JOIN warehouse w ON t.warehouse_id = w.warehouse_id
            LEFT OUTER JOIN branch b ON t.branch_id = b.branch_id
            LEFT OUTER JOIN employee e ON t.employee_id = e.employee_id
            LEFT OUTER JOIN transfer_detail td ON t.transfer_id = td.transfer_id
            GROUP BY t.transfer_id
            ORDER BY t.transfer_id DESC
        """)
    return myCursor.fetchall()


def loadTransferHeader(transfer_id):
    myCursor.execute("""
        SELECT t.transfer_id,
               t.transfer_date,
               t.warehouse_id, w.warehouse_name,
               t.branch_id, b.branch_name,
               t.employee_id, e.employee_name
        FROM transfer t
        LEFT OUTER JOIN warehouse w ON t.warehouse_id = w.warehouse_id
        LEFT OUTER JOIN branch b ON t.branch_id = b.branch_id
        LEFT OUTER JOIN employee e ON t.employee_id = e.employee_id
        WHERE t.transfer_id = %s
    """, (transfer_id,))
    return myCursor.fetchone()


def loadTransferDetails(transfer_id):
    myCursor.execute("""
        SELECT td.transfer_detail_id,
               td.transfer_id,
               td.product_id, pr.product_name,
               td.quantity
        FROM transfer_detail td
        LEFT OUTER JOIN product pr ON td.product_id = pr.product_id
        WHERE td.transfer_id = %s
        ORDER BY td.transfer_detail_id
    """, (transfer_id,))
    return myCursor.fetchall()


def loadBranchesForSelect():
    myCursor.execute("""
        SELECT branch_id, branch_name
        FROM branch
        WHERE is_deleted IS NULL
        ORDER BY branch_id
    """)
    return myCursor.fetchall()


def loadWarehouseProductsWithQty(warehouse_id):
    myCursor.execute("""
        SELECT ws.product_id, p.product_name, ws.quantity
        FROM warehouse_stock ws
        LEFT OUTER JOIN product p ON ws.product_id = p.product_id
        WHERE ws.warehouse_id = %s AND ws.quantity > 0 AND p.is_deleted IS NULL
        ORDER BY ws.product_id
    """, (warehouse_id,))
    return myCursor.fetchall()


def upsertBranchStock(branch_id, product_id, delta_qty):
    myCursor.execute("""
        INSERT INTO branch_stock (branch_id, product_id, quantity)
        VALUES (%s, %s, %s)
        ON DUPLICATE KEY UPDATE quantity = quantity + VALUES(quantity)
    """, (branch_id, product_id, delta_qty))


def getBranchStockQty(branch_id, product_id):
    myCursor.execute("""
        SELECT quantity
        FROM branch_stock
        WHERE branch_id = %s AND product_id = %s
    """, (branch_id, product_id))
    row = myCursor.fetchone()
    return float(row[0]) if row else 0.0


@app.route('/transfer/add', methods=['GET', 'POST'])
def transfer_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    wh_id = session.get('warehouse_id')
    if not wh_id and session.get('access_level') != 'admin':
        return "Access denied: Transfers are available for warehouse employees only."
    if request.method == 'GET':
        branchesData = loadBranchesForSelect()
        warehousesData = loadWarehousesForSelect() if session.get('access_level') == 'admin' else None
        warehouse_id_for_form = session.get('warehouse_id')
        productsData = loadWarehouseProductsWithQty(warehouse_id_for_form) if warehouse_id_for_form else []
        return render_template('transfer_form.html',
                               mode='add',
                               transfer=None,
                               transfer_details=None,
                               branches=branchesData,
                               warehouses=warehousesData,
                               products=productsData,
                               warehouse_id_for_form=warehouse_id_for_form)

    try:
        transfer_date = request.form.get('transfer_date')
        if not transfer_date:
            transfer_date = date.today().isoformat()

        if session.get('access_level') == 'admin':
            warehouse_id = int(request.form.get('warehouse_id'))
        else:
            warehouse_id = int(session.get('warehouse_id'))

        branch_id = request.form.get('branch_id')
        if not branch_id:
            return "Error: branch is required."

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')

        details = []
        for pid, qty in zip(product_ids, quantities):
            if not pid:
                continue
            q = float(qty) if qty else 0
            if q <= 0:
                continue
            details.append((int(pid), q))

        if len(details) == 0:
            return "Error: add at least one product line."

        # Validate warehouse stock
        for pid, qty in details:
            available = getWarehouseStockQty(warehouse_id, pid)
            if available < qty:
                return f"Not enough stock in warehouse (Product {pid} available {available}, requested {qty})."

        myCursor.execute("""
            INSERT INTO transfer (warehouse_id, branch_id, employee_id, transfer_date)
            VALUES (%s, %s, %s, %s)
        """, (warehouse_id, branch_id, session.get('user_id'), transfer_date))
        transfer_id = myCursor.lastrowid

        for pid, qty in details:
            myCursor.execute("""
                INSERT INTO transfer_detail (transfer_id, product_id, quantity)
                VALUES (%s, %s, %s)
            """, (transfer_id, pid, qty))
            # Stock move
            upsertWarehouseStock(warehouse_id, pid, -qty)
            upsertBranchStock(branch_id, pid, qty)

        salesDB.commit()
        return redirect(url_for('transfer'))
    except Exception as e:
        try:
            salesDB.rollback()
        except Exception:
            pass
        return f"Error adding transfer: {e}"


@app.route('/transfer/view/<int:transfer_id>')
def transfer_view(transfer_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    header = loadTransferHeader(transfer_id)
    details = loadTransferDetails(transfer_id)
    if not header:
        return "Transfer not found."

    if session.get('access_level') != 'admin':
        if session.get('warehouse_id') != header[2]:
            return "Access denied."

    return render_template('transfer_view.html', transfer=header, details=details)


@app.route('/transfer/edit/<int:transfer_id>', methods=['GET', 'POST'])
def transfer_edit(transfer_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('warehouse_id') is None:  # If this employee does not work at a warehouse
        return redirect(url_for('home'))
    if session.get('access_level') != 'admin':
        return "Access denied: only admin can edit transfers."

    header = loadTransferHeader(transfer_id)
    if not header:
        return "Transfer not found."

    if request.method == 'GET':
        branchesData = loadBranchesForSelect()
        warehousesData = loadWarehousesForSelect()
        details = loadTransferDetails(transfer_id)
        productsData = loadWarehouseProductsWithQty(header[2])
        return render_template('transfer_form.html',
                               mode='edit',
                               transfer=header,
                               transfer_details=details,
                               branches=branchesData,
                               warehouses=warehousesData,
                               products=productsData,
                               warehouse_id_for_form=header[2])

    try:
        transfer_date = request.form.get('transfer_date')
        warehouse_id_new = int(request.form.get('warehouse_id'))
        branch_id_new = int(request.form.get('branch_id'))

        product_ids = request.form.getlist('product_id[]')
        quantities = request.form.getlist('quantity[]')

        new_details = []
        for pid, qty in zip(product_ids, quantities):
            if not pid:
                continue
            q = float(qty) if qty else 0
            if q <= 0:
                continue
            new_details.append((int(pid), q))

        if len(new_details) == 0:
            return "Error: add at least one product line."

        warehouse_id_old = header[2]
        branch_id_old = header[4]
        old_details = loadTransferDetails(transfer_id)
        for d in old_details:
            pid = d[2]
            old_qty = float(d[4])
            current_bqty = getBranchStockQty(branch_id_old, pid)
            if current_bqty < old_qty:
                return ("Cannot edit this transfer because some quantities were already sold in the branch. "
                        f"(Branch {branch_id_old}, Product {pid} needs {old_qty} in stock, but has {current_bqty}).")

        old_map = {}
        for d in old_details:
            old_map[int(d[2])] = old_map.get(int(d[2]), 0.0) + float(d[4])

        for pid, qty in new_details:
            current_wqty = getWarehouseStockQty(warehouse_id_new, pid)
            add_back = old_map.get(pid, 0.0) if warehouse_id_new == warehouse_id_old else 0.0
            effective = current_wqty + add_back
            if effective < qty:
                return f"Not enough stock in warehouse for edit (Product {pid} available {effective}, requested {qty})."

        # Revert old stock movement
        for d in old_details:
            pid = int(d[2])
            old_qty = float(d[4])
            upsertWarehouseStock(warehouse_id_old, pid, old_qty)
            upsertBranchStock(branch_id_old, pid, -old_qty)

        # Update header
        myCursor.execute("""
            UPDATE transfer
            SET warehouse_id = %s,
                branch_id = %s,
                transfer_date = %s
            WHERE transfer_id = %s
        """, (warehouse_id_new, branch_id_new, transfer_date, transfer_id))

        myCursor.execute("DELETE FROM transfer_detail WHERE transfer_id = %s", (transfer_id,))

        for pid, qty in new_details:
            myCursor.execute("""
                INSERT INTO transfer_detail (transfer_id, product_id, quantity)
                VALUES (%s, %s, %s)
            """, (transfer_id, pid, qty))
            upsertWarehouseStock(warehouse_id_new, pid, -qty)
            upsertBranchStock(branch_id_new, pid, qty)

        salesDB.commit()
        return redirect(url_for('transfer_view', transfer_id=transfer_id))
    except Exception as e:
        try:
            salesDB.rollback()
        except Exception:
            pass
        return f"Error editing transfer: {e}"


@app.route('/transfer/delete/<int:transfer_id>', methods=['POST'])
def transfer_delete(transfer_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if session.get('access_level') != 'admin':
        return "Access denied: only admin can delete transfers."

    header = loadTransferHeader(transfer_id)
    if not header:
        return "Transfer not found."

    warehouse_id = header[2]
    branch_id = header[4]
    details = loadTransferDetails(transfer_id)

    for d in details:
        pid = int(d[2])
        qty = float(d[4])
        current_bqty = getBranchStockQty(branch_id, pid)
        if current_bqty < qty:
            return ("Cannot delete this transfer because some quantities were already sold in the branch. "f"(Branch {branch_id}, Product {pid} needs {qty} in stock, but has {current_bqty}).")

    try:

        # Revert stock
        for d in details:
            pid = int(d[2])
            qty = float(d[4])
            upsertWarehouseStock(warehouse_id, pid, qty)
            upsertBranchStock(branch_id, pid, -qty)

        myCursor.execute("DELETE FROM transfer_detail WHERE transfer_id = %s", (transfer_id,))
        myCursor.execute("DELETE FROM transfer WHERE transfer_id = %s", (transfer_id,))

        salesDB.commit()
        return redirect(url_for('transfer'))
    except Exception as e:
        try:
            salesDB.rollback()
        except Exception:
            pass
        return f"Error deleting transfer: {e}"

# === Reports ===

@app.route('/reports')
def reports():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    myCursor.execute("SELECT branch_id, branch_name FROM branch ORDER BY branch_id")  # Get Branch ID + Name
    branchesData = myCursor.fetchall()
    reportsSQL = {  # Each SQL Report has an id, a name, an SQL code and a type (bar chart, line chart, pie chart or table)
        "1": {
            "name": "Total Income per branch",
            "type": "bar",
            "sql": """
            SELECT b.branch_name, SUM(sd.quantity*sd.kg_price_at_sale_time)
            FROM branch b,sale s,sale_detail sd
            WHERE s.branch_id = b.branch_id AND sd.sale_id = s.sale_id AND s.is_deleted is NULL and b.is_deleted is NULL AND sd.is_deleted is NULL
            AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
            GROUP BY b.branch_name
                """
        },
        "2": {
            "name": "Number of sales per branch",
            "type": "bar",
            "sql": """
            SELECT b.branch_name, COUNT(*)
            FROM branch b, sale s
            WHERE s.branch_id = b.branch_id AND b.is_deleted is NULL AND s.is_deleted is NULL
            AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
            GROUP BY branch_name
                """
        },
        "3": {
            "name": "Average amount of money in a sale per branch",
            "type": "bar",
            "sql": """
            SELECT b.branch_name, AVG(s1.amount)
            FROM branch b JOIN (
                            SELECT s.sale_id, s.branch_id, SUM(sd.quantity * kg_price_at_sale_time) AS amount
                            FROM sale s, sale_detail sd
                            WHERE s.sale_id = sd.sale_id AND s.is_deleted is NULL and sd.is_deleted is NULL
                            AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
                            GROUP BY s.branch_id, s.sale_id ) s1 ON b.branch_id = s1.branch_id
            WHERE b.branch_id = s1.branch_id AND b.is_deleted is NULL
            GROUP BY b.branch_name
                """
        },
        "4": {
            "name": "Daily Sales Amount for a chosen branch",
            "type": "line",
            "sql": """
            SELECT s.sale_date, SUM(sd.quantity*kg_price_at_sale_time)
            FROM sale s, sale_detail sd
            WHERE s.sale_id = sd.sale_id AND s.is_deleted is NULL AND sd.is_deleted is NULL AND s.branch_id = %s
            AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
            GROUP BY s.sale_date
                """
        },
        "5": {
            "name": "Number of sales by employee",
            "type": "table",
            "sql": """
            SELECT e.employee_name AS Employee_Name, COUNT(*) As Number_Of_Sales
            FROM employee e, sale s
            WHERE e.employee_id = s.employee_id AND e.is_deleted is NULL AND s.is_deleted is NULL
            AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
            GROUP BY e.employee_name
            ORDER BY Number_Of_Sales DESC 
                """
        },
        "6": {
            "name": "Total amount of money each product sold for",
            "type": "table",
            "sql": """
            SELECT p.product_id AS Product_ID, p.product_name AS Product_Name, SUM(sd.quantity * sd.kg_price_at_sale_time) AS Total_Sales_Amount
            FROM product p, sale_detail sd, sale s
            WHERE p.product_id = sd.product_id AND sd.is_deleted is NULL AND s.is_deleted is NULL AND s.sale_id = sd.sale_id
            AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
            GROUP BY p.product_id, p.product_name
            ORDER BY Total_Sales_Amount DESC
                """
        },
        "7": {
            "name": "Sales amount for each product category",
            "type": "pie",
            "sql": """
                SELECT p.category, SUM(sd.quantity*sd.kg_price_at_sale_time)
                FROM product p, sale_detail sd, sale s
                WHERE p.product_id = sd.product_id AND sd.is_deleted is NULL AND s.is_deleted is NULL AND s.sale_id = sd.sale_id
                AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
                GROUP BY p.category
                """
        },
        "8": {
            "name": "Registered Customers and total amount spent by each one",
            "type": "table",
            "sql": """
            SELECT c.customer_id AS Customer_ID, c.customer_name AS Customer_Name, SUM(sd.quantity*sd.kg_price_at_sale_time) AS Total_Amount_Spent
            FROM customer c, sale_detail sd, sale s
            WHERE s.customer_id = c.customer_id AND s.sale_id = sd.sale_id AND s.is_deleted is NULL AND sd.is_deleted is NULL
            AND (%s is NULL or s.sale_date >= %s) AND (%s is NULL or s.sale_date <= %s)
            GROUP BY c.customer_id, c.customer_name
            ORDER BY Total_Amount_Spent DESC 
                """
        },
        "9": {
            "name": "Total payments amounts per supplier",
            "type": "table",
            "sql": """
            SELECT s.supplier_id AS Supplier_ID, s.supplier_name AS Supplier_Name, SUM(pay.amount) AS Total_Payments_Amount
            FROM supplier s, payment pay, purchase p
            WHERE s.supplier_id = p.supplier_id AND pay.purchase_id = p.purchase_id AND s.is_deleted is NULL AND pay.is_deleted is NULL AND p.is_deleted is NULL
            AND (%s is NULL or pay.payment_date >= %s) AND (%s is NULL or pay.payment_date <= %s)
            GROUP BY s.supplier_id, s.supplier_name
            ORDER BY Total_Payments_Amount DESC
                """
        },
        "10": {  # Total Unpaid Amount Per Supplier = Total Required Amounts per Supplier - Total Paid amounts per supplier
            "name": "Total unpaid amount per supplier",
            "type": "table",
            "sql": """
            SELECT s.supplier_id AS Supplier_ID, s.supplier_name AS Supplier_Name, SUM(IFNULL(remaining.amount,0)-IFNULL(paid.amount,0)) AS Unpaid_Amount
            FROM supplier s LEFT OUTER JOIN (SELECT s1.supplier_id, SUM(pay1.amount) AS amount
                              FROM supplier s1, payment pay1, purchase p1
                              WHERE s1.supplier_id = p1.supplier_id AND pay1.purchase_id = p1.purchase_id AND s1.is_deleted is NULL AND pay1.is_deleted is NULL AND p1.is_deleted is NULL
                              GROUP BY s1.supplier_id) paid ON s.supplier_id = paid.supplier_id LEFT OUTER JOIN
                              (
                              SELECT s2.supplier_id, SUM(pd.quantity*pd.kg_price_at_purchase_time) AS amount
                              FROM supplier s2, purchase p2, purchase_detail pd
                              WHERE s2.supplier_id = p2.supplier_id AND pd.purchase_id = p2.purchase_id AND s2.is_deleted is NULL AND p2.is_deleted is NULL AND pd.is_deleted is NULL
                              GROUP BY s2.supplier_id) remaining ON s.supplier_id = remaining.supplier_id
            WHERE s.is_deleted is NULL
            GROUP BY s.supplier_id, s.supplier_name
            ORDER BY Unpaid_Amount DESC
                """
        }        ,
        "11": {
            "name": "Total purchase value per warehouse",
            "type": "bar",
            "sql": """
        SELECT w.warehouse_name, SUM(pd.quantity * pd.kg_price_at_purchase_time) AS total_purchase_value
        FROM warehouse w, purchase p, purchase_detail pd
        WHERE w.warehouse_id = p.warehouse_id
          AND pd.purchase_id = p.purchase_id
          AND p.is_deleted IS NULL
          AND pd.is_deleted IS NULL
          AND (%s is NULL or p.purchase_date >= %s) AND (%s is NULL or p.purchase_date <= %s)
        GROUP BY w.warehouse_name
        ORDER BY total_purchase_value DESC
            """
        },

        "12": {
            "name": "Number of purchases per warehouse",
            "type": "bar",
            "sql": """
        SELECT w.warehouse_name, COUNT(*) AS purchases_count
        FROM warehouse w, purchase p
        WHERE w.warehouse_id = p.warehouse_id
          AND p.is_deleted IS NULL
          AND (%s is NULL or p.purchase_date >= %s) AND (%s is NULL or p.purchase_date <= %s)
        GROUP BY w.warehouse_name
        ORDER BY purchases_count DESC
            """
        },

        "13": {
            "name": "Total purchased amount per supplier",
            "type": "table",
            "sql": """
        SELECT s.supplier_id AS Supplier_ID, s.supplier_name AS Supplier_Name,
               SUM(pd.quantity * pd.kg_price_at_purchase_time) AS Total_Purchased_Amount
        FROM supplier s, purchase p, purchase_detail pd
        WHERE s.supplier_id = p.supplier_id
          AND pd.purchase_id = p.purchase_id
          AND s.is_deleted IS NULL
          AND p.is_deleted IS NULL
          AND pd.is_deleted IS NULL
          AND (%s is NULL or p.purchase_date >= %s) AND (%s is NULL or p.purchase_date <= %s)
        GROUP BY s.supplier_id, s.supplier_name
        ORDER BY Total_Purchased_Amount DESC
            """
        },

        "14": {
            "name": "Average purchase value per supplier",
            "type": "bar",
            "sql": """
        SELECT s.supplier_name, AVG(x.purchase_total) AS avg_purchase_value
        FROM supplier s JOIN (
            SELECT p.purchase_id, p.supplier_id,
                   SUM(pd.quantity * pd.kg_price_at_purchase_time) AS purchase_total,
                   p.purchase_date
            FROM purchase p, purchase_detail pd
            WHERE p.purchase_id = pd.purchase_id
              AND p.is_deleted IS NULL
              AND pd.is_deleted IS NULL
              AND (%s is NULL or p.purchase_date >= %s) AND (%s is NULL or p.purchase_date <= %s)
            GROUP BY p.purchase_id, p.supplier_id, p.purchase_date
        ) x ON s.supplier_id = x.supplier_id
        WHERE s.is_deleted IS NULL
        GROUP BY s.supplier_name
        ORDER BY avg_purchase_value DESC
            """
        },

        "15": {
            "name": "Payment method distribution (by total amount)",
            "type": "pie",
            "sql": """
        SELECT pay.method, SUM(pay.amount) AS total_amount
        FROM payment pay
        WHERE pay.is_deleted is NULL
        AND (%s is NULL or pay.payment_date >= %s) AND (%s is NULL or pay.payment_date <= %s)
        GROUP BY pay.method
        ORDER BY total_amount DESC
            """
        },

        "16": {
            "name": "Number of transfers per branch",
            "type": "bar",
            "sql": """
        SELECT b.branch_name, COUNT(*) AS transfers_count
        FROM branch b, transfer t
        WHERE b.branch_id = t.branch_id AND b.is_deleted is NULL
        AND (%s is NULL or t.transfer_date >= %s) AND (%s is NULL or t.transfer_date <= %s)
        GROUP BY b.branch_name
        ORDER BY transfers_count DESC
            """
        },

        "17": {
            "name": "Total quantity transferred to each branch",
            "type": "bar",
            "sql": """
        SELECT b.branch_name, SUM(td.quantity) AS total_transferred_qty
        FROM branch b, transfer t, transfer_detail td
        WHERE b.branch_id = t.branch_id AND t.transfer_id = td.transfer_id AND b.is_deleted is NULL
        AND (%s is NULL or t.transfer_date >= %s) AND (%s is NULL or t.transfer_date <= %s)
        GROUP BY b.branch_name
        ORDER BY total_transferred_qty DESC
            """
        },

        "18": {
            "name": "Top transferred products by quantity",
            "type": "table",
            "sql": """
        SELECT pr.product_id AS Product_ID, pr.product_name AS Product_Name,
               SUM(td.quantity) AS Total_Transferred_Qty
        FROM transfer t, transfer_detail td, product pr
        WHERE t.transfer_id = td.transfer_id AND pr.product_id = td.product_id
        AND (%s is NULL or t.transfer_date >= %s) AND (%s is NULL or t.transfer_date <= %s)
        GROUP BY pr.product_id, pr.product_name
        ORDER BY Total_Transferred_Qty DESC
            """
        },

        "19": {
            "name": "Out-of-stock products at warehouses",
            "type": "table",
            "sql": """
        SELECT w.warehouse_name AS Warehouse_Name,
               p.product_id AS Product_ID,
               p.product_name AS Product_Name,
               ws.quantity AS Quantity
        FROM warehouse_stock ws, warehouse w, product p
        WHERE ws.warehouse_id = w.warehouse_id
          AND ws.product_id = p.product_id
          AND ws.quantity <= 0
          AND (p.is_deleted IS NULL)
        ORDER BY w.warehouse_name, p.product_name
            """
        },

        "20": {
            "name": "Out-of-stock products at retail branches",
            "type": "table",
            "sql": """
        SELECT b.branch_name AS Branch_Name,
               p.product_id AS Product_ID,
               p.product_name AS Product_Name,
               bs.quantity AS Quantity
        FROM branch_stock bs, branch b, product p
        WHERE bs.branch_id = b.branch_id
          AND bs.product_id = p.product_id
          AND bs.quantity <= 0
          AND (p.is_deleted IS NULL)
        ORDER BY b.branch_name, p.product_name
            """
        }
    }
    report_id = request.args.get('r_id')
    start_date = request.args.get('start_date') or None
    end_date = request.args.get('end_date') or None
    branch_id = request.args.get('branch_id') or None
    int_branch_id = None
    if branch_id:
        int_branch_id = int(branch_id)
    sql = reportsSQL.get(report_id)
    generate = request.args.get('generate') or None
    queryData = None
    chartLabels = []
    chartValues = []
    if generate:
        if sql:
            if report_id == "4":
                myCursorDict.execute(sql["sql"], (branch_id, start_date, start_date, end_date, end_date))
            elif report_id =="10" or report_id == "20" or report_id == "19":
                myCursorDict.execute(sql["sql"])
            else:
                myCursorDict.execute(sql["sql"], (start_date, start_date, end_date, end_date))
            queryData = myCursorDict.fetchall()
            if queryData and sql["type"] != "table":
                column_names = list(queryData[0].keys())
                labels_name = column_names[0]
                values_name = column_names[1]
                for data in queryData:
                    chartLabels.append(data[labels_name])
                    chartValues.append(data[values_name])
    return render_template('reports.html', reports=reportsSQL, selected_report_id=report_id, selected_report=sql, query_data=queryData, start_date=start_date, end_date=end_date, branch_id=int_branch_id, generate=generate, branches=branchesData, chart_labels=chartLabels, chart_values=chartValues)


# === Employees ===
def loadEmpData():
    myCursor.execute(
        """
            SELECT e.employee_id, e.employee_name, e.phone_number, e.date_of_birth, e.position, e.salary, e.warehouse_id, w.warehouse_name, e.branch_id, b.branch_name,e.is_deleted,e.access_level,e.user_password
            FROM employee e LEFT OUTER JOIN warehouse w ON e.warehouse_id = w.warehouse_id LEFT OUTER JOIN branch b ON e.branch_id = b.branch_id
            WHERE e.is_deleted is NULL
            ORDER BY e.employee_id
            """
    )
    empData = myCursor.fetchall()  # Save the selected data
    myCursor.execute("SELECT warehouse_id, warehouse_name FROM warehouse ORDER BY warehouse_id")  # Get Warehouse ID + Name
    warehousesData = myCursor.fetchall()
    myCursor.execute("SELECT branch_id, branch_name FROM branch ORDER BY branch_id")  # Get Branch ID + Name
    branchesData = myCursor.fetchall()
    myCursor.execute(
        """
            SELECT e.employee_id, e.employee_name, e.phone_number, e.date_of_birth, e.position, e.salary, e.warehouse_id, w.warehouse_name, e.branch_id, b.branch_name,e.is_deleted
            FROM employee e LEFT OUTER JOIN warehouse w ON e.warehouse_id = w.warehouse_id LEFT OUTER JOIN branch b ON e.branch_id = b.branch_id
            WHERE e.is_deleted = 1
            ORDER BY e.employee_id
            """)
    deletedEmpData = myCursor.fetchall()
    employeesData = []  # List of employees data
    """
    The list contains employees, each employee is represented as a tuple "t" with the following format:
    t[0] = Employee ID, t[1] = Employee Name, t[2] = Employee Phone Number
    t[3] = Employee Date of Birth, t[4] = Employee Position, t[5] = Employee Salary
    t[6] = Warehouse ID, t[7] = Warehouse Name, t[8] = Branch ID, t[9] = Branch Name,
    t[10] = 1 if the employee is deleted else NULL, t[11]= Access level (if "admin" then full access)
    t[12] = Password used by the employee to sign in
    """
    for emp in empData:
        if emp[3]:  # Format date of birth into YYYY-MM-DD if it exists
            dob = emp[3].strftime('%Y-%m-%d')
        else:
            dob = ''
        employeesData.append((emp[0], emp[1], emp[2], dob, emp[4], emp[5], emp[6], emp[7], emp[8], emp[9], emp[10], emp[11], emp[12]))
    return employeesData, warehousesData, branchesData, deletedEmpData


@app.route('/employees')
def employees():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    employeesData, warehousesData, branchesData, deletedEmpData = loadEmpData()
    return render_template('employees.html', employees=employeesData, warehouses=warehousesData, branches=branchesData)


@app.route('/employees/deleted')
def employees_deleted():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    employeesData, warehousesData, branchesData, deletedEmpData = loadEmpData()
    return render_template('employees_deleted.html', employees=deletedEmpData, warehouses=warehousesData, branches=branchesData)


def getEmpFormData(form):  # Extracts Employee data from input form
    name = form['employee_name'].strip()
    phone = form['phone_number'].strip()
    if form.get('salary'):
        salary = float(form['salary'])
    else:
        salary = None
    year = form.get('dob_year')
    month = form.get('dob_month')
    day = form.get('dob_day')
    if year and month and day:
        dob = f"{int(year):04d}-{int(month):02d}-{int(day):02d}"
    else:
        dob = None
    position = form['position'] or None
    if form.get('warehouse_id'):
        warehouse_id = int(form['warehouse_id'])
    else:
        warehouse_id = None
    if form.get('branch_id'):
        branch_id = int(form['branch_id'])
    else:
        branch_id = None
    if form.get('user_password'):
        password = form['user_password']
    else:
        password = phone  # Default password when adding an employee is set to the phone number
    access_level = form.get('access_level')
    return (name, phone, dob, position, salary, warehouse_id, branch_id, password, access_level)


@app.route('/employees/add', methods=['GET', 'POST'])
def employees_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    employeesData, warehousesData, branchesData, deletedEmpData = loadEmpData()
    if request.method == 'GET':  # If the page is loading
        return render_template('employees_form.html', action=url_for('employees_add'), emp=None, warehouses=warehousesData, branches=branchesData)
    if request.method == 'POST':  # If the user is submitting a new employee
        empForm = request.form  # Returns a dictionary with the added employee data
        try:
            employeeData = getEmpFormData(empForm)  # Gets the employee data from the form
            myCursor.execute("""
                INSERT INTO employee (employee_name, phone_number, date_of_birth, position, salary, warehouse_id, branch_id, user_password, access_level, is_deleted)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)
            """, employeeData)
            salesDB.commit()
        except Exception as e:
            flash(f"Error adding employee: {e}")
    return redirect(url_for('employees'))


@app.route('/employees/edit/<int:emp_id>', methods=['GET', 'POST'])
def employees_edit(emp_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    employeesData, warehousesData, branchesData, deletedEmpData = loadEmpData()
    if request.method == 'GET':
        emp = None  # Look for the employee data, to edit
        for e in employeesData+deletedEmpData:  # Look in employees and deleted employees
            if e[0] == emp_id:
                emp = e
                break
        return render_template('employees_form.html', action=url_for('employees_edit', emp_id=emp_id), emp=emp, warehouses=warehousesData, branches=branchesData)
    else:
        empForm = request.form
        try:
            emp_data = getEmpFormData(empForm)
            myCursor.execute("""
                UPDATE employee
                SET employee_name=%s, phone_number=%s, date_of_birth=%s, position=%s, salary=%s, warehouse_id=%s, branch_id=%s, user_password=%s, access_level=%s
                WHERE employee_id=%s
            """, emp_data + (emp_id,))
            salesDB.commit()
        except Exception as e:
            flash(f"Error updating employee: {e}")
    return redirect(url_for('employees'))

@app.route('/employees/delete/<int:emp_id>', methods=['POST'])
def employees_delete(emp_id):  # Deletes an existing employee, this sets the is_deleted to 1, but the employee data is kept
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("UPDATE employee SET is_deleted=1 WHERE employee_id=%s", (emp_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"Error deleting employee: {e}")
    return redirect(url_for('employees'))


@app.route('/employees/recover/<int:emp_id>', methods=['POST'])
def employees_recover(emp_id):  # Recovers a deleted employee
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("UPDATE employee SET is_deleted=NULL WHERE employee_id=%s", (emp_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"Error recovering employee: {e}")
    return redirect(url_for('employees_deleted'))


# === Branches ===

def loadBranchesData():
    myCursor.execute("""
    SELECT *
    FROM branch
    WHERE is_deleted is NULL
    """)
    branchesData = myCursor.fetchall()
    # Branches Data [0] = ID, [1] = Name, [2] = Location, [3] = Phone Number, [4] = is_deleted
    return branchesData


def loadDeletedBranchesData():
    myCursor.execute("""
    SELECT *
    FROM branch
    WHERE is_deleted = 1
    """)
    branchesData = myCursor.fetchall()
    # Branches Data [0] = ID, [1] = Name, [2] = Location, [3] = Phone Number, [4] = is_deleted
    return branchesData


@app.route('/branches')
def branches():  # Branches can be viewed by a normal employee, but can only be added,edited or deleted by an admin level employee
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    return render_template('branches.html', branches=loadBranchesData())


@app.route('/branches/deleted')
def branches_deleted():  # Deleted Branches can be viewed by admin
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    return render_template('branches_deleted.html', branches=loadDeletedBranchesData())


def getBranchDataFromForm(form):
    name = form['branch_name'].strip()
    location = form['branch_location'].strip()
    phone = form['branch_phone'].strip()
    return (name, location, phone)


@app.route('/branches/add', methods=['GET', 'POST'])
def branches_add():  # Add a new branch, requires admin access level
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    if request.method == 'GET':  # If the page is loading
        return render_template('branches_form.html', action=url_for('branches_add'), b=None)
    if request.method == 'POST':  # If the user is submitting a new branch
        branchForm = request.form  # Returns a dictionary with the added branch data
        try:
            brData = getBranchDataFromForm(branchForm)  # Gets the branch data from the form
            myCursor.execute("""
                INSERT INTO branch (branch_name, location, phone_number,is_deleted)
                VALUES (%s,%s,%s,NULL)
            """, brData)
            salesDB.commit()
        except Exception as e:
            flash(f"error adding branch: {e}")
    return redirect(url_for('branches'))


@app.route('/branches/edit/<int:br_id>', methods=['GET', 'POST'])
def branches_edit(br_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    branchesData = loadBranchesData()
    br = None  # Look for the branch data, to edit
    for b in branchesData:  # Look in branches data
        if b[0] == br_id:
            br = b
            break
    if request.method == 'GET':  # If the page is loading
        return render_template('branches_form.html', action=url_for('branches_edit', br_id=br_id), b=br)
    if request.method == 'POST':  # If the user is submitting a new branch
        branchForm = request.form  # Returns a dictionary with the added branch data
        try:
            brData = getBranchDataFromForm(branchForm)  # Gets the branch data from the form
            myCursor.execute("""
                UPDATE branch
                SET branch_name=%s, location=%s, phone_number=%s
                WHERE branch_id=%s
            """, brData + (br_id,))
            salesDB.commit()
        except Exception as e:
            flash(f"error updating branch: {e}")
    return redirect(url_for('branches'))


@app.route('/branches/delete/<int:br_id>', methods=['POST'])
def branches_delete(br_id):  # Deletes an existing branch, this sets the is_deleted to 1, but the branch data is kept
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("UPDATE branch SET is_deleted=1 WHERE branch_id=%s", (br_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"error deleting branch: {e}")
    return redirect(url_for('branches'))


@app.route('/branches/recover/<int:br_id>', methods=['POST'])
def branches_recover(br_id):  # Recovers a deleted branch
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return redirect(url_for('home'))
    try:
        myCursor.execute("UPDATE branch SET is_deleted=NULL WHERE branch_id=%s", (br_id,))
        salesDB.commit()
    except Exception as e:
        flash(f"error recovering branch: {e}")
    return redirect(url_for('branches_deleted'))

# ====warehouses====

@app.route('/warehouses')
def warehouses():
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    myCursor.execute("""
        SELECT warehouse_id, warehouse_name, location, phone_number
        FROM warehouse
        ORDER BY warehouse_id
    """)
    warehousesData = myCursor.fetchall()
    return render_template('warehouses.html', warehouses=warehousesData)

@app.route('/warehouses/add', methods=['GET', 'POST'])
def warehouses_add():
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return "Access denied: only admin can add warehouses."
    if request.method == 'GET':
        return render_template('warehouses_form.html', mode='add', warehouse=None)
    try:
        name = request.form.get('warehouse_name')
        location = request.form.get('location')
        phone = request.form.get('phone_number')
        if not name or not location:
            return "Error: warehouse name and location are required."
        myCursor.execute("""
            INSERT INTO warehouse (warehouse_name, location, phone_number)
            VALUES (%s, %s, %s)
        """, (name, location, phone))
        salesDB.commit()
        return redirect(url_for('warehouses'))
    except Exception as e:
        return f"Error adding warehouse: {e}"
@app.route('/warehouses/edit/<int:warehouse_id>', methods=['GET', 'POST'])
def warehouses_edit(warehouse_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))
    if session.get('access_level') != 'admin':
        return "Access denied: only admin can edit warehouses."
    myCursor.execute("""
        SELECT warehouse_id, warehouse_name, location, phone_number
        FROM warehouse
        WHERE warehouse_id = %s
    """, (warehouse_id,))
    warehouse = myCursor.fetchone()
    if not warehouse:
        return "Warehouse not found."
    if request.method == 'GET':
        return render_template('warehouses_form.html', mode='edit', warehouse=warehouse)
    try:
        name = request.form.get('warehouse_name')
        location = request.form.get('location')
        phone = request.form.get('phone_number')
        myCursor.execute("""
            UPDATE warehouse
            SET warehouse_name = %s,
                location = %s,
                phone_number = %s
            WHERE warehouse_id = %s
        """, (name, location, phone, warehouse_id))
        salesDB.commit()
        return redirect(url_for('warehouses'))
    except Exception as e:
        return f"Error editing warehouse: {e}"
@app.route('/warehouses/delete/<int:warehouse_id>', methods=['POST'])
def warehouses_delete(warehouse_id):
    if 'logged_in' not in session:
        return redirect(url_for('login'))

    if session.get('access_level') != 'admin':
        return "Access denied: only admin can delete warehouses."

    try:
        myCursor.execute("DELETE FROM warehouse WHERE warehouse_id = %s", (warehouse_id,))
        salesDB.commit()
        return redirect(url_for('warehouses'))
    except Exception as e:
        return ("Cannot delete this warehouse (it has related purchases/transfers/stock). "f"Error: {e}")

# === Log out ===


@app.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    session.pop('logged_in', None)
    session.pop('access_level', None)
    session.pop('user_name', None)
    session.pop('branch_id', None)
    session.pop('warehouse_id', None)
    return redirect(url_for('login'))


if __name__ == '__main__':
    app.run()
