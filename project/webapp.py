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
    
    body { 
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; 
      background-color: var(--tg-bg); 
      color: var(--tg-text); 
      padding-bottom: 80px; /* Отступ под нижнее меню */
      padding-top: 10px;
    }

    /* --- НАВИГАЦИЯ СНИЗУ --- */
    .tabs { 
      display: flex; 
      background: var(--tg-sec-bg); 
      padding-bottom: env(safe-area-inset-bottom); /* Для iPhone */
      position: fixed; 
      bottom: 0; 
      left: 0;
      right: 0;
      z-index: 1000; 
      border-top: 1px solid rgba(0,0,0,0.1); 
      height: 60px;
    }
    .tab { 
      flex: 1; 
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 13px; 
      font-weight: 600; 
      cursor: pointer; 
      color: var(--tg-hint); 
      transition: color 0.2s;
    }
    .tab.active { 
      color: var(--tg-link); 
      background: rgba(0,0,0,0.05);
    }

    .content-section { display: none; padding: 16px; animation: fadeIn 0.3s ease; }
    .content-section.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

    .card { background: var(--tg-sec-bg); border-radius: 16px; padding: 20px; margin-bottom: 16px; }
    .balance-card { background: linear-gradient(135deg, var(--tg-btn), #4facfe); color: white; text-align: center; box-shadow: 0 8px 20px rgba(36, 129, 204, 0.2); }
    .balance-value { font-size: 36px; font-weight: 800; }
    
    .chart-container { margin-top: 20px; width: 100%; height: 200px; }
    
    .btn { background: var(--tg-btn); color: var(--tg-btn-text); border: none; padding: 12px 20px; border-radius: 12px; font-weight: 600; width: 100%; font-size: 15px; cursor: pointer; }
    .btn-secondary { background: transparent; color: var(--tg-text); border: 1px solid rgba(0,0,0,0.15); }
    
    .input { width: 100%; padding: 12px; border-radius: 12px; border: 1px solid rgba(0,0,0,0.08); background: var(--tg-bg); color: var(--tg-text); font-size: 14px; outline: none; }

    /* --- МЕРЧ --- */
    .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }
    .merch-item { 
        background: var(--tg-sec-bg); 
        border-radius: 12px; 
        padding: 0; 
        text-align: center; 
        overflow: hidden; 
        cursor: pointer; 
        transition: transform 0.1s;
    }
    .merch-item:active { transform: scale(0.98); }
    .merch-img { width: 100%; height: 140px; object-fit: cover; background: #eee; }
    .merch-info { padding: 10px; }
    .merch-name { font-weight: 600; font-size: 14px; margin-bottom: 5px; }
    .merch-price { color: var(--tg-link); font-weight: 700; margin-bottom: 0; }

    /* Модальное окно Мерча */
    .modal-overlay {
        position: fixed; top: 0; left: 0; width: 100%; height: 100%;
        background: rgba(0,0,0,0.6); z-index: 2000;
        display: none; justify-content: center; align-items: flex-end;
    }
    .modal-content {
        background: var(--tg-bg);
        width: 100%;
        max-height: 90vh;
        border-radius: 20px 20px 0 0;
        padding: 20px;
        overflow-y: auto;
        animation: slideUp 0.3s ease;
    }
    @keyframes slideUp { from { transform: translateY(100%); } to { transform: translateY(0); } }
    .modal-img-full { width: 100%; border-radius: 12px; margin-bottom: 15px; object-fit: cover; max-height: 300px; }
    .modal-title { font-size: 20px; font-weight: 800; margin-bottom: 5px; }
    .modal-price { font-size: 18px; color: var(--tg-link); font-weight: 700; margin-bottom: 15px; }
    .spec-row { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; border-bottom: 1px solid rgba(0,0,0,0.05); padding-bottom: 8px; }
    .spec-label { color: var(--tg-hint); }
    .spec-val { font-weight: 500; }

    /* --- БИРЖА --- */
    .service-item { background: var(--tg-bg); border: 1px solid var(--tg-sec-bg); border-radius: 12px; padding: 15px; margin-bottom: 12px; }

    /* --- ИСТОРИЯ --- */
    .history-item { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(0,0,0,0.05); }
    .history-item:last-child { border-bottom: none; }
    .history-meta { font-size: 12px; color: var(--tg-hint); }
    .history-amount.earn { color: #4caf50; font-weight: bold; }
    .history-amount.spend { color: #f44336; font-weight: bold; }

    /* --- FAQ --- */
    .faq-item { border-bottom: 1px solid rgba(0,0,0,0.1); }
    .faq-question {
        padding: 16px 0;
        font-weight: 600;
        font-size: 15px;
        cursor: pointer;
        display: flex;
        justify-content: space-between;
        align-items: center;
    }
    .faq-question::after {
        content: '+';
        font-size: 18px;
        color: var(--tg-link);
        transition: transform 0.2s;
    }
    .faq-item.active .faq-question::after { transform: rotate(45deg); }
    .faq-answer {
        max-height: 0;
        overflow: hidden;
        transition: max-height 0.3s ease;
        font-size: 14px;
        color: var(--tg-text);
        opacity: 0.9;
        line-height: 1.5;
    }
    .faq-item.active .faq-answer { padding-bottom: 16px; max-height: 200px; }

  </style>
</head>
<body>

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
      <h4 style="margin-bottom: 10px;">История транзакций</h4>
      <div id="history-list">
        <div style="text-align:center; color: var(--tg-hint); font-size: 13px;">Загрузка...</div>
      </div>
    </div>

    <div class="card">
      <h4 style="margin-bottom: 10px;">Топ студентов</h4>
      <div id="leaderboard" style="font-size: 14px;"></div>
    </div>
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

  <div id="merch" class="content-section">
    <h3 style="margin-bottom: 15px;">Магазин мерча</h3>
    <div class="grid">
        <div class="merch-item" onclick="openMerchModal('Футболка Basic', 1000, 'Хлопок 100%', 'S, M, L, XL', 'В наличии', '/static/merch1.jpg')">
            <img src="/static/merch1.jpg" class="merch-img" onerror="this.src='https://via.placeholder.com/150'">
            <div class="merch-info">
                <div class="merch-name">Футболка Basic</div>
                <div class="merch-price">1000 STC</div>
            </div>
        </div>
        <div class="merch-item" onclick="openMerchModal('Худи Oversize', 1000, 'Футер 3-х нитка', 'M, L, XL', 'В наличии', '/static/merch2.jpg')">
            <img src="/static/merch2.jpg" class="merch-img" onerror="this.src='https://via.placeholder.com/150'">
            <div class="merch-info">
                <div class="merch-name">Худи Oversize</div>
                <div class="merch-price">1000 STC</div>
            </div>
        </div>
        <div class="merch-item" onclick="openMerchModal('Свитшот Logo', 1000, 'Хлопок + Полиэстер', 'XS, S, M', 'Мало', '/static/merch3.jpg')">
            <img src="/static/merch3.jpg" class="merch-img" onerror="this.src='https://via.placeholder.com/150'">
            <div class="merch-info">
                <div class="merch-name">Свитшот Logo</div>
                <div class="merch-price">1000 STC</div>
            </div>
        </div>
    </div>
  </div>

  <div id="faq" class="content-section">
    <h3 style="margin-bottom: 15px;">Частые вопросы</h3>
    
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">Что такое Student Coins?</div>
        <div class="faq-answer">Это внутренняя валюта для студентов. Зарабатывай баллы за активность в университете и трать их на реальные вещи или услуги.</div>
    </div>
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">За что начисляются баллы?</div>
        <div class="faq-answer">За учебные достижения, участие в мероприятиях, конференциях и организаторскую деятельность.</div>
    </div>
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">Где посмотреть историю операций?</div>
        <div class="faq-answer">В приложении на вкладке «Профиль». Там видны все начисления и списания.</div>
    </div>
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">Что такое Рейтинг?</div>
        <div class="faq-answer">Это топ студентов. Чем больше баллов ты заработал, тем выше твоя позиция в списке лидеров на главной странице.</div>
    </div>
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">Как купить мерч?</div>
        <div class="faq-answer">Перейди во вкладку «Мерч», выбери товар и нажми «Купить». Если баллов хватает, товар забронируется за тобой.</div>
    </div>
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">Что такое «Биржа»?</div>
        <div class="faq-answer">Это площадка, где студенты помогают друг другу. Ты можешь купить услугу (например, помощь с проектом) у другого студента за баллы.</div>
    </div>
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">Могу ли я сам предложить услугу?</div>
        <div class="faq-answer">Да, в разделе «Биржа» можно разместить свое предложение, указав цену и описание.</div>
    </div>
    <div class="faq-item" onclick="toggleFaq(this)">
        <div class="faq-question">У меня не открывается MiniApp.</div>
        <div class="faq-answer">Убедись, что у тебя обновлен Telegram до последней версии и есть стабильный интернет.</div>
    </div>
  </div>

  <div class="tabs">
    <div class="tab active" onclick="showTab('main', this)">Профиль</div>
    <div class="tab" onclick="showTab('exchange', this)">Биржа услуг</div>
    <div class="tab" onclick="showTab('merch', this)">Мерч</div>
    <div class="tab" onclick="showTab('faq', this)">FAQ</div>
  </div>

  <div id="merch-modal" class="modal-overlay">
      <div class="modal-content">
          <img id="modal-img" src="" class="modal-img-full">
          <div id="modal-title" class="modal-title">Товар</div>
          <div id="modal-price" class="modal-price">1000 STC</div>
          
          <div class="spec-row">
              <span class="spec-label">Материал</span>
              <span class="spec-val" id="modal-material">-</span>
          </div>
          <div class="spec-row">
              <span class="spec-label">Размеры</span>
              <span class="spec-val" id="modal-sizes">-</span>
          </div>
          <div class="spec-row" style="border:none;">
              <span class="spec-label">Статус</span>
              <span class="spec-val" id="modal-status" style="color:green;">-</span>
          </div>

          <button class="btn" style="margin-top: 20px;" onclick="buyCurrentMerch()">Заказать</button>
          <button class="btn btn-secondary" style="margin-top: 10px;" onclick="closeMerchModal()">Закрыть</button>
      </div>
  </div>

  <script>
    const tg = (window.Telegram && window.Telegram.WebApp) ? window.Telegram.WebApp : null;
    if (tg) tg.expand();

    const userId = new URLSearchParams(window.location.search).get('user_id');
    let currentMerchId = null; // Для хранения ID текущего открытого товара (пока фейковый)

    // --- Утилиты ---
    function uiAlert(msg) {
      if (tg && tg.showPopup) tg.showAlert(msg);
      else alert(msg);
    }
    
    function uiConfirm(msg, callback) {
      if (tg && tg.showPopup) tg.showConfirm(msg, callback);
      else { const r = confirm(msg); callback(r); }
    }

    let myChart = null;

    // --- НАВИГАЦИЯ ---
    function showTab(tabId, el) {
        document.querySelectorAll('.content-section').forEach(s => s.classList.remove('active'));
        document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
        
        document.getElementById(tabId).classList.add('active');
        if (el) el.classList.add('active');

        // Логика загрузки данных
        if(tabId === 'main') updateAllData(); 
        if(tabId === 'exchange') loadServices();
        // Вкладка merch теперь статичная (хардкод), но можно вызвать loadMerch() если нужно из БД
    }

    // --- ДАННЫЕ ПРОФИЛЯ ---
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
      // Баланс
      fetch(`/api/user/${userId}`).then(r => r.json()).then(user => {
        document.getElementById('balance-display').innerText = user.current_points;
      });
      // График
      fetch(`/api/stats/${userId}`).then(r => r.json()).then(stats => renderChart(stats));
      // История (теперь в профиле)
      loadHistory();
      // Лидерборд (теперь в профиле)
      fetch(`/api/leaderboard`).then(r => r.json()).then(list => {
        document.getElementById('leaderboard').innerHTML = list.map((s, i) => 
          `<div style="display:flex; justify-content:space-between; padding: 8px 0; border-bottom: 1px solid rgba(0,0,0,0.05);">
            <span>${i+1}. ${s.first_name}</span><b>${s.current_points}</b>
          </div>`).join('');
      });
    }

    function loadHistory() {
      fetch(`/api/history/${userId}`).then(r => r.json()).then(data => {
        if (!data || data.length === 0) {
            document.getElementById('history-list').innerHTML = '<div style="text-align:center; padding:10px; color:var(--tg-hint)">Истории пока нет</div>';
            return;
        }
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

    // --- МЕРЧ МОДАЛКА ---
    // Открытие
    function openMerchModal(title, price, material, sizes, status, imgUrl) {
        document.getElementById('modal-title').innerText = title;
        document.getElementById('modal-price').innerText = price + ' STC';
        document.getElementById('modal-material').innerText = material;
        document.getElementById('modal-sizes').innerText = sizes;
        document.getElementById('modal-status').innerText = status;
        document.getElementById('modal-img').src = imgUrl;
        
        // В реальном проекте тут должен быть реальный ID из БД. 
        // Пока используем заглушку, чтобы кнопка работала визуально.
        currentMerchId = 'dummy_id'; 
        
        document.getElementById('merch-modal').style.display = 'flex';
    }

    // Закрытие
    function closeMerchModal() {
        document.getElementById('merch-modal').style.display = 'none';
    }

    // Покупка (вызывает API)
    function buyCurrentMerch() {
      uiConfirm("Вы уверены, что хотите заказать этот товар?", (ok) => {
        if(ok) {
          // Здесь мы отправляем ID. Так как карточки тестовые, 
          // сервер может вернуть ошибку "Товар не найден", если в БД нет товара с таким ID.
          // Но логика запроса сохранена.
          fetch('/api/buy_merch', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({user_id: userId, merch_id: currentMerchId})
          }).then(r => r.json()).then(res => {
            uiAlert(res.message);
            closeMerchModal();
            updateAllData(); // Обновить баланс
          });
        }
      });
    }

    // --- БИРЖА УСЛУГ ---
    function loadServices() {
        fetch(`/api/services?user_id=${userId}`).then(r => r.json()).then(data => {
        const list = document.getElementById('services-list');
        if (data.length === 0) {
            list.innerHTML = '<div style="text-align:center; padding:20px; color:var(--tg-hint)">Заданий нет</div>';
            return;
        }

        list.innerHTML = data.map(s => {
            if (s.status === 'completed') return ''; 

            let actionButton = '';
            let statusBadge = '';

            if (s.is_my_task) {
            if (s.status === 'in_progress') {
                statusBadge = '<span style="color:#2481cc;">⚙️ В работе</span>';
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

    function toggleCreateService(force) {
        const card = document.getElementById('create-service-card');
        const show = (typeof force === 'boolean') ? force : (card.style.display === 'none');
        card.style.display = show ? 'block' : 'none';
    }

    function createService() {
        const name = document.getElementById('svc-name').value.trim();
        const price = parseInt(document.getElementById('svc-price').value, 10);
        const desc = document.getElementById('svc-desc').value.trim();
        if (!name || !price || price < 1) return uiAlert('Заполни поля корректно.');

        uiConfirm(`Опубликовать?`, (ok) => {
            if (!ok) return;
            fetch('/api/add_service', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: parseInt(userId, 10), name: name, points_cost: price, description: desc})
            }).then(r => r.json()).then(res => {
                uiAlert(res.message || (res.success ? 'Готово' : 'Ошибка'));
                if (res.success) {
                    toggleCreateService(false);
                    loadServices();
                }
            });
        });
    }

    function takeTask(id) {
        uiConfirm("Взять задание?", (ok) => {
            if(!ok) return;
            fetch('/api/take_task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: userId, service_id: id})
            }).then(r => r.json()).then(res => { uiAlert(res.message); loadServices(); });
        });
    }

    function confirmTask(orderId) {
        uiConfirm("Подтвердить выполнение?", (ok) => {
            if(!ok) return;
            fetch('/api/confirm_task', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({user_id: userId, order_id: orderId})
            }).then(r => r.json()).then(res => { uiAlert(res.message); updateAllData(); loadServices(); });
        });
    }

    // --- FAQ ЛОГИКА ---
    function toggleFaq(el) {
        el.classList.toggle('active');
    }

    // Инициализация при старте
    updateAllData();

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

        success, message = db.add_service(u_id, name, points_cost, description)
        if success:
            send_telegram_notification(u_id, f"✅ Услуга размещена: <b>{name}</b>\nЦена: {points_cost} STC")
        return jsonify({"success": success, "message": message})
    except Exception as e:
        return jsonify({"success": False, "message": "Ошибка сервера"}), 500
  
@app.route('/api/take_task', methods=['POST'])
def api_take_task():
    try:
        data = request.json
        try:
            u_id = int(data.get('user_id'))
        except (ValueError, TypeError):
            return jsonify({"success": False, "message": "Ошибка: user_id должен быть числом"}), 400
            
        success, msg = db.assign_service(data.get('service_id'), u_id)
        return jsonify({"success": success, "message": msg})
    except Exception as e:
        return jsonify({"success": False, "message": f"Ошибка сервера: {str(e)}"}), 500

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