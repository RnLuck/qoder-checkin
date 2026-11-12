# Qoder 每日自动签到 · 运行手册

云端无人值守签到：GitHub Actions 每天定时跑一次 `qoder_checkin.py`，凭据状态存在一个**私有 Gist** 里（每次运行前拉取、运行后回写，解决 token 轮换持久化）。

## 部署概览

| 项目 | 值 |
| --- | --- |
| 仓库 | `RnLuck/qoder-checkin`（公开；**不含任何凭据**） |
| 工作流 | `.github/workflows/checkin.yml` |
| 定时 | 多时段兜底（UTC→北京）：`10 2`=10:10 主、`10 3`=11:10、`10 5`=13:10、`10 7`=15:10、`10 11`=19:10 |
| 凭据存储 | 私有 Gist（ID 保存在仓库 Secret `GIST_ID`，值不外泄） |
| 令牌回写 | 每次运行用 Secret `GH_GIST_TOKEN` 拉取 / 回写 Gist |
| 端点 | `https://openapi.qoder.sh`（国际服） |

Secrets 位置：仓库 **Settings → Secrets and variables → Actions**。

## 一、日志查看方式

### 云端运行日志（每日自动跑，主要看这个）
Actions 每次运行都会留下完整步骤日志，保留约 90 天：

- 网页：https://github.com/RnLuck/qoder-checkin/actions → 点开某次运行 → `checkin` 作业 → **Run checkin** 步骤。
- 命令行（需 `gh` 且已登录）：

```bash
# 最近若干次运行状态一览
gh run list -R RnLuck/qoder-checkin --workflow checkin.yml --limit 10

# 看某次运行的完整日志（把 <RUN_ID> 换成上面列表里的 ID）
gh run view <RUN_ID> -R RnLuck/qoder-checkin --log
```

关键看 `Run checkin` 步骤末尾这几行：

```
✅ 签到成功 Qoder账号1: 签到成功 +2,000 Credits（+2,000）
成功 1 · 已领 0 · 待下发 0 · 失败 0
```

### 本机运行日志（手动跑 `qoder/` 里的脚本时）
如果哪天你用本机的 `每日签到.bat` 或 `python qoder_checkin.py`，结果写在本机文件：

```
D:\Files\Code\Qoder\workspace\qoder-checkin\qoder\qoder_checkin.log   (JSON 行日志，UTF-8)
```

> 用记事本/VS Code 打开即为 UTF-8，不乱码；控制台直接打印时因 GBK 显示可能乱码，属正常，文件内容无误。

## 二、每日运行结果怎么判读

`Run checkin` 步骤输出里每个账号会有一个状态，对应含义与处理：

| 状态 | 显示 | 含义 | 需要做什么 |
| --- | --- | --- | --- |
| `claimed` | ✅ 签到成功 | 今天领到了积分 | 无 |
| `already` | ☑️ 已领取 | 今天已领过（重复运行正常） | 无 |
| `pending` | ⏳ 待下发 | 活动还没下发，本次没领到 | 通常下轮 cron 会自动补，无需操作 |
| `login_required` | 🔑 需重新提取 | 令牌/刷新链失效 | **需本机重新提取凭据并更新 Gist**（见下） |
| `error` | ❌ 失败 | 接口报错/网络异常 | 看该行 `msg`，多为临时问题，下轮重试；持续失败再排查 |

作业整体结论：绿色 `success` 只代表脚本正常退出，**不等于领到积分**——以上面的状态为准。

## 三、几个需要注意的点

1. **令牌到期（约 2026-12-04）**
   脚本会在到期前 72 小时自动用 refreshToken 刷新并回写 Gist，正常能持续续期。
   若日志出现 `🔑 需重新提取 (login_required)`，说明刷新链断了，需在本机执行：
   ```bash
   cd D:\Files\Code\Qoder\workspace\qoder-checkin\qoder
   python qoder_extract.py                 # 本机（登录 Qoder 的同一 Windows 用户）重新提取
   cd ..\cloud
   # 用新凭据覆盖 Gist（先设好临时环境变量 GH_GIST_TOKEN=<有gist权限的token>）
   python gist_store.py push               # 把 ../qoder 的新 json 回写到既有 Gist
   ```
   > `gist_store.py push` 更新**现有** Gist（需先 `set GIST_ID=<原ID>`）；若 Gist 已不存在，改用 `python gist_store.py init` 新建，并同步更新仓库 Secret `GIST_ID`。

2. **60 天不活跃会被 GitHub 自动停用定时**
   GitHub 对连续 60 天无提交/活动的仓库会禁用 scheduled workflow。每日签到本身不产生提交，长期可能触发。若发现不再自动跑：去 Actions 页面点 **Enable workflow**，或手动 `gh workflow run checkin.yml -R RnLuck/qoder-checkin` 一次即可恢复。

3. **GitHub 定时不可靠，已用多时段兜底**
   `schedule` 是「尽力而为」：高峰会延迟甚至丢弃，免费账号常被降优先级（实测 2026-11-11 的定时晚了约 7 小时，11-12 到 10:51 仍未触发）。因此设了 5 个时段（北京 10:10/11:10/13:10/15:10/19:10），任一时段成功即可，领取幂等不会重复发币。若某天 5 个时段全被丢（极少见），手动 `gh workflow run checkin.yml -R RnLuck/qoder-checkin` 补一次。脚本另有「活动未下发就本次运行内重查 3 次 × 20 秒」兜底，应对 10:00 刷新后的短暂抖动。

4. **安全说明**
   - 仓库虽公开，但**只有脚本代码**（源自公开 MIT 项目）；token、Gist ID 均在 Secrets / 私有 Gist 中，外人读不到。
   - 私有 Gist 凭链接无法匿名访问（需 owner 登录或令牌）。**不要把 Gist 改成公开**。
   - `GH_GIST_TOKEN` 目前是 gh 登录用的 OAuth 令牌，权限偏宽。若想收紧，可为其单独生成一个**只含 `gist` 权限**的经典 PAT 替换该 Secret。

## 四、常用命令速查

```bash
# 立即手动跑一次（改代码后验证很有用）
gh workflow run checkin.yml -R RnLuck/qoder-checkin

# 看最近运行
gh run list -R RnLuck/qoder-checkin --workflow checkin.yml --limit 10

# 看某次日志
gh run view <RUN_ID> -R RnLuck/qoder-checkin --log

# 更新脚本：改 cloud/qoder_checkin.py 或 cloud/gist_store.py 后
git add -A && git commit -m "update" && git push
```
