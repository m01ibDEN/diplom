# db.py
import mysql.connector
from mysql.connector import Error
import os
from dotenv import load_dotenv
from datetime import datetime
import uuid

load_dotenv()

class Database:
    def __init__(self):
        self.config = {
            'host': os.getenv('MYSQL_HOST', 'localhost'),
            'user': os.getenv('MYSQL_USER', 'root'),
            'password': os.getenv('MYSQL_PASSWORD', ''),
            'database': os.getenv('MYSQL_DB', 'student_coins')
        }
    
    def get_connection(self):
        try:
            conn = mysql.connector.connect(**self.config)
            return conn
        except Error as e:
            print(f"Ошибка подключения к MySQL: {e}")
            return None
    
    # ==================== СТУДЕНТЫ ====================
    
    def get_or_create_student(self, telegram_user_id, first_name, last_name='', username=''):
        """Получить студента или создать нового"""
        conn = self.get_connection()
        if not conn:
            return None
        
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем существует ли
        cursor.execute("SELECT * FROM students WHERE telegram_user_id = %s", (telegram_user_id,))
        student = cursor.fetchone()
        
        if student:
            cursor.close()
            conn.close()
            return student
        
        # Создаём нового
        student_uuid = str(uuid.uuid4())
        student_id = f"STU{telegram_user_id}"  # Уникальный студенческий ID
        
        cursor.execute("""
            INSERT INTO students (id, telegram_user_id, student_id, last_name, first_name, email)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (student_uuid, telegram_user_id, student_id, last_name, first_name, f"{username}@telegram.user"))
        
        # Создаём баланс
        cursor.execute("""
            INSERT INTO balances (student_id, current_points, total_earned, total_spent)
            VALUES (%s, 0, 0, 0)
        """, (student_uuid,))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return self.get_or_create_student(telegram_user_id, first_name, last_name, username)
    
    # ==================== БАЛАНС ====================
    def get_balance(self, telegram_user_id):
        """Получить баланс студента"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT b.current_points, b.total_earned, b.total_spent, r.position as `rank`
            FROM students s
            LEFT JOIN balances b ON s.id = b.student_id
            LEFT JOIN ranking r ON s.id = r.student_id
            WHERE s.telegram_user_id = %s
        """, (telegram_user_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if not result:
            return {"current": 0, "total_earned": 0, "total_spent": 0, "rank": 999}
        
        return {
            "current": result['current_points'] or 0,
            "total_earned": result['total_earned'] or 0,
            "total_spent": result['total_spent'] or 0,
            "rank": result['rank'] or 999
        }

    
    # ==================== ТРАНЗАКЦИИ ====================
    
    def add_transaction(self, telegram_user_id, tx_type, amount, description, entity_type=None, entity_id=None):
        """Добавить транзакцию и обновить баланс"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем ID студента
        cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (telegram_user_id,))
        student = cursor.fetchone()
        if not student:
            cursor.close()
            conn.close()
            return False
        
        student_id = student['id']
        tx_uuid = str(uuid.uuid4())
        
        # Добавляем транзакцию
        cursor.execute("""
            INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id, status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'completed')
        """, (tx_uuid, student_id, tx_type, amount, description, entity_type, entity_id))
        
        # Обновляем баланс
        if tx_type == 'earn':
            cursor.execute("""
                UPDATE balances 
                SET current_points = current_points + %s, 
                    total_earned = total_earned + %s 
                WHERE student_id = %s
            """, (amount, amount, student_id))
        elif tx_type == 'spend':
            cursor.execute("""
                UPDATE balances 
                SET current_points = current_points - %s, 
                    total_spent = total_spent + %s 
                WHERE student_id = %s
            """, (amount, amount, student_id))
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    
    def get_transactions(self, telegram_user_id, limit=50):
        """Получить историю транзакций"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT t.type, t.amount, t.description, t.created_at, t.status
            FROM transactions t
            JOIN students s ON t.student_id = s.id
            WHERE s.telegram_user_id = %s
            ORDER BY t.created_at DESC
            LIMIT %s
        """, (telegram_user_id, limit))
        
        transactions = cursor.fetchall()
        cursor.close()
        conn.close()
        
        # Форматируем для фронтенда
        result = []
        for tx in transactions:
            result.append({
                "type": tx['type'],
                "amount": tx['amount'],
                "description": tx['description'],
                "date": tx['created_at'].strftime('%Y-%m-%d %H:%M'),
                "status": tx['status']
            })
        
        return result
    
    # ==================== РЕЙТИНГ ====================
    
    def get_ranking(self, limit=10):
        """Топ студентов по баллам"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT s.first_name, s.last_name, b.current_points, r.position
            FROM students s
            JOIN balances b ON s.id = b.student_id
            LEFT JOIN ranking r ON s.id = r.student_id
            ORDER BY b.current_points DESC
            LIMIT %s
        """, (limit,))
        
        ranking = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = []
        for idx, item in enumerate(ranking, 1):
            result.append({
                "rank": item['position'] or idx,
                "name": f"{item['first_name']} {item['last_name']}",
                "points": item['current_points']
            })
        
        return result
    
    # ==================== МЕРЧ ====================
    
    def get_merch(self):
        """Получить список мерча"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("SELECT * FROM merch WHERE stock > 0 ORDER BY created_at DESC")
        merch = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = []
        for item in merch:
            result.append({
                "id": item['id'],
                "name": item['name'],
                "price": item['price_points'],
                "stock": item['stock'],
                "image": "🎁",  # можно брать из item['image_url']
                "description": item['description']
            })
        
        return result
    
    def buy_merch(self, telegram_user_id, merch_id, quantity=1):
        """Купить мерч"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Проверяем наличие и цену
        cursor.execute("SELECT name, price_points, stock FROM merch WHERE id = %s", (merch_id,))
        merch = cursor.fetchone()
        
        if not merch or merch['stock'] < quantity:
            cursor.close()
            conn.close()
            return False, "Товар закончился"
        
        # Проверяем баланс
        cursor.execute("""
            SELECT b.current_points, s.id as student_id
            FROM students s
            JOIN balances b ON s.id = b.student_id
            WHERE s.telegram_user_id = %s
        """, (telegram_user_id,))
        student = cursor.fetchone()
        
        total_price = merch['price_points'] * quantity
        
        if not student or student['current_points'] < total_price:
            cursor.close()
            conn.close()
            return False, "Недостаточно баллов"
        
        # Создаём заказ
        order_uuid = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO merch_orders (id, merch_id, buyer_id, quantity, status)
            VALUES (%s, %s, %s, %s, 'paid')
        """, (order_uuid, merch_id, student['student_id'], quantity))
        
        # Уменьшаем stock
        cursor.execute("UPDATE merch SET stock = stock - %s WHERE id = %s", (quantity, merch_id))
        
        # Добавляем транзакцию
        cursor.execute("""
            INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id, status)
            VALUES (%s, %s, 'spend', %s, %s, 'merch_order', %s, 'completed')
        """, (str(uuid.uuid4()), student['student_id'], total_price, f"Купил {merch['name']}", order_uuid))
        
        # Обновляем баланс
        cursor.execute("""
            UPDATE balances 
            SET current_points = current_points - %s, 
                total_spent = total_spent + %s 
            WHERE student_id = %s
        """, (total_price, total_price, student['student_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Успешно"
    
    # ==================== УСЛУГИ ====================
    
    def get_my_services(self, telegram_user_id):
        """Мои услуги"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        cursor.execute("""
            SELECT s.id, s.name, s.points_cost as price, s.active, 
                   COUNT(so.id) as orders,
                   SUM(CASE WHEN so.status = 'completed' THEN s.points_cost ELSE 0 END) as earnings
            FROM services s
            JOIN students st ON s.provider_id = st.id
            LEFT JOIN service_orders so ON s.id = so.service_id
            WHERE st.telegram_user_id = %s
            GROUP BY s.id
        """, (telegram_user_id,))
        
        services = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = []
        for svc in services:
            result.append({
                "id": svc['id'],
                "name": svc['name'],
                "price": svc['price'],
                "orders": svc['orders'] or 0,
                "status": "active" if svc['active'] else "inactive",
                "earnings": svc['earnings'] or 0
            })
        
        return result
    
    def add_service(self, telegram_user_id, name, price, description=""):
        """Разместить услугу"""
        print(f"[DB] add_service вызван: user={telegram_user_id}, name={name}, price={price}")
        
        conn = self.get_connection()
        if not conn:
            print("[DB ERROR] Нет подключения к БД")
            return False
            
        cursor = conn.cursor(dictionary=True)
        
        # ВРЕМЕННЫЙ ХАРДКОД ДЛЯ ТЕСТА
        cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (telegram_user_id,))
        student = cursor.fetchone()
        
        if not student:
            print(f"[DB WARNING] Студент не найден, создаю нового: telegram_user_id={telegram_user_id}")
            # Создаём студента на лету
            student_uuid = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO students (id, telegram_user_id, student_id, last_name, first_name, email)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (student_uuid, telegram_user_id, f"STU{telegram_user_id}", "Автоматически", "Созданный", f"auto{telegram_user_id}@test.com"))
            
            cursor.execute("""
                INSERT INTO balances (student_id, current_points, total_earned, total_spent)
                VALUES (%s, 0, 0, 0)
            """, (student_uuid,))
            
            conn.commit()
            student = {'id': student_uuid}
        
        service_uuid = str(uuid.uuid4())
        print(f"[DB] Создание услуги с ID: {service_uuid} для студента {student['id']}")
        
        try:
            cursor.execute("""
                INSERT INTO services (id, provider_id, name, points_cost, description, active)
                VALUES (%s, %s, %s, %s, %s, TRUE)
            """, (service_uuid, student['id'], name, price, description))
            
            conn.commit()
            print(f"[DB SUCCESS] Услуга '{name}' создана успешно!")
            cursor.close()
            conn.close()
            return True
        except Exception as e:
            print(f"[DB ERROR] Ошибка при INSERT: {e}")
            import traceback
            traceback.print_exc()
            conn.rollback()
            cursor.close()
            conn.close()
            return False

    
    def get_all_services(self, exclude_user_id=None):
        """Все услуги (биржа)"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        query = """
            SELECT s.id, s.name, s.points_cost as price, s.description,
                   st.first_name, st.last_name,
                   COUNT(so.id) as orders,
                   AVG(CASE WHEN so.status = 'completed' THEN 5 ELSE NULL END) as rating
            FROM services s
            JOIN students st ON s.provider_id = st.id
            LEFT JOIN service_orders so ON s.id = so.service_id
            WHERE s.active = TRUE
        """
        
        if exclude_user_id:
            query += " AND st.telegram_user_id != %s"
            cursor.execute(query + " GROUP BY s.id LIMIT 20", (exclude_user_id,))
        else:
            cursor.execute(query + " GROUP BY s.id LIMIT 20")
        
        services = cursor.fetchall()
        cursor.close()
        conn.close()
        
        result = []
        for svc in services:
            result.append({
                "id": svc['id'],
                "name": svc['name'],
                "price": svc['price'],
                "provider": f"{svc['first_name']} {svc['last_name']}",
                "rating": round(svc['rating'] or 4.5, 1),
                "orders": svc['orders'] or 0
            })
        
        return result
    
    def buy_service(self, telegram_user_id, service_id):
        """Заказать услугу"""
        conn = self.get_connection()
        cursor = conn.cursor(dictionary=True)
        
        # Получаем инфо об услуге
        cursor.execute("""
            SELECT s.name, s.points_cost, s.provider_id,
                   st.telegram_user_id as provider_tg_id
            FROM services s
            JOIN students st ON s.provider_id = st.id
            WHERE s.id = %s AND s.active = TRUE
        """, (service_id,))
        service = cursor.fetchone()
        
        if not service:
            cursor.close()
            conn.close()
            return False, "Услуга недоступна"
        
        # Проверяем баланс покупателя
        cursor.execute("""
            SELECT s.id, b.current_points
            FROM students s
            JOIN balances b ON s.id = b.student_id
            WHERE s.telegram_user_id = %s
        """, (telegram_user_id,))
        buyer = cursor.fetchone()
        
        if not buyer or buyer['current_points'] < service['points_cost']:
            cursor.close()
            conn.close()
            return False, "Недостаточно баллов"
        
        # Создаём заказ
        order_uuid = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO service_orders (id, service_id, buyer_id, status)
            VALUES (%s, %s, %s, 'pending')
        """, (order_uuid, service_id, buyer['id']))
        
        # Списываем у покупателя
        cursor.execute("""
            INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id, status)
            VALUES (%s, %s, 'spend', %s, %s, 'service_order', %s, 'completed')
        """, (str(uuid.uuid4()), buyer['id'], service['points_cost'], f"Заказ: {service['name']}", order_uuid))
        
        cursor.execute("""
            UPDATE balances SET current_points = current_points - %s, total_spent = total_spent + %s
            WHERE student_id = %s
        """, (service['points_cost'], service['points_cost'], buyer['id']))
        
        # Начисляем провайдеру
        cursor.execute("""
            INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id, status)
            VALUES (%s, %s, 'earn', %s, %s, 'service_order', %s, 'completed')
        """, (str(uuid.uuid4()), service['provider_id'], service['points_cost'], f"Заказали: {service['name']}", order_uuid))
        
        cursor.execute("""
            UPDATE balances SET current_points = current_points + %s, total_earned = total_earned + %s
            WHERE student_id = %s
        """, (service['points_cost'], service['points_cost'], service['provider_id']))
        
        conn.commit()
        cursor.close()
        conn.close()
        
        return True, "Успешно"

# Экземпляр БД
db = Database()
