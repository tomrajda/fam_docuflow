from redis import Redis
from rq import Worker # Importujemy tylko Worker
import os

REDIS_HOST = os.getenv("REDIS_HOST", "redis")

def start_worker():
    print(f"[*] Starting RQ Worker, connecting to Redis at {REDIS_HOST}...")

    redis_conn = Redis(host=REDIS_HOST, port=6379)

    try:
        # Worker przyjmuje połączenie bezpośrednio
        worker = Worker(['default'], connection=redis_conn) 
        worker.work()
    except Exception as e:
        print(f"[!] Error connecting to Redis: {e}")

if __name__ == '__main__':
    start_worker()