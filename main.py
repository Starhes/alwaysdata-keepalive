#!/usr/bin/env python3
"""
AlwaysData 自动登录脚本
- 支持多账户 (ACCOUNTS_JSON)
- 邮箱密码登录
- Telegram 通知
- 支持多种在线代理 (AProxy, BestProxy, CroxyProxy, SiteProxy, NSocks, LumiProxy)
- 自动回退机制 (如果所有代理失败，尝试直连)
"""

import os
import sys
import time
import json
import requests
import urllib.parse
import random
from playwright.sync_api import sync_playwright

# ==================== 配置 ====================
ALWAYS_DATA_URL = "https://admin.alwaysdata.com"
TARGET_URL = f"{ALWAYS_DATA_URL}/login/"


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
    """脱敏邮箱 (包括域名)"""
    if not email or "@" not in email:
        return email
    try:
        user, domain = email.split("@")
        
        # 脱敏用户名
        if len(user) <= 2:
            masked_user = f"{user[0]}***"
        else:
            masked_user = f"{user[0]}***{user[-1]}"
            
        # 脱敏域名
        if "." in domain:
            name, tld = domain.rsplit(".", 1)
            if len(name) <= 2:
                masked_domain = f"{name[0]}***.{tld}"
            else:
                masked_domain = f"{name[0]}***{name[-1]}.{tld}"
        else:
            masked_domain = domain
            
        return f"{masked_user}@{masked_domain}"
    except:
        return email


# ==================== 代理策略 ====================

class ProxyStrategy:
    def navigate(self, page, target_url):
        raise NotImplementedError

class AProxyStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "AProxy (aproxy.com)"

    def navigate(self, page, target_url):
        # https://aproxy.com/zh/proxysite/
        # 直接构造 webproxy URL
        base = "https://webproxy.aproxy.com/request?area=US&u="
        final_url = f"{base}{urllib.parse.quote(target_url)}"
        page.goto(final_url, timeout=60000)

class BestProxyStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "BestProxy (bestproxy.com)"

    def navigate(self, page, target_url):
        # https://bestproxy.com/
        page.goto("https://bestproxy.com/", timeout=60000)
        # 等待输入框出现
        # <input class="m-input__inner" ...>
        page.wait_for_selector('.m-input__inner', state='visible', timeout=30000)
        
        page.fill('.m-input__inner', target_url)
        
        # 点击GO
        # <button class="m-button ...">GO</button>
        page.click('.m-button')

class CroxyProxyStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "CroxyProxy (croxyproxy.com)"

    def navigate(self, page, target_url):
        # https://www.croxyproxy.com/
        page.goto("https://www.croxyproxy.com/", timeout=60000)
        # 等待输入框出现
        # <input id="url" ...>
        page.wait_for_selector('#url', state='visible', timeout=30000)
        
        page.fill('#url', target_url)
        
        # 点击GO
        # <button id="requestSubmit" ...>
        page.click('#requestSubmit')

class SiteProxyStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "SiteProxy (siteproxy.ai)"

    def navigate(self, page, target_url):
        # https://siteproxy.ai/zh-Hans
        page.goto("https://siteproxy.ai/zh-Hans", timeout=60000)
        # Wait for input
        # <input id="url-input" ...>
        page.wait_for_selector('#url-input', state='visible', timeout=30000)
        page.fill('#url-input', target_url)
        
        # Click button "开启代理"
        page.click('button:has-text("开启代理")')

class NSocksStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "NSocks (nsocks.com)"

    def navigate(self, page, target_url):
        # https://www.nsocks.com/zh/proxysite/
        page.goto("https://www.nsocks.com/zh/proxysite/", timeout=60000)
        
        # Wait for input
        # Placeholder: "请输入网址"
        input_sel = 'input[placeholder="请输入网址"]'
        page.wait_for_selector(input_sel, state='visible', timeout=30000)
        page.fill(input_sel, target_url)
        
        # Click GO button
        page.click('button:has-text("GO")')

class LumiProxyStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "LumiProxy (lumiproxy.com)"

    def navigate(self, page, target_url):
        # https://webproxy.lumiproxy.com/request?area=US&u=...
        base = "https://webproxy.lumiproxy.com/request?area=US&u="
        final_url = f"{base}{urllib.parse.quote(target_url)}"
        page.goto(final_url, timeout=60000)

class ProxyCCStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "ProxyCC (proxy.cc)"

    def navigate(self, page, target_url):
        # https://webproxy.proxy.cc/request?area=US&u=...
        base = "https://webproxy.proxy.cc/request?area=US&u="
        final_url = f"{base}{urllib.parse.quote(target_url)}"
        page.goto(final_url, timeout=60000)

class DirectStrategy(ProxyStrategy):
    def __init__(self):
        self.name = "Direct (No Proxy)"

    def navigate(self, page, target_url):
        page.goto(target_url, timeout=60000)


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
        
        msg += "\n\n<b>日志:</b>\n" + "\n".join(self.logs[-8:])
        
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
        
        # 代理策略列表
        proxy_strategies = [
            AProxyStrategy(), 
            BestProxyStrategy(), 
            CroxyProxyStrategy(),
            SiteProxyStrategy(),
            NSocksStrategy(),
            LumiProxyStrategy(),
            ProxyCCStrategy()
        ]
        # 随机打乱代理顺序
        random.shuffle(proxy_strategies)
        
        # 最后添加直连策略 (fallback)
        strategies = proxy_strategies + [DirectStrategy()]
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
            context = browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            )
            # 每次 run 都是新的 context 和 page
            page = context.new_page()
            
            try:
                # 1. 尝试通过各种策略加载页面
                login_page_loaded = False
                
                for strategy in strategies:
                    self.log(f"尝试连接: {strategy.name}", "STEP")
                    try:
                        strategy.navigate(page, TARGET_URL)
                        
                        # 等待页面加载
                        if isinstance(strategy, DirectStrategy):
                            page.wait_for_load_state('networkidle', timeout=30000)
                        else:
                            # 代理通常更慢，且可能有跳转
                            time.sleep(8) 
                            try:
                                page.wait_for_load_state('networkidle', timeout=45000)
                            except:
                                pass
                        
                        # 检查是否加载成功 (出现登录框 或 已登录)
                        # 1. 登录框
                        has_login_input = False
                        if page.locator('input[name="password"]').count() > 0 or \
                           page.locator('#id_password').count() > 0 or \
                           page.locator('input[type="password"]').count() > 0:
                            has_login_input = True
                            
                        # 2. 已登录标志
                        is_logged_in = False
                        if page.get_by_text("Administration").count() > 0 or \
                           page.get_by_text("Logout").count() > 0 or \
                           page.get_by_text("Se déconnecter").count() > 0: # 法语 Logout
                            is_logged_in = True
                            
                        if has_login_input or is_logged_in:
                            self.log(f"策略 {strategy.name} 连接成功", "SUCCESS")
                            login_page_loaded = True
                            self.shot(page, f"ok_{strategy.name.split()[0]}")
                            break
                        else:
                            self.log(f"策略 {strategy.name} 未能加载目标页面", "WARN")
                            self.shot(page, f"fail_{strategy.name.split()[0]}")
                            
                    except Exception as e:
                        self.log(f"策略 {strategy.name} 异常: {str(e)[:100]}", "WARN")
                
                if not login_page_loaded:
                    self.log("所有策略(含直连)均失败，终止", "ERROR")
                    self.notify(False, "所有连接方式均失败")
                    return False

                # 检查是否已经登录
                if page.get_by_text("Administration").count() > 0 or \
                   page.get_by_text("Logout").count() > 0 or \
                   page.get_by_text("Se déconnecter").count() > 0:
                    self.log("已登录！", "SUCCESS")
                    self.keepalive(page)
                    self.notify(True)
                    return True

                # 2. 输入账号密码
                self.log("步骤2: 输入凭据", "STEP")
                try:
                    # 总是重新检测元素，因为 DOM 可能变化
                    username_selectors = ['input[name="email"]', 'input[name="username"]', 'input[type="email"]', '#id_email']
                    password_selectors = ['input[name="password"]', 'input[type="password"]', '#id_password']
                    
                    user_input = None
                    for sel in username_selectors:
                        if page.locator(sel).is_visible():
                            user_input = sel
                            break
                    
                    if not user_input:
                        # 盲试
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
                    self.log(f"输入失败: {str(e)[:100]}", "ERROR")
                    self.shot(page, "input_fail")
                    self.notify(False, f"输入失败")
                    return False
                
                self.shot(page, "filled")

                # 3. 提交登录
                self.log("步骤3: 提交登录", "STEP")
                try:
                    # 尝试点击登录按钮
                    # 有些代理可能会注入额外的 button，所以要精确
                    # AlwaysData 的登录按钮通常是 type="submit"
                    submit_btn = page.locator('button[type="submit"], input[type="submit"]').last
                    if submit_btn.is_visible():
                        submit_btn.click()
                    else:
                        page.keyboard.press('Enter')
                except Exception as e:
                    self.log(f"点击登录失败: {e}", "WARN")
                    page.keyboard.press('Enter')
                
                # 等待跳转
                time.sleep(5)
                # 尝试等待网络空闲，但不强求，因为代理环境可能一直有心跳包
                try:
                    page.wait_for_load_state('networkidle', timeout=15000)
                except:
                    pass

                self.shot(page, "after_submit")
                
                # 4. 验证登录成功
                self.log("步骤4: 验证登录", "STEP")
                
                # 再次检查是否有密码框
                if page.locator('input[name="password"]').count() > 0:
                     self.log("仍在登录页，可能失败", "ERROR")
                     # 尝试获取错误信息
                     try:
                        err = page.locator('.alert-danger, .error').first
                        if err.is_visible():
                            self.log(f"登录错误: {err.inner_text()}", "ERROR")
                     except:
                        pass
                     self.notify(False, "登录失败")
                     return False
                
                self.log("登录成功！(猜测)", "SUCCESS")

                # 5. 保活
                self.keepalive(page)
                
                self.notify(True)
                return True
                
            except Exception as e:
                self.log(f"运行异常: {e}", "ERROR")
                self.shot(page, "exception")
                import traceback
                traceback.print_exc()
                self.notify(False, f"运行异常: {str(e)[:100]}")
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
    print("🚀 AlwaysData 自动登录 (Proxy Redundancy)")
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
            # 成功后随机等待，增加拟人化
            time.sleep(random.randint(5, 15))
        else:
            fail_count += 1
            
    print("\n" + "="*50)
    print(f"🏁 运行结束 - 成功: {success_count} | 失败: {fail_count}")
    print("="*50 + "\n")
    
    if fail_count > 0:
        sys.exit(1)
