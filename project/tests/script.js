import http from 'k6/http';
import { check, sleep } from 'k6';

export let options = {
  stages: [
    { duration: '10s', target: 100  },   // разогрев: 100 VUs
    { duration: '20s', target: 300  },   // 300 VUs — стабильная нагрузка
    { duration: '20s', target: 600  },   // 600 VUs — средняя нагрузка
    { duration: '20s', target: 1000 },   // 1000 VUs — высокая нагрузка
    { duration: '20s', target: 1500 },   // 1500 VUs — начало подвисания
  ],
  thresholds: {
    'http_req_duration': ['p(95) < 500'],   // 95% запросов быстрее 500 мс
    'http_req_failed': ['rate == 0.00'],    // 0% ошибок
  },
};

export default function () {
  // Замени на свой реальный адрес и порт
  let res = http.get('http://localhost:8000/api/auctions');

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response time < 500ms': (r) => r.timings.duration < 500,
  });

  // Плавная нагрузка
  sleep(0.05);  // 50 мс пауза на виртуального юзера
}