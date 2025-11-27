from redis import Redis
from rq import Worker
import os

REDIS_HOST = os.getenv("REDIS_HOST")
REDIS_PORT = int(os.getenv("REDIS_PORT"))

def start_worker():
    print(f"Starting RQ Worker, connecting to Redis at {REDIS_HOST}...")

    redis_conn = Redis(host=REDIS_HOST, port=REDIS_PORT)

    try:
        worker = Worker(['default'], connection=redis_conn) 
        worker.work()
    except Exception as e:
        print(f"Error connecting to Redis: {e}")

if __name__ == '__main__':
    start_worker()