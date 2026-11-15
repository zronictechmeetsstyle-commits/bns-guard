from datetime import datetime, timedelta
import io
import os
import socket
import sqlite3
from flask import (
    Flask,
    jsonify,
    redirect,
    render_template_string,
    request,
    send_file,
    url_for,
)
import qrcode

app = Flask(__name__)

# Correct absolute path for SQLite database in the script's folder
BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bns_guard.db')


def get_local_ip():
  try:
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(('8.8.8.8', 80))
    ip = s.getsockname()[0]
    s.close()
    return ip
  except Exception:
    return '127.0.0.1'


def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  # 1. Customers Table Create with GPS Columns
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS customers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            phone_model TEXT NOT NULL,
            imei TEXT NOT NULL,
            android_id TEXT,
            total_price REAL NOT NULL,
            advance_paid REAL NOT NULL,
            months INTEGER NOT NULL,
            remaining_balance REAL NOT NULL,
            monthly_installment REAL NOT NULL,
            due_date TEXT NOT NULL,
            status TEXT DEFAULT 'ACTIVE',
            latitude TEXT,
            longitude TEXT
        )
    ''')

  # Safe Migration: Check if missing columns exist in older database, add them automatically
  cursor.execute("PRAGMA table_info(customers)")
  columns = [col[1] for col in cursor.fetchall()]
  if 'android_id' not in columns:
    cursor.execute('ALTER TABLE customers ADD COLUMN android_id TEXT')
  if 'latitude' not in columns:
    cursor.execute('ALTER TABLE customers ADD COLUMN latitude TEXT')
  if 'longitude' not in columns:
    cursor.execute('ALTER TABLE customers ADD COLUMN longitude TEXT')

  # 2. Customer Details Table Create
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS customer_details (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            customer_phone TEXT,
            nic_number TEXT,
            witness_name TEXT,
            witness_phone TEXT,
            address TEXT,
            notes TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
        )
    ''')

  # 3. Payments Table Create
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer_id INTEGER,
            amount_paid REAL NOT NULL,
            payment_date TEXT NOT NULL,
            month_label TEXT NOT NULL,
            FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
        )
    ''')

  conn.commit()
  conn.close()


with app.app_context():
  init_db()


@app.route('/')
def index():
  search_query = request.args.get('search', '').strip()

  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  if search_query:
    cursor.execute(
        '''
            SELECT DISTINCT c.* FROM customers c 
            LEFT JOIN customer_details d ON c.id = d.customer_id
            WHERE c.name LIKE ? OR c.imei LIKE ? OR c.android_id LIKE ? OR d.customer_phone LIKE ?
        ''',
        (
            f'%{search_query}%',
            f'%{search_query}%',
            f'%{search_query}%',
            f'%{search_query}%',
        ),
    )
  else:
    cursor.execute('SELECT * FROM customers')

  customers = cursor.fetchall()
  conn.close()

  html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>BNS-GUARD-01 Admin Panel</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; direction: ltr; }
            h2 { color: #333; margin-bottom: 5px; }
            table { width: 100%; border-collapse: collapse; background: #fff; margin-top: 20px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
            th, td { padding: 10px; border: 1px solid #ddd; text-align: center; font-size: 14px; }
            th { background-color: #007bff; color: white; }
            form { background: #fff; padding: 20px; margin-top: 15px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); border-radius: 5px; display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
            input, select, textarea { padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
            button { background: #28a745; color: white; border: none; padding: 10px; cursor: pointer; border-radius: 4px; font-size: 16px; }
            button:hover { background: #218838; }
            .search-section { background: #fff; padding: 15px; margin-top: 15px; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); display: flex; justify-content: space-between; align-items: center; }
            .search-form { display: flex; gap: 10px; margin: 0; padding: 0; background: none; box-shadow: none; width: 100%; }
            .search-form input { flex: 1; padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
            .search-form button { background: #007bff; padding: 10px 20px; font-size: 14px; grid-column: auto; }
            .badge-active { color: green; font-weight: bold; }
            .badge-locked { color: red; font-weight: bold; }
            .highlight { background-color: #fff3cd; font-weight: bold; }
            .inst-highlight { background-color: #d4edda; font-weight: bold; color: #155724; }
            .btn-action { text-decoration: none; padding: 6px 10px; color: white; border-radius: 3px; font-size: 11px; display: inline-block; margin: 2px; }
            .btn-delete { background: #dc3545; }
            .btn-delete:hover { background: #c82333; }
            .top-actions { margin-bottom: 15px; }
        </style>
    </head>
    <body>
        <h2>BNS-GUARD-01 - Admin Dashboard & Portfolio Control</h2>
        
        <div class="top-actions">
            <a href="/admin/update-qr" target="_blank" style="background: #17a2b8; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; display: inline-block; font-weight: bold;">📱 Get Master App Update QR</a>
        </div>

        <div class="search-section">
            <form class="search-form" method="GET" action="/">
                <input type="text" name="search" placeholder="Search customer by Name, IMEI, Android ID, or Phone..." value="{{ request.args.get('search', '') }}">
                <button type="submit">Search</button>
                {% if request.args.get('search') %}
                    <a href="/" style="background: #6c757d; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; display: inline-block; font-size: 14px;">Reset</a>
                {% endif %}
            </form>
        </div>

        <form action="/add" method="POST">
            <input type="text" name="name" placeholder="Customer Name" required>
            <input type="text" name="phone_model" placeholder="Phone Model" required>
            <input type="text" name="imei" placeholder="IMEI Number" required>
            <input type="text" name="android_id" placeholder="Android ID (Optional)">
            <input type="number" step="any" name="total_price" placeholder="Base Price (e.g. 43000)" required>
            <input type="number" step="any" name="advance_paid" placeholder="Advance / Down Payment" required>
            <input type="number" name="months" placeholder="Installment Months (e.g. 6)" required>
            <input type="date" name="due_date" required>
            <button type="submit" style="grid-column: span 4;">Calculate & Save Customer</button>
        </form>

        <table>
            <tr>
                <th>ID</th>
                <th>Name</th>
                <th>Model</th>
                <th>IMEI</th>
                <th>Android ID</th>
                <th>Total Price</th>
                <th>Advance</th>
                <th>Months</th>
                <th>Remaining</th>
                <th>Monthly Inst.</th>
                <th>Due Date</th>
                <th>GPS Location</th>
                <th>Status</th>
                <th>Actions</th>
            </tr>
            {% for c in customers %}
            <tr>
                <td>{{ c['id'] }}</td>
                <td>{{ c['name'] }}</td>
                <td>{{ c['phone_model'] }}</td>
                <td>{{ c['imei'] }}</td>
                <td>{{ c['android_id'] if c['android_id'] else '-' }}</td>
                <td>Rs. {{ c['total_price'] }}</td>
                <td>Rs. {{ c['advance_paid'] }}</td>
                <td>{{ c['months'] }} Months</td>
                <td class="highlight">Rs. {{ c['remaining_balance'] }}</td>
                <td class="inst-highlight">Rs. {{ "%.2f"|format(c['monthly_installment']) }}</td>
                <td>{{ c['due_date'] }}</td>
                <td>
                    {% if c['latitude'] and c['longitude'] %}
                        <a href="https://maps.google.com/?q={{ c['latitude'] }},{{ c['longitude'] }}" target="_blank" style="background: #e83e8c; color: white; padding: 4px 8px; border-radius: 3px; text-decoration: none; font-size: 11px;">📍 View Map</a>
                    {% else %}
                        <span style="color: #777; font-size: 11px;">No Signal</span>
                    {% endif %}
                </td>
                <td>
                    {% if c['status'] == 'ACTIVE' %}
                        <span class="badge-active">ACTIVE</span>
                    {% else %}
                        <span class="badge-locked">LOCKED</span>
                    {% endif %}
                </td>
                <td>
                    <a href="/portfolio/{{ c['id'] }}" class="btn-action" style="background: #007bff;">Portfolio</a>
                    <a href="/customer/{{ c['id'] }}" class="btn-action" style="background: #17a2b8;">Details</a>
                    <a href="/print/{{ c['id'] }}" class="btn-action" style="background: #6f42c1;" target="_blank">Print</a>
                    <a href="/qrcode/{{ c['id'] }}" class="btn-action" style="background: #20c997;" target="_blank">Get QR</a>
                    <a href="/toggle/{{ c['id'] }}" class="btn-action" style="background: #ffc107; color: black;">{% if c['status'] == 'ACTIVE' %}Lock{% else %}Unlock{% endif %}</a>
                    <a href="/delete/{{ c['id'] }}" class="btn-action btn-delete" onclick="return confirm('Are you sure you want to delete this customer entry? All related payments and details will be permanently removed.')">Delete</a>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="14" style="color: #777; padding: 20px;">No customers found.</td>
            </tr>
            {% endfor %}
        </table>
    </body>
    </html>
    """
  return render_template_string(html_template, customers=customers)


@app.route('/add', methods=['POST'])
def add_customer():
  name = request.form['name']
  phone_model = request.form['phone_model']
  imei = request.form['imei']
  android_id = request.form.get('android_id', '').strip()
  base_price = float(request.form['total_price'])
  advance_paid = float(request.form['advance_paid'])
  months = int(request.form['months'])
  due_date = request.form['due_date']

  if months <= 3:
    profit = base_price * 0.15
  else:
    profit = base_price * 0.30

  total_price = base_price + profit
  remaining_balance = total_price - advance_paid
  monthly_installment = remaining_balance / months if months > 0 else 0

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      '''
        INSERT INTO customers (name, phone_model, imei, android_id, total_price, advance_paid, months, remaining_balance, monthly_installment, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
    ''',
      (
          name,
          phone_model,
          imei,
          android_id,
          round(total_price, 2),
          advance_paid,
          months,
          round(remaining_balance, 2),
          round(monthly_installment, 2),
          due_date,
      ),
  )
  conn.commit()
  conn.close()

  return redirect(url_for('index'))


@app.route('/portfolio/<int:id>', methods=['GET', 'POST'])
def customer_portfolio(id):
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  if request.method == 'POST':
    amount_paid = float(request.form['amount_paid'])
    month_label = request.form['month_label']
    payment_date = datetime.now().strftime('%Y-%m-%d %H:%M')

    cursor.execute(
        '''
            INSERT INTO payments (customer_id, amount_paid, payment_date, month_label)
            VALUES (?, ?, ?, ?)
        ''',
        (id, amount_paid, payment_date, month_label),
    )

    cursor.execute(
        '''
            UPDATE customers SET remaining_balance = remaining_balance - ? WHERE id = ?
        ''',
        (amount_paid, id),
    )

    conn.commit()
    conn.close()
    return redirect(url_for('customer_portfolio', id=id))

  cursor.execute('SELECT * FROM customers WHERE id = ?', (id,))
  customer = cursor.fetchone()

  cursor.execute('SELECT * FROM customer_details WHERE customer_id = ?', (id,))
  details = cursor.fetchone()

  cursor.execute(
      'SELECT * FROM payments WHERE customer_id = ? ORDER BY id DESC', (id,)
  )
  payments = cursor.fetchall()

  conn.close()

  html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Customer Portfolio & Ledger</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; direction: ltr; }
            .container { max-width: 800px; margin: auto; }
            .card { background: #fff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
            h2, h3 { color: #007bff; margin-top: 0; }
            .info-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; background: #e9ecef; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            table { width: 100%; border-collapse: collapse; margin-top: 10px; background: #fff; }
            th, td { padding: 10px; border: 1px solid #ddd; text-align: center; }
            th { background-color: #007bff; color: white; }
            form { display: grid; grid-template-columns: 2fr 2fr 1fr; gap: 10px; margin-top: 15px; }
            input { padding: 10px; border: 1px solid #ccc; border-radius: 4px; }
            button { background: #28a745; color: white; border: none; padding: 10px; cursor: pointer; border-radius: 4px; font-size: 15px; }
            button:hover { background: #218838; }
            .back-link { display: inline-block; margin-top: 10px; text-decoration: none; color: #007bff; }
            .btn-delete-payment { background: #dc3545; color: white; padding: 5px 10px; text-decoration: none; border-radius: 3px; font-size: 12px; }
            .btn-delete-payment:hover { background: #c82333; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="card">
                <h2>Customer Portfolio & Payment Ledger</h2>
                <div class="info-grid">
                    <div><strong>Name:</strong> {{ customer['name'] }}</div>
                    <div><strong>Phone:</strong> {{ details['customer_phone'] if details else 'N/A' }}</div>
                    <div><strong>Model:</strong> {{ customer['phone_model'] }}</div>
                    <div><strong>IMEI:</strong> {{ customer['imei'] }}</div>
                    <div><strong>Android ID:</strong> {{ customer['android_id'] if customer['android_id'] else 'N/A' }}</div>
                    <div><strong>Total Price:</strong> Rs. {{ customer['total_price'] }}</div>
                    <div><strong>Advance Paid:</strong> Rs. {{ customer['advance_paid'] }}</div>
                    <div><strong>Monthly Installment:</strong> Rs. {{ "%.2f"|format(customer['monthly_installment']) }}</div>
                    <div><strong>Remaining Balance:</strong> <span style="color: red; font-weight: bold;">Rs. {{ customer['remaining_balance'] }}</span></div>
                </div>

                <h3>Receive New Installment Payment</h3>
                <form method="POST">
                    <input type="text" name="month_label" placeholder="Month/Installment Name (e.g. Month 1 - Nov)" required>
                    <input type="number" step="any" name="amount_paid" placeholder="Amount Received (e.g. 9000)" required>
                    <button type="submit">Add Payment</button>
                </form>
            </div>

            <div class="card">
                <h3>Payment History Ledger</h3>
                <table>
                    <tr>
                        <th>Receipt ID</th>
                        <th>Month / Detail</th>
                        <th>Amount Paid</th>
                        <th>Date & Time</th>
                        <th>Action</th>
                    </tr>
                    {% for p in payments %}
                    <tr>
                        <td>#{{ p['id'] }}</td>
                        <td>{{ p['month_label'] }}</td>
                        <td style="color: green; font-weight: bold;">Rs. {{ p['amount_paid'] }}</td>
                        <td>{{ p['payment_date'] }}</td>
                        <td>
                            <a href="/delete-payment/{{ p['id'] }}" class="btn-delete-payment" onclick="return confirm('Do you want to delete this payment entry? Remaining balance will be adjusted back.')">Delete</a>
                        </td>
                    </tr>
                    {% else %}
                    <tr>
                        <td colspan="5" style="color: #777;">No payments received yet.</td>
                    </tr>
                    {% endfor %}
                </table>
                <a href="/" class="back-link">&larr; Back to Dashboard</a>
            </div>
        </div>
    </body>
    </html>
    """
  return render_template_string(
      html_template, customer=customer, details=details, payments=payments
  )


@app.route('/delete/<int:id>')
def delete_customer(id):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute('DELETE FROM payments WHERE customer_id = ?', (id,))
  cursor.execute('DELETE FROM customer_details WHERE customer_id = ?', (id,))
  cursor.execute('DELETE FROM customers WHERE id = ?', (id,))
  conn.commit()
  conn.close()
  return redirect(url_for('index'))


@app.route('/delete-payment/<int:payment_id>')
def delete_payment(payment_id):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  cursor.execute(
      'SELECT customer_id, amount_paid FROM payments WHERE id = ?', (payment_id,)
  )
  payment = cursor.fetchone()

  if payment:
    customer_id, amount_paid = payment
    cursor.execute(
        'UPDATE customers SET remaining_balance = remaining_balance + ? WHERE id'
        ' = ?',
        (amount_paid, customer_id),
    )
    cursor.execute('DELETE FROM payments WHERE id = ?', (payment_id,))
    conn.commit()
    conn.close()
    return redirect(url_for('customer_portfolio', id=customer_id))

  conn.close()
  return redirect(url_for('index'))


@app.route('/customer/<int:id>', methods=['GET', 'POST'])
def customer_details(id):
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  if request.method == 'POST':
    customer_phone = request.form['customer_phone']
    nic = request.form['nic_number']
    witness_name = request.form['witness_name']
    witness_phone = request.form['witness_phone']
    address = request.form['address']
    notes = request.form['notes']

    cursor.execute(
        'SELECT id FROM customer_details WHERE customer_id = ?', (id,)
    )
    exists = cursor.fetchone()

    if exists:
      cursor.execute(
          '''
                UPDATE customer_details SET customer_phone=?, nic_number=?, witness_name=?, witness_phone=?, address=?, notes=?
                WHERE customer_id=?
            ''',
          (
              customer_phone,
              nic,
              witness_name,
              witness_phone,
              address,
              notes,
              id,
          ),
      )
    else:
      cursor.execute(
          '''
                INSERT INTO customer_details (customer_id, customer_phone, nic_number, witness_name, witness_phone, address, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''',
          (
              id,
              customer_phone,
              nic,
              witness_name,
              witness_phone,
              address,
              notes,
          ),
      )

    conn.commit()
    conn.close()
    return redirect(url_for('index'))

  cursor.execute('SELECT * FROM customers WHERE id = ?', (id,))
  customer = cursor.fetchone()

  cursor.execute('SELECT * FROM customer_details WHERE customer_id = ?', (id,))
  details = cursor.fetchone()
  conn.close()

  html_template = """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>Customer Details</title>
        <style>
            body { font-family: Arial, sans-serif; background: #f4f6f9; margin: 0; padding: 20px; direction: ltr; }
            .card { background: #fff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); max-width: 600px; margin: auto; }
            h2 { color: #007bff; margin-top: 0; }
            .info-box { background: #e9ecef; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
            form { display: grid; gap: 15px; }
            input, textarea { padding: 12px; border: 1px solid #ccc; border-radius: 4px; width: 100%; box-sizing: border-box; }
            button { background: #28a745; color: white; border: none; padding: 12px; cursor: pointer; border-radius: 4px; font-size: 16px; }
            button:hover { background: #218838; }
            .back-link { display: inline-block; margin-top: 15px; text-decoration: none; color: #007bff; }
        </style>
    </head>
    <body>
        <div class="card">
            <h2>Customer Verification & Contact Details</h2>
            <div class="info-box">
                <p><strong>Customer Name:</strong> {{ customer['name'] }}</p>
                <p><strong>Phone Model:</strong> {{ customer['phone_model'] }} | <strong>IMEI:</strong> {{ customer['imei'] }}</p>
                {% if customer['android_id'] %}<p><strong>Android ID:</strong> {{ customer['android_id'] }}</p>{% endif %}
                <p><strong>Monthly Installment:</strong> Rs. {{ "%.2f"|format(customer['monthly_installment']) }} ({{ customer['months'] }} Months)</p>
            </div>

            <form method="POST">
                <div>
                    <label><strong>Customer Phone Number:</strong></label>
                    <input type="text" name="customer_phone" value="{{ details['customer_phone'] if details else '' }}" placeholder="0300-1234567" required>
                </div>
                <div>
                    <label><strong>Customer NIC Number:</strong></label>
                    <input type="text" name="nic_number" value="{{ details['nic_number'] if details else '' }}" placeholder="e.g. 42101-1234567-1" required>
                </div>
                <div>
                    <label><strong>Witness Name:</strong></label>
                    <input type="text" name="witness_name" value="{{ details['witness_name'] if details else '' }}" placeholder="Witness Name" required>
                </div>
                <div>
                    <label><strong>Witness Phone Number:</strong></label>
                    <input type="text" name="witness_phone" value="{{ details['witness_phone'] if details else '' }}" placeholder="Witness Phone Number" required>
                </div>
                <div>
                    <label><strong>Customer Home Address:</strong></label>
                    <textarea name="address" rows="3" placeholder="Complete Address" required>{{ details['address'] if details else '' }}</textarea>
                </div>
                <div>
                    <label><strong>Notes:</strong></label>
                    <textarea name="notes" rows="2" placeholder="Any special note...">{{ details['notes'] if details else '' }}</textarea>
                </div>
                <button type="submit">Save Details</button>
            </form>
            <a href="/" class="back-link">&larr; Back to Dashboard</a>
        </div>
    </body>
    </html>
    """
  return render_template_string(html_template, customer=customer, details=details)


@app.route('/print/<int:id>')
def print_agreement(id):
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT * FROM customers WHERE id = ?', (id,))
  customer = cursor.fetchone()

  cursor.execute('SELECT * FROM customer_details WHERE customer_id = ?', (id,))
  details = cursor.fetchone()
  conn.close()

  html_template = """
    <!DOCTYPE html>
    <html lang="ur">
    <head>
        <meta charset="UTF-8">
        <title>BNS TRADERS - Installment Agreement</title>
        <style>
            body { font-family: Arial, sans-serif; background: #fff; margin: 0; padding: 20px; direction: ltr; color: #000; }
            .invoice-box { max-width: 800px; margin: auto; padding: 20px; border: 2px solid #333; font-size: 15px; line-height: 24px; }
            .header { text-align: center; border-bottom: 2px solid #333; padding-bottom: 10px; margin-bottom: 20px; }
            .header h1 { margin: 0; font-size: 24px; }
            .section-title { background: #333; color: #fff; padding: 5px 10px; font-weight: bold; margin-top: 15px; margin-bottom: 10px; }
            table { width: 100%; border-collapse: collapse; margin-bottom: 15px; }
            table, th, td { border: 1px solid #333; padding: 8px; text-align: left; }
            th { background-color: #f2f2f2; }
            .terms { font-size: 13px; line-height: 20px; text-align: justify; margin-top: 15px; }
            .signatures { display: flex; justify-content: space-between; margin-top: 50px; text-align: center; }
            .sig-box { width: 30%; border-top: 1px solid #333; padding-top: 5px; }
            @media print { .no-print { display: none; } }
        </style>
    </head>
    <body>
        <div class="invoice-box">
            <div class="header">
                <h1>BNS TRADERS & COMMUNICATION SERVICES</h1>
                <p>Mobile Phone Installment & Security Agreement (BNS-GUARD-01)</p>
            </div>

            <div class="section-title">Customer & Device Details</div>
            <table>
                <tr>
                    <th>Customer Name:</th><td>{{ customer['name'] }}</td>
                    <th>Phone Number:</th><td>{{ details['customer_phone'] if details else 'N/A' }}</td>
                </tr>
                <tr>
                    <th>NIC Number:</th><td>{{ details['nic_number'] if details else 'N/A' }}</td>
                    <th>Home Address:</th><td>{{ details['address'] if details else 'N/A' }}</td>
                </tr>
                <tr>
                    <th>Phone Model:</th><td>{{ customer['phone_model'] }}</td>
                    <th>IMEI / Android ID:</th><td>{{ customer['imei'] }} {% if customer['android_id'] %}/ {{ customer['android_id'] }}{% endif %}</td>
                </tr>
            </table>

            <div class="section-title">Payment Plan</div>
            <table>
                <tr>
                    <th>Total Price</th><th>Advance</th><th>Remaining Balance</th><th>Monthly Inst.</th><th>Months</th><th>Due Date</th>
                </tr>
                <tr>
                    <td>Rs. {{ customer['total_price'] }}</td>
                    <td>Rs. {{ customer['advance_paid'] }}</td>
                    <td>Rs. {{ customer['remaining_balance'] }}</td>
                    <td>Rs. {{ "%.2f"|format(customer['monthly_installment']) }}</td>
                    <td>{{ customer['months'] }} Months</td>
                    <td>{{ customer['due_date'] }}</td>
                </tr>
            </table>

            <div class="section-title">Terms & Conditions</div>
            <div class="terms">
                <ol>
                    <li><strong>وقت پر ادائیگی:</strong> گاہک ہر ماہ کی مقررہ تاریخ پر ماہانہ قسط ادا کرنے کا پابند ہے۔</li>
                    <li><strong>قانونی کاروائی:</strong> قسط ادا نہ کرنے یا تاخیر پر BNS Traders موبائل کو فوری لاک کرنے اور قانونی چارہ جوئی کا حق رکھتا ہے۔</li>
                    <li><strong>چوری یا گم ہونے کی ذمہ داری:</strong> موبائل چوری یا گم ہونے کی صورت میں بھی قسط معاف نہیں ہوگی، کل بقایا جات ادا کرنا ہوں گے۔</li>
                </ol>
            </div>

            <div class="signatures">
                <div class="sig-box"><p>Customer Signature</p></div>
                <div class="sig-box"><p>Witness Signature</p></div>
                <div class="sig-box"><p>BNS Traders</p></div>
            </div>

            <div style="text-align: center; margin-top: 30px;" class="no-print">
                <button onclick="window.print()" style="background: #007bff; color: white; border: none; padding: 10px 20px; cursor: pointer;">Print Agreement</button>
            </div>
        </div>
    </body>
    </html>
    """
  return render_template_string(html_template, customer=customer, details=details)


@app.route('/toggle/<int:id>')
def toggle_status(id):
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute('SELECT status FROM customers WHERE id = ?', (id,))
  row = cursor.fetchone()
  if row:
    new_status = 'LOCKED' if row[0] == 'ACTIVE' else 'ACTIVE'
    cursor.execute(
        'UPDATE customers SET status = ? WHERE id = ?', (new_status, id)
    )
    conn.commit()
  conn.close()
  return redirect(url_for('index'))


@app.route('/download-app')
def download_app():
  try:
    # Looks for app-debug.apk in the script's folder
    return send_file(os.path.join(BASE_DIR, 'app-debug.apk'), as_attachment=True)
  except Exception as e:
    return f'APK file not found on server directory: {e}', 404


@app.route('/admin/update-qr')
def admin_update_qr():
  local_ip = get_local_ip()
  download_link = f'http://{local_ip}:5000/download-app'

  img = qrcode.make(download_link)
  buf = io.BytesIO()
  img.save(buf, format='PNG')
  buf.seek(0)

  return send_file(
      buf, mimetype='image/png', as_attachment=False, download_name='master_update_qr.png'
  )


@app.route('/qrcode/<int:id>')
def generate_qr(id):
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT imei, android_id FROM customers WHERE id = ?', (id,))
  customer = cursor.fetchone()
  conn.close()

  if not customer:
    return 'Customer not found', 404

  local_ip = get_local_ip()
  identifier = (
      customer['android_id'] if customer['android_id'] else customer['imei']
  )
  download_link = f'http://{local_ip}:5000/download-app?id={identifier}'

  img = qrcode.make(download_link)
  buf = io.BytesIO()
  img.save(buf, format='PNG')
  buf.seek(0)

  return send_file(
      buf, mimetype='image/png', as_attachment=False, download_name='device_qr.png'
  )


# --- GPS LOCATION API ENDPOINT ---
@app.route('/api/update-location', methods=['POST'])
def update_location():
  data = request.json
  if not data:
    return jsonify({'status': 'error', 'message': 'No data provided'}), 400

  identifier = data.get('id') or data.get('imei') or data.get('android_id')
  latitude = data.get('latitude')
  longitude = data.get('longitude')

  if not identifier:
    return jsonify({'status': 'error', 'message': 'Identifier missing'}), 400

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()
  cursor.execute(
      '''
        UPDATE customers 
        SET latitude = ?, longitude = ? 
        WHERE id = ? OR imei = ? OR android_id = ?
    ''',
      (latitude, longitude, identifier, identifier, identifier),
  )
  conn.commit()
  conn.close()

  return jsonify({'status': 'success', 'message': 'Location updated'})


# --- INTELLIGENT STATUS & AUTO-RELEASE API ENDPOINT ---
@app.route('/api/check-status', methods=['GET'])
def check_status():
  identifier = (
      request.args.get('id')
      or request.args.get('imei')
      or request.args.get('android_id')
  )

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  row = None
  if identifier:
    cursor.execute(
        'SELECT status, remaining_balance FROM customers WHERE id = ? OR imei = ? OR android_id = ?',
        (identifier, identifier, identifier),
    )
    row = cursor.fetchone()

    if not row:
      cursor.execute(
          'SELECT status, remaining_balance FROM customers WHERE imei LIKE ? OR android_id LIKE ?',
          (f'%{identifier}%', f'%{identifier}%'),
      )
      row = cursor.fetchone()

  conn.close()

  if row:
    status, remaining_balance = row[0], row[1]
    if remaining_balance is not None and remaining_balance <= 0:
      return jsonify({'status': 'COMPLETED', 'command': 'release'})
    elif status == 'LOCKED':
      return jsonify({'status': 'LOCKED', 'command': 'lock'})

  return jsonify({'status': 'ACTIVE', 'command': 'unlock'})


if __name__ == '__main__':
  app.run(debug=True, host='0.0.0.0', port=5000)
