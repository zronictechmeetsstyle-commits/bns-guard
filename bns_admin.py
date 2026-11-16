# --- DEVICE BINDING & GPS LOCATION API ENDPOINT ---
@app.route('/api/update-location', methods=['POST'])
def update_location():
  data = request.json
  if not data:
    return jsonify({'status': 'error'}), 400

  customer_id = data.get('customer_id')
  android_id = data.get('android_id') or data.get('id') or data.get('imei')
  latitude = data.get('latitude')
  longitude = data.get('longitude')

  conn = sqlite3.connect(DB_PATH)
  cursor = conn.cursor()

  # 1. Check karein ke kya yeh android_id pehle se database mein mojood hai
  row_exists = None
  if android_id:
    cursor.execute('SELECT id FROM customers WHERE LOWER(TRIM(android_id)) = LOWER(?)', (str(android_id).strip(),))
    row_exists = cursor.fetchone()

  if customer_id:
    # Agar QR code se customer_id mila hai, toh us row par android_id bind kar do
    cursor.execute(
        'UPDATE customers SET android_id = ?, latitude = ?, longitude = ? WHERE id = ?',
        (android_id, latitude, longitude, customer_id),
    )
  elif row_exists:
    # Agar device pehle se registered hai, toh sirf location update karo
    cursor.execute(
        'UPDATE customers SET latitude = ?, longitude = ? WHERE LOWER(TRIM(android_id)) = LOWER(?)',
        (latitude, longitude, str(android_id).strip()),
    )
  else:
    # Agar bilkul naya unlinked device hai, toh usay automatically panel par show karne ke liye insert kar lo!
    cursor.execute(
        '''
        INSERT INTO customers (name, phone_model, imei, android_id, total_price, advance_paid, months, remaining_balance, monthly_installment, due_date, status, latitude, longitude)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'ACTIVE', ?, ?)
    ''',
        (
            f"Auto Device {str(android_id)[:6] if android_id else 'Unknown'}",
            "Android Device",
            str(android_id) if android_id else "AUTO",
            android_id,
            0.0,
            0.0,
            1,
            0.0,
            0.0,
            "2026-12-31",
            latitude,
            longitude
        ),
    )

  conn.commit()
  conn.close()
  return jsonify({'status': 'success'})
