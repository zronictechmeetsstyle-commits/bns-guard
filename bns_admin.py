@app.route('/add', methods=['POST'])
def add_customer():
  name = request.form['name']
  phone_model = request.form['phone_model']
  imei = request.form.get('imei', 'AUTO').strip()
  base_price = float(request.form['total_price'])
  advance_paid = float(request.form['advance_paid'])
  months = int(request.form['months'])  # 🔥 Yahan se ghalat line theek kar di gayi hai
  due_date = request.form['due_date']

  customer_phone = request.form.get('customer_phone', '')
  nic_number = request.form.get('nic_number', '')
  witness_name = request.form.get('witness_name', '')
  witness_phone = request.form.get('witness_phone', '')
  address = request.form.get('address', '')
  notes = request.form.get('notes', '')

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
  customer_id = cursor.lastrowid

  cursor.execute(
      '''
        INSERT INTO customer_details (customer_id, customer_phone, nic_number, witness_name, witness_phone, address, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''',
      (
          customer_id,
          customer_phone,
          nic_number,
          witness_name,
          witness_phone,
          address,
          notes,
      ),
  )

  conn.commit()
  conn.close()
  return redirect(url_for('index'))
