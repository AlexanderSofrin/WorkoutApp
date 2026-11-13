import os
import subprocess
from datetime import datetime

os.makedirs("backups", exist_ok=True)
timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
backup_file = f"backups/workout_vault_{timestamp}.sql"

cmd = [
    "docker", "exec", "workout_vault_db",
    "pg_dump", "-U", "postgres", "-d", "workout_vault"
]

with open(backup_file, "w", encoding="utf-8") as f:
    subprocess.run(cmd, stdout=f, check=True)

print(f"УСПЕХ! Резервная копия базы сохранена в файл: {backup_file}")
