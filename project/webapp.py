from flask import Flask, jsonify, render_template, request
from db import db
import os
import requests
from dotenv import load_dotenv
from werkzeug.utils import secure_filename
import random
import string
import uuid  # <--- Был пропущен

# Загружаем переменные окружения
load_dotenv()

app = Flask(__name__)

# Настройка папки для картинок
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Этот блок обрабатывает ВСЕ запросы и разрешает CORS для всего
@app.after_request
def after_request(response):
    response.headers.add('Access-Control-Allow-Origin', '*')
    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization,X-API-Key,ngrok-skip-browser-warning')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---

def check_api_key(req):
    """Проверяет API Key через базу данных"""
    key = req.headers.get('X-API-Key')
    if not key:
        return None
    
    # Спрашиваем у БД, есть ли такой ключ
    service_name = db.validate_api_key(key)
    return service_name

def send_telegram_notification(user_id, text):
    token = os.getenv("BOT_TOKEN")
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
    except Exception as e:
        print(f"[ERROR] Ошибка отправки: {e}")

# --- SDK API ---

@app.route('/api/sdk/balance', methods=['GET', 'OPTIONS'])
def sdk_get_balance():
    if request.method == 'OPTIONS': return jsonify({'status': 'ok'}), 200

    service_name = check_api_key(request)
    if not service_name: return jsonify({"error": "Invalid API Key"}), 401
    
    tg_id = request.args.get('user_id')
    user = db.get_student_by_tg_id(tg_id)
    if not user: return jsonify({"error": "User not found"}), 404
    
    return jsonify({"balance": user['current_points']})

@app.route('/api/sdk/transaction', methods=['POST', 'OPTIONS'])
def sdk_transaction():
    if request.method == 'OPTIONS': return jsonify({'status': 'ok'}), 200

    try:
        service_name = check_api_key(request)
        if not service_name: return jsonify({"error": "Invalid API Key"}), 401
        
        data = request.json
        tg_id = data.get('user_id')
        amount = int(data.get('amount'))
        type_ = data.get('type')
        # Исправление кодировки (на всякий случай, если клиент шлет latin-1 вместо utf-8)
        desc_raw = data.get('description', '')
        # desc = desc_raw.encode('latin1').decode('utf-8') # Раскомментируй, если кракозябры останутся
        desc = f"[{service_name}] {desc_raw}"
        
        user = db.get_student_by_tg_id(tg_id)
        if not user: return jsonify({"error": "User not found"}), 404
        
        print(f"[SDK] Transaction: {tg_id} {type_} {amount} ({desc})") # Логируем
        
        if type_ == 'spend':
            if user['current_points'] < amount:
                return jsonify({"success": False, "message": "Недостаточно средств"}), 400
            
            # 🔥 ВАЖНО: Используем универсальный метод add_points с отрицательным значением
            # Проверь, как называется метод в твоем db.py! Обычно это add_points
            db.add_points(user['id'], -amount, desc) 
            
        elif type_ == 'earn':
             db.add_points(user['id'], amount, desc)
        
        # Получаем обновленный баланс
        updated_user = db.get_student_by_tg_id(tg_id)
        return jsonify({"success": True, "new_balance": updated_user['current_points']})
        
    except Exception as e:
        print(f"[SDK ERROR] {e}") # Вывод ошибки в консоль сервера
        return jsonify({"success": False, "message": f"Server Error: {str(e)}"}), 500

# --- MERCH API ---

@app.route('/api/buy_merch', methods=['POST'])
def api_buy_merch():
    try:
        data = request.json
        u_id = int(data.get('user_id'))
        m_id = data.get('merch_id')
        success, message = db.create_merch_order(u_id, m_id) # Используем создание заказа
        if success: send_telegram_notification(u_id, f"✅ Заказ создан!\n{message}")
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/merch/orders/pending', methods=['GET'])
def get_pending_orders():
    orders = db.get_pending_merch_orders()
    return jsonify(orders)

@app.route('/api/merch/orders/approve', methods=['POST'])
def approve_order():
    data = request.json
    order_id = data.get('order_id')
    action = data.get('action') 
    secret_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6)) if action == 'approve' else None
    success, msg = db.process_merch_order(order_id, action, secret_code)
    return jsonify({"success": success, "message": msg})

@app.route('/api/merch/my_orders', methods=['GET'])
def get_my_orders():
    user_id = request.args.get('user_id')
    orders = db.get_student_merch_orders(user_id)
    return jsonify(orders)

@app.route('/api/add_merch_item', methods=['POST'])
def api_add_merch_item():
    try:
        user_id = request.form.get('user_id')
        name = request.form.get('name')
        price = request.form.get('price')
        stock = request.form.get('stock')
        desc = request.form.get('description', '')
        file = request.files.get('image')

        user = db.get_student_by_tg_id(user_id)
        if not user or user['role'] not in ['admin', 'stud_council']:
            return jsonify({"success": False, "message": "Нет прав"}), 403

        image_url = ''
        if file and file.filename:
            filename = secure_filename(file.filename)
            unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(filepath)
            image_url = f"/static/uploads/{unique_name}"

        success, msg = db.add_new_merch(name, desc, int(price), int(stock), image_url)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": str(e)}), 500
@app.route('/api/merch/delete/<merch_id>', methods=['POST'])
def api_delete_merch(merch_id):
    try:
        data = request.json
        if not data:
            return jsonify({"success": False, "message": "No JSON data"}), 400
        user_id = data.get('user_id')
        if not user_id:
            return jsonify({"success": False, "message": "No user_id"}), 400
        
        # Проверка прав
        user = db.get_student_by_tg_id(user_id)
        if not user or user['role'] not in ['admin', 'stud_council']:
            return jsonify({"success": False, "message": "Нет прав"}), 403
        
        success, msg = db.delete_merch(merch_id)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/merch')
def api_merch():
    try:
        return jsonify(db.get_all_merch())
    except Exception as e:
        return jsonify([]), 500

# --- SERVICES API ---

@app.route('/api/services')
def api_services():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify([])
    try:
        return jsonify(db.get_all_services(int(user_id)))
    except Exception as e:
        return jsonify([]), 500
    
@app.route('/api/services/take', methods=['POST'])
def api_take_service():
    data = request.get_json()
    service_id = data.get('service_id')
    user_id = data.get('user_id') # Это твой telegram_user_id из фронта
    
    if not service_id or not user_id:
        return jsonify({'success': False, 'message': 'Нет данных'}), 400
        
    # Вызываем тот самый метод, который я написал тебе в прошлом ответе
    # Предполагаем, что класс с БД называется db (или как он у тебя называется)
    success, message = db.take_service_order(service_id, user_id)
    
    if success:
        return jsonify({'success': True, 'message': message}), 200
    else:
        return jsonify({'success': False, 'message': message}), 400

@app.route('/api/buy_service', methods=['POST'])
def api_buy_service():
    try:
        data = request.json
        u_id = int(data.get('user_id'))
        s_id = data.get('service_id')
        success, message = db.buy_service(u_id, s_id)
        if success: send_telegram_notification(u_id, f"💼 Услуга оплачена!\n{message}")
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/add_service', methods=['POST'])
def api_add_service():
    try:
        data = request.json
        if not data: return jsonify({"success": False, "message": "Нет данных"}), 400
        try:
            u_id = int(str(data.get('user_id', '')).strip())
            points = int(str(data.get('points_cost', '')).strip())
        except ValueError:
             return jsonify({"success": False, "message": "Некорректный ID или цена"}), 400
        name = str(data.get('name', '')).strip()
        desc = str(data.get('description', '')).strip()
        if not name or points < 1:
            return jsonify({"success": False, "message": "Название и цена обязательны"}), 400
        success, msg = db.add_service(u_id, name, points, desc)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/take_task', methods=['POST'])
def api_take_task():
    try:
        data = request.json
        u_id = int(str(data.get('user_id', '')).strip())
        svc_id = data.get('service_id')
        success, msg = db.assign_service(svc_id, u_id)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/confirm_task', methods=['POST'])
def api_confirm_task():
    try:
        data = request.json
        customer_id = int(data.get('user_id'))  # Клиент, который платит
        order_id = data.get('order_id') 
        success, msg = db.complete_service_order(order_id, customer_id)  # Передаем клиента!
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


# --- USER & ADMIN API ---

@app.route('/miniapp')
def miniapp():
    return render_template("index.html")

@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    try:
        student = db.get_student_by_tg_id(user_id)
        if not student: return jsonify({"error": "User not found"}), 404
        return jsonify(student)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats/<int:user_id>')
def api_stats(user_id):
    try:
        return jsonify(db.get_user_stats(user_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/history/<int:user_id>')
def api_history(user_id):
    try:
        return jsonify(db.get_student_history(user_id))
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/leaderboard')
def api_leaderboard():
    try:
        return jsonify(db.get_leaderboard())
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/admin/stats')
def api_admin_stats():
    uid = request.args.get('user_id')
    user = db.get_student_by_tg_id(uid)
    if not user or user['role'] != 'admin':
        return jsonify({"error": "No access"}), 403
    return jsonify(db.get_admin_stats())

@app.route('/api/create_activity', methods=['POST'])
def api_create_activity():
    data = request.json
    uid = data.get('user_id')
    user = db.get_student_by_tg_id(uid)
    if not user or user['role'] not in ['admin', 'stud_council']:
        return jsonify({"success": False, "message": "Нет прав"}), 403
    success, msg = db.create_activity(data.get('title'), int(data.get('points')), "", data.get('date'))
    return jsonify({"success": success, "message": msg})

@app.route('/api/activities')
def api_activities():
    return jsonify(db.get_active_activities())

# --- ЗАПУСК ---
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
