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
        conn = self.get_connection()
        if not conn: return None
        
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT * FROM students WHERE telegram_user_id = %s", (telegram_user_id,))
            student = cursor.fetchone()
            
            if student:
                return student
            
            student_uuid = str(uuid.uuid4())
            student_id = f"STU{telegram_user_id}"
            
            # По умолчанию роль 'student'. Если первый пользователь - можно вручную в БД сделать 'admin'
            cursor.execute("""
                INSERT INTO students (id, telegram_user_id, student_id, first_name, last_name, role)
                VALUES (%s, %s, %s, %s, %s, 'student')
            """, (student_uuid, telegram_user_id, student_id, first_name, last_name))
            
            cursor.execute("""
                INSERT INTO balances (student_id, current_points)
                VALUES (%s, 500)
            """, (student_uuid,))
            
            conn.commit()
            return {"id": student_uuid, "telegram_user_id": telegram_user_id, "first_name": first_name, "role": "student"}
        except Error as e:
            print(f"Error in get_or_create_student: {e}")
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()

    def get_student_by_tg_id(self, telegram_id):
        conn = self.get_connection()
        if not conn: return None
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, b.current_points, b.total_earned, b.total_spent,
                   g.group_code, f.name as faculty_name
            FROM students s
            JOIN balances b ON s.id = b.student_id
            LEFT JOIN `groups` g ON s.group_id = g.id
            LEFT JOIN faculties f ON s.faculty_id = f.id
            WHERE s.telegram_user_id = %s
        """, (telegram_id,))
        student = cursor.fetchone()
        cursor.close()
        conn.close()
        return student

    # ==================== АДМИНКА ====================

    def is_admin(self, telegram_id):
        """Проверка прав администратора"""
        conn = self.get_connection()
        if not conn: return False
        cursor = conn.cursor()
        cursor.execute("SELECT role FROM students WHERE telegram_user_id = %s", (telegram_id,))
        res = cursor.fetchone()
        cursor.close()
        conn.close()
        return res and res[0] == 'admin'

    def admin_add_points(self, target_tg_id, amount, description):
        """Ручное начисление баллов (транзакция)"""
        conn = self.get_connection()
        if not conn: return False, "DB Error"
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()
            
            # Находим студента
            cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (target_tg_id,))
            student = cursor.fetchone()
            if not student: return False, "Студент не найден (он должен запустить бота)"
            
            # Обновляем баланс
            cursor.execute("""
                UPDATE balances 
                SET current_points = current_points + %s, total_earned = total_earned + %s 
                WHERE student_id = %s
            """, (amount, amount, student['id']))
            
            # Пишем транзакцию
            cursor.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, status)
                VALUES (%s, %s, 'earn', %s, %s, 'completed')
            """, (str(uuid.uuid4()), student['id'], amount, description))
            
            conn.commit()
            return True, f"Начислено {amount} баллов студенту."
        except Exception as e:
            conn.rollback()
            return False, str(e)
        finally:
            cursor.close()
            conn.close()

    def admin_add_merch(self, name, price, stock, description=""):
        conn = self.get_connection()
        if not conn: return False
        cursor = conn.cursor()
        try:
            cursor.execute("""
                INSERT INTO merch (id, name, price_points, stock, description)
                VALUES (%s, %s, %s, %s, %s)
            """, (str(uuid.uuid4()), name, price, stock, description))
            conn.commit()
            return True
        except:
            return False
        finally:
            cursor.close()
            conn.close()

    # ==================== АНАЛИТИКА И ИСТОРИЯ ====================

    def get_user_stats(self, telegram_id):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT DATE(created_at) as date, SUM(amount) as total 
                FROM transactions 
                WHERE student_id = (SELECT id FROM students WHERE telegram_user_id = %s)
                AND type = 'spend'
                GROUP BY DATE(created_at) 
                ORDER BY date ASC 
                LIMIT 7
            """, (telegram_id,))
            data = cursor.fetchall()
            for row in data:
                row['date'] = row['date'].strftime('%d.%m') if isinstance(row['date'], datetime) else str(row['date'])
            return data
        finally:
            cursor.close()
            conn.close()

    def get_student_history(self, telegram_id, limit=10):
        """Получение истории транзакций пользователя"""
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("""
                SELECT type, amount, description, created_at, status
                FROM transactions
                WHERE student_id = (SELECT id FROM students WHERE telegram_user_id = %s)
                ORDER BY created_at DESC
                LIMIT %s
            """, (telegram_id, limit))
            data = cursor.fetchall()
            # Форматируем дату
            for row in data:
                row['created_at'] = row['created_at'].strftime('%d.%m %H:%M')
            return data
        finally:
            cursor.close()
            conn.close()

    # ==================== МЕРЧ И СЕРВИСЫ ====================

    def get_all_merch(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM merch WHERE stock > 0")
        items = cursor.fetchall()
        cursor.close()
        conn.close()
        return items

    def buy_merch(self, telegram_id, merch_id, quantity=1):
        conn = self.get_connection()
        if not conn: return False, "Ошибка БД"
        
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()
            cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (telegram_id,))
            student = cursor.fetchone()
            if not student: return False, "Студент не найден"

            cursor.execute("SELECT * FROM merch WHERE id = %s FOR UPDATE", (merch_id,))
            item = cursor.fetchone()
            if not item: return False, "Товар не найден"
            if item['stock'] < quantity: return False, "Товара нет в наличии"

            cursor.execute("SELECT current_points FROM balances WHERE student_id = %s FOR UPDATE", (student['id'],))
            balance = cursor.fetchone()
            
            total_price = item['price_points'] * quantity
            if balance['current_points'] < total_price:
                return False, f"Недостаточно баллов (нужно {total_price})"

            cursor.execute("""
                UPDATE balances 
                SET current_points = current_points - %s, total_spent = total_spent + %s 
                WHERE student_id = %s
            """, (total_price, total_price, student['id']))

            cursor.execute("UPDATE merch SET stock = stock - %s WHERE id = %s", (quantity, merch_id))

            cursor.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id, status)
                VALUES (%s, %s, 'spend', %s, %s, 'merch', %s, 'completed')
            """, (str(uuid.uuid4()), student['id'], total_price, f"Покупка мерча: {item['name']}", item['id']))

            conn.commit()
            return True, f"Вы успешно купили {item['name']}"

        except Exception as e:
            conn.rollback()
            print(f"Ошибка при покупке мерча: {e}")
            return False, "Внутренняя ошибка сервера"
        finally:
            cursor.close()
            conn.close()

    def get_active_services(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, st.first_name as provider_name 
            FROM services s
            JOIN students st ON s.provider_id = st.id
            WHERE s.active = 1
        """)
        services = cursor.fetchall()
        cursor.close()
        conn.close()
        return services

    def add_service(self, telegram_id, name, price, description):
        conn = self.get_connection()
        if not conn: return False
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (telegram_id,))
            student = cursor.fetchone()
            if not student: return False
            
            service_id = str(uuid.uuid4())
            cursor.execute("""
                INSERT INTO services (id, provider_id, name, description, points_cost)
                VALUES (%s, %s, %s, %s, %s)
            """, (service_id, student['id'], name, description, price))
            conn.commit()
            return True
        except:
            conn.rollback()
            return False
        finally:
            cursor.close()
            conn.close()

    def buy_service(self, telegram_id, service_id):
        conn = self.get_connection()
        if not conn: return False, "Ошибка соединения"
        
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (telegram_id,))
            buyer = cursor.fetchone()
            
            cursor.execute("SELECT * FROM services WHERE id = %s FOR UPDATE", (service_id,))
            service = cursor.fetchone()
            
            if not buyer or not service: return False, "Объект не найден"
            if buyer['id'] == service['provider_id']: return False, "Нельзя купить у самого себя"

            cursor.execute("SELECT current_points FROM balances WHERE student_id = %s FOR UPDATE", (buyer['id'],))
            balance = cursor.fetchone()
            
            if balance['current_points'] < service['points_cost']:
                return False, "Недостаточно баллов"

            cursor.execute("UPDATE balances SET current_points = current_points - %s, total_spent = total_spent + %s WHERE student_id = %s",
                           (service['points_cost'], service['points_cost'], buyer['id']))
            
            cursor.execute("UPDATE balances SET current_points = current_points + %s, total_earned = total_earned + %s WHERE student_id = %s",
                           (service['points_cost'], service['points_cost'], service['provider_id']))

            order_uuid = str(uuid.uuid4())
            cursor.execute("INSERT INTO service_orders (id, service_id, buyer_id, status) VALUES (%s, %s, %s, 'completed')",
                           (order_uuid, service_id, buyer['id']))
            
            cursor.execute("INSERT INTO transactions (id, student_id, type, amount, description) VALUES (%s, %s, 'spend', %s, %s)",
                           (str(uuid.uuid4()), buyer['id'], service['points_cost'], f"Заказ услуги: {service['name']}"))
            
            cursor.execute("INSERT INTO transactions (id, student_id, type, amount, description) VALUES (%s, %s, 'earn', %s, %s)",
                           (str(uuid.uuid4()), service['provider_id'], service['points_cost'], f"Оплата за услугу: {service['name']}"))

            conn.commit()
            return True, f"Услуга '{service['name']}' успешно оплачена"
        except Exception as e:
            conn.rollback()
            return False, f"Ошибка: {str(e)}"
        finally:
            cursor.close()
            conn.close()

    def get_leaderboard(self, limit=10):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.first_name, s.last_name, b.current_points
            FROM students s
            JOIN balances b ON s.id = b.student_id
            ORDER BY b.current_points DESC
            LIMIT %s
        """, (limit,))
        result = cursor.fetchall()
        cursor.close()
        conn.close()
        return result

db = Database()