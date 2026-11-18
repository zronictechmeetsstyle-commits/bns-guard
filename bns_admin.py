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

app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DB_PATH = os.path.join(BASE_DIR, 'bns_guard.db')


def init_db():
  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

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

  cursor.execute("PRAGMA table_info(customers)")
  columns = [col[1] for col in cursor.fetchall()]
  if 'android_id' not in columns:
    cursor.execute('ALTER TABLE customers ADD COLUMN android_id TEXT')
  if 'latitude' not in columns:
    cursor.execute('ALTER TABLE customers ADD COLUMN latitude TEXT')
  if 'longitude' not in columns:
    cursor.execute('ALTER TABLE customers ADD COLUMN longitude TEXT')

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
            .btn-action { text-decoration: none; padding: 6px 10px; color: white; border-radius: 3px; font-size: 11px; display: inline-block; margin: 2px; border: none; cursor: pointer; }
            .btn-delete { background: #dc3545; }
            .btn-delete:hover { background: #c82333; }
            .top-actions { margin-bottom: 15px; display: flex; gap: 10px; }
        </style>
    </head>
    <body>
        <h2>BNS-GUARD-01 - Admin Dashboard & Portfolio Control</h2>
        
        <div class="top-actions">
            <a href="/download-app" style="background: #17a2b8; color: white; padding: 10px 15px; text-decoration: none; border-radius: 4px; display: inline-block; font-weight: bold;">📥 Download Master APK</a>
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
            <input type="text" name="imei" placeholder="IMEI / Initial ID (Optional)" value="AUTO">
            <input type="number" step="any" name="total_price" placeholder="Total Price (e.g. 43000)" required>
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
                <th>IMEI / ID</th>
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
                <td>{{ c['android_id'] if c['android_id'] else 'Not Linked Yet' }}</td>
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
                    <a href="/admin/edit/{{ c['id'] }}" class="btn-action" style="background: #007bff;">Edit</a>
                    <a href="/portfolio/{{ c['id'] }}" class="btn-action" style="background: #6f42c1;">Portfolio</a>
                    <a href="/customer/{{ c['id'] }}" class="btn-action" style="background: #17a2b8;">Details</a>
                    <a href="/print/{{ c['id'] }}" class="btn-action" style="background: #343a40;" target="_blank">Print</a>
                    <a href="/toggle/{{ c['id'] }}" class="btn-action" style="background: #ffc107; color: black;">{% if c['status'] == 'ACTIVE' %}Lock{% else %}Unlock{% endif %}</a>
                    <button type="button" class="btn-action btn-delete" onclick="secureDelete('{{ c['id'] }}')">Delete</button>
                </td>
            </tr>
            {% else %}
            <tr>
                <td colspan="14" style="color: #777; padding: 20px;">No customers found.</td>
            </tr>
            {% endfor %}
        </table>

        <script>
        function secureDelete(customerId) {
            let password = prompt("⚠️ Security Warning: Yeh entry delete karne ke liye Master Password enter karein:");
            if (password === "Imk786787") {
                window.location.href = "/delete/" + customerId;
            } else if (password !== null) {
                alert("❌ Ghalat Password! Aapko yeh entry delete karne ki ijazat nahi hai.");
            }
        }
        </script>
    </body>
    </html>
    """
  return render_template_string(html_template, customers=customers)


@app.route('/add', methods=['POST'])
def add_customer():
  name = request.form['name']
  phone_model = request.form['phone_model']
  imei = request.form.get('imei', 'AUTO').strip()
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
        INSERT INTO customers (name, phone_model, imei, total_price, advance_paid, months, remaining_balance, monthly_installment, due_date, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE')
    ''',
      (
          name,
          phone_model,
          imei,
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


@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_customer(id):
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()

  if request.method == 'POST':
    name = request.form['name']
    phone_model = request.form['phone_model']
    imei = request.form['imei']
    total_price = float(request.form['total_price'])
    advance_paid = float(request.form['advance_paid'])
    months = int(request.form['months'])
    remaining_balance = float(request.form['remaining_balance'])
    monthly_installment = float(request.form['monthly_installment'])
    due_date = request.form['due_date']
    status = request.form['status']

    cursor.execute(
        '''
        UPDATE customers 
        SET name = ?, phone_model = ?, imei = ?, total_price = ?, advance_paid = ?, 
            months = ?, remaining_balance = ?, monthly_installment = ?, due_date = ?, status = ?
        WHERE id = ?
    ''',
        (
            name,
            phone_model,
            imei,
            total_price,
            advance_paid,
            months,
            remaining_balance,
            monthly_installment,
            due_date,
            status,
            id,
        ),
    )
    conn.commit()
    conn.close()
    return redirect(url_for('index'))

  cursor.execute('SELECT * FROM customers WHERE id = ?', (id,))
  customer = cursor.fetchone()
  conn.close()

  if not customer:
    return 'Customer not found', 404

  return render_template_string(
      """
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>Edit Customer</title></head>
    <body style="font-family: Arial; padding: 20px;">
        <h2>Edit Customer Details</h2>
        <form method="POST">
            <input type="text" name="name" value="{{ customer['name'] }}" required><br><br>
            <input type="text" name="phone_model" value="{{ customer['phone_model'] }}" required><br><br>
            <input type="text" name="imei" value="{{ customer['imei'] }}" required><br><br>
            <input type="number" step="any" name="total_price" value="{{ customer['total_price'] }}" required><br><br>
            <input type="number" step="any" name="advance_paid" value="{{ customer['advance_paid'] }}" required><br><br>
            <input type="number" name="months" value="{{ customer['months'] }}" required><br><br>
            <input type="number" step="any" name="remaining_balance" value="{{ customer['remaining_balance'] }}" required><br><br>
            <input type="number" step="any" name="monthly_installment" value="{{ customer['monthly_installment'] }}" required><br><br>
            <input type="date" name="due_date" value="{{ customer['due_date'] }}" required><br><br>
            <select name="status">
                <option value="ACTIVE" {% if customer['status'] == 'ACTIVE' %}selected{% endif %}>ACTIVE</option>
                <option value="LOCKED" {% if customer['status'] == 'LOCKED' %}selected{% endif %}>LOCKED</option>
            </select><br><br>
            <button type="submit">Update</button>
        </form>
        <a href="/">Back</a>
    </body>
    </html>
    """,
      customer=customer,
  )


@app.route('/customer/<int:id>')
def customer_details(id):
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT * FROM customers WHERE id = ?', (id,))
  customer = cursor.fetchone()
  cursor.execute('SELECT * FROM customer_details WHERE customer_id = ?', (id,))
  details = cursor.fetchone()
  cursor.execute('SELECT * FROM payments WHERE customer_id = ?', (id,))
  payments = cursor.fetchall()
  conn.close()

  if not customer:
    return 'Customer not found', 404

  return render_template_string(
      """
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>Customer Details</title></head>
    <body style="font-family: Arial; padding: 20px;">
        <h2>Details for {{ customer['name'] }}</h2>
        <p><b>Model:</b> {{ customer['phone_model'] }}</p>
        <p><b>Total Price:</b> Rs. {{ customer['total_price'] }}</p>
        <p><b>Remaining:</b> Rs. {{ customer['remaining_balance'] }}</p>
        <hr>
        <a href="/">Back to Dashboard</a>
    </body>
    </html>
    """,
      customer=customer,
      details=details,
      payments=payments,
  )


@app.route('/print/<int:id>')
def print_customer(id):
  conn = sqlite3.connect(DB_PATH)
  conn.row_factory = sqlite3.Row
  cursor = conn.cursor()
  cursor.execute('SELECT * FROM customers WHERE id = ?', (id,))
  customer = cursor.fetchone()
  conn.close()

  if not customer:
    return 'Customer not found', 404

  return render_template_string(
      """
    <!DOCTYPE html>
    <html lang="en">
    <head><meta charset="UTF-8"><title>Print Invoice</title></head>
    <body style="font-family: Arial; padding: 20px;" onload="window.print()">
        <h2>BNS-GUARD-01 Invoice</h2>
        <p><b>Customer Name:</b> {{ customer['name'] }}</p>
        <p><b>Phone Model:</b> {{ customer['phone_model'] }}</p>
        <p><b>Total Price:</b> Rs. {{ customer['total_price'] }}</p>
        <p><b>Advance Paid:</b> Rs. {{ customer['advance_paid'] }}</p>
        <p><b>Remaining Balance:</b> Rs. {{ customer['remaining_balance'] }}</p>
        <p><b>Monthly Installment:</b> Rs. {{ customer['monthly_installment'] }}</p>
        <p><b>Due Date:</b> {{ customer['due_date'] }}</p>
    </body>
    </html>
    """,
      customer=customer,
  )


@app.route('/portfolio/<int:id>')
def portfolio(id):
  return redirect(url_for('customer_details', id=id))


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
    return send_file(os.path.join(BASE_DIR, 'app-debug.apk'), as_attachment=True)
  except Exception as e:
    return f'APK not found: {e}', 404


@app.route('/api/check-status', methods=['GET'])
def check_status():
  identifier = (
      request.args.get('id')
      or request.args.get('imei')
      or request.args.get('android_id')
      or ''
  ).strip()

  if not identifier:
    return jsonify({'status': 'ACTIVE', 'command': 'unlock'})

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  row = None
  if identifier.isdigit():
    cursor.execute(
        'SELECT status, remaining_balance FROM customers WHERE id = ?',
        (identifier,),
    )
    row = cursor.fetchone()

  if not row:
    cursor.execute(
        '''
        SELECT status, remaining_balance 
        FROM customers 
        WHERE LOWER(TRIM(imei)) = LOWER(?) OR LOWER(TRIM(android_id)) = LOWER(?)
    ''',
        (identifier, identifier),
    )
    row = cursor.fetchone()

  conn.close()

  if row:
    status, remaining_balance = row[0], row[1]
    if remaining_balance is not None and float(remaining_balance) <= 0:
      return jsonify({'status': 'COMPLETED', 'command': 'release'})
    elif status and str(status).strip().upper() == 'LOCKED':
      return jsonify({'status': 'LOCKED', 'command': 'lock'})

  return jsonify({'status': 'ACTIVE', 'command': 'unlock'})


@app.route('/api/update-location', methods=['POST'])
def update_location():
  data = request.json or {}
  if not data:
    return jsonify({'status': 'error'}), 400

  customer_id = data.get('customer_id')
  android_id = data.get('android_id') or data.get('id') or data.get('imei')
  latitude = data.get('latitude')
  longitude = data.get('longitude')

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  row_exists = None
  if android_id:
    cursor.execute(
        'SELECT id FROM customers WHERE LOWER(TRIM(android_id)) = LOWER(?)',
        (str(android_id).strip(),),
    )
    row_exists = cursor.fetchone()

  if customer_id:
    cursor.execute(
        'UPDATE customers SET android_id = ?, latitude = ?, longitude = ? WHERE id = ?',
        (android_id, latitude, longitude, customer_id),
    )
  elif row_exists:
    cursor.execute(
        'UPDATE customers SET latitude = ?, longitude = ? WHERE LOWER(TRIM(android_id)) = LOWER(?)',
        (latitude, longitude, str(android_id).strip()),
    )
  else:
    cursor.execute(
        '''
        INSERT INTO customers (name, phone_model, imei, android_id, total_price, advance_paid, months, remaining_balance, monthly_installment, due_date, status, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
    ''',
        (
            f"Auto Device {str(android_id)[:6] if android_id else 'Unknown'}",
            'Android Device',
            str(android_id) if android_id else 'AUTO',
            android_id,
            0.0,
            0.0,
            1,
            25000.0,
            0.0,
            '2026-12-31',
            latitude,
            longitude,
        ),
    )

  conn.commit()
  conn.close()
  return jsonify({'status': 'success'})


if __name__ == '__main__':
  port = int(os.environ.get('PORT', 5000))
  app.run(host='0.0.0.0', port=port)
