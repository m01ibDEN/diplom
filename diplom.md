1. Таблица students (студенты)
* id (PK, UUID) — уникальный идентификатор студента;
* student_id (VARCHAR(20)) — номер зачётной книжки;
* full_name (VARCHAR(100)) — ФИО;
* group_id (INT, FK) — связь с группой;
* faculty_id (INT, FK) — связь с факультетом;
* email (VARCHAR(100), UNIQUE) — email студента;
* phone (VARCHAR(20)) — телефон;
* created_at (TIMESTAMP) — дата регистрации в системе;
* updated_at (TIMESTAMP) — дата последнего обновления профиля.
2. Таблица groups (группы)
* id (PK, INT);
* group_code (VARCHAR(10)) — код группы (например, «ИВТ-21»);
* faculty_id (INT, FK) — связь с факультетом;
* created_at (TIMESTAMP).
3. Таблица faculties (факультеты)
* id (PK, INT);
* name (VARCHAR(100)) — название факультета;
* dean (VARCHAR(100)) — ФИО декана;
* created_at (TIMESTAMP).
4. Таблица balances (балансы студентов)
* student_id (PK, UUID, FK) — связь со студентом;
* current_points (BIGINT) — текущее количество баллов;
* total_earned (BIGINT) — всего заработано баллов;
* total_spent (BIGINT) — всего потрачено баллов;
* updated_at (TIMESTAMP) — время последнего изменения баланса.
5. Таблица transactions (транзакции)
* id (PK, UUID);
* student_id (UUID, FK) — кто совершил операцию;
* type (ENUM: ‘earn’, ‘spend’, ‘transfer’) — тип транзакции;
* amount (BIGINT) — сумма баллов;
* description (TEXT) — описание (например, «Участие в конференции»);
* target_id (UUID) — ID цели (мероприятие, товар, услуга);
* created_at (TIMESTAMP);
* status (ENUM: ‘pending’, ‘completed’, ‘cancelled’) — статус операции.
6. Таблица activities (мероприятия/действия для заработка баллов)
* id (PK, UUID);
* title (VARCHAR(255)) — название (например, «Организация концерта»);
* points (INT) — количество баллов за участие;
* category (ENUM: ‘event’, ‘lecture’, ‘service’, ‘queue’) — категория (связь с пунктами а–d из ТЗ);
* start_date (DATE);
* end_date (DATE);
* status (ENUM: ‘active’, ‘completed’, ‘cancelled’);
* created_at (TIMESTAMP).
7. Таблица merch (мерч)
* id (PK, UUID);
* name (VARCHAR(255));
* description (TEXT);
* price_points (INT) — стоимость в баллах;
* stock (INT) — остаток на складе;
* image_url (VARCHAR(255)) — ссылка на изображение;
* created_at (TIMESTAMP).
8. Таблица services (услуги через SDK)
* id (PK, UUID);
* provider_id (UUID) — ID провайдера (внешнего сервиса);
* name (VARCHAR(255));
* points_cost (INT);
* description (TEXT);
* active (BOOLEAN);
* created_at (TIMESTAMP).
9. Таблица ranking (рейтинг студентов)
* student_id (PK, UUID, FK);
* score (BIGINT) — рейтинг (комбинация баллов и активности);
* position (INT) — текущая позиция в рейтинге;
* calculated_at (TIMESTAMP) — время расчёта.
10. Таблица auctions (аукционы на «Бирже»)
* id (PK, UUID);
* student_id (UUID, FK) — организатор;
* item_id (UUID, FK) — ID товара/услуги;
* start_price (INT) — стартовая цена в баллах;
* current_bid (INT);
* end_time (TIMESTAMP);
* status (ENUM: ‘open’, ‘closed’, ‘cancelled’);
* winner_id (UUID, FK) — победитель (если аукцион завершён).
11. Таблица settings (настройки системы)
* key (PK, VARCHAR(50)) — имя настройки (например, max_points_per_user);
* value (TEXT) — значение;
* description (TEXT) — пояснение.
Связи между таблицами
1. Один ко многим (One-to-Many):
    * students ↔ balances (один студент — один баланс);
    * students ↔ transactions (один студент — много транзакций);
    * activities ↔ transactions (одно мероприятие — много транзакций участников);
    * merch ↔ transactions (один товар — много покупок);
    * services ↔ transactions (одна услуга — много использований).
2. Многие ко многим (Many-to-Many) через промежуточные таблицы:
    * связь студентов с группами (students.group_id → groups.id);
    * связь групп с факультетами (groups.faculty_id → faculties.id).
3. Внешние ключи (Foreign Keys):
    * transactions.student_id → students.id;
    * balances.student_id → students.id;
    * auctions.student_id → students.id;
    * auctions.item_id → merch.id или services.id (можно сделать единую таблицу items).

