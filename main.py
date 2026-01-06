#!/usr/bin/env python3
"""
AlwaysData 自动登录脚本
- 支持多账户 (ACCOUNTS_JSON)
- 邮箱密码登录
- Telegram 通知
"""

import os
import sys
import time
import json
import requests
from playwright.sync_api import sync_playwright

# ==================== 配置 ====================
ALWAYS_DATA_URL = "https://admin.alwaysdata.com"
LOGIN_URL = f"{ALWAYS_DATA_URL}/login/"


class Telegram:
    """Telegram 通知"""
    
    def __init__(self):
        self.token = os.environ.get('TG_BOT_TOKEN')
        self.chat_id = os.environ.get('TG_CHAT_ID')
        self.ok = bool(self.token and self.chat_id)
    
    def send(self, msg):
        if not self.ok:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{self.token}/sendMessage",
                data={"chat_id": self.chat_id, "text": msg, "parse_mode": "HTML"},
                timeout=30
            )
        except:
            pass
    
    def photo(self, path, caption=""):
        if not self.ok or not os.path.exists(path):
            return
        try:
            with open(path, 'rb') as f:
                requests.post(
                    f"https://api.telegram.org/bot{self.token}/sendPhoto",
                    data={"chat_id": self.chat_id, "caption": caption[:1024]},
                    files={"photo": f},
                    timeout=60
                )
        except:
            pass


def mask_email(email):
    """脱敏邮箱"""
    if not email or "@" not in email:
        return email
    try:
        user, domain = email.split("@")
        if len(user) <= 2:
            return f"{user[0]}***@{domain}"
        return f"{user[0]}***{user[-1]}@{domain}"
    except:
        return email


class AutoLogin:
    """自动登录"""
    
    def __init__(self, username, password, index=0):
        self.username = username
        self.password = password
        self.masked_username = mask_email(username)
        self.index = index
        self.tg = Telegram()
        self.shots = []
        self.logs = []
        self.n = 0
        
    def log(self, msg, level="INFO"):
        icons = {"INFO": "ℹ️", "SUCCESS": "✅", "ERROR": "❌", "WARN": "⚠️", "STEP": "🔹"}
        prefix = f"[{self.masked_username}]"
        line = f"{icons.get(level, '•')} {prefix} {msg}"
        print(line)
        self.logs.append(line)
    
    def shot(self, page, name):
        self.n += 1
        f = f"{self.index}_{self.n:02d}_{name}.png"
        try:
            page.screenshot(path=f)
            self.shots.append(f)
        except:
            pass
        return f
    
    def keepalive(self, page):
        """保活"""
        self.log("保活...", "STEP")
        try:
            page.reload(timeout=30000)
            page.wait_for_load_state('networkidle', timeout=15000)
            self.log("已刷新页面", "SUCCESS")
            time.sleep(2)
        except:
            pass
        self.shot(page, "完成")
    
    def notify(self, ok, err=""):
        if not self.tg.ok:
            return
        
        msg = f"""<b>🤖 AlwaysData 自动登录</b>

<b>状态:</b> {"✅ 成功" if ok else "❌ 失败"}
<b>用户:</b> {self.masked_username}
<b>时间:</b> {time.strftime('%Y-%m-%d %H:%M:%S')}"""
        
        if err:
            msg += f"\n<b>错误:</b> {err}"
        
        msg += "\n\n<b>日志:</b>\n" + "\n".join(self.logs[-6:])
        
        self.tg.send(msg)
        
        if self.shots:
            if not ok:
                for s in self.shots[-3:]:
                    self.tg.photo(s, s)
            else:
                self.tg.photo(self.shots[-1], "完成")
    
    def run(self):
        self.log("开始处理...")
        
        if not self.username or not self.password:
            self.log("缺少凭据", "ERROR")
            self.notify(False, "凭据未配置")
            return False
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            page = context.new_page()
            
            try:
                # 1. 访问 AlwaysData 登录页
                self.log("步骤1: 打开 AlwaysData", "STEP")
                page.goto(LOGIN_URL, timeout=60000)
                page.wait_for_load_state('networkidle', timeout=30000)
                time.sleep(2)
                self.shot(page, "login_page")
                
                # 检查是否已经登录
                if 'login' not in page.url:
                    self.log("已登录！", "SUCCESS")
                    self.keepalive(page)
                    self.notify(True)
                    return True

                # 2. 输入账号密码
                self.log("步骤2: 输入凭据", "STEP")
                try:
                    username_selectors = ['input[name="email"]', 'input[name="username"]', 'input[type="email"]', '#id_email']
                    password_selectors = ['input[name="password"]', 'input[type="password"]', '#id_password']
                    
                    user_input = None
                    for sel in username_selectors:
                        if page.locator(sel).is_visible():
                            user_input = sel
                            break
                    
                    if not user_input:
                        self.log("未找到明显的用户名输入框，尝试默认 input[name='email']", "WARN")
                        user_input = 'input[name="email"]'

                    page.fill(user_input, self.username)
                    
                    pass_input = None
                    for sel in password_selectors:
                        if page.locator(sel).is_visible():
                            pass_input = sel
                            break
                    
                    if not pass_input:
                        pass_input = 'input[name="password"]'
                        
                    page.fill(pass_input, self.password)
                    self.log("已输入凭据")
                except Exception as e:
                    self.log(f"输入失败: {e}", "ERROR")
                    self.notify(False, f"输入失败: {e}")
                    return False
                
                self.shot(page, "filled")

                # 3. 提交登录
                self.log("步骤3: 提交登录", "STEP")
                try:
                    page.click('button[type="submit"], input[type="submit"]')
                except Exception as e:
                    self.log(f"点击登录失败: {e}", "ERROR")
                    page.keyboard.press('Enter')
                
                # 等待跳转
                try:
                    page.wait_for_url(lambda u: 'login' not in u, timeout=30000)
                    page.wait_for_load_state('networkidle', timeout=30000)
                except:
                    self.log("登录超时或失败", "ERROR")
                    self.shot(page, "login_fail")
                    
                    try:
                        err = page.locator('.alert-danger, .error').first
                        if err.is_visible():
                            self.log(f"登录错误: {err.inner_text()}", "ERROR")
                    except:
                        pass
                        
                    self.notify(False, "登录超时或失败")
                    return False

                self.shot(page, "login_success")
                
                # 4. 验证登录成功
                self.log("步骤4: 验证登录", "STEP")
                if 'login' in page.url:
                     self.log("仍在登录页，可能失败", "ERROR")
                     self.notify(False, "登录失败")
                     return False
                
                self.log("登录成功！", "SUCCESS")

                # 5. 保活
                self.keepalive(page)
                
                self.notify(True)
                return True
                
            except Exception as e:
                self.log(f"异常: {e}", "ERROR")
                self.shot(page, "异常")
                import traceback
                traceback.print_exc()
                self.notify(False, str(e))
                return False
            finally:
                browser.close()


def get_accounts():
    """获取所有需要登录的账户"""
    accounts = []
    
    # 1. 尝试从 ACCOUNTS_JSON 获取
    accounts_json = os.environ.get('ACCOUNTS_JSON')
    if accounts_json:
        try:
            data = json.loads(accounts_json)
            if isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and 'username' in item and 'password' in item:
                        accounts.append(item)
            elif isinstance(data, dict):
                 if 'username' in data and 'password' in data:
                        accounts.append(data)
        except json.JSONDecodeError:
            print("❌ ACCOUNTS_JSON 格式错误，忽略")
    
    # 2. 尝试从 AD_USERNAME / AD_PASSWORD 获取 (向后兼容)
    u = os.environ.get('AD_USERNAME')
    p = os.environ.get('AD_PASSWORD')
    if u and p:
        # 避免重复
        if not any(a['username'] == u for a in accounts):
            accounts.append({'username': u, 'password': p})
            
    return accounts


if __name__ == "__main__":
    print("\n" + "="*50)
    print("🚀 AlwaysData 自动登录 (多账户版)")
    print("="*50 + "\n")
    
    accounts = get_accounts()
    
    if not accounts:
        print("❌ 未找到有效账户配置")
        print("请配置 ACCOUNTS_JSON (JSON数组) 或 AD_USERNAME/AD_PASSWORD")
        sys.exit(1)
        
    print(f"📋 共找到 {len(accounts)} 个账户")
    
    success_count = 0
    fail_count = 0
    
    for i, acc in enumerate(accounts):
        masked_user = mask_email(acc['username'])
        print(f"\n▶️ 开始处理第 {i+1} 个账户: {masked_user}")
        bot = AutoLogin(acc['username'], acc['password'], index=i+1)
        if bot.run():
            success_count += 1
        else:
            fail_count += 1
            
    print("\n" + "="*50)
    print(f"🏁 运行结束 - 成功: {success_count} | 失败: {fail_count}")
    print("="*50 + "\n")
    
    if fail_count > 0:
        sys.exit(1)
