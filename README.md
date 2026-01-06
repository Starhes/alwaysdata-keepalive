# AlwaysData Keepalive

这个项目使用 GitHub Actions 每天自动登录 AlwaysData 面板，保持账户活跃，并（可选）通过 Telegram 发送通知。

## 功能

- 自动登录 AlwaysData 管理面板
- 如果登录失败，会截图并通知（如果配置了 Telegram）
- 使用 GitHub Actions 设置定时任务
- 支持 Telegram 通知成功或失败状态

## 配置

### 1. Fok 这个仓库 (如果是私有仓库) 或上传代码

### 2. 配置 GitHub Secrets

在仓库的 **Settings** -> **Secrets and variables** -> **Actions** 中添加以下 Repository secrets：

| Secret 名称 | 必须 | 描述 |
| --- | --- | --- |
| `AD_USERNAME` | ✅ | AlwaysData 的登录邮箱 |
| `AD_PASSWORD` | ✅ | AlwaysData 的登录密码 |
| `TG_BOT_TOKEN` | ❌ | (可选) Telegram Bot Token |
| `TG_CHAT_ID` | ❌ | (可选) 接收通知的 Telegram Chat ID |

### 3. 运行

- 自动：默认每天 UTC 00:00 (北京时间 08:00) 自动运行。
- 手动：在 **Actions** 标签页，选择 **AlwaysData Keepalive**，点击 **Run workflow** 手动触发。
