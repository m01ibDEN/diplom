from diagrams import Diagram, Edge
from diagrams.custom import Custom
from diagrams.programming.language import Python
from diagrams.aws.storage import Database
from diagrams.aws.integration import SQS
from diagrams.onprem.client import User
from diagrams.onprem.network import Nginx
from diagrams.onprem.queue import Kafka

with Diagram(
    "Архитектура Telegram Mini App",
    show=False,
    direction="LR",
    filename="telegram_miniapp_arch",
    outformat="png",
    graph_attr={
        "fontsize": "24",         # Глобальный размер шрифта
        "fontname": "Arial",
        "nodesep": "0.8",
        "ranksep": "0.7"
    }
):
    # Компоненты
    client = User("Клиентская часть\nTelegram Mini App")
    sdk = Custom("Сторонние сервисы\nSDK", "./icons/thirdparty.png")  # можно иконку, или просто текст
    api_gateway = Nginx("Flask REST API\n(JSON + X-API-Key)")
    
    # Эндпоинты
    endpoints = Python("Эндпоинты:\n/api/user & admin\n/api/merch\n/api/auctions\n/api/services\n/api/sdk")
    
    db = Database("MySQL 3NF")
    scheduler = SQS("APScheduler\nРегулярные фоновые\nпополнения")
    
    # Связи
    client >> Edge(label="HTTPS") >> api_gateway
    sdk >> Edge(label="вызовы") >> api_gateway
    api_gateway >> Edge(label="обработка") >> endpoints
    endpoints >> Edge(label="CRUD") >> db
    scheduler >> Edge(label="триггер") >> db
    
    # Дополнительно: фоновая задача может обновлять кэш или вызывать API
    scheduler >> Edge(label="обновление") >> endpoints