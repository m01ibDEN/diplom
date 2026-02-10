# webapp.py
from flask import Flask, jsonify, render_template_string, request
from db import db
import os
import requests
import traceback
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

def send_telegram_notification(user_id, text):
    token = os.getenv("BOT_TOKEN")
    if not token: return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    try:
        requests.post(url, json={"chat_id": user_id, "text": text, "parse_mode": "HTML"})
    except Exception as e:
        print(f"[ERROR] Ошибка отправки: {e}")

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
    body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: var(--tg-bg); color: var(--tg-text); padding-bottom: 100px; }
    .tabs { display: flex; background: var(--tg-sec-bg); padding: 4px; position: sticky; top: 0; z-index: 1000; border-bottom: 1px solid rgba(0,0,0,0.1); }
    .tab { flex: 1; padding: 10px 5px; text-align: center; font-size: 12px; font-weight: 600; cursor: pointer; border-radius: 8px; color: var(--tg-hint); }
    .tab.active { background: var(--tg-bg); color: var(--tg-text); box-shadow: 0 2px 6px rgba(0,0,0,0.05); }
    .content-section { display: none; padding: 16px; animation: fadeIn 0.3s ease; }
    .content-section.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    .card { background: var(--tg-sec-bg); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
    .balance-card { background: linear-gradient(135deg, var(--tg-btn), #4facfe); color: white; text-align: center; box-shadow: 0 8px 20px rgba(36, 129, 204, 0.2); }
    .balance-value { font-size: 36px; font-weight: 800; }
    .chart-container { margin-top: 20px; width: 100%; height: 200px; }
    .btn { background: var(--tg-btn); color: var(--tg-btn-text); border: none; padding: 12px 20px; border-radius: 12px; font-weight: 600; width: 100%; font-size: 15px; cursor: pointer; }
    .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .merch-item { background: var(--tg-sec-bg); border-radius: 12px; padding: 12px; text-align: center; }
    .merch-price { color: var(--tg-link); font-weight: 700; margin-bottom: 10px; }
    .service-item { background: var(--tg-bg); border: 1px solid var(--tg-sec-bg); border-radius: 12px; padding: 15px; margin-bottom: 12px; }
    /* Стиль для истории */
    .history-item { display: flex; justify-content: space-between; align-items: center; padding: 10px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
    .history-meta { font-size: 12px; color: var(--tg-hint); }
    .history-amount.earn { color: #4caf50; font-weight: bold; }
    .history-amount.spend { color: #f44336; font-weight: bold; }
    .input {
      width: 100%;
      padding: 12px;
      border-radius: 12px;
      border: 1px solid rgba(0,0,0,0.08);
      background: var(--tg-bg);
      color: var(--tg-text);
      font-size: 14px;
      outline: none;
    }

    .btn-secondary {
      background: transparent;
      color: var(--tg-text);
      border: 1px solid rgba(0,0,0,0.15);
    }

  </style>
</head>
<body>
  <div class="tabs">
    <div class="tab active" onclick="showTab('main', this)">Профиль</div>
    <div class="tab" onclick="showTab('history', this)">История</div>
    <div class="tab" onclick="showTab('merch', this)">Мерч</div>
    <div class="tab" onclick="showTab('exchange', this)">Биржа</div>
  </div>


  <div id="main" class="content-section active">
    <div class="card balance-card">
      <div style="font-size: 14px; opacity: 0.9;">Мой баланс</div>
      <div class="balance-value" id="balance-display">0</div>
      <div style="font-size: 12px;">Student Coins (STC)</div>
    </div>
    <div class="card">
      <h4 style="margin-bottom: 10px;">Аналитика расходов</h4>
      <div class="chart-container"><canvas id="expensesChart"></canvas></div>
    </div>
    <div class="card">
      <h4 style="margin-bottom: 10px;">Топ студентов</h4>
      <div id="leaderboard" style="font-size: 14px;"></div>
    </div>
  </div>

  <div id="history" class="content-section">
    <h3 style="margin-bottom: 15px;">Последние операции</h3>
    <div id="history-list"></div>
  </div>

  <div id="merch" class="content-section">
    <h3 style="margin-bottom: 15px;">Магазин мерча</h3>
    <div id="merch-grid" class="grid"></div>
  </div>

  <div id="exchange" class="content-section">
  <button class="btn" style="margin-bottom: 12px;" onclick="toggleCreateService()">
    + Разместить услугу
  </button>

  <div id="create-service-card" class="card" style="display:none;">
    <h3 style="margin-bottom: 12px;">Новая услуга</h3>

    <div style="margin-bottom: 10px;">
      <div style="font-size: 12px; color: var(--tg-hint); margin-bottom: 6px;">Название</div>
      <input id="svc-name" class="input" placeholder="Напр.: Помощь с Python" />
    </div>

    <div style="margin-bottom: 10px;">
      <div style="font-size: 12px; color: var(--tg-hint); margin-bottom: 6px;">Цена (STC)</div>
      <input id="svc-price" class="input" type="number" min="1" placeholder="100" />
    </div>

    <div style="margin-bottom: 10px;">
      <div style="font-size: 12px; color: var(--tg-hint); margin-bottom: 6px;">Описание</div>
      <textarea id="svc-desc" class="input" rows="3" placeholder="Кратко опиши, что именно делаешь"></textarea>
    </div>

    <button class="btn" onclick="createService()">Опубликовать</button>
    <button class="btn btn-secondary" style="margin-top: 8px;" onclick="toggleCreateService(false)">Отмена</button>
  </div>

  <div id="services-list"></div>
  </div>


  <script>
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (tg) tg.expand();

    const userId = new URLSearchParams(window.location.search).get('user_id');

    function uiAlert(msg) {
      // Если есть tg и версия >= 6.2 — используем нативный popup
      if (tg && tg.showPopup && isVersionAtLeast('6.2')) {
        tg.showAlert(msg);
      } else {
        // Иначе обычный браузерный alert
        alert(msg);
      }
    }

    function uiConfirm(msg, callback) {
      if (tg && tg.showPopup && isVersionAtLeast('6.2')) {
        tg.showConfirm(msg, callback);
      } else {
        // Браузерный confirm (синхронный)
        const result = confirm(msg);
        callback(result);
      }
    }

    // Хелпер для проверки версии (6.0 < 6.2)
    function isVersionAtLeast(minVer) {
      if (!tg || !tg.version) return false;
      const v1 = tg.version.split('.').map(Number);
      const v2 = minVer.split('.').map(Number);
      return (v1[0] > v2[0]) || (v1[0] === v2[0] && v1[1] >= v2[1]);
    }


    let myChart = null;

    function showTab(tabId, el) {
        // 1. Скрываем все секции
        document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
        
        // 2. Убираем активность со всех табов
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        
        // 3. Активируем нужную секцию
        const section = document.getElementById(tabId);
        if (section) section.classList.add('active');

        // 4. Активируем таб (если el передан — используем его, иначе ищем через event)
        if (el) {
            el.classList.add('active');
        } else if (window.event && window.event.currentTarget) {
            window.event.currentTarget.classList.add('active');
        }

        // 5. Загружаем данные
        if(tabId === 'main') updateAllData();
        if(tabId === 'history') loadHistory();
        if(tabId === 'merch') loadMerch();
        if(tabId === 'exchange') loadServices();
    }



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
        options: { responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, grid: { display: false } }, x: { grid: { display: false } } } }
      });
    }

    function updateAllData() {
      fetch(`/api/user/${userId}`).then(r => r.json()).then(user => {
        document.getElementById('balance-display').innerText = user.current_points;
      });
      fetch(`/api/stats/${userId}`).then(r => r.json()).then(stats => renderChart(stats));
      fetch(`/api/leaderboard`).then(r => r.json()).then(list => {
        document.getElementById('leaderboard').innerHTML = list.map((s, i) => 
          `<div style="display:flex; justify-content:space-between; padding: 5px 0; border-bottom: 1px solid var(--tg-sec-bg);">
            <span>${i+1}. ${s.first_name}</span><b>${s.current_points}</b>
          </div>`).join('');
      });
    }

    function loadHistory() {
      fetch(`/api/history/${userId}`).then(r => r.json()).then(data => {
        document.getElementById('history-list').innerHTML = data.map(item => `
          <div class="history-item">
            <div>
              <div style="font-weight: 500; font-size: 14px;">${item.description}</div>
              <div class="history-meta">${item.created_at}</div>
            </div>
            <div class="history-amount ${item.type}">
              ${item.type === 'earn' ? '+' : '-'}${item.amount}
            </div>
          </div>
        `).join('');
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
          // Обязательно передаем user_id в GET-параметре, чтобы SQL знал, кто "я"
          fetch(`/api/services?user_id=${userId}`).then(r => r.json()).then(data => {
            const list = document.getElementById('services-list');
            
            if (data.length === 0) {
                list.innerHTML = '<div style="text-align:center; padding:20px;">Заданий нет</div>';
                return;
            }

            list.innerHTML = data.map(s => {
              if (s.status === 'completed') return ''; 

              let actionButton = '';
              let statusBadge = '';

              // Логика теперь проще, так как сервер уже все посчитал
              if (s.is_my_task) {
                if (s.status === 'in_progress') {
                    statusBadge = '<span style="color:#2481cc;">⚙️ В работе</span>';
                    // Передаем s.order_id для подтверждения!
                    actionButton = `<button class="btn" style="background:#4caf50; margin-top:5px;" onclick="confirmTask('${s.order_id}')">✅ Принять и оплатить</button>`;
                } else {
                    statusBadge = '<span style="color:var(--tg-hint);">⏳ Ждем исполнителя</span>';
                }
              } else {
                if (s.status === 'open') {
                    actionButton = `<button class="btn" onclick="takeTask('${s.id}')">⚡️ Выполнить за ${s.points_cost}</button>`;
                } else if (s.am_i_executor) {
                    statusBadge = '<span style="color:#4caf50; font-weight:bold;">🛠 Вы выполняете</span>';
                    actionButton = `<div style="font-size:12px; margin-top:5px; color:var(--tg-hint);">Выполните работу и сообщите заказчику</div>`;
                } else {
                    statusBadge = '<span style="color:var(--tg-hint);">🔒 Занято</span>';
                }
              }

              return `
              <div class="service-item">
                <div style="display:flex; justify-content:space-between; align-items:start;">
                  <div style="flex:1; padding-right:10px;">
                    <div style="font-weight:700; font-size:15px;">${s.name}</div>
                    <div style="font-size:13px; margin:4px 0;">${s.description || ''}</div>
                    <div style="font-size:11px; color:var(--tg-hint);">
                        Автор: ${s.is_my_task ? 'Вы' : s.provider_name}
                    </div>
                    <div style="margin-top:5px;">${statusBadge}</div>
                  </div>
                  <div style="text-align:right; min-width:80px;">
                    <div style="color:var(--tg-link); font-weight:800; font-size:16px;">${s.points_cost}</div>
                    ${actionButton}
                  </div>
                </div>
              </div>
              `;
            }).join('');
          });
        }

        // Новые функции-действия
        function takeTask(id) {
            uiConfirm("Взять это задание в работу? Вы станете единственным исполнителем.", (ok) => {
                if(!ok) return;
                fetch('/api/take_task', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({user_id: userId, service_id: id})
                }).then(r => r.json()).then(res => {
                    uiAlert(res.message);
                    loadServices(); // Обновляем список
                });
            });
        }

        function confirmTask(orderId) {
          uiConfirm("Подтвердить выполнение и оплатить?", (ok) => {
              if(!ok) return;
              fetch('/api/confirm_task', {
                  method: 'POST',
                  headers: {'Content-Type': 'application/json'},
                  body: JSON.stringify({user_id: userId, order_id: orderId})
              }).then(r => r.json()).then(res => {
                  uiAlert(res.message);
                  updateAllData();
                  loadServices();
              });
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

    function toggleCreateService(force) {
      const card = document.getElementById('create-service-card');
      const show = (typeof force === 'boolean') ? force : (card.style.display === 'none');
      card.style.display = show ? 'block' : 'none';
    }

    function createService() {
      if (!userId) return uiAlert('Нет user_id в URL. Открой /miniapp?user_id=12345');

      const name = document.getElementById('svc-name').value.trim();
      const price = parseInt(document.getElementById('svc-price').value, 10);
      const desc = document.getElementById('svc-desc').value.trim();

      if (!name || !price || price < 1) return uiAlert('Заполни название и цену (>= 1).');

      uiConfirm(`Опубликовать услугу "${name}" за ${price} STC?`, (ok) => {
        if (!ok) return;

        fetch('/api/add_service', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            user_id: parseInt(userId, 10),
            name: name,
            points_cost: price,
            description: desc
          })
        })
        .then(r => r.json())
        .then(res => {
          uiAlert(res.message || (res.success ? 'Готово' : 'Ошибка'));
          if (res.success) {
            document.getElementById('svc-name').value = '';
            document.getElementById('svc-price').value = '';
            document.getElementById('svc-desc').value = '';
            toggleCreateService(false);
            loadServices(); // обновим список
          }
        })
        .catch(err => uiAlert('Ошибка сети: ' + err));
      });
    }

  </script>
</body>
</html>
"""

@app.route('/miniapp')
def miniapp():
    return render_template_string(HTML_TEMPLATE)

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
        # Передаем user_id (число), чтобы БД знала, кто смотрит список
        return jsonify(db.get_all_services(int(user_id)))
    except Exception as e:
        print(e)
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

@app.route('/api/add_service', methods=['POST'])
def api_add_service():
    try:
        data = request.get_json(silent=True) or {}

        u_id = int(data.get('user_id') or 0)
        name = (data.get('name') or '').strip()
        points_cost = int(data.get('points_cost') or 0)
        description = (data.get('description') or '').strip()

        if not u_id or not name or points_cost < 1:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400

        # на всякий случай создаём студента (для web-тестов)
        # db.get_or_create_student(u_id, first_name="Student", last_name="", username="")

        success, message = db.add_service(u_id, name, points_cost, description)

        if success:
            send_telegram_notification(u_id, f"✅ Услуга размещена: <b>{name}</b>\nЦена: {points_cost} STC")
        return jsonify({"success": success, "message": message})
    except Exception as e:
        print("[api_add_service ERROR]", e)
        traceback.print_exc()
        return jsonify({"success": False, "message": "Ошибка сервера"}), 500
  
@app.route('/api/take_task', methods=['POST'])
def api_take_task():
    try:
        data = request.json
        # Безопасно пытаемся получить ID
        try:
            u_id = int(data.get('user_id'))
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Ошибка: user_id должен быть числом (Telegram ID)"}), 400
            
        success, msg = db.assign_service(data.get('service_id'), u_id)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка сервера: {str(e)}"}), 500


@app.route('/api/confirm_task', methods=['POST'])
def api_confirm_task():
    try:
        data = request.json
        u_id = int(data.get('user_id'))
        # ВНИМАНИЕ: здесь мы подтверждаем конкретный ORDER_ID, а не service_id
        # (потому что в service_orders может быть несколько заказов на одну услугу теоретически, 
        #  но у нас пока 1 к 1. Но для точности используем ID заказа)
        order_id = data.get('order_id') 
        
        success, msg = db.complete_service_order(order_id, u_id)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=True)