# webapp.py — ПОЛНАЯ ВЕРСИЯ (СОХРАНЕН ОРИГИНАЛЬНЫЙ ОБЪЕМ + НОВЫЙ ФУНКЦИОНАЛ)
from flask import Flask, jsonify, render_template_string, request
from db import db
import os
import requests
import traceback
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# --- НОВАЯ ФУНКЦИЯ УВЕДОМЛЕНИЙ ---
def send_telegram_notification(user_id, text):
    token = os.getenv("BOT_TOKEN")
    if not token:
        print("[DEBUG] BOT_TOKEN не найден в .env, уведомление не отправлено")
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        res = requests.post(url, json={
            "chat_id": user_id,
            "text": text,
            "parse_mode": "HTML"
        })
        print(f"[DEBUG] Статус отправки уведомления: {res.status_code}")
    except Exception as e:
        print(f"[ERROR] Ошибка отправки уведомления: {e}")

# Твой оригинальный HTML_TEMPLATE с добавлением Chart.js и логики графика
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
  <title>Student Coins</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
  <style>
    :root {
      --tg-bg: var(--tg-theme-bg-color, #ffffff);
      --tg-text: var(--tg-theme-text-color, #000000);
      --tg-hint: var(--tg-theme-hint-color, #999999);
      --tg-link: var(--tg-theme-link-color, #2481cc);
      --tg-btn: var(--tg-theme-button-color, #2481cc);
      --tg-btn-text: var(--tg-theme-button-text-color, #ffffff);
      --tg-sec-bg: var(--tg-theme-secondary-bg-color, #f0f0f0);
    }

    * { margin: 0; padding: 0; box-sizing: border-box; -webkit-tap-highlight-color: transparent; }
    
    body {
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      background-color: var(--tg-bg);
      color: var(--tg-text);
      line-height: 1.5;
      overflow-x: hidden;
      padding-bottom: 100px;
    }

    .tabs {
      display: flex;
      background: var(--tg-sec-bg);
      padding: 4px;
      position: sticky;
      top: 0;
      z-index: 1000;
      backdrop-filter: blur(10px);
      border-bottom: 1px solid rgba(0,0,0,0.1);
    }

    .tab {
      flex: 1;
      padding: 10px 5px;
      text-align: center;
      font-size: 13px;
      font-weight: 600;
      cursor: pointer;
      border-radius: 8px;
      transition: all 0.2s ease;
      color: var(--tg-hint);
    }

    .tab.active {
      background: var(--tg-bg);
      color: var(--tg-text);
      box-shadow: 0 2px 6px rgba(0,0,0,0.05);
    }

    .content-section { display: none; padding: 16px; animation: fadeIn 0.3s ease; }
    .content-section.active { display: block; }

    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

    .card {
      background: var(--tg-sec-bg);
      border-radius: 16px;
      padding: 20px;
      margin-bottom: 16px;
      border: 1px solid rgba(0,0,0,0.05);
    }

    .balance-card {
      background: linear-gradient(135deg, var(--tg-btn), #4facfe);
      color: white;
      text-align: center;
      box-shadow: 0 8px 20px rgba(36, 129, 204, 0.2);
    }

    .balance-label { font-size: 14px; opacity: 0.9; margin-bottom: 4px; }
    .balance-value { font-size: 36px; font-weight: 800; letter-spacing: -1px; }

    /* СТИЛИ ДЛЯ ГРАФИКА */
    .chart-container { margin-top: 20px; width: 100%; height: 200px; }

    .btn {
      background: var(--tg-btn);
      color: var(--tg-btn-text);
      border: none;
      padding: 12px 20px;
      border-radius: 12px;
      font-weight: 600;
      width: 100%;
      font-size: 15px;
      cursor: pointer;
      transition: opacity 0.2s;
    }

    .btn:active { opacity: 0.8; }

    .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }

    .merch-item {
      background: var(--tg-sec-bg);
      border-radius: 12px;
      padding: 12px;
      text-align: center;
    }

    .merch-name { font-weight: 600; font-size: 14px; margin-bottom: 4px; }
    .merch-price { color: var(--tg-link); font-weight: 700; margin-bottom: 10px; }

    .service-item {
      background: var(--tg-bg);
      border: 1px solid var(--tg-sec-bg);
      border-radius: 12px;
      padding: 15px;
      margin-bottom: 12px;
    }
  </style>
</head>
<body>

  <div class="tabs">
    <div class="tab active" onclick="showTab('main')">Профиль</div>
    <div class="tab" onclick="showTab('merch')">Мерч</div>
    <div class="tab" onclick="showTab('exchange')">Биржа</div>
    <div class="tab" onclick="showTab('faq')">FAQ</div>
  </div>

  <div id="main" class="content-section active">
    <div class="card balance-card">
      <div class="balance-label">Мой баланс</div>
      <div class="balance-value" id="balance-display">0</div>
      <div style="font-size: 12px; margin-top: 5px;">Student Coins (STC)</div>
    </div>

    <div class="card">
      <h4 style="margin-bottom: 10px;">Аналитика расходов</h4>
      <div class="chart-container">
        <canvas id="expensesChart"></canvas>
      </div>
    </div>

    <div class="card">
      <h4 style="margin-bottom: 10px;">Топ студентов</h4>
      <div id="leaderboard" style="font-size: 14px;"></div>
    </div>
  </div>

  <div id="merch" class="content-section">
    <h3 style="margin-bottom: 15px;">Магазин мерча</h3>
    <div id="merch-grid" class="grid"></div>
  </div>

  <div id="exchange" class="content-section">
    <button class="btn" style="margin-bottom: 20px;" onclick="tg.showAlert('Функция добавления будет в след. обновлении')">+ Разместить услугу</button>
    <div id="services-list"></div>
  </div>

  <div id="faq" class="content-section">
    <div class="card">
      <h4 style="color: var(--tg-link)">Как работают транзакции?</h4>
      <p style="font-size: 13px; margin-top: 8px;">Все покупки защищены протоколом ACID. Ваши баллы списываются мгновенно и безопасно.</p>
    </div>
  </div>

  <script>
    let tg = window.Telegram.WebApp;
    tg.expand();
    const userId = new URLSearchParams(window.location.search).get('user_id');
    let myChart = null;

    function showTab(tabId) {
      document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.getElementById(tabId).classList.add('active');
      event.currentTarget.classList.add('active');
      
      if(tabId === 'main') updateAllData();
      if(tabId === 'merch') loadMerch();
      if(tabId === 'exchange') loadServices();
    }

    // НОВАЯ ФУНКЦИЯ ГРАФИКА
    function renderChart(stats) {
      const ctx = document.getElementById('expensesChart').getContext('2d');
      if (myChart) myChart.destroy();
      
      myChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: stats.map(s => s.date),
          datasets: [{
            label: 'Траты',
            data: stats.map(s => s.total),
            borderColor: '#2481cc',
            tension: 0.4,
            fill: true,
            backgroundColor: 'rgba(36, 129, 204, 0.1)'
          }]
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          plugins: { legend: { display: false } },
          scales: { y: { beginAtZero: true, grid: { display: false } }, x: { grid: { display: false } } }
        }
      });
    }

    function updateAllData() {
      // Загрузка профиля
      fetch(`/api/user/${userId}`).then(r => r.json()).then(user => {
        document.getElementById('balance-display').innerText = user.current_points;
      });
      // Загрузка статистики для графика
      fetch(`/api/stats/${userId}`).then(r => r.json()).then(stats => renderChart(stats));
      // Загрузка рейтинга
      fetch(`/api/leaderboard`).then(r => r.json()).then(list => {
        document.getElementById('leaderboard').innerHTML = list.map((s, i) => 
          `<div style="display:flex; justify-content:space-between; padding: 5px 0; border-bottom: 1px solid var(--tg-sec-bg);">
            <span>${i+1}. ${s.first_name}</span><b>${s.current_points}</b>
          </div>`).join('');
      });
    }

    function loadMerch() {
      fetch('/api/merch').then(r => r.json()).then(data => {
        const grid = document.getElementById('merch-grid');
        grid.innerHTML = data.map(item => `
          <div class="merch-item">
            <div class="merch-name">${item.name}</div>
            <div class="merch-price">${item.points_cost} STC</div>
            <button class="btn" style="padding: 6px; font-size: 12px;" onclick="buyItem('${item.id}')">Купить</button>
          </div>
        `).join('');
      });
    }

    function buyItem(id) {
      tg.showConfirm("Подтвердить покупку?", (ok) => {
        if(ok) {
          fetch('/api/buy_merch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId, merch_id: id})
          }).then(r => r.json()).then(res => {
            tg.showAlert(res.message);
            updateAllData();
          });
        }
      });
    }

    function loadServices() {
      fetch('/api/services').then(r => r.json()).then(data => {
        document.getElementById('services-list').innerHTML = data.map(s => `
          <div class="service-item">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <div>
                <div style="font-weight:600;">${s.name}</div>
                <div style="font-size:12px; color:var(--tg-hint);">Автор: ${s.provider_name}</div>
              </div>
              <div style="text-align:right;">
                <div style="color:var(--tg-link); font-weight:700;">${s.points_cost}</div>
                <button class="btn" style="padding:4px 10px; font-size:11px; margin-top:5px;" onclick="buyService('${s.id}')">Заказать</button>
              </div>
            </div>
          </div>
        `).join('');
      });
    }

    function buyService(id) {
      fetch('/api/buy_service', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({user_id: userId, service_id: id})
      }).then(r => r.json()).then(res => {
        tg.showAlert(res.message);
        updateAllData();
      });
    }

    updateAllData();
  </script>
</body>
</html>
"""

# ==================== ТВОИ ОРИГИНАЛЬНЫЕ ЭНДПОИНТЫ (ВОЗВРАЩЕНЫ) ====================

@app.route('/miniapp')
def miniapp():
    return render_template_string(HTML_TEMPLATE)

@app.route('/api/user/<int:user_id>')
def api_user(user_id):
    try:
        print(f"[DEBUG] Запрос данных пользователя: {user_id}")
        student = db.get_student_by_tg_id(user_id)
        if not student:
            return jsonify({"error": "User not found"}), 404
        return jsonify(student)
    except Exception as e:
        print(f"[ERROR] api_user: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/api/stats/<int:user_id>')
def api_stats(user_id):
    try:
        stats = db.get_user_stats(user_id)
        return jsonify(stats)
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
        print("[DEBUG] Получение списка мерча")
        items = db.get_all_merch()
        return jsonify(items)
    except Exception as e:
        print(f"[ERROR] api_merch: {e}")
        return jsonify([]), 500

@app.route('/api/services')
def api_services():
    try:
        return jsonify(db.get_active_services())
    except Exception as e:
        return jsonify([]), 500

@app.route('/api/buy_merch', methods=['POST'])
def api_buy_merch():
    try:
        data = request.json
        u_id = int(data.get('user_id'))
        m_id = data.get('merch_id')
        
        print(f"[API] Покупка мерча {m_id} пользователем {u_id}")
        success, message = db.buy_merch(u_id, m_id)
        
        if success:
            send_telegram_notification(u_id, f"<b>✅ Покупка прошла успешно!</b>\n\nВы приобрели мерч.\nСтатус: {message}")
            
        return jsonify({"success": success, "message": message})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"success": False, "message": "Ошибка сервера"}), 500

@app.route('/api/buy_service', methods=['POST'])
def api_buy_service():
    try:
        data = request.json
        u_id = int(data.get('user_id'))
        s_id = data.get('service_id')
        
        success, message = db.buy_service(u_id, s_id)
        
        if success:
            send_telegram_notification(u_id, f"<b>💼 Услуга оплачена!</b>\n\nДетали: {message}")
            
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == '__main__':
    print("--- Запуск Flask сервера Student Coins ---")
    app.run(host='0.0.0.0', port=8000, debug=True)