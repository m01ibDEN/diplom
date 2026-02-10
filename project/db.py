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
        """Статистика для графика (по транзакциям)"""
        uuid_id = self._get_student_uuid(telegram_id)
        if not uuid_id: return []

        conn = self._get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(dictionary=True)
            # Группируем расходы по дням
            cur.execute("""
                SELECT DATE_FORMAT(created_at, '%d.%m') as date, SUM(amount) as total
                FROM transactions
                WHERE student_id = %s AND type = 'spend'
                GROUP BY DATE(created_at)
                ORDER BY created_at DESC
                LIMIT 7
            """, (uuid_id,))
            data = cur.fetchall()
            return list(reversed(data)) # Чтобы график шел слева направо
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
            cur.execute("SELECT * FROM merch WHERE stock > 0 ORDER BY price_points ASC")
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

    def get_all_services(self, current_user_tg_id):
        """
        Возвращает список услуг + статус для текущего юзера.
        Использует LEFT JOIN с service_orders, чтобы понять, занята ли задача.
        """
        user_uuid = self._get_student_uuid(current_user_tg_id)
        # Если юзера нет, вернем пустой список или ошибку, но лучше пустой список чтоб не падало
        if not user_uuid: 
            # Можно попробовать создать юзера "на лету" если это тест
            return []

        conn = self._get_connection()
        if not conn: return []
        try:
            cur = conn.cursor(dictionary=True)
            
            # Выбираем услуги.
            # Если service_orders существует с активным статусом -> задача занята.
            # Нам нужно знать order_id, чтобы подтвердить выполнение.
            query = """
            SELECT 
                s.id, s.name, s.description, s.points_cost, s.provider_id,
                st.first_name as provider_name,
                ord.id as order_id,
                ord.buyer_id as executor_id,
                ord.status as order_status
            FROM services s
            JOIN students st ON s.provider_id = st.id
            LEFT JOIN service_orders ord ON s.id = ord.service_id 
                 AND ord.status IN ('pending', 'in_progress', 'completed')
            WHERE s.active = 1
            ORDER BY s.created_at DESC
            """
            cur.execute(query)
            rows = cur.fetchall()
            
            result = []
            for row in rows:
                status = 'open'
                # Определяем статус для фронтенда
                if row['order_status'] in ['pending', 'in_progress']:
                    status = 'in_progress'
                elif row['order_status'] == 'completed':
                    status = 'completed'

                result.append({
                    'id': row['id'],
                    'name': row['name'],
                    'description': row['description'],
                    'points_cost': row['points_cost'],
                    'provider_name': row['provider_name'],
                    'is_my_task': (str(row['provider_id']) == str(user_uuid)),
                    'am_i_executor': (str(row['executor_id']) == str(user_uuid)) if row['executor_id'] else False,
                    'status': status,
                    'order_id': row['order_id'] # Нужен для подтверждения
                })
            return result
        finally:
            conn.close()

    def add_service(self, tg_id, name, points, desc):
        provider_uuid = self._get_student_uuid(tg_id)
        if not provider_uuid: return False, "Студент не найден"
        
        conn = self._get_connection()
        if not conn: return False, "Нет связи с БД"
        try:
            cur = conn.cursor()
            svc_id = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO services (id, provider_id, name, points_cost, description, active) VALUES (%s, %s, %s, %s, %s, 1)",
                (svc_id, provider_uuid, name, points, desc)
            )
            conn.commit()
            return True, "Услуга опубликована"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def assign_service(self, service_id, executor_tg_id):
        """Исполнитель берет задачу (создаем service_orders)"""
        executor_uuid = self._get_student_uuid(executor_tg_id)
        if not executor_uuid: return False, "Пользователь не найден"

        conn = self._get_connection()
        if not conn: return False, "Ошибка БД"
        try:
            cur = conn.cursor(dictionary=True)
            
            # 1. Проверка: задача свободна?
            # Смотрим, есть ли активные ордера на этот сервис
            cur.execute("""
                SELECT id FROM service_orders 
                WHERE service_id = %s AND status IN ('pending', 'in_progress', 'completed')
            """, (service_id,))
            if cur.fetchone():
                return False, "Задание уже занято или выполнено"

            # 2. Проверка: не автор ли это?
            cur.execute("SELECT provider_id FROM services WHERE id = %s", (service_id,))
            svc = cur.fetchone()
            if not svc: return False, "Услуга не найдена"
            if str(svc['provider_id']) == str(executor_uuid):
                return False, "Нельзя выполнять свои задания"

            # 3. Создаем заказ
            order_id = str(uuid.uuid4())
            cur.execute("""
                INSERT INTO service_orders (id, service_id, buyer_id, status)
                VALUES (%s, %s, %s, 'in_progress')
            """, (order_id, service_id, executor_uuid))
            
            conn.commit()
            return True, "Вы взяли задание в работу!"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

    def complete_service_order(self, order_id, provider_tg_id):
        """Заказчик подтверждает выполнение и платит"""
        if not order_id: return False, "Не передан ID заказа"
        
        provider_uuid = self._get_student_uuid(provider_tg_id)
        if not provider_uuid: return False, "Пользователь не найден"
        
        conn = self._get_connection()
        if not conn: return False, "Ошибка БД"
        try:
            cur = conn.cursor(dictionary=True)
            
            # Получаем детали заказа + цену из услуги
            query = """
            SELECT ord.id, ord.buyer_id as executor_id, ord.status, 
                   s.points_cost, s.provider_id, s.name as service_name
            FROM service_orders ord
            JOIN services s ON ord.service_id = s.id
            WHERE ord.id = %s
            """
            cur.execute(query, (order_id,))
            order = cur.fetchone()

            if not order: return False, "Заказ не найден"
            # Проверяем права (только создатель услуги может подтвердить)
            if str(order['provider_id']) != str(provider_uuid): 
                return False, "Вы не автор этой задачи"
            
            if order['status'] == 'completed': return False, "Уже оплачено"

            cost = order['points_cost']
            executor_uuid = order['executor_id']

            # Проверяем баланс заказчика
            cur.execute("SELECT current_points FROM balances WHERE student_id = %s", (provider_uuid,))
            bal = cur.fetchone()
            if not bal or bal['current_points'] < cost:
                return False, "Недостаточно средств на балансе!"

            # --- ТРАНЗАКЦИЯ ---
            
            # 1. Обновляем статус заказа
            cur.execute("UPDATE service_orders SET status = 'completed' WHERE id = %s", (order_id,))
            
            # 2. Списываем у заказчика
            cur.execute("""
                UPDATE balances SET current_points = current_points - %s, total_spent = total_spent + %s 
                WHERE student_id = %s
            """, (cost, cost, provider_uuid))

            # 3. Начисляем исполнителю
            cur.execute("""
                UPDATE balances SET current_points = current_points + %s, total_earned = total_earned + %s
                WHERE student_id = %s
            """, (cost, cost, executor_uuid))

            # 4. Пишем в историю (transactions)
            # Расход
            cur.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id)
                VALUES (%s, %s, 'spend', %s, %s, 'service', %s)
            """, (str(uuid.uuid4()), provider_uuid, cost, f"Оплата задачи: {order['service_name']}", order_id))
            
            # Доход
            cur.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id)
                VALUES (%s, %s, 'earn', %s, %s, 'service', %s)
            """, (str(uuid.uuid4()), executor_uuid, cost, f"Выполнение задачи: {order['service_name']}", order_id))

            conn.commit()
            return True, "Задание подтверждено, оплата проведена!"
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            conn.close()

# Создаем единственный экземпляр
db = Database()
