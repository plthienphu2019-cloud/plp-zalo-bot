# -*- coding: utf-8 -*-
# PLP ZALO BOT — Webhook + Web Admin gửi tin về nhóm
from __future__ import annotations
import os, json, time, threading, logging
from flask import Flask, request, jsonify, render_template_string, redirect, url_for
import requests

# ============================================================
# CẤU HÌNH — SỬA Ở ĐÂY HOẶC DÙNG ENV VAR TRÊN RENDER
# ============================================================
BOT_TOKEN      = os.environ.get("540134130817105426", "DÁN_BOT_TOKEN_VÀO_ĐÂY")
ADMIN_PASS     = os.environ.get("ADMIN_PASS", "plp2026")
WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "plptool-update2026")
DEFAULT_CHAT_ID= os.environ.get("DEFAULT_CHAT_ID", "")   # có thể để trống, bot sẽ tự học khi vào nhóm
ZALO_API       = f"https://bot-api.zaloplatforms.com/bot{BOT_TOKEN}"

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("plp-zalo")

# ============================================================
# STATE — lưu tạm trong RAM (đủ cho use case đơn giản)
# ============================================================
STATE = {
    "chat_id": DEFAULT_CHAT_ID or None,   # ID nhóm Zalo
    "chat_title": "PLP TOOL",                     # tên nhóm
    "last_update": None,                  # raw update cuối
    "history": [],                        # [{ts, text, ok, chat_id}]
}

# ============================================================
# ZALO API
# ============================================================
def send_zalo(chat_id: str, text: str) -> dict:
    """Gửi tin nhắn đến chat_id qua Zalo Bot API."""
    try:
        r = requests.post(
            f"{ZALO_API}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10,
        )
        try:    data = r.json()
        except: data = {"raw": r.text}
        ok = r.status_code == 200 and (data.get("ok") is True or "result" in data)
        # ghi log
        STATE["history"].append({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chat_id": chat_id, "text": text, "ok": ok,
        })
        STATE["history"] = STATE["history"][-100:]
        return {"ok": ok, "status": r.status_code, "data": data}
    except Exception as e:
        log.error(f"send_zalo error: {e}")
        STATE["history"].append({
            "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
            "chat_id": chat_id, "text": text, "ok": False,
        })
        return {"ok": False, "error": str(e)}

# ============================================================
# WEBHOOK — Zalo gọi vào khi có tin trong nhóm
# ============================================================
@app.route("/webhook", methods=["POST", "GET"])
def webhook():
    if request.method == "GET":
        return "PLP Zalo Webhook OK", 200

    # xác thực secret (Zalo gửi kèm header nếu bạn đã set Secret Token)
    secret = request.headers.get("X-Bot-Api-Secret-Token", "")
    if WEBHOOK_SECRET and secret and secret != WEBHOOK_SECRET:
        log.warning("Webhook sai secret")
        return jsonify({"ok": False, "error": "invalid secret"}), 401

    try:
        data = request.get_json(silent=True) or {}
        STATE["last_update"] = data
        log.info(f"WEBHOOK: {json.dumps(data, ensure_ascii=False)[:500]}")

        # Bóc update — Zalo có thể bọc trong "result" hoặc "data"
        update = data
        for key in ("result", "data", "update"):
            if isinstance(update, dict) and isinstance(update.get(key), dict):
                update = update[key]
                break
        if isinstance(update, list) and update:
            update = update[0]

        # Lấy chat info
        msg = update.get("message") or update
        chat = msg.get("chat") or {}
        chat_id = chat.get("id") or update.get("chat_id") or update.get("chatId")
        chat_title = chat.get("title") or chat.get("name") or ""

        # Tự học chat_id lần đầu
        if chat_id and chat_id != STATE["chat_id"]:
            STATE["chat_id"] = chat_id
            STATE["chat_title"] = chat_title
            log.info(f"Đã lưu chat_id mới: {chat_id} ({chat_title})")

        return jsonify({"ok": True}), 200
    except Exception as e:
        log.error(f"webhook error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 200

# ============================================================
# WEB ADMIN — gõ tin nhắn + xem trạng thái
# ============================================================
ADMIN_HTML = """
<!DOCTYPE html><html lang="vi"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>PLP ZALO BOT</title>
<style>
*{margin:0;padding:0;box-sizing:border-box;font-family:system-ui,sans-serif}
body{background:#0b1220;color:#eaf2ff;padding:20px;min-height:100vh}
.card{max-width:720px;margin:0 auto 16px;background:#111c33;border:1px solid #1f355e;border-radius:14px;padding:20px}
h1{font-size:22px;margin-bottom:6px;color:#00d4ff}
.sub{color:#7a8ca3;font-size:12px;margin-bottom:14px}
label{display:block;font-size:12px;color:#7a8ca3;margin:10px 0 6px;text-transform:uppercase}
input,textarea{width:100%;padding:12px;background:#0b1220;border:1px solid #1f355e;border-radius:8px;color:#eaf2ff;font-size:14px}
input:focus,textarea:focus{outline:none;border-color:#00d4ff}
button{padding:12px 20px;background:linear-gradient(135deg,#00d4ff,#2563eb);color:#050a14;border:none;border-radius:8px;font-weight:700;cursor:pointer;margin-top:12px;font-size:14px}
button:hover{opacity:.9}
.info{background:#0b1220;padding:12px;border-radius:8px;margin-bottom:12px;font-family:monospace;font-size:12px;line-height:1.6}
.info b{color:#00d4ff}
.ok{color:#00e676}.err{color:#ff4d6d}
.history{margin-top:14px;max-height:300px;overflow-y:auto;font-size:12px}
.history .item{padding:8px;border-bottom:1px solid #1f355e;font-family:monospace}
</style></head><body>

<div class="card">
  <h1>🤖 PLP ZALO BOT</h1>
  <div class="sub">Webhook + Web Admin gửi tin về nhóm</div>

  <div class="info">
    📌 <b>Chat ID:</b> {{ chat_id or "Chưa có — gửi 1 tin vào nhóm để bot tự học" }}<br>
    👥 <b>Nhóm:</b> {{ chat_title or "—" }}<br>
    🔑 <b>Webhook URL:</b> <code>{{ webhook_url }}</code>
  </div>

  <form method="POST" action="/send">
    <label>Nội dung gửi vào nhóm</label>
    <textarea name="text" rows="4" placeholder="VD: 🚀 Tool đã khởi động!"></textarea>
    <button type="submit">📤 GỬI NGAY</button>
  </form>
</div>

<div class="card">
  <h1>📜 Lịch sử gửi (100 gần nhất)</h1>
  <div class="history">
  {% for h in history %}
    <div class="item">
      [{{ h.ts }}] <span class="{{ 'ok' if h.ok else 'err' }}">{{ "✔" if h.ok else "✘" }}</span>
      → {{ h.text }}
    </div>
  {% else %}
    <div class="item">Chưa gửi gì.</div>
  {% endfor %}
  </div>
</div>

<div class="card">
  <h1>🔍 Update cuối từ Zalo</h1>
  <div class="info" style="max-height:300px;overflow:auto">
    <pre>{{ last_update }}</pre>
  </div>
</div>

</body></html>
"""

def _check_admin():
    pw = request.args.get("pw") or request.form.get("pw") or ""
    return pw == ADMIN_PASS

@app.route("/", methods=["GET"])
def home():
    if not _check_admin():
        return f'''
        <body style="background:#0b1220;color:#eaf2ff;font-family:sans-serif;padding:40px;text-align:center">
          <h2>🔐 Nhập mật khẩu admin</h2>
          <form method="get">
            <input name="pw" type="password" placeholder="Mật khẩu"
              style="padding:12px;border-radius:8px;border:1px solid #1f355e;background:#111c33;color:#fff">
            <button style="padding:12px 18px;margin-left:8px;border-radius:8px;border:none;background:#00d4ff;font-weight:700">Vào</button>
          </form>
          <div style="color:#7a8ca3;margin-top:14px;font-size:13px">Mặc định: <b>{ADMIN_PASS}</b></div>
        </body>''', 401

    webhook_url = request.url_root.rstrip("/") + "/webhook"
    return render_template_string(
        ADMIN_HTML,
        chat_id=STATE["chat_id"],
        chat_title=STATE["chat_title"],
        last_update=json.dumps(STATE["last_update"], ensure_ascii=False, indent=2) if STATE["last_update"] else "—",
        history=list(reversed(STATE["history"])),
        webhook_url=webhook_url,
    )

@app.route("/send", methods=["POST"])
def admin_send():
    if not _check_admin():
        return "Unauthorized", 401
    text = (request.form.get("text") or "").strip()
    chat_id = STATE["chat_id"]
    if not chat_id:
        return redirect(url_for("home", pw=ADMIN_PASS) + "&err=no_chat_id")
    if not text:
        return redirect(url_for("home", pw=ADMIN_PASS) + "&err=empty")
    send_zalo(chat_id, text)
    return redirect(url_for("home", pw=ADMIN_PASS))

# ============================================================
# API phụ — gửi tin qua HTTP (dùng từ tool khác nếu cần)
# ============================================================
@app.route("/api/send", methods=["POST"])
def api_send():
    data = request.get_json(silent=True) or {}
    if data.get("secret") != WEBHOOK_SECRET:
        return jsonify({"ok": False, "error": "invalid secret"}), 401
    text = (data.get("text") or "").strip()
    chat_id = data.get("chat_id") or STATE["chat_id"]
    if not text or not chat_id:
        return jsonify({"ok": False, "error": "missing text/chat_id"}), 400
    res = send_zalo(chat_id, text)
    return jsonify(res)

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"ok": True, "time": time.time(), "chat_id": STATE["chat_id"]})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
