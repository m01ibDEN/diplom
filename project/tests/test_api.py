# tests/test_api.py
# Unit тесты для API

import pytest
import json
from unittest.mock import patch, MagicMock
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webapp import app, db  # ← db тоже импортируем
from db import db


@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def mock_db():
    with patch('webapp.db') as mock:
        yield mock


# --- SDK API ---


def test_sdk_balance_no_key(client, mock_db):
    mock_db.validate_api_key.return_value = None
    rv = client.get('/api/sdk/balance?user_id=123')
    assert rv.status_code == 401
    assert 'Invalid API Key' in rv.json['error']


def test_sdk_balance_ok(client, mock_db):
    mock_db.validate_api_key.return_value = 'test_service'
    mock_db.get_student_by_tg_id.return_value = {'id': 1, 'current_points': 500}

    rv = client.get('/api/sdk/balance?user_id=123',
                    headers={'X-API-Key': 'fake'})
    assert rv.status_code == 200
    assert rv.json['balance'] == 500


def test_sdk_transaction_spend_ok(client, mock_db):
    mock_db.validate_api_key.return_value = 'test_service'
    # Начальный баланс
    mock_db.get_student_by_tg_id.side_effect = [
        {'id': 1, 'current_points': 500},  # первый раз — при проверке
        {'id': 1, 'current_points': 400},  # после add_points — новый баланс
    ]
    mock_db.add_points.return_value = True

    rv = client.post('/api/sdk/transaction',
                     json={
                         'user_id': '123',
                         'amount': 100,
                         'type': 'spend',
                         'description': 'test spend'
                     },
                     headers={'X-API-Key': 'fake'})

    print("Resp:", rv.status_code, rv.json)

    assert rv.status_code == 200
    assert rv.json['success'] is True
    assert rv.json['new_balance'] == 400


# --- AUCTIONS API ---


def test_auctions_list_empty(client, mock_db):
    mock_db._get_connection.return_value.cursor.return_value.fetchall.return_value = []
    rv = client.get('/api/auctions')
    assert rv.status_code == 200
    assert rv.json == []


def test_place_bid_insufficient_funds(client, mock_db):
    mock_db.get_student_by_tg_id.return_value = {'id': 1, 'current_points': 50}
    mock_db.place_bid.return_value = (False, 'Недостаточно средств')
    rv = client.post('/api/auctions/bid', json={
        'auction_id': 'auc123',
        'user_id': '123',
        'bid_amount': 100
    })
    assert rv.status_code == 400
    assert rv.json['success'] is False


def test_create_custom_auction_ok(client, mock_db):
    mock_db.create_standalone_auction.return_value = (True, 'Лот создан')
    rv = client.post('/api/auctions/create_custom', json={
        'user_id': '123',
        'name': 'Новый лот',
        'start_price': 100,
        'end_time': '2026-04-07 10:00:00'
    })
    assert rv.status_code == 200
    assert rv.json['success'] is True


# --- MERCH API ---


def test_buy_merch_success(client, mock_db):
    mock_db.create_merch_order.return_value = (True, 'Заказ создан')
    rv = client.post('/api/buy_merch', json={
        'user_id': 123,
        'merch_id': 'tshirt123'
    })
    assert rv.status_code == 200
    assert rv.json['success'] is True


def test_add_merch_no_permission(client, mock_db):
    mock_db.get_student_by_tg_id.return_value = {'id': 1, 'role': 'student'}
    rv = client.post('/api/add_merch_item', data={
        'user_id': '123',
        'name': 'Кепка',
        'price': '200',
        'stock': '10'
    })
    assert rv.status_code == 403
    assert 'Нет прав' in rv.json['message']


# --- SERVICES API ---


def test_add_service_ok(client, mock_db):
    mock_db.add_service.return_value = (True, 'Услуга добавлена')
    rv = client.post('/api/add_service', json={
        'user_id': 123,
        'name': 'Репетитор',
        'points_cost': 100,
        'description': 'Помогу с учёбой'
    })
    assert rv.status_code == 200
    assert rv.json['success'] is True


def test_take_task_already_taken(client, mock_db):
    mock_db.assign_service.return_value = (False, 'Задание уже занято')
    rv = client.post('/api/take_task', json={
        'user_id': 123,
        'service_id': 'svc123'
    })
    assert rv.status_code == 400
    assert rv.json['success'] is False


# --- USER & ADMIN API ---


def test_get_user_ok(client, mock_db):
    mock_db.get_student_by_tg_id.return_value = {'id': 1, 'current_points': 500}
    rv = client.get('/api/user/123')
    assert rv.status_code == 200
    assert rv.json['current_points'] == 500


def test_admin_stats_no_access(client, mock_db):
    mock_db.get_student_by_tg_id.return_value = {'id': 1, 'role': 'student'}
    rv = client.get('/api/admin/stats?user_id=123')
    assert rv.status_code == 403
    assert 'No access' in rv.json['error']


def test_admin_grant_points_ok(client, mock_db):
    mock_db.get_student_by_tg_id.side_effect = [
        {'id': 1, 'role': 'admin'},
        {'id': 2, 'current_points': 500}
    ]
    mock_db.add_points.return_value = True

    rv = client.post('/api/admin/grant_points', json={
        'admin_id': 123,
        'target_user_id': 456,  # ← Число, не строка!
        'amount': 100
    })

    assert rv.status_code == 200
    assert rv.json['success'] is True


def test_reset_all_data_ok(client, mock_db):
    mock_db.reset_all_data.return_value = (True, 'Всё сброшено')
    rv = client.post('/api/admin/reset_all_data', json={
        'user_id': 123
    })
    assert rv.status_code == 200
    assert rv.json['success'] is True