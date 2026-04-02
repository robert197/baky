import multiprocessing
import os

# Bind
bind = "0.0.0.0:8000"

# Workers
workers = int(os.environ.get("WEB_CONCURRENCY", multiprocessing.cpu_count() * 2 + 1))
worker_class = "gthread"
threads = 4
worker_tmp_dir = "/dev/shm"

# Timeouts
timeout = 30
graceful_timeout = 30
keepalive = 5

# Memory leak protection (important: WeasyPrint/Pillow can leak)
max_requests = 1000
max_requests_jitter = 50

# Logging
accesslog = "-"
errorlog = "-"
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "info")

# Reverse proxy
forwarded_allow_ips = "*"

# Preload for memory sharing via copy-on-write
preload_app = True
