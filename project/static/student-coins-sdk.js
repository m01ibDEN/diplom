(function(window) {
    class StudentCoinsSDK {
        constructor() {
            this.baseUrl = ""; 
            this.apiKey = null;
            this.userId = null;
        }

        init(apiKey, backendUrl) {
            this.apiKey = apiKey;
            // Убираем слеш в конце URL если есть
            this.baseUrl = backendUrl ? backendUrl.replace(/\/$/, "") : "";
            console.log("SDK initialized with:", this.baseUrl);
        }

        setUser(tgId) {
            this.userId = tgId;
        }

        async _request(endpoint, method = 'GET', body = null) {
            if (!this.apiKey) throw new Error("SDK not initialized. Call init() first.");
            if (!this.baseUrl) throw new Error("Base URL is missing. Pass it to init().");
            
            const headers = {
                'Content-Type': 'application/json',
                'X-API-Key': this.apiKey,
                'ngrok-skip-browser-warning': 'true' 
            };

            const options = { method, headers };
            if (body) options.body = JSON.stringify(body);

            try {
                const res = await fetch(`${this.baseUrl}${endpoint}`, options);
                if (!res.ok) {
                    const errorText = await res.text();
                    throw new Error(`Server error: ${res.status} ${errorText}`);
                }
                return await res.json();
            } catch (err) {
                console.error("SDK Request Error:", err);
                throw err;
            }
        }

        async getBalance() {
            if (!this.userId) throw new Error("User not set");
            return await this._request(`/api/sdk/balance?user_id=${this.userId}`);
        }

        async pay(amount, description) {
            if (!this.userId) throw new Error("User not set");
            return await this._request('/api/sdk/transaction', 'POST', {
                user_id: this.userId,
                amount: amount,
                type: 'spend',
                description: description
            });
        }
        
        /**
         * Создать кнопку оплаты с колбэком
         * @param {string} containerId - ID элемента, куда вставить кнопку
         * @param {number} amount - Сумма
         * @param {string} desc - Описание
         * @param {function} onSuccess - Функция, которая сработает после успеха (получит новый баланс)
         */
        createPayButton(containerId, amount, desc, onSuccess) {
            const container = document.getElementById(containerId);
            if (!container) return;

            const btn = document.createElement('button');
            btn.innerText = `Оплатить ${amount} STC`;
            btn.style.cssText = "background:#2481cc; color:white; padding:10px 20px; border:none; border-radius:8px; cursor:pointer; font-weight:bold; margin-top:10px;";
            
            btn.onclick = async () => {
                if (!this.userId) { alert("Сначала авторизуйтесь!"); return; }
                
                try {
                    btn.disabled = true;
                    btn.innerText = "Обработка...";
                    
                    const res = await this.pay(amount, desc);
                    
                    if(res.success) {
                        alert("Оплата успешна! ✅");
                        btn.innerText = "Оплачено";
                        btn.style.background = "#28a745";
                        
                        // 🔥 ВОТ ГЛАВНОЕ ИЗМЕНЕНИЕ 🔥
                        // Если передали функцию onSuccess, вызываем её с новым балансом
                        if (onSuccess && typeof onSuccess === 'function') {
                            onSuccess(res.new_balance);
                        }
                    } else {
                        alert("Ошибка: " + (res.message || "Неизвестная ошибка"));
                        btn.disabled = false;
                        btn.innerText = `Оплатить ${amount} STC`;
                    }
                } catch (e) {
                    alert("Ошибка сети");
                    btn.disabled = false;
                    btn.innerText = `Оплатить ${amount} STC`;
                }
            };
            
            container.appendChild(btn);
        }

    }

    // Экспортируем экземпляр класса
    window.StudentCoins = new StudentCoinsSDK();

})(window);
