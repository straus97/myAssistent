import platform
from datetime import datetime

print("Привет, Никита! 🚀 Git установлен и работает.")
print(f"Python: {platform.python_version()} | ОС: {platform.system()} {platform.release()}")
print(f"Время: {datetime.now():%Y-%m-%d %H:%M:%S}")
