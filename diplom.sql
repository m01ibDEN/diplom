-- Таблица факультетов
CREATE TABLE faculties (
    id INT AUTO_INCREMENT PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    dean VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Таблица групп (в кавычках!)
CREATE TABLE `groups` (
    id INT AUTO_INCREMENT PRIMARY KEY,
    group_code VARCHAR(10) UNIQUE NOT NULL,
    faculty_id INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE RESTRICT
);

-- Таблица студентов
CREATE TABLE students (
    id CHAR(36) PRIMARY KEY,
    telegram_user_id BIGINT UNIQUE NOT NULL,
    student_id VARCHAR(20) UNIQUE NOT NULL,
    last_name VARCHAR(50) NOT NULL,
    first_name VARCHAR(50) NOT NULL,
    middle_name VARCHAR(50),
    group_id INT,
    faculty_id INT,
    email VARCHAR(100) UNIQUE,
    phone VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (group_id) REFERENCES `groups`(id) ON DELETE SET NULL,
    FOREIGN KEY (faculty_id) REFERENCES faculties(id) ON DELETE SET NULL
);

-- Настройки системы
CREATE TABLE settings (
    `key` VARCHAR(50) PRIMARY KEY,
    value TEXT NOT NULL,
    description TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Баланс студента
CREATE TABLE balances (
    student_id CHAR(36) PRIMARY KEY,
    current_points BIGINT NOT NULL DEFAULT 0,
    total_earned BIGINT NOT NULL DEFAULT 0,
    total_spent BIGINT NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Все транзакции
CREATE TABLE transactions (
    id CHAR(36) PRIMARY KEY,
    student_id CHAR(36) NOT NULL,
    type VARCHAR(20) NOT NULL,
    amount BIGINT NOT NULL,
    description TEXT,
    entity_type VARCHAR(20),
    entity_id CHAR(36),
    status VARCHAR(20) NOT NULL DEFAULT 'completed',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Рейтинг
CREATE TABLE ranking (
    student_id CHAR(36) PRIMARY KEY,
    score BIGINT NOT NULL,
    position INT NOT NULL,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Активности
CREATE TABLE activities (
    id CHAR(36) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    points INT NOT NULL,
    category VARCHAR(20) NOT NULL,
    start_date DATE,
    end_date DATE,
    max_participants INT,
    status VARCHAR(20) NOT NULL DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Участие в активностях
CREATE TABLE student_activities (
    id CHAR(36) PRIMARY KEY,
    student_id CHAR(36) NOT NULL,
    activity_id CHAR(36) NOT NULL,
    earned_points INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (activity_id) REFERENCES activities(id) ON DELETE CASCADE,
    UNIQUE KEY unique_student_activity (student_id, activity_id)
);

-- Мерч
CREATE TABLE merch (
    id CHAR(36) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price_points INT NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    image_url VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Заказы мерча
CREATE TABLE merch_orders (
    id CHAR(36) PRIMARY KEY,
    merch_id CHAR(36) NOT NULL,
    buyer_id CHAR(36) NOT NULL,
    quantity INT NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (merch_id) REFERENCES merch(id) ON DELETE CASCADE,
    FOREIGN KEY (buyer_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Услуги от студентов
CREATE TABLE services (
    id CHAR(36) PRIMARY KEY,
    provider_id CHAR(36) NOT NULL,
    name VARCHAR(255) NOT NULL,
    points_cost INT NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (provider_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Заказы услуг
CREATE TABLE service_orders (
    id CHAR(36) PRIMARY KEY,
    service_id CHAR(36) NOT NULL,
    buyer_id CHAR(36) NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (service_id) REFERENCES services(id) ON DELETE CASCADE,
    FOREIGN KEY (buyer_id) REFERENCES students(id) ON DELETE CASCADE
);

-- Аукционы
CREATE TABLE auctions (
    id CHAR(36) PRIMARY KEY,
    student_id CHAR(36) NOT NULL,
    merch_id CHAR(36) NOT NULL,
    start_price INT NOT NULL,
    current_bid INT DEFAULT 0,
    end_time TIMESTAMP NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'open',
    winner_id CHAR(36),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (student_id) REFERENCES students(id) ON DELETE CASCADE,
    FOREIGN KEY (merch_id) REFERENCES merch(id) ON DELETE CASCADE,
    FOREIGN KEY (winner_id) REFERENCES students(id)
);

-- Ставки на аукционах
CREATE TABLE bids (
    id CHAR(36) PRIMARY KEY,
    auction_id CHAR(36) NOT NULL,
    bidder_id CHAR(36) NOT NULL,
    amount INT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (auction_id) REFERENCES auctions(id) ON DELETE CASCADE,
    FOREIGN KEY (bidder_id) REFERENCES students(id) ON DELETE CASCADE
);

CREATE INDEX idx_transactions_student_time ON transactions(student_id, created_at);
CREATE INDEX idx_transactions_status ON transactions(status);
