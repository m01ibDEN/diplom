# webapp.py — ПОЛНАЯ ВЕРСИЯ С РАБОЧИМИ ТАБАМИ
from flask import Flask, jsonify, render_template_string, request
from db import db
import os
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Student Coins</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    * { margin: 0; padding: 0; box-sizing: border-box; }
    body { 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; 
      background: var(--tg-theme-bg-color); 
      color: var(--tg-theme-text-color); 
      padding-bottom: 80px; 
    }
    
    .tabs { 
      display: flex; 
      background: var(--tg-theme-secondary-bg-color); 
      padding: 8px 0; 
      position: sticky; 
      top: 0; 
      z-index: 100; 
      box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .tab { 
      flex: 1; 
      text-align: center; 
      padding: 10px 6px; 
      cursor: pointer; 
      font-size: 0.85em;
      transition: all 0.3s;
    }
    .tab.active { 
      background: var(--tg-theme-button-color); 
      color: var(--tg-theme-button-text-color); 
      border-radius: 12px 12px 0 0; 
      margin: 0 3px;
      font-weight: 600;
    }
    
    .tab-content { display: none; padding: 16px; }
    .tab-content.active { display: block; }
    
    .card { 
      background: var(--tg-theme-secondary-bg-color); 
      padding: 20px; 
      border-radius: 16px; 
      margin-bottom: 16px;
    }
    
    .balance-card { 
      background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
      color: white; 
      padding: 30px; 
      border-radius: 20px; 
      margin-bottom: 20px; 
      text-align: center;
    }
    .points-huge { font-size: 3.5em; font-weight: 800; margin: 10px 0; }
    
    .section-title { 
      font-size: 1.4em; 
      font-weight: 600; 
      margin: 24px 0 12px 0; 
      padding-bottom: 8px; 
      border-bottom: 2px solid var(--tg-theme-hint-color);
    }
    
    .ranking-item { 
      display: flex; 
      align-items: center; 
      padding: 14px; 
      background: var(--tg-theme-secondary-bg-color); 
      margin-bottom: 10px; 
      border-radius: 12px;
    }
    .rank-badge { 
      width: 40px; 
      height: 40px; 
      background: var(--tg-theme-button-color); 
      color: white; 
      border-radius: 50%; 
      display: flex; 
      align-items: center; 
      justify-content: center; 
      font-weight: bold; 
      margin-right: 14px;
    }
    
    .transaction { 
      display: flex; 
      justify-content: space-between; 
      padding: 14px; 
      background: var(--tg-theme-secondary-bg-color); 
      margin-bottom: 10px; 
      border-radius: 12px;
    }
    .transaction.earn { border-left: 4px solid #4CAF50; }
    .transaction.spend { border-left: 4px solid #f44336; }
    
    .merch-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; }
    .merch-card { 
      background: var(--tg-theme-secondary-bg-color); 
      padding: 16px; 
      border-radius: 16px; 
      text-align: center;
    }
    .merch-image { font-size: 3em; margin: 10px 0; }
    .merch-price { font-size: 1.3em; font-weight: bold; color: var(--tg-theme-button-color); margin: 8px 0; }
    
    .service-form { 
      background: linear-gradient(135deg, #667eea15, #764ba215); 
      padding: 20px; 
      border-radius: 16px; 
      margin-bottom: 24px; 
      border: 2px dashed var(--tg-theme-hint-color);
    }
    .form-group { margin-bottom: 14px; }
    .form-group label { display: block; margin-bottom: 6px; font-weight: 500; }
    .form-group input, .form-group textarea { 
      width: 100%; 
      padding: 12px; 
      border: 1px solid var(--tg-theme-hint-color); 
      border-radius: 10px; 
      background: var(--tg-theme-bg-color); 
      color: var(--tg-theme-text-color); 
      font-size: 1em;
      font-family: inherit;
    }
    
    .service-card { 
      background: var(--tg-theme-secondary-bg-color); 
      padding: 18px; 
      border-radius: 16px; 
      margin-bottom: 14px;
    }
    .service-price { font-size: 1.4em; font-weight: bold; color: var(--tg-theme-button-color); }
    .service-provider { color: var(--tg-theme-hint-color); font-size: 0.9em; margin: 4px 0; }
    
    .btn { 
      border: none; 
      padding: 12px 24px; 
      border-radius: 25px; 
      font-weight: 600; 
      cursor: pointer; 
      width: 100%;
      margin-top: 8px;
    }
    .btn-primary { background: var(--tg-theme-button-color); color: var(--tg-theme-button-text-color); }
    .btn-success { background: #4CAF50; color: white; }
    
    .faq-item { 
      background: var(--tg-theme-secondary-bg-color); 
      padding: 18px; 
      border-radius: 14px; 
      margin-bottom: 12px;
    }
    .faq-question { font-weight: 600; font-size: 1.05em; margin-bottom: 10px; }
    
    .badge-success { 
      display: inline-block; 
      padding: 4px 10px; 
      border-radius: 12px; 
      font-size: 0.8em; 
      background: #4CAF50; 
      color: white;
    }
  </style>
</head>
<body>
  <div class="tabs">
    <div class="tab active" data-tab="home">🏠<br>Главная</div>
    <div class="tab" data-tab="merch">🛒<br>Мерч</div>
    <div class="tab" data-tab="exchange">🔄<br>Биржа</div>
    <div class="tab" data-tab="faq">❓<br>FAQ</div>
  </div>

  <!-- ГЛАВНАЯ -->
  <div id="home" class="tab-content active">
    <div class="balance-card">
      <div class="points-huge">{{ balance.current }}</div>
      <p>Рейтинг: #{{ balance.rank }}</p>
    </div>
    <h2 class="section-title">🏆 Рейтинг</h2>
    {% for item in ranking %}
    <div class="ranking-item">
      <div class="rank-badge">#{{ item.rank }}</div>
      <div>{{ item.name }}<br><strong>{{ item.points }} баллов</strong></div>
    </div>
    {% endfor %}
    
    <h2 class="section-title">📜 История</h2>
    {% for tx in transactions %}
    <div class="transaction {{ tx.type }}">
      <div>{{ tx.description }}<br><small>{{ tx.date }}</small></div>
      <div style="font-weight: bold;">{{ tx.amount }}</div>
    </div>
    {% endfor %}
  </div>

  <!-- МЕРЧ -->
  <div id="merch" class="tab-content">
    <h2 class="section-title">🛒 Мерч</h2>
    <div class="merch-grid">
      {% for item in merch %}
      <div class="merch-card">
        <div class="merch-image">{{ item.image }}</div>
        <div>{{ item.name }}</div>
        <div class="merch-price">{{ item.price }} 💰</div>
        <div>В наличии: {{ item.stock }}</div>
        <button class="btn btn-primary" onclick="buyMerch('{{ item.id }}', '{{ item.name }}', {{ item.price }})">Купить</button>
      </div>
      {% endfor %}
    </div>
  </div>

  <!-- БИРЖА -->
  <div id="exchange" class="tab-content">
    <h2 class="section-title">💼 Мои услуги</h2>
    
    <div class="service-form">
      <div class="form-group">
        <label>Название</label>
        <input id="service-name" type="text" placeholder="Помощь с Python">
      </div>
      <div class="form-group">
        <label>Цена (баллов)</label>
        <input id="service-price" type="number" placeholder="100" min="1">
      </div>
      <div class="form-group">
        <label>Описание</label>
        <textarea id="service-desc" rows="2" placeholder="Краткое описание"></textarea>
      </div>
      <button class="btn btn-success" onclick="addService()">🚀 Разместить</button>
    </div>
    
    {% if my_services %}
    {% for service in my_services %}
    <div class="service-card">
      <div style="display: flex; justify-content: space-between;">
        <div>
          <h3>{{ service.name }}</h3>
          <div class="service-price">{{ service.price }} 💰</div>
        </div>
        <span class="badge-success">{{ service.status }}</span>
      </div>
      <div style="margin-top: 10px; color: var(--tg-theme-hint-color); font-size: 0.9em;">
        📦 Заказов: {{ service.orders }} | 💰 Заработано: {{ service.earnings }}
      </div>
    </div>
    {% endfor %}
    {% else %}
    <div class="card" style="text-align: center;">У вас пока нет услуг</div>
    {% endif %}
    
    <h2 class="section-title">🔄 Услуги других</h2>
    {% for service in exchange_services %}
    <div class="service-card">
      <h3>{{ service.name }}</h3>
      <div class="service-provider">от {{ service.provider }}</div>
      <div style="display: flex; justify-content: space-between; margin-top: 12px;">
        <div>
          <div class="service-price">{{ service.price }} 💰</div>
          <div style="font-size: 0.85em;">⭐ {{ service.rating }} | 📦 {{ service.orders }}</div>
        </div>
        <button class="btn btn-primary" style="width: auto; padding: 10px 20px;" 
                onclick="buyService('{{ service.id }}', '{{ service.name }}', {{ service.price }}, '{{ service.provider }}')">
          Заказать
        </button>
      </div>
    </div>
    {% endfor %}
  </div>

  <!-- FAQ -->
  <div id="faq" class="tab-content">
    <h2 class="section-title">❓ FAQ</h2>
    {% for item in faq %}
    <div class="faq-item">
      <div class="faq-question">{{ item.q }}</div>
      <div>{{ item.a }}</div>
    </div>
    {% endfor %}
  </div>
    <script>
    // Определяем среду
    var tg = null;
    var isTelegram = false;
    
    try {
      if (window.Telegram && window.Telegram.WebApp && window.Telegram.WebApp.initData) {
        tg = window.Telegram.WebApp;
        isTelegram = true;
        tg.ready();
        tg.expand();
        console.log('[APP] Telegram mode');
      } else {
        console.log('[APP] Browser mode');
      }
    } catch(e) {
      console.log('[APP] Browser mode (catch)');
    }
    
    var userId = {{ user_id }};
    console.log('[APP] userId:', userId, 'isTelegram:', isTelegram);

    // ТАБЫ
    setTimeout(function() {
      var tabs = document.querySelectorAll('.tab');
      var contents = document.querySelectorAll('.tab-content');
      
      for (var i = 0; i < tabs.length; i++) {
        tabs[i].onclick = (function(index) {
          return function() {
            for (var j = 0; j < tabs.length; j++) {
              tabs[j].classList.remove('active');
              contents[j].classList.remove('active');
            }
            tabs[index].classList.add('active');
            contents[index].classList.add('active');
          };
        })(i);
      }
      console.log('[TABS] Инициализированы:', tabs.length);
    }, 100);

    // РАЗМЕСТИТЬ УСЛУГУ
    function addService() {
      var name = document.getElementById('service-name').value.trim();
      var price = parseInt(document.getElementById('service-price').value);
      var desc = document.getElementById('service-desc').value.trim();
      
      console.log('[addService] name:', name, 'price:', price, 'isTelegram:', isTelegram);
      
      if (!name || !price || price < 1) {
        if (isTelegram && tg) {
          tg.showAlert('⚠️ Заполните название и цену!');
        } else {
          alert('⚠️ Заполните название и цену!');
        }
        return;
      }
      
      // Очищаем форму сразу
      document.getElementById('service-name').value = '';
      document.getElementById('service-price').value = '';
      document.getElementById('service-desc').value = '';
      
      if (isTelegram && tg) {
        // TELEGRAM: отправляем через sendData
        console.log('[addService] Отправка через Telegram');
        tg.sendData(JSON.stringify({
          action: 'add_service',
          name: name,
          price: price,
          description: desc
        }));
        tg.showAlert('✅ Услуга "' + name + '" размещена!');
      } else {
        // БРАУЗЕР: отправляем через fetch
        console.log('[addService] Отправка через fetch API');
        
        fetch('/api/add_service', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          body: JSON.stringify({
            user_id: userId,
            name: name,
            price: price,
            description: desc
          })
        })
        .then(function(res) {
          console.log('[addService] Response status:', res.status);
          return res.json();
        })
        .then(function(data) {
          console.log('[addService] Response:', data);
          if (data.success) {
            alert('✅ ' + data.message);
            setTimeout(function() { location.reload(); }, 500);
          } else {
            alert('❌ ' + data.message);
          }
        })
        .catch(function(err) {
          console.error('[addService] Error:', err);
          alert('❌ Ошибка: ' + err.message);
        });
      }
    }

    // КУПИТЬ МЕРЧ
    function buyMerch(id, name, price) {
      var msg = 'Купить "' + name + '" за ' + price + ' баллов?';
      
      var doAction = function() {
        if (isTelegram && tg) {
          tg.sendData(JSON.stringify({
            action: 'buy_merch',
            merch_id: id,
            name: name,
            price: price
          }));
          tg.showAlert('✅ Заказ оформлен!');
        } else {
          fetch('/api/buy_merch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              user_id: userId,
              merch_id: id,
              quantity: 1
            })
          })
          .then(function(res) { return res.json(); })
          .then(function(data) {
            if (data.success) {
              alert('✅ ' + data.message);
              setTimeout(function() { location.reload(); }, 500);
            } else {
              alert('❌ ' + data.message);
            }
          })
          .catch(function(err) {
            alert('❌ Ошибка: ' + err.message);
          });
        }
      };
      
      if (isTelegram && tg) {
        tg.showConfirm(msg, function(ok) { if (ok) doAction(); });
      } else {
        if (confirm(msg)) doAction();
      }
    }

    // КУПИТЬ УСЛУГУ
    function buyService(id, name, price, provider) {
      var msg = 'Заказать "' + name + '" у ' + provider + ' за ' + price + ' баллов?';
      
      var doAction = function() {
        if (isTelegram && tg) {
          tg.sendData(JSON.stringify({
            action: 'buy_service',
            service_id: id,
            name: name,
            price: price
          }));
          tg.showAlert('✅ Заказ отправлен!');
        } else {
          fetch('/api/buy_service', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
              user_id: userId,
              service_id: id
            })
          })
          .then(function(res) { return res.json(); })
          .then(function(data) {
            if (data.success) {
              alert('✅ ' + data.message);
              setTimeout(function() { location.reload(); }, 500);
            } else {
              alert('❌ ' + data.message);
            }
          })
          .catch(function(err) {
            alert('❌ Ошибка: ' + err.message);
          });
        }
      };
      
      if (isTelegram && tg) {
        tg.showConfirm(msg, function(ok) { if (ok) doAction(); });
      } else {
        if (confirm(msg)) doAction();
      }
    }
  </script>
</body>
</html>
"""

@app.route('/miniapp')
def miniapp():
    user_id = int(request.args.get('user_id', 12345))
    
    balance = db.get_balance(user_id)
    transactions = db.get_transactions(user_id, limit=10)
    ranking = db.get_ranking(limit=10)
    merch = db.get_merch()
    my_services = db.get_my_services(user_id)
    exchange_services = db.get_all_services(exclude_user_id=user_id)
    
    data = {
        "user_id": user_id,
        "balance": balance,
        "transactions": transactions,
        "ranking": ranking,
        "merch": merch,
        "my_services": my_services,
        "exchange_services": exchange_services,
        "faq": [
            {"q": "Как заработать баллы?", "a": "Участвуйте в мероприятиях, пишите конспекты, оказывайте услуги."},
            {"q": "Как потратить баллы?", "a": "Покупайте мерч ВУЗа или заказывайте услуги других студентов."},
            {"q": "Что такое рейтинг?", "a": "Топ студентов по количеству баллов. Лидеры имеют приоритет на бирже."}
        ]
    }
    
    return render_template_string(HTML_TEMPLATE, **data)

# ==================== API ENDPOINTS ====================

@app.route('/api/add_service', methods=['POST'])
def api_add_service():
    """Разместить услугу"""
    try:
        data = request.json
        user_id = int(data.get('user_id'))
        name = data.get('name')
        price = int(data.get('price'))
        description = data.get('description', '')
        
        print(f"[API] Размещение услуги: '{name}' за {price} баллов (user_id={user_id})")
        
        if not name or price < 1:
            return jsonify({"success": False, "message": "Некорректные данные"}), 400
        
        success = db.add_service(user_id, name, price, description)
        
        if success:
            return jsonify({
                "success": True,
                "message": f"Услуга '{name}' успешно размещена!"
            })
        else:
            return jsonify({
                "success": False,
                "message": "Ошибка при размещении услуги"
            }), 500
            
    except Exception as e:
        print(f"[API ERROR] add_service: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/buy_merch', methods=['POST'])
def api_buy_merch():
    """Купить мерч"""
    try:
        data = request.json
        user_id = int(data.get('user_id'))
        merch_id = data.get('merch_id')
        quantity = int(data.get('quantity', 1))
        
        print(f"[API] Покупка мерча: {merch_id} (user_id={user_id})")
        
        success, message = db.buy_merch(user_id, merch_id, quantity)
        
        return jsonify({"success": success, "message": message})
        
    except Exception as e:
        print(f"[API ERROR] buy_merch: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

@app.route('/api/buy_service', methods=['POST'])
def api_buy_service():
    """Заказать услугу"""
    try:
        data = request.json
        user_id = int(data.get('user_id'))
        service_id = data.get('service_id')
        
        print(f"[API] Заказ услуги: {service_id} (user_id={user_id})")
        
        success, message = db.buy_service(user_id, service_id)
        
        return jsonify({"success": success, "message": message})
        
    except Exception as e:
        print(f"[API ERROR] buy_service: {e}")
        return jsonify({"success": False, "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)

