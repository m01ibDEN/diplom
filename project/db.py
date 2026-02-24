import mysql.connector
import os
import uuid
from dotenv import load_dotenv

load_dotenv()

class Database:
    def __init__(self):
        # db.py
        self.host = os.getenv("MYSQL_HOST", "127.0.0.1")
        self.user = os.getenv("MYSQL_USER", "root")
        self.password = os.getenv("MYSQL_PASSWORD", "password") # Теперь он найдет Danila.789
        self.database = os.getenv("MYSQL_DB", "store")


    def _get_connection(self):
        try:
            return mysql.connector.connect(
                host=self.host,
                user=self.user,
                password=self.password,
                database=self.database
            )
        except mysql.connector.Error as err:
            print(f"[DB ERROR] Connection failed: {err}")
            return None

    def _get_student_uuid(self, telegram_id):
        conn = self._get_connection()
        if not conn: return None
        try:
            # Превращаем в int, чтобы убрать возможные пробелы или кавычки
            tg_id_clean = int(telegram_id)
            
            cur = conn.cursor(dictionary=True)
            
            # ВНИМАНИЕ: Проверь, что имя колонки совпадает с твоей таблицей MySQL!
            # В твоем последнем CREATE TABLE это telegram_user_id
            query = "SELECT id FROM students WHERE telegram_user_id = %s"
            
            # ДЛЯ ОТЛАДКИ (будет видно в консоли терминала):
            print(f"DEBUG: Ищу студента с telegram_user_id={tg_id_clean}")
            
            cur.execute(query, (tg_id_clean,))
            res = cur.fetchone()
            
            if res:
                print(f"DEBUG: Нашел UUID: {res['id']}")
                return res['id']
            else:
                print(f"DEBUG: Студент не найден в БД!")
                return None
        except Exception as e:
            print(f"DEBUG ERROR: {e}")
            return None
        finally:
            conn.close()

    def get_student_by_tg_id(self, telegram_id):
        """Получает инфо о студенте + баланс"""
        conn = self._get_connection()
        if not conn: return None
        try:
            cur = conn.cursor(dictionary=True)
            # JOIN таблиц students и balances
            query = """
                SELECT s.id, s.telegram_user_id, s.first_name, s.last_name, 
                       IFNULL(b.current_points, 0) as current_points,
                       IFNULL(b.total_earned, 0) as total_earned,
                       IFNULL(b.total_spent, 0) as total_spent
                FROM students s
                LEFT JOIN balances b ON s.id = b.student_id
                WHERE s.telegram_user_id = %s
            """
            cur.execute(query, (telegram_id,))
            return cur.fetchone()
        finally:
            conn.close()

    def get_or_create_student(self, telegram_id, first_name="", last_name="", username=""):
        """Создает студента, если его нет (для тестов/авторегистрации)"""
        if self.get_student_by_tg_id(telegram_id):
            return True

        conn = self._get_connection()
        if not conn: return False
        try:
            cur = conn.cursor()
            new_uuid = str(uuid.uuid4())
            # Генерируем фейковые уникальные поля, если их нет
            stud_id_code = f"STU-{telegram_id}"
            
            # 1. Создаем студента
            cur.execute("""
                INSERT INTO students (id, telegram_user_id, student_id, first_name, last_name, email)
                VALUES (%s, %s, %s, %s, %s, NULL)
            """, (new_uuid, telegram_id, stud_id_code, first_name, last_name))

            # 2. Создаем баланс
            cur.execute("""
                INSERT INTO balances (student_id, current_points) VALUES (%s, 0)
            """, (new_uuid,))
            
            conn.commit()
            return True
        except Exception as e:
            print(f"[DB CREATE USER ERROR] {e}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def get_user_stats(self, telegram_id):
        uuid_id = self._get_student_uuid(telegram_id)
        if not uuid_id: return []

        conn = self._get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(dictionary=True)
            
            # ИСПРАВЛЕННЫЙ ЗАПРОС:
            # 1. Группируем по DATE(created_at)
            # 2. Сортируем по этой же дате
            cur.execute("""
                SELECT 
                    DATE_FORMAT(created_at, '%d.%m') as date, 
                    SUM(amount) as total
                FROM transactions
                WHERE student_id = %s AND type = 'spend'
                GROUP BY DATE(created_at), DATE_FORMAT(created_at, '%d.%m')
                ORDER BY DATE(created_at) DESC
                LIMIT 7
            """, (uuid_id,))
            
            data = cur.fetchall()
            
            # Превращаем Decimal в float (на всякий случай)
            for row in data:
                if 'total' in row:
                    row['total'] = float(row['total'])
                    
            return list(reversed(data))
        except Exception as e:
            print(f"[DB STATS ERROR] {e}")
            return []
        finally:
            conn.close()


    def get_student_history(self, telegram_id):
        """История операций"""
        uuid_id = self._get_student_uuid(telegram_id)
        if not uuid_id: return []

        conn = self._get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT description, amount, type, DATE_FORMAT(created_at, '%d.%m %H:%i') as created_at
                FROM transactions
                WHERE student_id = %s
                ORDER BY created_at DESC
                LIMIT 20
            """, (uuid_id,))
            return cur.fetchall()
        finally:
            conn.close()

    def get_leaderboard(self):
        """Топ студентов по балансу"""
        conn = self._get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT s.first_name, b.current_points 
                FROM students s
                JOIN balances b ON s.id = b.student_id
                ORDER BY b.current_points DESC
                LIMIT 10
            """)
            return cur.fetchall()
        finally:
            conn.close()

    def get_all_merch(self):
        conn = self._get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("SELECT * FROM merch ORDER BY price_points ASC")
            return cur.fetchall()
        finally:
            conn.close()

    def buy_merch(self, telegram_id, merch_id):
        """Покупка мерча (с транзакцией)"""
        buyer_uuid = self._get_student_uuid(telegram_id)
        if not buyer_uuid: return False, "Пользователь не найден"

        conn = self._get_connection()
        if not conn: return False, "Ошибка БД"
        
        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Проверяем товар
            cur.execute("SELECT name, price_points, stock FROM merch WHERE id = %s", (merch_id,))
            item = cur.fetchone()
            if not item: return False, "Товар не найден"
            if item['stock'] < 1: return False, "Товар закончился"

            # 2. Проверяем баланс
            cur.execute("SELECT current_points FROM balances WHERE student_id = %s", (buyer_uuid,))
            bal = cur.fetchone()
            if not bal or bal['current_points'] < item['price_points']:
                return False, "Недостаточно средств"

            cost = item['price_points']

            # --- ТРАНЗАКЦИЯ ---
            # Списываем деньги
            cur.execute("UPDATE balances SET current_points = current_points - %s, total_spent = total_spent + %s WHERE student_id = %s", (cost, cost, buyer_uuid))
            
            # Уменьшаем сток
            cur.execute("UPDATE merch SET stock = stock - 1 WHERE id = %s", (merch_id,))
            
            # Создаем заказ
            order_id = str(uuid.uuid4())
            cur.execute("INSERT INTO merch_orders (id, merch_id, buyer_id, quantity, status) VALUES (%s, %s, %s, 1, 'completed')", (order_id, merch_id, buyer_uuid))
            
            # Записываем в историю
            trans_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id)
                VALUES (%s, %s, 'spend', %s, %s, 'merch', %s)
            """, (trans_id, buyer_uuid, cost, f"Покупка: {item['name']}", merch_id))

            conn.commit()
            return True, f"Вы купили {item['name']}"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    # ==========================
    # БЛОК УСЛУГ (БИРЖА)
    # ==========================
    def add_service(self, tg_id, name, points, desc, max_orders=None):
        """Создание услуги с лимитом заказов"""
        provider_uuid = self._get_student_uuid(tg_id)
        if not provider_uuid: return False, "Студент не найден"
        
        conn = self._get_connection()
        if not conn: return False, "Нет связи с БД"
        try:
            cur = conn.cursor()
            svc_id = str(uuid.uuid4())
            
            # Гибридный подход: если max_orders=None, значит неограниченно
            cur.execute("""
                INSERT INTO services 
                (id, provider_id, name, points_cost, description, active, max_orders, orders_completed) 
                VALUES (%s, %s, %s, %s, %s, 1, %s, 0)
            """, (svc_id, provider_uuid, name, points, desc, max_orders))
            
            conn.commit()
            return True, "Услуга опубликована"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def get_all_services(self, current_user_tg_id):
        user_uuid = self._get_student_uuid(current_user_tg_id)
        if not user_uuid: return []

        conn = self._get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(dictionary=True)
            
            # 🔥 Логика: мои закрытые услуги + общие активные
            query = """
            SELECT 
                s.id, s.name, s.description, s.points_cost, s.provider_id,
                s.max_orders, s.orders_completed, s.active,
                st.first_name as provider_name,
                ord.id as order_id, ord.buyer_id as executor_id, ord.status as order_status
            FROM services s
            JOIN students st ON s.provider_id = st.id
            LEFT JOIN service_orders ord ON s.id = ord.service_id 
                AND ord.status IN ('pending', 'in_progress')
            WHERE 
                -- Общие активные услуги
                (s.active = 1) 
                OR 
                -- Мои закрытые услуги
                (s.provider_id = %s)
            ORDER BY s.created_at DESC
            """
            cur.execute(query, (user_uuid,))
            rows = cur.fetchall()
            
            result = []
            for row in rows:
                status = 'open'  # По умолчанию
                
                # 🔥 ЛОГИКА СТАТУСОВ:
                if row['order_status'] == 'in_progress':
                    status = 'in_progress'  # Только реально активный заказ
                elif row['order_status'] == 'pending':
                    status = 'pending'

                # Вычисляем оставшиеся заказы
                remaining_orders = "Неограниченно"
                if row['max_orders'] is not None:
                    remaining_orders = row['max_orders'] - row['orders_completed']
                    if remaining_orders <= 0:
                        remaining_orders = "Закончилось"

                service_info = {
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'points_cost': row['points_cost'],
                    'provider_name': row['provider_name'],
                    'is_my_task': (str(row['provider_id']) == str(user_uuid)),
                    'am_i_executor': (str(row['executor_id']) == str(user_uuid)) if row['executor_id'] else False,
                    'status': status,
                    'order_id': row['order_id'],
                    'remaining_orders': remaining_orders,
                    'max_orders': row['max_orders'],
                    'orders_completed': row['orders_completed']
                }
                result.append(service_info)
                
            return result
        finally:
            conn.close()
    def complete_service_order(self, order_id, customer_tg_id):
        """Подтверждение с ПОЛНЫМ commit всех изменений"""
        if not order_id: return False, "Не передан ID заказа"
        
        customer_uuid = self._get_student_uuid(customer_tg_id)
        if not customer_uuid: return False, "Клиент не найден"
        
        conn = self._get_connection()
        if not conn: return False, "Ошибка БД"
        
        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Получаем данные заказа
            query = """
            SELECT ord.id, ord.buyer_id, ord.status, 
                s.id as service_id, s.points_cost, s.provider_id, s.name as service_name
            FROM service_orders ord
            JOIN services s ON ord.service_id = s.id
            WHERE ord.id = %s
            """
            cur.execute(query, (order_id,))
            order = cur.fetchone()
            
            print(f"[DEBUG] Заказ: {order}")
            
            if not order: return False, "Заказ не найден"
            if order['status'] == 'completed': return False, "Уже оплачено"
            
            cost = order['points_cost']
            executor_uuid = order['buyer_id']  # Исполнитель
            
            print(f"[DEBUG] Клиент: {customer_uuid}, Исполнитель: {executor_uuid}, Сумма: {cost}")
            
            # 2. Проверяем баланс КЛИЕНТА
            cur.execute("SELECT current_points FROM balances WHERE student_id = %s", (customer_uuid,))
            customer_bal = cur.fetchone()
            if not customer_bal or customer_bal['current_points'] < cost:
                return False, f"Недостаточно средств ({customer_bal['current_points']} < {cost})"

            # 3. Проверяем баланс ИСПОЛНИТЕЛЯ (существует ли)
            cur.execute("SELECT current_points FROM balances WHERE student_id = %s", (executor_uuid,))
            executor_bal = cur.fetchone()
            if not executor_bal:
                return False, "Баланс исполнителя не найден"

            print(f"[DEBUG] Баланс клиента ДО: {customer_bal['current_points']}, Исполнителя ДО: {executor_bal['current_points']}")

            # 🔥 4. НАЧИНАЕМ ТРАНЗАКЦИЮ (явная)
            cur.execute("START TRANSACTION")
            
            # Обновляем статус заказа
            cur.execute("UPDATE service_orders SET status = 'completed' WHERE id = %s", (order_id,))
            
            # Списываем у клиента
            cur.execute("""
                UPDATE balances SET current_points = current_points - %s, total_spent = total_spent + %s 
                WHERE student_id = %s
            """, (cost, cost, customer_uuid))
            
            # Начисляем исполнителю
            cur.execute("""
                UPDATE balances SET current_points = current_points + %s, total_earned = total_earned + %s
                WHERE student_id = %s
            """, (cost, cost, executor_uuid))
            
            # История
            cur.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id)
                VALUES (%s, %s, 'spend', %s, %s, 'service', %s)
            """, (str(uuid.uuid4()), customer_uuid, cost, f"Оплата услуги: {order['service_name']}", order_id))
            
            cur.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id)
                VALUES (%s, %s, 'earn', %s, %s, 'service', %s)
            """, (str(uuid.uuid4()), executor_uuid, cost, f"Выполнение услуги: {order['service_name']}", order_id))
            
            # ЯВНЫЙ COMMIT
            conn.commit()
            print(f"[SUCCESS] ✅ Все изменения сохранены!")
            
            return True, f"Оплата прошла! +{cost} STC исполнителю"
            
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Откат изменений: {e}")
            return False, f"Ошибка: {str(e)}"
        finally:
            conn.close()
    def assign_service(self, service_id, executor_tg_id):
        executor_uuid = self._get_student_uuid(executor_tg_id)
        if not executor_uuid: return False, "Пользователь не найден"

        conn = self._get_connection()
        if not conn: return False, "Ошибка БД"
        try:
            cur = conn.cursor(dictionary=True)
            
            # Задача свободна?
            cur.execute("""
                SELECT id FROM service_orders 
                WHERE service_id = %s AND status IN ('pending', 'in_progress')
            """, (service_id,))
            if cur.fetchone():
                return False, "Задание уже занято"

            # Не автор ли это?
            cur.execute("SELECT provider_id FROM services WHERE id = %s", (service_id,))
            svc = cur.fetchone()
            if not svc: return False, "Услуга не найдена"
            if str(svc['provider_id']) == str(executor_uuid):
                return False, "Нельзя выполнять свои задания"

            # Создаем заказ
            order_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO service_orders (id, service_id, buyer_id, status)
                VALUES (%s, %s, %s, 'in_progress')
            """, (order_id, service_id, executor_uuid))

            cur.execute("UPDATE services SET active = 0 WHERE id = %s", (service_id,))
            
            conn.commit()
            return True, "Вы взяли задание в работу!"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def get_student_by_tg_id(self, telegram_id):
        # ОБНОВЛЕННЫЙ МЕТОД: теперь возвращает role
        conn = self._get_connection()
        if not conn: return None
        try:
            cur = conn.cursor(dictionary=True)
            query = """
                SELECT s.id, s.telegram_user_id, s.first_name, s.last_name, s.role,
                       IFNULL(b.current_points, 0) as current_points,
                       IFNULL(b.total_earned, 0) as total_earned,
                       IFNULL(b.total_spent, 0) as total_spent
                FROM students s
                LEFT JOIN balances b ON s.id = b.student_id
                WHERE s.telegram_user_id = %s
            """
            cur.execute(query, (telegram_id,))
            return cur.fetchone()
        finally:
            conn.close()

    def get_admin_stats(self):
        """Статистика для админки"""
        conn = self._get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            stats = {}
            # Всего пользователей
            cur.execute("SELECT COUNT(*) as cnt FROM students")
            stats['users_count'] = cur.fetchone()['cnt']
            # Всего денег в системе
            cur.execute("SELECT SUM(current_points) as total FROM balances")
            stats['money_in_system'] = cur.fetchone()['total'] or 0
            # Последние 10 транзакций
            cur.execute("""
                SELECT t.amount, t.type, t.description, s.last_name 
                FROM transactions t
                JOIN students s ON t.student_id = s.id
                ORDER BY t.created_at DESC LIMIT 10
            """)
            stats['last_transactions'] = cur.fetchall()
            return stats
        finally:
            conn.close()

    # --- МЕРОПРИЯТИЯ (Студсовет) ---

    def create_activity(self, title, points, description, date_str):
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            act_id = str(uuid.uuid4())
            # Предполагаем, что date_str это строка YYYY-MM-DD
            cur.execute("""
                INSERT INTO activities (id, title, points, category, start_date, status)
                VALUES (%s, %s, %s, 'event', %s, 'active')
            """, (act_id, title, points, date_str))
            conn.commit()
            return True, "Мероприятие создано"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    def get_active_activities(self):
        conn = self._get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            # Берем только активные
            cur.execute("""
                SELECT id, title, points, DATE_FORMAT(start_date, '%d.%m.%Y') as date 
                FROM activities WHERE status = 'active' ORDER BY start_date
            """)
            return cur.fetchall()
        finally:
            conn.close()

    # --- МЕРЧ (Студсовет) ---
    
    def add_new_merch(self, name, description, price, stock):
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            m_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO merch (id, name, description, price_points, stock)
                VALUES (%s, %s, %s, %s, %s)
            """, (m_id, name, description, price, stock))
            conn.commit()
            return True, "Товар добавлен"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()
    def add_new_merch(self, name, description, price, stock, image_url=""):
        conn = self._get_connection()
        try:
            cur = conn.cursor()
            m_id = str(uuid.uuid4())
            # Добавили image_url в INSERT
            cur.execute("""
                INSERT INTO merch (id, name, description, price_points, stock, image_url)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (m_id, name, description, price, stock, image_url))
            conn.commit()
            return True, "Товар добавлен"
        except Exception as e:
            return False, str(e)
        finally:
            conn.close()

    def create_merch_order(self, tg_id, merch_id):
        conn = self._get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            # 1. Получаем студента и мерч
            cur.execute("SELECT id FROM students WHERE telegram_user_id = %s", (tg_id,))
            student = cur.fetchone()
            if not student: return False, "Студент не найден"

            cur.execute("SELECT price_points, stock, name FROM merch WHERE id = %s", (merch_id,))
            item = cur.fetchone()
            if not item: return False, "Товар не найден"
            if item['stock'] < 1: return False, "Товар закончился"

            # 2. Проверяем баланс
            cur.execute("SELECT current_points FROM balances WHERE student_id = %s", (student['id'],))
            balance = cur.fetchone()['current_points']
            if balance < item['price_points']: return False, "Недостаточно средств"

            # 3. Создаем заказ (статус pending)
            # ВАЖНО: Сразу списываем баллы и резервируем товар, чтобы не ушли в минус
            # Если откажут — вернем баллы.
            cur.execute("UPDATE balances SET current_points = current_points - %s WHERE student_id = %s", (item['price_points'], student['id']))
            cur.execute("UPDATE merch SET stock = stock - 1 WHERE id = %s", (merch_id,))
            
            order_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO merch_orders (id, merch_id, buyer_id, quantity, status)
                VALUES (%s, %s, %s, 1, 'pending')
            """, (order_id, merch_id, student['id']))
            
            conn.commit()
            return True, "Заявка создана! Ждите одобрения."
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def get_pending_orders(self):
        conn = self._get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT mo.id, m.name as merch_name, s.first_name, s.last_name, mo.created_at
                FROM merch_orders mo
                JOIN merch m ON mo.merch_id = m.id
                JOIN students s ON mo.buyer_id = s.id
                WHERE mo.status = 'pending'
                ORDER BY mo.created_at DESC
            """)
            return cur.fetchall()
        finally:
            conn.close()

    def process_merch_order(self, order_id, action, secret_code=None):
        conn = self._get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            
            if action == 'approve':
                cur.execute("UPDATE merch_orders SET status = 'approved', secret_code = %s WHERE id = %s", (secret_code, order_id))
                msg = "Заказ одобрен"
            else:
                # Возврат средств и товара
                cur.execute("SELECT merch_id, buyer_id FROM merch_orders WHERE id = %s", (order_id,))
                order = cur.fetchone()
                
                cur.execute("SELECT price_points FROM merch WHERE id = %s", (order['merch_id'],))
                price = cur.fetchone()['price_points']
                
                cur.execute("UPDATE balances SET current_points = current_points + %s WHERE student_id = %s", (price, order['buyer_id']))
                cur.execute("UPDATE merch SET stock = stock + 1 WHERE id = %s", (order['merch_id'],))
                cur.execute("UPDATE merch_orders SET status = 'rejected' WHERE id = %s", (order_id,))
                msg = "Заказ отклонен, средства возвращены"
            
            conn.commit()
            return True, msg
        finally:
            conn.close()

    def get_student_merch_orders(self, tg_id):
        conn = self._get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            cur.execute("""
                SELECT mo.id, m.name, mo.status, mo.secret_code, m.image_url
                FROM merch_orders mo
                JOIN merch m ON mo.merch_id = m.id
                JOIN students s ON mo.buyer_id = s.id
                WHERE s.telegram_user_id = %s
                ORDER BY mo.created_at DESC
            """, (tg_id,))
            return cur.fetchall()
        finally:
            conn.close()

    def get_pending_merch_orders(self):
        conn = self._get_connection()
        try:
            cur = conn.cursor(dictionary=True)
            # Запрос получает заявки со статусом 'pending'
            # + имя покупателя и название товара
            cur.execute("""
                SELECT mo.id, m.name as merch_name, s.first_name, s.last_name, mo.created_at
                FROM merch_orders mo
                JOIN merch m ON mo.merch_id = m.id
                JOIN students s ON mo.buyer_id = s.id
                WHERE mo.status = 'pending'
                ORDER BY mo.created_at DESC
            """)
            return cur.fetchall()
        except Exception as e:
            print(f"Error getting pending orders: {e}")
            return []
        finally:
            conn.close()

    def add_points(self, user_db_uuid, amount, description="Транзакция SDK"):
        conn = self._get_connection()
        if not conn: return False, "DB Connection Failed"
        
        try:
            cur = conn.cursor()
            
            print(f"[DB] Обновляем баланс пользователя UUID={user_db_uuid} на {amount}")
            
            # 1. Обновляем таблицу balances (MySQL синтаксис: %s)
            cur.execute(
                "UPDATE balances SET current_points = current_points + %s WHERE student_id = %s", 
                (amount, user_db_uuid)
            )
            
            # 2. Обновляем total_spent или total_earned
            if amount < 0:
                cur.execute(
                    "UPDATE balances SET total_spent = total_spent + %s WHERE student_id = %s", 
                    (abs(amount), user_db_uuid)
                )
            else:
                 cur.execute(
                    "UPDATE balances SET total_earned = total_earned + %s WHERE student_id = %s", 
                    (amount, user_db_uuid)
                )

            # 3. Записываем в transactions (используем UUID для ID транзакции)
            trans_id = str(uuid.uuid4())
            t_type = 'spend' if amount < 0 else 'earn'
            # Используем abs(amount), так как в базе обычно хранят положительное число в amount + тип
            
            cur.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id)
                VALUES (%s, %s, %s, %s, %s, 'sdk', NULL)
            """, (trans_id, user_db_uuid, t_type, abs(amount), description))

            conn.commit()
            
            return True, "Баланс обновлен"
            
        except Exception as e:
            print(f"[DB Error] add_points: {e}")
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def validate_api_key(self, api_key):
        """Проверяет наличие и активность API ключа"""
        conn = self._get_connection()
        if not conn: return None
        try:
            cur = conn.cursor(dictionary=True)
            # Ищем активный ключ
            query = "SELECT service_name FROM api_services WHERE api_key = %s AND is_active = 1"
            cur.execute(query, (api_key,))
            result = cur.fetchone()
            
            if result:
                return result['service_name'] # Возвращаем имя сервиса (например, 'Biblioteka')
            return None
        except Exception as e:
            print(f"[DB API CHECK ERROR] {e}")
            return None
        finally:
            conn.close()

    def register_student_by_card(self, telegram_id, card_number, first_name, last_name):
        conn = self._get_connection()
        if not conn: return False, "Ошибка подключения к БД"
        
        try:
            cur = conn.cursor(dictionary=True)
            
            cur.execute("SELECT id, telegram_user_id FROM students WHERE student_id = %s", (card_number,))
            existing = cur.fetchone()
            
            if existing:
                if existing['telegram_user_id']:
                    return False, "Этот номер студенческого уже привязан к другому Telegram аккаунту!"
                else:
                    # Сценарий "Предзагрузка": Админ загрузил номера, но без Телеграма.
                    # Мы обновляем запись, привязывая Телеграм.
                    cur.execute("""
                        UPDATE students 
                        SET telegram_user_id = %s, first_name = %s, last_name = %s 
                        WHERE student_id = %s
                    """, (telegram_id, first_name, last_name, card_number))
                    
                    # Создаем баланс, если нет
                    cur.execute("INSERT IGNORE INTO balances (student_id, current_points) VALUES (%s, 0)", (existing['id'],))
                    conn.commit()
                    return True, "Успешно привязано"

            # 2. Сценарий "Свободная регистрация" (если белого списка нет)
            # Создаем нового студента с нуля
            new_uuid = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO students (id, telegram_user_id, student_id_number, first_name, last_name)
                VALUES (%s, %s, %s, %s, %s)
            """, (new_uuid, telegram_id, card_number, first_name, last_name))
            
            cur.execute("INSERT INTO balances (student_id, current_points) VALUES (%s, 0)", (new_uuid,))
            
            conn.commit()
            return True, "Новый профиль создан"
            
        except Exception as e:
            conn.rollback()
            # Ловим дубликаты (если telegram_id уже есть)
            if "Duplicate entry" in str(e):
                return False, "Вы уже зарегистрированы."
            return False, str(e)
        finally:
            conn.close()



# Создаем единственный экземпляр
db = Database()
