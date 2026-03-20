import json
from datetime import datetime

def log_event(user, action, data=None):

    record = {
        "timestamp": datetime.utcnow().isoformat(),
        "user": user,
        "action": action,
        "data": data
    }

    with open("audit.log", "a") as f:
        f.write(json.dumps(record) + "\n")
