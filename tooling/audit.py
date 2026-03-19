from datetime import datetime

def log_event(user, action):
    with open("audit.log", "a") as f:
        f.write(f"{datetime.now()} | {user} | {action}\n")
