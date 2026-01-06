#!/usr/bin/env python3
"""
AlwaysData 自动登录脚本
- 邮箱密码登录
- Telegram 通知
"""

import os
import sys
import time
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


class AutoLogin:
    """自动登录"""
    
    def __init__(self):
        self.username = os.environ.get('AD_USERNAME')
        self.password = os.environ.get('AD_PASSWORD')
        self.tg = Telegram()
        self.shots = []
        self.logs = []
        self.n = 0
        
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
        except:
            pass
        return f
    
    def keepalive(self, page):
        """保活"""
        self.log("保活...", "STEP")
        # 登录后默认就在管理界面，可以刷新一下或者访问特定页面
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
<b>用户:</b> {self.username}
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
        print("\n" + "="*50)
        print("🚀 AlwaysData 自动登录")
        print("="*50 + "\n")
        
        self.log(f"用户名: {self.username}")
        self.log(f"密码: {'有' if self.password else '无'}")
        
        if not self.username or not self.password:
            self.log("缺少凭据", "ERROR")
            self.notify(False, "凭据未配置")
            sys.exit(1)
        
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
                
                # 检查是否已经登录（虽然不太可能，因为没有持久化cookie）
                if 'login' not in page.url:
                    self.log("已登录！", "SUCCESS")
                    self.keepalive(page)
                    self.notify(True)
                    print("\n✅ 成功！\n")
                    return

                # 2. 输入账号密码
                self.log("步骤2: 输入凭据", "STEP")
                try:
                    # AlwaysData 登录页面的输入框 name 属性通常是 email (Courriel)
                    # 尝试多种选择器以提高兼容性
                    username_selectors = ['input[name="email"]', 'input[name="username"]', 'input[type="email"]', '#id_email']
                    password_selectors = ['input[name="password"]', 'input[type="password"]', '#id_password']
                    
                    # 查找用户名输入框
                    user_input = None
                    for sel in username_selectors:
                        if page.locator(sel).is_visible():
                            user_input = sel
                            break
                    
                    if not user_input:
                        self.log("未找到明显的用户名输入框，尝试默认 input[name='email']", "WARN")
                        user_input = 'input[name="email"]'

                    self.log(f"使用用户名选择器: {user_input}")
                    page.fill(user_input, self.username)
                    
                    # 查找密码输入框
                    pass_input = None
                    for sel in password_selectors:
                        if page.locator(sel).is_visible():
                            pass_input = sel
                            break
                    
                    if not pass_input:
                        pass_input = 'input[name="password"]'
                        
                    self.log(f"使用密码选择器: {pass_input}")
                    page.fill(pass_input, self.password)
                    
                    self.log("已输入凭据")
                except Exception as e:
                    self.log(f"输入失败: {e}", "ERROR")
                    self.notify(False, f"输入失败: {e}")
                    sys.exit(1)
                
                self.shot(page, "filled")

                # 3. 提交登录
                self.log("步骤3: 提交登录", "STEP")
                try:
                    # 尝试点击登录按钮，通常是 type="submit"
                    page.click('button[type="submit"], input[type="submit"]')
                except Exception as e:
                    self.log(f"点击登录失败: {e}", "ERROR")
                    # 尝试回车
                    page.keyboard.press('Enter')
                
                # 等待跳转
                try:
                    page.wait_for_url(lambda u: 'login' not in u, timeout=30000)
                    page.wait_for_load_state('networkidle', timeout=30000)
                except:
                    self.log("登录超时或失败", "ERROR")
                    self.shot(page, "login_fail")
                    
                    # 检查是否有错误提示
                    try:
                        err = page.locator('.alert-danger, .error').first
                        if err.is_visible():
                            self.log(f"登录错误: {err.inner_text()}", "ERROR")
                    except:
                        pass
                        
                    self.notify(False, "登录超时或失败")
                    sys.exit(1)

                self.shot(page, "login_success")
                
                # 4. 验证登录成功
                self.log("步骤4: 验证登录", "STEP")
                if 'login' in page.url:
                     self.log("仍在登录页，可能失败", "ERROR")
                     self.notify(False, "登录失败")
                     sys.exit(1)
                
                self.log("登录成功！", "SUCCESS")

                # 5. 保活
                self.keepalive(page)
                
                self.notify(True)
                print("\n" + "="*50)
                print("✅ 成功！")
                print("="*50 + "\n")
                
            except Exception as e:
                self.log(f"异常: {e}", "ERROR")
                self.shot(page, "异常")
                import traceback
                traceback.print_exc()
                self.notify(False, str(e))
                sys.exit(1)
            finally:
                browser.close()


if __name__ == "__main__":
    AutoLogin().run()
