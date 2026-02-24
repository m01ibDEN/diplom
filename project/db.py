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
            
            # 🔥 ФИКС SQL: Добавили provider_ord для Заказчика!
            query = """
            SELECT 
                s.id, s.name, s.description, s.points_cost, s.provider_id,
                s.max_orders, s.orders_completed, s.active, s.status as base_status,
                st.first_name as provider_name,
                my_ord.id as my_order_id, my_ord.status as my_order_status,
                provider_ord.id as provider_order_id, provider_ord.status as provider_order_status
            FROM services s
            JOIN students st ON s.provider_id = st.id
            
            -- 1. Джоиним МОЙ заказ (если я Исполнитель)
            LEFT JOIN service_orders my_ord 
                ON s.id = my_ord.service_id 
                AND my_ord.buyer_id = %s 
                AND my_ord.status IN ('pending', 'in_progress')
                
            -- 2. Джоиним АКТИВНЫЙ ЗАКАЗ на эту услугу (если я Заказчик/Провайдер)
            LEFT JOIN service_orders provider_ord
                ON s.id = provider_ord.service_id
                AND s.provider_id = %s
                AND provider_ord.status IN ('pending', 'in_progress')
                
            WHERE 
                (s.active = 1) OR (s.provider_id = %s)
            ORDER BY s.created_at DESC
            """
            # Передаем user_uuid три раза (1 - для my_ord, 2 - для provider_ord, 3 - для WHERE)
            cur.execute(query, (user_uuid, user_uuid, user_uuid))
            rows = cur.fetchall()
            
            result = []
            for row in rows:
                status = row['base_status'] or 'open'
                
                # 🔥 Логика статусов 2.0
                is_my_task = (str(row['provider_id']) == str(user_uuid))
                order_id_to_return = None
                
                if is_my_task:
                    # Если я Заказчик, и кто-то взял таску в работу — показываем статус заказа
                    if row['provider_order_status']:
                        status = row['provider_order_status']
                        order_id_to_return = row['provider_order_id']
                else:
                    # Если я Исполнитель, показываем статус МОЕГО заказа
                    if row['my_order_status']:
                        status = row['my_order_status']
                        order_id_to_return = row['my_order_id']


                remaining_orders = -1 
                if row['max_orders'] is not None:
                    remaining_orders = max(0, row['max_orders'] - row['orders_completed'])

                service_info = {
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'points_cost': row['points_cost'],
                    'provider_name': row['provider_name'],
                    'is_my_task': is_my_task,
                    'am_i_executor': bool(row['my_order_id']),
                    'status': status,
                    'order_id': order_id_to_return, # 🔥 Важно! Отдаем ID заказа Заказчику, чтобы он мог его принять
                    'remaining_orders': remaining_orders,
                    'max_orders': row['max_orders'],
                    'orders_completed': row['orders_completed'],
                    'is_active': bool(row['active'])
                }
                result.append(service_info)
                
            return result
        finally:
            conn.close()

    def take_service_order(self, service_id, executor_tg_id):
        """Исполнитель берет задачу в работу (статус: in_progress)"""
        executor_uuid = self._get_student_uuid(executor_tg_id)
        if not executor_uuid: return False, "Исполнитель не найден"

        conn = self._get_connection()
        if not conn: return False, "Ошибка БД"

        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Проверяем услугу (существует ли и активна ли)
            cur.execute("SELECT * FROM services WHERE id = %s AND active = 1", (service_id,))
            service = cur.fetchone()
            
            if not service: 
                return False, "Услуга не найдена или уже неактивна"
                
            if str(service['provider_id']) == str(executor_uuid):
                return False, "Бро, нельзя взять свою же таску!"

            # 2. Проверяем лимиты заказов (если max_orders задан)
            if service['max_orders'] is not None:
                if service['orders_completed'] >= service['max_orders']:
                    return False, "Упс, лимит заказов на эту услугу исчерпан"

            # 3. Проверяем, не взял ли этот чел её УЖЕ в работу
            cur.execute("""
                SELECT id FROM service_orders 
                WHERE service_id = %s AND buyer_id = %s AND status IN ('pending', 'in_progress')
            """, (service_id, executor_uuid))
            
            if cur.fetchone():
                return False, "Ты уже взял эту задачу, иди делай!"

            # 4. СОЗДАЁМ ЗАКАЗ СО СТАТУСОМ in_progress
            import uuid
            order_id = str(uuid.uuid4())
            
            # Начинаем транзакцию
            cur.execute("START TRANSACTION")
            
            cur.execute("""
                INSERT INTO service_orders (id, service_id, buyer_id, status)
                VALUES (%s, %s, %s, 'in_progress')
            """, (order_id, service_id, executor_uuid))
            
            conn.commit()
            return True, "Задача взята в работу! Жди, пока заказчик примет."
            
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Ошибка взятия задачи: {e}")
            return False, "Внутренняя ошибка сервера"
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

            # НАЧИНАЕМ ТРАНЗАКЦИЮ (явная)
            cur.execute("START TRANSACTION")
            
            # Обновляем статус заказа
            cur.execute("UPDATE service_orders SET status = 'completed' WHERE id = %s", (order_id,))

            # 🔥 ЗАКРЫВАЕМ УСЛУГУ (Мягкое удаление)
            # Увеличиваем счетчик выполненных заказов
            cur.execute("UPDATE services SET orders_completed = orders_completed + 1 WHERE id = %s", (order['service_id'],))

            # Если у услуги лимит заказов 1 (разовая таска), или лимит исчерпан — гасим её
            cur.execute("""
                UPDATE services 
                SET active = 0, status = 'completed' 
                WHERE id = %s AND (max_orders IS NULL OR orders_completed >= max_orders)
            """, (order['service_id'],))
            
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

    def place_bid(self, auction_id, student_tg_id, bid_amount):
        """Студент делает ставку на аукционе"""
        student_uuid = self._get_student_uuid(student_tg_id)
        if not student_uuid: return False, "Кто ты, воин? Юзер не найден."

        conn = self._get_connection()
        if not conn: return False, "БД прилегла отдохнуть."

        try:
            cur = conn.cursor(dictionary=True)

            cur.execute("SELECT id, role FROM students WHERE telegram_user_id = %s", (student_tg_id,))
            user = cur.fetchone()
            
            if not user: return False, "Юзер не найден."
            
            # БАН СТУДСОВЕТУ И АДМИНАМ
            if user['role'] in ('stud_council', 'admin'):
                return False, "Эй, организаторам торгов запрещено делать ставки на свои же лоты! 🛑"
                
            student_uuid = user['id']

            # 2. Проверяем аукцион (что он открыт, время не вышло и т.д.)
            cur.execute("SELECT * FROM auctions WHERE id = %s", (auction_id,))
            auction = cur.fetchone()
            
            # 1. Достаем инфу по аукциону
            cur.execute("SELECT * FROM auctions WHERE id = %s", (auction_id,))
            auction = cur.fetchone()
            
            if not auction:
                return False, "Аукцион испарился."
            if auction['status'] != 'open':
                return False, "Поезд ушёл, аукцион уже закрыт"
                
            # 2. Проверяем время (не истекло ли)
            from datetime import datetime
            if auction['end_time'] < datetime.now():
                return False, "Время вышло! Ставки больше не принимаются."

            # 3. Чекаем минимальную ставку
            min_required_bid = auction['current_bid'] + 10 if auction['current_bid'] > 0 else auction['start_price']
            if bid_amount < min_required_bid:
                return False, f"Маловато будет! Минимальная ставка сейчас: {min_required_bid} STC."

            # 4. 🔥 ЧЕКАЕМ БАЛАНС И ВЕЖЛИВО ШЛЁМ НАХУЙ 🔥
            cur.execute("SELECT current_points FROM balances WHERE student_id = %s", (student_uuid,))
            balance = cur.fetchone()
            
            if not balance or balance['current_points'] < bid_amount:
                return False, f"Сорян, бро, твои финансы поют романсы. Хочешь поставить {bid_amount} STC, а в кармане только {balance['current_points'] if balance else 0}. Иди фарми коины на тасках!"

            # 5. Делаем дела: пишем ставку и апдейтим аукцион
            import uuid
            bid_id = str(uuid.uuid4())
            
            cur.execute("START TRANSACTION")
            
            # Записываем ставку в историю
            cur.execute("""
                INSERT INTO bids (id, auction_id, bidder_id, amount)
                VALUES (%s, %s, %s, %s)
            """, (bid_id, auction_id, student_uuid, bid_amount))
            
            # Обновляем текущую максимальную ставку в аукционе
            cur.execute("""
                UPDATE auctions SET current_bid = %s WHERE id = %s
            """, (bid_amount, auction_id))
            
            conn.commit()
            return True, "Ставка принята! Ты пока что батя этого лота 😎"

        except Exception as e:
            conn.rollback()
            return False, f"Внутренняя ошибка: {e}"
        finally:
            conn.close()

    def get_auction_details(self, auction_id):
        """Отдает инфу о лоте и хистори ставок"""
        conn = self._get_connection()
        cur = conn.cursor(dictionary=True)
        
        # Достаем сам лот с картинкой и описанием из таблицы merch
        cur.execute("""
            SELECT a.id, a.start_price, a.current_bid, a.end_time, a.status,
                m.name, m.description, m.image_url
            FROM auctions a
            JOIN merch m ON a.merch_id = m.id
            WHERE a.id = %s
        """, (auction_id,))
        auction = cur.fetchone()
        
        if not auction: return None
        
        # Вытаскиваем историю ставок (кто ставил)
        cur.execute("""
            SELECT b.amount, b.created_at, s.first_name, s.last_name
            FROM bids b
            JOIN students s ON b.bidder_id = s.id
            WHERE b.auction_id = %s
            ORDER BY b.amount DESC
        """, (auction_id,))
        
        auction['bids_history'] = cur.fetchall()
        conn.close()
        return auction
    
    def process_finished_auctions(self):
        """Фоновый воркер: закрывает истекшие аукционы и списывает коины"""
        conn = self._get_connection()
        if not conn: return
        
        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Ищем все открытые аукционы, у которых время вышло
            cur.execute("""
                SELECT id, title, current_bid 
                FROM auctions 
                WHERE status = 'open' AND end_time <= NOW()
            """)
            finished_auctions = cur.fetchall()
            
            if not finished_auctions:
                return  # Если никто не закончился, просто выходим
                
            import uuid
            
            for auction in finished_auctions:
                auction_id = auction['id']
                lot_title = auction['title']
                final_price = auction['current_bid']
                
                # Начинаем транзакцию для каждого отдельного аукциона
                cur.execute("START TRANSACTION")
                
                # 2. Ищем, кто поставил финальную (максимальную) ставку первым
                cur.execute("""
                    SELECT bidder_id 
                    FROM bids 
                    WHERE auction_id = %s AND amount = %s
                    ORDER BY created_at ASC 
                    LIMIT 1
                """, (auction_id, final_price))
                
                winner = cur.fetchone()
                
                if winner:
                    winner_id = winner['bidder_id']
                    
                    # 3. Чекаем баланс победителя (хватит ли ему сейчас денег)
                    cur.execute("SELECT current_points FROM balances WHERE student_id = %s", (winner_id,))
                    bal = cur.fetchone()
                    
                    if bal and bal['current_points'] >= final_price:
                        # Бабки есть! Списываем коины за победу в лоте
                        cur.execute("""
                            UPDATE balances 
                            SET current_points = current_points - %s, total_spent = total_spent + %s 
                            WHERE student_id = %s
                        """, (final_price, final_price, winner_id))
                        
                        # Пишем красивую запись в историю транзакций
                        tx_id = str(uuid.uuid4())
                        cur.execute("""
                            INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id)
                            VALUES (%s, %s, 'spend', %s, %s, 'auction', %s)
                        """, (tx_id, winner_id, final_price, f"Победа в аукционе: {lot_title}", auction_id))
                        
                        import string
                        import random
                        secret_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                        
                        cur.execute("""
                            UPDATE auctions 
                            SET status = 'completed', winner_id = %s, secret_code = %s
                            WHERE id = %s
                        """, (winner_id, secret_code, auction_id))
                        
                        print(f"[AUCTION BOT] Ура! Лот '{lot_title}' продан. Код победителя: {secret_code}")
                    
                    else:
                        # ⚠️ Студент перебил ставку, а потом потратил все коины на шавуху. 
                        # Лочим аукцион со статусом failed.
                        cur.execute("UPDATE auctions SET status = 'failed' WHERE id = %s", (auction_id,))
                        print(f"[AUCTION BOT] Фейл. Лот '{lot_title}' сорвался: победитель оказался бомжом.")
                else:
                    # На лот не поставили вообще ни одной ставки
                    cur.execute("UPDATE auctions SET status = 'no_bids' WHERE id = %s", (auction_id,))
                    print(f"[AUCTION BOT] Лот '{lot_title}' закрыт: никто не сделал ставок.")

                # Коммитим транзакцию конкретного аукциона
                conn.commit()
        
                
        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Ошибка в планировщике аукционов: {e}")
        finally:
            conn.close()

    def delete_auction(self, tg_user_id, auction_id):
        """Студсовет удаляет ошибочный лот (если на него еще нет ставок)"""
        conn = self._get_connection()
        if not conn: return False, "БД прилегла."

        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Защита от хакеров: проверяем роль
            cur.execute("SELECT role FROM students WHERE telegram_user_id = %s", (tg_user_id,))
            user = cur.fetchone()
            
            if not user or user['role'] not in ('stud_council', 'admin'):
                return False, "Удалять лоты могут только модераторы! 🛑"

            # 2. Ищем аукцион и чекаем его статус и ставки
            cur.execute("SELECT current_bid, status FROM auctions WHERE id = %s", (auction_id,))
            auction = cur.fetchone()
            
            if not auction:
                return False, "Такого аукциона не существует."
                
            if auction['status'] != 'open':
                return False, "Аукцион уже завершен или отменен. Удалить нельзя."
                
            # 3. 🔥 ЗАЩИТА СТАВОК 🔥
            if auction['current_bid'] > 0:
                return False, "Слишком поздно! На этот лот уже пошли ставки. Удаление запрещено 💸"

            # 4. Сносим лот из базы (поскольку ставок нет, ничьи деньги не пострадают)
            cur.execute("DELETE FROM auctions WHERE id = %s", (auction_id,))
            conn.commit()
            
            return True, "Лот успешно снят с торгов 🗑️"

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Ошибка при удалении аукциона: {e}")
            return False, "Внутренняя ошибка сервера."
        finally:
            conn.close()


    def get_auction_details(self, auction_id):
        """Достает ВСЮ инфу о лоте + историю ставок"""
        conn = self._get_connection()
        if not conn: return None
        
        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Забираем сам лот из обновленной таблицы auctions
            cur.execute("""
                SELECT id, title, description, image_url, start_price, current_bid, end_time, status, winner_id
                FROM auctions 
                WHERE id = %s
            """, (auction_id,))
            auction = cur.fetchone()
            
            if not auction: return None
            
            # Конвертируем дату в строку для шаблонизатора (Jinja)
            if auction['end_time']:
                auction['end_time_str'] = auction['end_time'].strftime('%d.%m.%Y %H:%M')
                
            # Определяем минимальную ставку для инпута
            auction['min_bid'] = auction['current_bid'] + 10 if auction['current_bid'] > 0 else auction['start_price']

            # 2. 🔥 ДОСТАЁМ ИСТОРИЮ СТАВОК 🔥 (от самых свежих к старым)
            cur.execute("""
                SELECT b.amount, b.created_at, s.first_name, s.last_name
                FROM bids b
                JOIN students s ON b.bidder_id = s.id
                WHERE b.auction_id = %s
                ORDER BY b.amount DESC
            """, (auction_id,))
            
            bids = cur.fetchall()
            for b in bids:
                b['time_str'] = b['created_at'].strftime('%H:%M:%S') if b['created_at'] else ''
                
            auction['bids_history'] = bids
            
            return auction
        finally:
            conn.close()

    def create_standalone_auction(self, tg_user_id, title, description, image_url, start_price, end_time_str):
        """Студсовет выставляет уникальный лот напрямую в аукционы (без merch)"""
        conn = self._get_connection()
        if not conn: return False, "БД прилегла."

        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Проверяем роль (доступ только студсовету/админам)
            cur.execute("SELECT id, role FROM students WHERE telegram_user_id = %s", (tg_user_id,))
            user = cur.fetchone()

            if not user or user['role'] not in ('stud_council', 'admin'):
                return False, "Недостаточно прав! Только Студсовет выставляет лоты."

            # 2. Валидация времени (не больше недели)
            from datetime import datetime, timedelta
            end_time_dt = datetime.strptime(end_time_str, '%Y-%m-%dT%H:%M')
            max_end_time = datetime.now() + timedelta(days=7)
            
            if end_time_dt > max_end_time:
                return False, "Время аукциона не может превышать 1 неделю! 📅"
            if end_time_dt <= datetime.now():
                return False, "Аукцион в прошлом? Выбери нормальную дату."

            # 3. Пишем лот напрямую в таблицу auctions!
            import uuid
            auction_id = str(uuid.uuid4())
            
            cur.execute("""
                INSERT INTO auctions (id, student_id, title, description, image_url, start_price, end_time, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'open')
            """, (auction_id, user['id'], title, description, image_url, start_price, end_time_str))
            
            conn.commit()
            return True, f"Лот «{title}» успешно выставлен на аукцион!"

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Ошибка при создании аукциона: {e}")
            return False, "Внутренняя ошибка сервера."
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

    def redeem_secret_code(self, staff_tg_id, secret_code):
        """Студсовет гасит код и выдает товар студенту"""
        conn = self._get_connection()
        if not conn: return False, "БД лежит отдыхает."

        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Проверяем, что чел из Студсовета
            cur.execute("SELECT role FROM students WHERE telegram_user_id = %s", (staff_tg_id,))
            staff = cur.fetchone()
            if not staff or staff['role'] not in ('stud_council', 'admin'):
                return False, "Куда лезешь? Выдавать лут может только Студсовет! 🛑"

            secret_code = secret_code.strip().upper() # Защита от кривого ввода пробелов и регистра

            # 2. ИЩЕМ В ОБЫЧНОМ МЕРЧЕ (статус 'approved')
            cur.execute("""
                SELECT mo.id, m.name, s.first_name, s.last_name 
                FROM merch_orders mo 
                JOIN merch m ON mo.merch_id = m.id 
                JOIN students s ON mo.buyer_id = s.id 
                WHERE mo.secret_code = %s AND mo.status = 'approved'
            """, (secret_code,))
            merch = cur.fetchone()

            if merch:
                # Нашли! Гасим заказ.
                cur.execute("UPDATE merch_orders SET status = 'delivered' WHERE id = %s", (merch['id'],))
                conn.commit()
                return True, f"Выдано: {merch['name']}\nСтудент: {merch['first_name']} {merch['last_name']}"

            # 3. ИЩЕМ В АУКЦИОНАХ (статус 'completed')
            cur.execute("""
                SELECT a.id, a.title, s.first_name, s.last_name 
                FROM auctions a 
                JOIN students s ON a.winner_id = s.id 
                WHERE a.secret_code = %s AND a.status = 'completed'
            """, (secret_code,))
            auc = cur.fetchone()

            if auc:
                # Нашли! Гасим аукцион.
                cur.execute("UPDATE auctions SET status = 'delivered' WHERE id = %s", (auc['id'],))
                conn.commit()
                return True, f"Выдан лот: {auc['title']}\nПобедитель: {auc['first_name']} {auc['last_name']}"

            # Если ничего не нашли
            return False, "Код не найден или уже использован! Гони мошенника ссаными тряпками."

        except Exception as e:
            conn.rollback()
            print(f"[ERROR] Ошибка гашения кода: {e}")
            return False, "Внутренняя ошибка сервера"
        finally:
            conn.close()

    def delete_merch(self, merch_id):

        conn = self._get_connection()
        if not conn:
            return False, "Ошибка подключения к БД"
        try:
            cur = conn.cursor()
            cur.execute("DELETE FROM merch WHERE id = %s", (merch_id,))
            if cur.rowcount == 0:
                return False, "Товар не найден"
            conn.commit()
            return True, "Товар удален"
        except Exception as e:
            conn.rollback()
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
        """Отдает список покупок мерча И выигранных аукционов"""
        conn = self._get_connection()
        if not conn: return []
        
        try:
            cur = conn.cursor(dictionary=True)
            
            # Получаем uuid юзера по его tg_id
            cur.execute("SELECT id FROM students WHERE telegram_user_id = %s", (tg_id,))
            user = cur.fetchone()
            if not user: return []
            student_uuid = user['id']

            # 1. Достаем обычные заказы из магазина
            # Обрати внимание, добавил mo.created_at, чтобы потом отсортировать общий список
            cur.execute("""
                SELECT mo.id, m.name, mo.status, mo.secret_code, m.image_url, mo.created_at
                FROM merch_orders mo
                JOIN merch m ON mo.merch_id = m.id
                WHERE mo.buyer_id = %s
                ORDER BY mo.created_at DESC
            """, (student_uuid,))
            merch_orders = cur.fetchall()

            # 2. 🔥 ДОСТАЕМ ВЫИГРАННЫЕ АУКЦИОНЫ 🔥
            # Притворяемся, что аукцион - это обычный мерч со статусом 'approved'
            cur.execute("""
                SELECT id, title as name, 'approved' as status, secret_code, image_url, end_time as created_at
                FROM auctions
                WHERE winner_id = %s AND status = 'completed'
                ORDER BY end_time DESC
            """, (student_uuid,))
            won_auctions = cur.fetchall()

            # 3. Склеиваем два списка в один
            all_purchases = merch_orders + won_auctions
            
            # Сортируем общий список по дате (самые свежие покупки сверху)
            all_purchases.sort(key=lambda x: x['created_at'], reverse=True)

            return all_purchases
        except Exception as e:
            print(f"[ERROR] Ошибка получения покупок: {e}")
            return []
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
