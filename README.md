# emos_magic_bot 部署说明

这是 Telegram 综合机器人项目。真实 Bot Token、服务商 Token、数据库密码、R2 Key 等都从 `.env` 或系统环境变量读取，仓库里只保留 `.env.example` 模板。

## 安全提醒

- 不要把 `.env` 提交到 GitHub。
- 不要提交 `prediction.db`、`local_database.db`、日志、票根图片目录。
- 如果 Token 曾经发到公开地方，建议去 BotFather 或服务商后台重新生成。
- 下注、结算、提现相关记录保存在 `prediction.db`，上线后要定期备份这个文件。

## 创建 .env

第一次部署到 VPS：

```bash
cd /opt/emos_magic_bot
cp .env.example .env
nano .env
chmod 600 .env
```

必须填写：

```env
BOT_TOKEN=BotFather 给你的机器人 Token
BOT_USERNAME=机器人用户名，不带 @
SERVICE_PROVIDER_TOKEN=服务商 Token

API_BASE_URL=https://emos.best/api
API_USER_ENDPOINT=https://emos.best/api/user

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=数据库密码
DB_NAME=game_db_test

PREDICTION_TICKET_ADMIN_IDS=管理员 Telegram ID，多个用英文逗号隔开
PREDICTION_PLATFORM_SUBSIDY=100
PREDICTION_MAX_STAKE=1000
PREDICTION_CUSTOM_MATCH_CREATE_FEE=50
```

可选填写：

```env
R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_BUCKET_NAME=redpacket-images
R2_PUBLIC_URL=
R2_ENDPOINT=

BUBBLE_FONT_PATH=
PREDICTION_TICKET_BG_URL=
PREDICTION_TICKET_FONT=
PREDICTION_FEE_RECEIVER_USER_ID=
```

本项目已经关闭代理配置。VPS 能正常访问 Telegram 和接口时，不需要配置任何代理变量。

## 世界杯预测配置

默认使用 FIFA 赛程接口：

```env
FIFA_MATCHES_URL=https://api.fifa.com/api/v3/calendar/matches
FIFA_COMPETITION_ID=17
FIFA_SEASON_ID=285023
PREDICTION_SETTLEMENT_INTERVAL_SECONDS=30
PREDICTION_DB=prediction.db
PREDICTION_TICKET_DIR=prediction_tickets
```

规则摘要：

- 用户登录后才能下注，下注会创建服务商支付订单。
- 比赛开始前 10 分钟停止下注。
- 每场平台补贴默认 100 萝卜。
- 单个用户单场下注上限默认 1000 萝卜。
- 结算前会通知管理员确认，管理员也可以手动输入比分结算。
- 奖池按胜平负 40%、准确比分 60% 分配；如果没人中准确比分，全部给胜平负命中者按下注比例分。

## Debian VPS 运行

安装依赖：

```bash
apt update
apt install -y python3 python3-venv python3-dev build-essential fonts-noto-cjk

cd /opt/emos_magic_bot
python3 -m venv venv
source venv/bin/activate
pip install -U pip setuptools wheel
pip install -r requirements.txt
pip check
```

编译检查：

```bash
source venv/bin/activate
python -m py_compile main.py config.py handlers/*.py utils/*.py app/*.py app/database/*.py
```

前台测试：

```bash
source venv/bin/activate
python main.py
```

后台运行：

```bash
pkill -f "python main.py" || true
nohup venv/bin/python main.py > bot_runtime.log 2> bot_runtime.err.log &
tail -f bot_runtime.log bot_runtime.err.log
```

## systemd 运行

创建服务：

```bash
nano /etc/systemd/system/emos_magic_bot.service
```

写入：

```ini
[Unit]
Description=Emos Magic Bot
After=network.target

[Service]
Type=simple
WorkingDirectory=/opt/emos_magic_bot
EnvironmentFile=/opt/emos_magic_bot/.env
ExecStart=/opt/emos_magic_bot/venv/bin/python /opt/emos_magic_bot/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

启动：

```bash
systemctl daemon-reload
systemctl enable emos_magic_bot
systemctl restart emos_magic_bot
journalctl -u emos_magic_bot -f
```

## 常用排错

检查机器人 Token：

```bash
source .env
curl "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
```

检查进程：

```bash
ps aux | grep python | grep main
```

查看日志：

```bash
tail -f bot_runtime.log bot_runtime.err.log
```

如果出现 `Conflict: terminated by other getUpdates request`，说明同一个 Bot Token 同时启动了多个 polling：

```bash
pkill -f "python main.py"
systemctl restart emos_magic_bot
```
