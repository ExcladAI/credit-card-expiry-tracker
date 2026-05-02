import os
import signal
import subprocess
import sys
import time


def main():
    port = os.getenv("APP_PORT", os.getenv("STREAMLIT_PORT", "8502"))
    processes = [
        subprocess.Popen([sys.executable, "bot.py"]),
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
    ]

    def stop_all(*_):
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()

    signal.signal(signal.SIGTERM, stop_all)
    signal.signal(signal.SIGINT, stop_all)

    try:
        while True:
            for proc in processes:
                code = proc.poll()
                if code is not None:
                    stop_all()
                    return code
            time.sleep(1)
    finally:
        stop_all()


if __name__ == "__main__":
    raise SystemExit(main())
