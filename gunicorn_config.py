
# Gunicorn server configuration

# Bind to all network interfaces on port 5000
bind = "0.0.0.0:5000"

# Number of worker processes
workers = 3

# Number of threads per worker
threads = 3

# Request timeout in seconds
timeout = 6000

# Keep-alive connection timeout
keepalive = 65

# Use threaded worker class
worker_class = "gthread"

# Maximum requests before worker restart
max_requests = 3000

# Random jitter to avoid all workers restarting simultaneously
max_requests_jitter = 50

# Logging level
loglevel = "warning"
