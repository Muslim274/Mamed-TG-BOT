#!/usr/bin/env python3
import os, sys, json, webbrowser
from pathlib import Path
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]

def main():
    secret_path = (
        sys.argv[1] if len(sys.argv) > 1
        else input("Введите путь к client_secret_*.json: ").strip()
    )
    if not Path(secret_path).is_file():
        sys.exit("❌ Файл не найден.")

    flow = InstalledAppFlow.from_client_secrets_file(secret_path, SCOPES)

    try:
        creds = flow.run_local_server(port=0)
    except (webbrowser.Error, OSError):
        print("⚠️  Браузер недоступен — включаю режим console…")
        if hasattr(flow, "run_console"):                   # новая библиотека
            creds = flow.run_console()
        else:                                             # очень старая версия
            auth_url, _ = flow.authorization_url(prompt="consent")
            print(f"\n➡ Перейдите по ссылке и дайте доступ:\n{auth_url}\n")
            code = input("Введите код подтверждения: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials

    # --- было ---
    # Path("token.json").write_text(json.dumps(creds_dict))

    # --- стало ---          # ← ИЗМЕНЕНО
    with open("token.json", "w") as f:  # ← ИЗМЕНЕНО
        f.write(creds.to_json())        # ← ИЗМЕНЕНО
    print("✅ token.json успешно создан/обновлён.")

if __name__ == "__main__":
    main()
