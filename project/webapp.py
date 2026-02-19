# webapp.py
from flask import Flask, jsonify, render_template, request
from db import db
import os
import requests
from dotenv import load_dotenv
from werkzeug.utils import secure_filename

# Настройка папки для картинок
UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

load_dotenv()

app = Flask(__name__)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.route('/api/add_merch_item', methods=['POST'])
def api_add_merch_item():
    try:
        # Теперь данные приходят не в json, а в form-data
        user_id = request.form.get('user_id')
        name = request.form.get('name')
        price = request.form.get('price')
        stock = request.form.get('stock')
        desc = request.form.get('description', '')
        
        file = request.files.get('image') # Получаем файл

        # Проверка прав (как раньше)
        user = db.get_student_by_tg_id(user_id)
        if not user or user['role'] not in ['admin', 'stud_council']:
            return jsonify({"success": False, "message": "Нет прав"}), 403

        image_url = ''
        if file and file.filename:
            filename = secure_filename(file.filename)
            # Уникальное имя, чтобы не перезатереть
            unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_name)
            file.save(filepath)
            # URL для фронтенда (доступен через static)
            image_url = f"/static/uploads/{unique_name}"

        # Сохраняем в БД (нужно обновить метод db.add_new_merch!)
        success, msg = db.add_new_merch(name, desc, int(price), int(stock), image_url)
        return jsonify({"success": success, "message": msg})
        
    except Exception as e:
        print(e)
        return jsonify({"success": False, "message": str(e)}), 500


def send_telegram_notification(user_id, text):
    token = os.getenv("BOT_TOKEN")
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
    except Exception as e:
        print(f"[ERROR] Ошибка отправки: {e}")

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

@app.route('/api/merch')
def api_merch():
    try:
        return jsonify(db.get_all_merch())
    except Exception as e:
        return jsonify([]), 500

@app.route('/api/services')
def api_services():
    user_id = request.args.get('user_id')
    if not user_id: return jsonify([])
    try:
        return jsonify(db.get_all_services(int(user_id)))
    except Exception as e:
        return jsonify([]), 500

@app.route('/api/buy_merch', methods=['POST'])
def api_buy_merch():
    try:
        data = request.json
        u_id = int(data.get('user_id'))
        m_id = data.get('merch_id')
        success, message = db.buy_merch(u_id, m_id)
        if success: send_telegram_notification(u_id, f"✅ Покупка мерча успешна!\n{message}")
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": "Ошибка сервера"}), 500

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

    # webapp.py

@app.route('/api/add_service', methods=['POST'])
def api_add_service():
    try:
        data = request.json
        if not data: return jsonify({"success": False, "message": "Нет данных"}), 400
        
        # Безопасно получаем данные
        try:
            u_id = int(str(data.get('user_id', '')).strip())
            points = int(str(data.get('points_cost', '')).strip())
        except ValueError:
             return jsonify({"success": False, "message": "Некорректный ID или цена (должны быть числами)"}), 400

        name = str(data.get('name', '')).strip()
        desc = str(data.get('description', '')).strip()

        if not name or points < 1:
            return jsonify({"success": False, "message": "Название и цена обязательны"}), 400

        success, msg = db.add_service(u_id, name, points, desc)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        print(f"[API ERROR] {e}") # Выведет ошибку в терминал Flask
        return jsonify({"success": False, "message": f"Ошибка сервера: {e}"}), 500


@app.route('/api/take_task', methods=['POST'])
def api_take_task():
    try:
        data = request.json
        try:
            u_id = int(str(data.get('user_id', '')).strip())
        except ValueError:
            return jsonify({"success": False, "message": "Некорректный ID"}), 400
            
        svc_id = data.get('service_id')
        
        success, msg = db.assign_service(svc_id, u_id)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        print(f"[API ERROR] {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/confirm_task', methods=['POST'])
def api_confirm_task():
    try:
        data = request.json
        u_id = int(data.get('user_id'))
        order_id = data.get('order_id') 
        success, msg = db.complete_service_order(order_id, u_id)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)


# --- НОВЫЕ API ---

@app.route('/api/admin/stats')
def api_admin_stats():
    # Проверка прав
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
    
    # Разрешено админу и студсовету
    if not user or user['role'] not in ['admin', 'stud_council']:
        return jsonify({"success": False, "message": "Нет прав"}), 403

    success, msg = db.create_activity(
        data.get('title'), 
        int(data.get('points')), 
        "", 
        data.get('date')
    )
    return jsonify({"success": success, "message": msg})

@app.route('/api/activities')
def api_activities():
    return jsonify(db.get_active_activities())

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)
