import platform
from datetime import datetime

print("Привет, Никита! 🚀 Git установлен и работает.")
print(f"Python: {platform.python_version()} | ОС: {platform.system()} {platform.release()}")
print(f"Время: {datetime.now():%Y-%m-%d %H:%M:%S}")

# добавь в конец файла (простой вариант)
from pathlib import Path

p = Path("logs")
p.mkdir(exist_ok=True)
Path("logs/env.txt").write_text(f"Python version log\n")
print("Лог записан в:", (p / "env.txt").resolve())
