import redis

# Redis setup, used to share global data across all workers & connected clients
redis_client = redis.Redis(host='localhost', port=6379, db=0)

# Get crosshair state
def get_crosshair():
    if redis_client.get('crosshair') is None:
        redis_client.set('crosshair', int(False)) # Set default value
    return int(redis_client.get('crosshair'))

# Set crosshair state
def set_crosshair(value):
    redis_client.set('crosshair', int(value))

# Get laser state
def get_laser():
    if redis_client.get('laser') is None:
        redis_client.set('laser', int(False)) # Set default value
    return int(redis_client.get('laser'))

# Set laser state
def set_laser(value):
    redis_client.set('laser', int(value))
