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
| `AD_USERNAME` | ❌ | (单账户) AlwaysData 的登录邮箱 |
| `AD_PASSWORD` | ❌ | (单账户) AlwaysData 的登录密码 |
| `ACCOUNTS_JSON` | ❌ | (多账户) JSON 格式的账户列表，见下文 |
| `TG_BOT_TOKEN` | ❌ | (可选) Telegram Bot Token |
| `TG_CHAT_ID` | ❌ | (可选) 接收通知的 Telegram Chat ID |

### 多账户配置 (推荐)

如果您有多个账号，请使用 `ACCOUNTS_JSON` secret，格式如下：

```json
[
  {
    "username": "user1@example.com",
    "password": "password1"
  },
  {
    "username": "user2@example.com",
    "password": "password"
  }
]
```

**注意**: 如果配置了 `ACCOUNTS_JSON`，脚本也会尝试读取 `AD_USERNAME` 和 `AD_PASSWORD` 并合并（去重）。

### 3. 运行

- 自动：默认每天 UTC 00:00 (北京时间 08:00) 自动运行。
- 手动：在 **Actions** 标签页，选择 **AlwaysData Keepalive**，点击 **Run workflow** 手动触发。
