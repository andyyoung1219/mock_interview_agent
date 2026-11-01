
print("[1] Python 程式開始執行", flush=True)

import os
from dotenv import load_dotenv

print("[2] 開始載入 Gemini SDK", flush=True)

from google import genai
from google.genai import types

print("[3] SDK 載入成功", flush=True)

load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
model_name = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")

if not api_key:
    raise RuntimeError("找不到 GEMINI_API_KEY")

print(f"[4] API Key 已讀取，模型：{model_name}", flush=True)

client = genai.Client(
    api_key=api_key,
    http_options=types.HttpOptions(
        timeout=15000,
        retry_options=types.HttpRetryOptions(attempts=1)
    )
)

print("[5] Client 建立成功，開始呼叫 API...", flush=True)

try:
    response = client.models.generate_content(
        model=model_name,
        contents="請用繁體中文簡單說你好。"
    )

    print("[6] API 呼叫成功", flush=True)
    print(response.text, flush=True)

except Exception as e:
    print("[ERROR] API 呼叫失敗", flush=True)
    print(type(e).__name__, str(e), flush=True)

finally:
    client.close()
