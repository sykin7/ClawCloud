# 🛡️ ClawCloud-Run 自动化保活哨兵 (Enhanced Version)

基于 Playwright 的 ClawCloud 账户自动化保活方案。通过模拟真实用户行为、处理 GitHub 状态机变换，实现高成功率的无人值守登录。

---

## 🛠️ 技术核心与特性

- **🛡️ 状态机自愈登录**: 自动识别 Session 过期、OAuth 授权页、以及“验证密码以继续”等复杂状态。
- **🔐 SealedBox 安全加密**: 采用 `libsodium` 标准加密算法更新 Secret，确保 Cookie 在 GitHub 基础设施内加密传输。
- **🌍 动态区域追踪**: 实时解析 URL 变更，自动追踪账户所在的子域名区域（如 `ap-southeast-1`）。
- **🤖 2FA 指令中继**: 通过 Telegram Bot 实现双向交互，支持移动端批准检测与 `/code` 指令远程输入。
- **📦 环境隔离适配**: 针对 GitHub Actions 容器优化的 Chromium 运行参数，彻底解决内存溢出与依赖缺失。

---

## ⚙️ 配置变量 (Secrets)

| Secret 名称 | 必须 | 权限/格式要求 | 说明 |
| :--- | :--- | :--- | :--- |
| `GH_USERNAME` | **是** | 字符串 | GitHub 账号。 |
| `GH_PASSWORD` | **是** | 字符串 | GitHub 密码。 |
| `REPO_TOKEN` | **是** | PAT (Classic) | 必须包含 `workflow` 和 `write:secrets` 权限。 |
| `TG_BOT_TOKEN` | **是** | HTTP API Token | 从 @BotFather 获取。 |
| `TG_CHAT_ID` | **是** | 数字 ID | 从 @userinfobot 获取。 |
| `GH_SESSION` | 否 | Cookie Value | 初始运行可留空，成功后脚本会自动接管更新。 |
| `TWO_FACTOR_WAIT`| 否 | 数字 (秒) | 默认 `120`，建议网络环境差时调大。 |

---

## 🚀 部署指引

### 1. 权限准备 (关键)
前往 [Developer settings](https://github.com/settings/tokens) 创建 Personal Access Token (PAT)：
- **勾选 `workflow`**: 允许脚本在失败时触发重试流程。
- **勾选 `write:secrets`**: 允许脚本自动回写最新的 `GH_SESSION`。

### 2. 仓库设置
1. **Fork** 本仓库。
2. 在仓库 `Settings > Secrets and variables > Actions` 中填入上述表格中的所有变量。

### 3. 激活保活
- **手动触发**: `Actions` -> `ClawCloud 自动登录保活` -> `Run workflow`。
- **定时触发**: 默认每 5 天运行一次（UTC 1:00），可修改 `.github/workflows/keep-alive.yml` 中的 `cron` 表达式。

---

## 📝 运维记录与审计

- **日志监控**: 脚本每步执行均有 Emoji 状态标识，可通过 Actions 实时查看。
- **可视化调试**: 失败时脚本会自动截图并发送至 Telegram，帮助定位 UI 变更。
- **依赖说明**: 本项目运行依赖 `playwright`, `requests`, `pynacl`。

---

## ⚖️ 免责声明
本脚本仅用于个人账户维护及技术交流。使用自动化工具可能违反平台服务条款，请自行承担相关风险。

## 🙏 致谢

本项目基于 [oyz8/ClawCloud-Run](https://github.com/oyz8/ClawCloud-Run) 感谢原作者的贡献，[frankiejun/ClawCloud-Run](https://github.com/frankiejun/ClawCloud-Run)做了些调整。
