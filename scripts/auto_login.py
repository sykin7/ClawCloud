import base64
import os
import re
import sys
import time
from urllib.parse import urlparse
import requests
from playwright.sync_api import sync_playwright

LOGIN_ENTRY_URL = "https://console.run.claw.cloud"
SIGNIN_URL = f"{LOGIN_ENTRY_URL}/signin"
DEVICE_VERIFY_WAIT = 60
TWO_FACTOR_WAIT = int(os.environ.get("TWO_FACTOR_WAIT", "120"))

class Telegram:
    def __init__(self):
        self.token = os.environ.get('TG_BOT_TOKEN')
        self.chat_id = os.environ.get('TG_CHAT_ID')
        self.ok = bool(self.token and self.chat_id)
    
    def send(self, msg):
        if not self.ok: return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=30
            )
        except: pass
    
    def photo(self, path, caption=""):
        if not self.ok or not os.path.exists(path): return
        try:
            with open(path, 'rb') as f:
                requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"photo": f},
                    timeout=60
                )
        except: pass
    
    def flush_updates(self):
        if not self.ok: return 0
        try:
            r = requests.get(f"https://api.telegram.org/bot{self.token}/getUpdates", params={"timeout": 0}, timeout=10)
            data = r.json()
            if data.get("ok") and data.get("result"):
                return data["result"][-1]["update_id"] + 1
        except: pass
        return 0
    
    def wait_code(self, timeout=120):
        if not self.ok: return None
        offset = self.flush_updates()
        deadline = time.time() + timeout
        pattern = re.compile(r"^/code\s+(\d{6,8})$")
        while time.time() < deadline:
            try:
                r = requests.get(
                    f"https://api.telegram.org/bot{self.token}/getUpdates",
                    params={"timeout": 20, "offset": offset},
                    timeout=30
                )
                data = r.json()
                if not data.get("ok"):
                    time.sleep(5)
                    continue
                for upd in data.get("result", []):
                    offset = upd["update_id"] + 1
                    msg = upd.get("message") or {}
                    if str(msg.get("chat", {}).get("id")) != str(self.chat_id): continue
                    text = (msg.get("text") or "").strip()
                    m = pattern.match(text)
                    if m: return m.group(1)
            except: time.sleep(5)
        return None

class SecretUpdater:
    def __init__(self):
        self.token = os.environ.get('REPO_TOKEN')
        self.repo = os.environ.get('GITHUB_REPOSITORY')
        self.ok = bool(self.token and self.repo)
    
    def update(self, name, value):
        if not self.ok: return False
        try:
            from nacl import encoding, public
            headers = {"Authorization": f"token {self.token}", "Accept": "application/vnd.github.v3+json"}
            r = requests.get(f"https://api.github.com/repos/{self.repo}/actions/secrets/public-key", headers=headers, timeout=30)
            if r.status_code != 200: return False
            key_data = r.json()
            pk = public.PublicKey(key_data['key'].encode(), encoding.Base64Encoder())
            encrypted = public.SealedBox(pk).encrypt(value.encode())
            r = requests.put(
                f"https://api.github.com/repos/{self.repo}/actions/secrets/{name}",
                headers=headers,
                json={"encrypted_value": base64.b64encode(encrypted).decode(), "key_id": key_data['key_id']},
                timeout=30
            )
            return r.status_code in [201, 204]
        except: return False

class AutoLogin:
    def __init__(self):
        self.username = os.environ.get('GH_USERNAME')
        self.password = os.environ.get('GH_PASSWORD')
        self.gh_session = os.environ.get('GH_SESSION', '').strip()
        self.tg = Telegram()
        self.secret = SecretUpdater()
        self.shots, self.logs, self.n = [], [], 0
        self.detected_region = None
    
    def log(self, msg, level="INFO"):
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "STEP": "🔹"}
        line = f"{icons.get(level, '•')} {msg}"
        print(line)
        self.logs.append(line)
    
    def shot(self, page, name):
        self.n += 1
        f = f"{self.n:02d}_{name}.png"
        try:
            page.screenshot(path=f)
            self.shots.append(f)
        except: pass
        return f
    
    def handle_github_auth(self, page):
        self.log("进入 GitHub 认证流程", "STEP")
        try:
            if page.locator('input[name="login"]').is_visible(timeout=5000):
                page.locator('input[name="login"]').fill(self.username)
                page.locator('input[name="password"]').fill(self.password)
                page.locator('input[type="submit"], button[type="submit"]').first.click()
                time.sleep(5)
            
            if "device-verification" in page.url or "verified-device" in page.url:
                self.tg.send("📲 触发设备锁，请在邮件或 App 确认批准")
                for _ in range(DEVICE_VERIFY_WAIT):
                    if "device" not in page.url: break
                    time.sleep(2)
                    page.reload()
            
            if "two-factor" in page.url:
                self.shot(page, "2fa_prompt")
                self.tg.send("🔐 需要 2FA 验证码，请回复 /code 123456")
                code = self.tg.wait_code(timeout=TWO_FACTOR_WAIT)
                if code:
                    otp_input = page.locator('input[autocomplete="one-time-code"], input#app_totp, input#otp').first
                    otp_input.fill(code)
                    page.keyboard.press("Enter")
                    time.sleep(5)
            return True
        except Exception as e:
            self.log(f"GitHub 认证失败: {str(e)}", "ERROR")
            return False

    def run(self):
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'])
            context = browser.new_context(viewport={'width': 1280, 'height': 720})
            if self.gh_session:
                context.add_cookies([{'name': 'user_session', 'value': self.gh_session, 'domain': '.github.com', 'path': '/'}])
            
            page = context.new_page()
            try:
                self.log(f"访问入口: {SIGNIN_URL}")
                page.goto(SIGNIN_URL, timeout=60000)
                
                gh_btn = page.locator('button:has-text("GitHub"), [data-provider="github"]').first
                gh_btn.click()
                
                page.wait_for_load_state("networkidle")
                
                if "github.com" in page.url:
                    if "oauth/authorize" in page.url:
                        page.locator('button[name="authorize"]').click()
                    else:
                        self.handle_github_auth(page)
                
                page.wait_for_url(lambda u: "claw.cloud" in u and "signin" not in u.lower(), timeout=60000)
                
                current_url = page.url
                self.detected_region = urlparse(current_url).netloc.split('.')[0]
                self.log(f"登录成功，当前区域: {self.detected_region}", "SUCCESS")
                
                page.goto(f"{LOGIN_ENTRY_URL}/", timeout=30000)
                time.sleep(2)
                self.shot(page, "dashboard")
                
                new_session = next((c['value'] for c in context.cookies() if c['name'] == 'user_session'), None)
                if new_session and new_session != self.gh_session:
                    if self.secret.update("GH_SESSION", new_session):
                        self.tg.send(f"✅ 保活成功 [区域: {self.detected_region}]\n🔑 Session 已自动更新")
                    else:
                        self.tg.send(f"⚠️ 保活成功，但更新 Secret 失败，请手动检查 REPO_TOKEN")
                else:
                    self.tg.send(f"✅ 保活成功 [区域: {self.detected_region}]\nℹ️ Session 仍然有效")
                
            except Exception as e:
                self.log(f"执行异常: {str(e)}", "ERROR")
                self.shot(page, "error_state")
                self.tg.photo(self.shots[-1], f"❌ 保活任务失败\n错误信息: {str(e)}")
            finally:
                browser.close()

if __name__ == "__main__":
    AutoLogin().run()
