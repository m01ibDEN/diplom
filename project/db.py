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
        try:
            # Проверяем существует ли
            cursor.execute("SELECT * FROM students WHERE telegram_user_id = %s", (telegram_user_id,))
            student = cursor.fetchone()
            
            if student:
                return student
            
            # Создаём нового
            student_uuid = str(uuid.uuid4())
            student_id = f"STU{telegram_user_id}"
            
            cursor.execute("""
                INSERT INTO students (id, telegram_user_id, student_id, first_name, last_name)
                VALUES (%s, %s, %s, %s, %s)
            """, (student_uuid, telegram_user_id, student_id, first_name, last_name))
            
            # Инициализируем баланс
            cursor.execute("""
                INSERT INTO balances (student_id, current_points)
                VALUES (%s, 500)
            """, (student_uuid,))
            
            conn.commit()
            return {"id": student_uuid, "telegram_user_id": telegram_user_id, "first_name": first_name}
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

    # ==================== АНАЛИТИКА (ДЛЯ ГРАФИКОВ) ====================

    def get_user_stats(self, telegram_id):
        """Получение данных о расходах за последние 7 дней для Chart.js"""
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
            # Форматируем дату для JS (строка)
            for row in data:
                row['date'] = row['date'].strftime('%d.%m') if isinstance(row['date'], datetime) else str(row['date'])
            return data
        finally:
            cursor.close()
            conn.close()

    # ==================== МЕРЧ (БЕЗОПАСНАЯ ТРАНЗАКЦИЯ) ====================

    def get_all_merch(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM merch WHERE stock_quantity > 0")
        items = cursor.fetchall()
        cursor.close()
        conn.close()
        return items

    def buy_merch(self, telegram_id, merch_id, quantity=1):
        """Покупка мерча с использованием транзакции и блокировки строк"""
        conn = self.get_connection()
        if not conn: return False, "Ошибка БД"
        
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction() # НАЧАЛО ТРАНЗАКЦИИ

            # 1. Получаем студента
            cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (telegram_id,))
            student = cursor.fetchone()
            if not student: return False, "Студент не найден"

            # 2. Получаем товар и БЛОКИРУЕМ его (FOR UPDATE)
            cursor.execute("SELECT * FROM merch WHERE id = %s FOR UPDATE", (merch_id,))
            item = cursor.fetchone()
            if not item: return False, "Товар не найден"
            if item['stock_quantity'] < quantity: return False, "Товара нет в наличии"

            # 3. Проверяем баланс и БЛОКИРУЕМ его
            cursor.execute("SELECT current_points FROM balances WHERE student_id = %s FOR UPDATE", (student['id'],))
            balance = cursor.fetchone()
            
            total_price = item['points_cost'] * quantity
            if balance['current_points'] < total_price:
                return False, f"Недостаточно баллов (нужно {total_price})"

            # 4. Выполняем действия
            # Списываем баллы
            cursor.execute("""
                UPDATE balances 
                SET current_points = current_points - %s, total_spent = total_spent + %s 
                WHERE student_id = %s
            """, (total_price, total_price, student['id']))

            # Уменьшаем склад
            cursor.execute("UPDATE merch SET stock_quantity = stock_quantity - %s WHERE id = %s", (quantity, merch_id))

            # Логируем транзакцию
            cursor.execute("""
                INSERT INTO transactions (id, student_id, type, amount, description, entity_type, entity_id, status)
                VALUES (%s, %s, 'spend', %s, %s, 'merch', %s, 'completed')
            """, (str(uuid.uuid4()), student['id'], total_price, f"Покупка мерча: {item['name']}", item['id']))

            conn.commit() # ФИКСИРУЕМ ВСЕ ИЗМЕНЕНИЯ
            return True, f"Вы успешно купили {item['name']}"

        except Exception as e:
            conn.rollback() # ОТКАТ ПРИ ЛЮБОЙ ОШИБКЕ
            print(f"Ошибка при покупке мерча: {e}")
            return False, "Внутренняя ошибка сервера"
        finally:
            cursor.close()
            conn.close()

    # ==================== БИРЖА УСЛУГ (БЕЗОПАСНАЯ ТРАНЗАКЦИЯ) ====================

    def get_active_services(self):
        conn = self.get_connection()
        if not conn: return []
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT s.*, st.first_name as provider_name 
            FROM services s
            JOIN students st ON s.provider_id = st.id
            WHERE s.is_active = 1
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
        """Покупка услуги с переводом баллов от студента к студенту"""
        conn = self.get_connection()
        if not conn: return False, "Ошибка соединения"
        
        cursor = conn.cursor(dictionary=True)
        try:
            conn.start_transaction()

            # 1. Покупатель
            cursor.execute("SELECT id FROM students WHERE telegram_user_id = %s", (telegram_id,))
            buyer = cursor.fetchone()
            
            # 2. Услуга и продавец
            cursor.execute("SELECT * FROM services WHERE id = %s FOR UPDATE", (service_id,))
            service = cursor.fetchone()
            
            if not buyer or not service: return False, "Объект не найден"
            if buyer['id'] == service['provider_id']: return False, "Нельзя купить у самого себя"

            # 3. Баланс покупателя
            cursor.execute("SELECT current_points FROM balances WHERE student_id = %s FOR UPDATE", (buyer['id'],))
            balance = cursor.fetchone()
            
            if balance['current_points'] < service['points_cost']:
                return False, "Недостаточно баллов"

            # 4. Процесс перевода
            # Минус у покупателя
            cursor.execute("UPDATE balances SET current_points = current_points - %s, total_spent = total_spent + %s WHERE student_id = %s",
                           (service['points_cost'], service['points_cost'], buyer['id']))
            
            # Плюс у продавца
            cursor.execute("UPDATE balances SET current_points = current_points + %s, total_earned = total_earned + %s WHERE student_id = %s",
                           (service['points_cost'], service['points_cost'], service['provider_id']))

            # Запись о заказе
            order_uuid = str(uuid.uuid4())
            cursor.execute("INSERT INTO service_orders (id, service_id, buyer_id, status) VALUES (%s, %s, %s, 'completed')",
                           (order_uuid, service_id, buyer['id']))
            
            # Логи транзакций для обоих
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

    # ==================== РЕЙТИНГ (ЛЕЙДЕРБОРД) ====================

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