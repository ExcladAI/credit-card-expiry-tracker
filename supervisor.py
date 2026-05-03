import os
import signal
import subprocess
import sys
import time

from dotenv import load_dotenv


load_dotenv()


def should_start_bot():
    setting = os.getenv("RUN_BOT", "auto").strip().lower()
    if setting in {"0", "false", "no", "off"}:
        return False
    if setting in {"1", "true", "yes", "on"}:
        return True
    return bool(os.getenv("TELEGRAM_BOT_TOKEN") and os.getenv("TELEGRAM_CHAT_ID"))


def is_bot_required():
    setting = os.getenv("RUN_BOT_REQUIRED", "false").strip().lower()
    return setting in {"1", "true", "yes", "on"}


def main():
    port = os.getenv("APP_PORT", os.getenv("STREAMLIT_PORT", "8502"))
    processes = []
    bot_required = is_bot_required()

    if should_start_bot():
        processes.append(("bot", subprocess.Popen([sys.executable, "bot.py"])))
    else:
        print("Telegram bot disabled; starting web dashboard only.", flush=True)

    processes.append((
        "api",
        subprocess.Popen([
            sys.executable,
            "-m",
            "uvicorn",
            "api:app",
            "--host",
            "0.0.0.0",
            "--port",
            port,
        ]),
    ))

    def stop_all(*_):
        for _, proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for _, proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)

    try:
        while True:
            for name, proc in processes:
                code = proc.poll()
                if code is not None:
                    if name == "bot" and not bot_required:
                        print(f"bot process exited with code {code}; web dashboard will keep running.", flush=True)
                        processes.remove((name, proc))
                        continue
                    print(f"{name} process exited with code {code}; stopping.", flush=True)
                    stop_all()
                    return code
            time.sleep(1)
    finally:
        stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
