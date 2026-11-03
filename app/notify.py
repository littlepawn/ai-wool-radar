"""Push module: one common interface send(title, body, url).

All channels are configured ONLY via environment variables; no token/key is
hard-coded here or in .env.example (placeholders only). Each channel is its
own small function; a failure in one channel never blocks the others.

Dry-run: --dry-run prints what WOULD be sent (with secrets masked) and
sends nothing. This is the safe way to test a new channel.

Usage:
    python3 -m app.notify --dry-run --title "标题" --body "内容" --url "https://example.com"
    python3 -m app.notify --dry-run --only bark,telegram --title "t" --body "b"
    NOTIFY_DRY_RUN=1 python3 app/check.py   # checker uses dry-run too

Python stdlib only.
"""
import argparse
import base64
import hashlib
import hmac
import json
import os
import smtplib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage


def _mask(s):
    """Mask a secret for logs: keep at most a hint of its shape, never the value."""
    if not s:
        return ""
    s = str(s)
    if len(s) <= 8:
        return "***"
    return s[:3] + "***" + s[-2:]


def _post(url, payload, headers=None, timeout=10):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/json", **(headers or {})})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()[:500].decode("utf-8", "replace")


def _form(url, fields, timeout=10):
    data = urllib.parse.urlencode(fields).encode("utf-8")
    req = urllib.request.Request(url, data=data,
                                 headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.status, resp.read()[:500].decode("utf-8", "replace")


def _result(channel, ok, detail, dry_run=False):
    return {"channel": channel, "ok": bool(ok), "detail": detail, "dry_run": dry_run}


def bark(title, body, url, dry_run=False):
    base = os.environ.get("BARK_URL") or ""
    if not base:
        key = os.environ.get("BARK_KEY")
        server = os.environ.get("BARK_SERVER", "https://api.day.app")
        base = f"{server.rstrip('/')}/{key}" if key else ""
    if not base:
        return _result("bark", False, "not configured (BARK_URL or BARK_KEY)", dry_run)
    payload = {"title": title, "body": body, "url": url}
    if dry_run:
        return _result("bark", True, f"POST {_mask(base)} payload={payload}", dry_run)
    try:
        return _result("bark", True, str(_post(base, payload)), dry_run)
    except Exception as e:
        return _result("bark", False, str(e), dry_run)


def serverchan(title, body, url, dry_run=False):
    key = os.environ.get("SCT_SENDKEY", "")
    if not key:
        return _result("serverchan", False, "not configured (SCT_SENDKEY)", dry_run)
    payload = {"title": title, "desp": f"{body}\n\n{url or ''}"}
    if dry_run:
        return _result("serverchan", True, f"POST sctapi.ftqq.com/{_mask(key)}.send payload={payload}", dry_run)
    try:
        return _result("serverchan", True, str(_post(f"https://sctapi.ftqq.com/{key}.send", payload)), dry_run)
    except Exception as e:
        return _result("serverchan", False, str(e), dry_run)


def pushplus(title, body, url, dry_run=False):
    token = os.environ.get("PUSHPLUS_TOKEN", "")
    if not token:
        return _result("pushplus", False, "not configured (PUSHPLUS_TOKEN)", dry_run)
    payload = {"token": token, "title": title, "content": f"{body}\n\n{url or ''}", "template": "html"}
    if dry_run:
        return _result("pushplus", True, f"POST pushplus.plus/send payload=token={_mask(token)} title={title}", dry_run)
    try:
        return _result("pushplus", True, str(_post("https://www.pushplus.plus/send", payload)), dry_run)
    except Exception as e:
        return _result("pushplus", False, str(e), dry_run)


def wecom(title, body, url, dry_run=False):
    hook = os.environ.get("WECOM_WEBHOOK_URL", "")
    if not hook:
        return _result("wecom", False, "not configured (WECOM_WEBHOOK_URL)", dry_run)
    payload = {"msgtype": "markdown", "markdown": {"content": f"## {title}\n{body}\n{url or ''}"}}
    if dry_run:
        return _result("wecom", True, f"POST {_mask(hook)} payload={payload}", dry_run)
    try:
        return _result("wecom", True, str(_post(hook, payload)), dry_run)
    except Exception as e:
        return _result("wecom", False, str(e), dry_run)


def _sign(secret, timestamp):
    msg = f"{timestamp}\n{secret}".encode("utf-8")
    return urllib.parse.quote_plus(base64.b64encode(
        hmac.new(secret.encode("utf-8"), msg, hashlib.sha256).digest()).decode())


def dingtalk(title, body, url, dry_run=False):
    hook = os.environ.get("DINGTALK_WEBHOOK_URL", "")
    secret = os.environ.get("DINGTALK_SECRET", "")
    if not hook:
        return _result("dingtalk", False, "not configured (DINGTALK_WEBHOOK_URL)", dry_run)
    ts = str(int(time.time() * 1000))
    final = hook + (f"&timestamp={ts}&sign={_sign(secret, ts)}" if secret else "")
    payload = {"msgtype": "markdown", "markdown": {"title": title, "text": f"## {title}\n{body}\n{url or ''}"}}
    if dry_run:
        return _result("dingtalk", True, f"POST {_mask(hook)} signed={bool(secret)} payload={payload}", dry_run)
    try:
        return _result("dingtalk", True, str(_post(final, payload)), dry_run)
    except Exception as e:
        return _result("dingtalk", False, str(e), dry_run)


def feishu(title, body, url, dry_run=False):
    hook = os.environ.get("FEISHU_WEBHOOK_URL", "")
    secret = os.environ.get("FEISHU_SECRET", "")
    if not hook:
        return _result("feishu", False, "not configured (FEISHU_WEBHOOK_URL)", dry_run)
    ts = str(int(time.time()))
    payload = {"msg_type": "text", "content": {"text": f"{title}\n{body}\n{url or ''}"}}
    if secret:
        # Feishu 签名约定：以 "timestamp\nsecret" 为 key，对空串做 HMAC-SHA256。
        sig = base64.b64encode(hmac.new(f"{ts}\n{secret}".encode(),
                                        b"", hashlib.sha256).digest()).decode()
        payload["sign"] = sig
    if dry_run:
        return _result("feishu", True, f"POST {_mask(hook)} signed={bool(secret)} payload_text={title}", dry_run)
    try:
        return _result("feishu", True, str(_post(hook, payload)), dry_run)
    except Exception as e:
        return _result("feishu", False, str(e), dry_run)


def telegram(title, body, url, dry_run=False):
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "")
    chat = os.environ.get("TELEGRAM_CHAT_ID", "")
    if not token or not chat:
        return _result("telegram", False, "not configured (TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID)", dry_run)
    payload = {"chat_id": chat, "text": f"{title}\n{body}\n{url or ''}"}
    if dry_run:
        return _result("telegram", True, f"POST api.telegram.org/bot{_mask(token)}/sendMessage payload={payload}", dry_run)
    try:
        return _result("telegram", True, str(_post(f"https://api.telegram.org/bot{token}/sendMessage", payload)), dry_run)
    except Exception as e:
        return _result("telegram", False, str(e), dry_run)


def ntfy(title, body, url, dry_run=False):
    topic_url = os.environ.get("NTFY_URL", "")
    if not topic_url:
        return _result("ntfy", False, "not configured (NTFY_URL)", dry_run)
    headers = {"Title": title}
    token = os.environ.get("NTFY_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if dry_run:
        return _result("ntfy", True, f"POST {_mask(topic_url)} headers=Title + auth={bool(token)} body={body} {url or ''}", dry_run)
    try:
        data = f"{body}\n{url or ''}".encode("utf-8")
        req = urllib.request.Request(topic_url, data=data, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            return _result("ntfy", True, str(resp.status), dry_run)
    except Exception as e:
        return _result("ntfy", False, str(e), dry_run)


def gotify(title, body, url, dry_run=False):
    base = os.environ.get("GOTIFY_URL", "")
    token = os.environ.get("GOTIFY_TOKEN", "")
    if not base or not token:
        return _result("gotify", False, "not configured (GOTIFY_URL/GOTIFY_TOKEN)", dry_run)
    payload = {"title": title, "message": f"{body}\n{url or ''}", "priority": 5}
    if dry_run:
        return _result("gotify", True, f"POST {_mask(base)}/message?token={_mask(token)} payload={payload}", dry_run)
    try:
        return _result("gotify", True, str(_post(f"{base.rstrip('/')}/message?token={token}", payload)), dry_run)
    except Exception as e:
        return _result("gotify", False, str(e), dry_run)


def discord(title, body, url, dry_run=False):
    hook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not hook:
        return _result("discord", False, "not configured (DISCORD_WEBHOOK_URL)", dry_run)
    payload = {"content": f"**{title}**\n{body}\n{url or ''}"}
    if dry_run:
        return _result("discord", True, f"POST {_mask(hook)} payload={payload}", dry_run)
    try:
        return _result("discord", True, str(_post(hook, payload)), dry_run)
    except Exception as e:
        return _result("discord", False, str(e), dry_run)


def slack(title, body, url, dry_run=False):
    hook = os.environ.get("SLACK_WEBHOOK_URL", "")
    if not hook:
        return _result("slack", False, "not configured (SLACK_WEBHOOK_URL)", dry_run)
    payload = {"text": f"*{title}*\n{body}\n{url or ''}"}
    if dry_run:
        return _result("slack", True, f"POST {_mask(hook)} payload={payload}", dry_run)
    try:
        return _result("slack", True, str(_post(hook, payload)), dry_run)
    except Exception as e:
        return _result("slack", False, str(e), dry_run)


def email_smtp(title, body, url, dry_run=False):
    host = os.environ.get("SMTP_HOST", "")
    to = os.environ.get("SMTP_TO", "")
    if not host or not to:
        return _result("email", False, "not configured (SMTP_HOST/SMTP_TO)", dry_run)
    if dry_run:
        return _result("email", True, f"SMTP {host}:{os.environ.get('SMTP_PORT', '587')} "
                                       f"from={_mask(os.environ.get('SMTP_FROM', ''))} to={to} subject={title}", dry_run)
    try:
        msg = EmailMessage()
        msg["Subject"] = title
        msg["From"] = os.environ.get("SMTP_FROM", os.environ.get("SMTP_USER", ""))
        msg["To"] = to
        msg.set_content(f"{body}\n\n{url or ''}")
        port = int(os.environ.get("SMTP_PORT", "587"))
        with smtplib.SMTP(host, port, timeout=10) as s:
            if os.environ.get("SMTP_TLS", "true").lower() == "true":
                s.starttls()
            user = os.environ.get("SMTP_USER", "")
            if user:
                s.login(user, os.environ.get("SMTP_PASS", ""))
            s.send_message(msg)
        return _result("email", True, "sent", dry_run)
    except Exception as e:
        return _result("email", False, str(e), dry_run)


def webhook(title, body, url, dry_run=False):
    hook = os.environ.get("WEBHOOK_URL", "")
    if not hook:
        return _result("webhook", False, "not configured (WEBHOOK_URL)", dry_run)
    payload = {"title": title, "body": body, "url": url}
    headers = {}
    token = os.environ.get("WEBHOOK_TOKEN", "")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if dry_run:
        return _result("webhook", True, f"POST {_mask(hook)} auth={bool(token)} payload={payload}", dry_run)
    try:
        return _result("webhook", True, str(_post(hook, payload, headers)), dry_run)
    except Exception as e:
        return _result("webhook", False, str(e), dry_run)


def wxpusher(title, body, url, dry_run=False):
    token = os.environ.get("WXPUSHER_APP_TOKEN", "")
    uids = os.environ.get("WXPUSHER_UIDS", "")
    if not token or not uids:
        return _result("wxpusher", False, "not configured (WXPUSHER_APP_TOKEN/WXPUSHER_UIDS)", dry_run)
    payload = {"appToken": token, "summary": title,
               "content": f"{body}\n\n{url or ''}", "contentType": 1,
               "uids": [u.strip() for u in uids.split(",") if u.strip()]}
    if dry_run:
        return _result("wxpusher", True, f"POST wxpusher.cn/api/send/message appToken={_mask(token)} uids={len(payload['uids'])} title={title}", dry_run)
    try:
        return _result("wxpusher", True, str(_post("https://wxpusher.cn/api/send/message", payload)), dry_run)
    except Exception as e:
        return _result("wxpusher", False, str(e), dry_run)


def pushdeer(title, body, url, dry_run=False):
    key = os.environ.get("PUSHDEER_KEY", "")
    server = os.environ.get("PUSHDEER_SERVER", "https://api2.pushdeer.com")
    if not key:
        return _result("pushdeer", False, "not configured (PUSHDEER_KEY)", dry_run)
    if dry_run:
        return _result("pushdeer", True, f"POST {server}/message/push pushkey={_mask(key)} text={title} desp={body} {url or ''}", dry_run)
    try:
        return _result("pushdeer", True, str(_form(f"{server.rstrip('/')}/message/push",
                                                   {"pushkey": key, "text": title,
                                                    "desp": f"{body}\n\n{url or ''}", "type": "markdown"})), dry_run)
    except Exception as e:
        return _result("pushdeer", False, str(e), dry_run)


CHANNELS = {
    "bark": bark, "serverchan": serverchan, "pushplus": pushplus,
    "wecom": wecom, "dingtalk": dingtalk, "feishu": feishu,
    "telegram": telegram, "ntfy": ntfy, "gotify": gotify,
    "discord": discord, "slack": slack, "email": email_smtp,
    "webhook": webhook, "wxpusher": wxpusher, "pushdeer": pushdeer,
}


def send(title, body, url=None, only=None, dry_run=False):
    """Send via every configured channel (or `only` subset). One failure never blocks others."""
    results = []
    names = only or list(CHANNELS)
    for name in names:
        fn = CHANNELS.get(name)
        if fn is None:
            results.append(_result(name, False, "unknown channel", dry_run))
            continue
        try:
            results.append(fn(title, body, url, dry_run=dry_run))
        except Exception as e:  # last-resort isolation
            results.append(_result(name, False, f"unexpected: {e}", dry_run))
    return results


def main(argv=None):
    p = argparse.ArgumentParser(description="Push a notification via configured channels.")
    p.add_argument("--title", required=True)
    p.add_argument("--body", default="")
    p.add_argument("--url", default="")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--only", default="", help="comma-separated channel names, e.g. bark,telegram")
    args = p.parse_args(argv)
    only = [x.strip() for x in args.only.split(",") if x.strip()] or None
    for r in send(args.title, args.body, args.url or None, only=only, dry_run=args.dry_run):
        print(f"[{r['channel']}] ok={r['ok']} dry_run={r['dry_run']} :: {r['detail']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
