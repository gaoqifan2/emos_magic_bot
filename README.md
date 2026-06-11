# emos_magic_bot 部署说明

这是 Telegram 综合机器人项目。代码里的敏感信息已经脱敏，Bot Token、服务商 Token、数据库密码、R2 Key 等都从 `.env` 或系统环境变量读取，不再写死在代码里。

## 当前推荐方案

Debian Trixie 默认 Python 较新，旧版 `python-telegram-bot` 容易触发类似下面的错误：

```text
AttributeError: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'
```

现在依赖已经升级到：

```text
python-telegram-bot==22.7
httpx==0.28.1
```

所以 VPS 上可以直接使用系统自带的 `python3` 建虚拟环境，不需要强行安装 `python3.11`。如果后续系统源缺包或 Python 环境太乱，再用 Docker。

## VPS 无代理配置

VPS 能直连 Telegram 时，`.env` 里代理必须留空：

```env
TELEGRAM_PROXY=
HTTP_PROXY_URL=
```

不要写 `None`，也不要写本地电脑的代理地址。代码只会在 `TELEGRAM_PROXY` 有值时启用 Telegram 代理。

## 创建 .env

第一次部署：

```bash
cd /opt/emos_magic_bot
cp .env.example .env
nano .env
chmod 600 .env
```

需要填的关键项：

```env
BOT_TOKEN=这里填 BotFather 给你的机器人 Token
BOT_USERNAME=这里填机器人用户名，不带 @
SERVICE_PROVIDER_TOKEN=这里填服务商 Token

API_BASE_URL=https://emos.best/api
API_USER_ENDPOINT=https://emos.best/api/user
DEFAULT_GROUP_CHAT_ID=这里填默认群 ID，没有就先留空

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=这里填数据库密码
DB_NAME=game_db_test

R2_ACCESS_KEY=这里填 R2 Access Key
R2_SECRET_KEY=这里填 R2 Secret Key
R2_BUCKET_NAME=redpacket-images
R2_PUBLIC_URL=这里填 R2 公开访问地址
R2_ENDPOINT=这里填 R2 Endpoint

BUBBLE_FONT_PATH=

TELEGRAM_PROXY=
HTTP_PROXY_URL=
```

气泡红包会把用户输入渲染成纯白底图片。VPS 上必须有中文字体，否则会变成问号或生成失败。Debian/Trixie 推荐安装：

```bash
apt update
apt install -y fonts-noto-cjk
```

如果系统字体路径特殊，可以在 `.env` 指定：

```env
BUBBLE_FONT_PATH=/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc
```

## Debian Trixie 直接运行

从 GitHub 强制拉最新代码：

```bash
cd /opt/emos_magic_bot
git fetch origin master
git reset --hard origin/master
git clean -fd
```

`.env` 已经被 `.gitignore` 忽略，正常不会被删。确认一下还在：

```bash
ls -la .env
```

重建虚拟环境并安装依赖：

```bash
cd /opt/emos_magic_bot
pkill -f "python main.py" || true
deactivate 2>/dev/null || true
rm -rf venv

apt update
apt install -y python3 python3-venv python3-dev build-essential fonts-noto-cjk

python3 -m venv venv
source venv/bin/activate
python -V

pip install -U pip setuptools wheel
pip install -r requirements.txt
pip check
```

语法检查：

```bash
cd /opt/emos_magic_bot
source venv/bin/activate
python -m py_compile main.py config.py handlers/*.py utils/*.py app/*.py app/database/*.py
```

前台测试：

```bash
cd /opt/emos_magic_bot
source venv/bin/activate
python main.py
```

确认没有报错后按 `Ctrl+C`，再后台运行：

```bash
cd /opt/emos_magic_bot
source venv/bin/activate
pkill -f "python main.py" || true
nohup python main.py > bot_runtime.log 2> bot_runtime.err.log &
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

启动并查看实时日志：

```bash
systemctl daemon-reload
systemctl enable emos_magic_bot
systemctl restart emos_magic_bot
journalctl -u emos_magic_bot -f
```

查看最近日志：

```bash
journalctl -u emos_magic_bot -n 100 --no-pager
```

## Docker 备用方案

如果 VPS 的 Python 环境继续冲突，可以直接用 Docker：

```dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
CMD ["python", "main.py"]
```

运行：

```bash
cd /opt/emos_magic_bot
docker build -t emos-bot .
docker rm -f emos-bot 2>/dev/null || true
docker run -d \
  --name emos-bot \
  --restart always \
  --env-file .env \
  -v /opt/emos_magic_bot/logs:/app/logs \
  emos-bot
docker logs -f emos-bot
```

## 快速排错

测试 Telegram Token：

```bash
source .env
curl "https://api.telegram.org/bot${BOT_TOKEN}/getMe"
```

检查进程：

```bash
ps aux | grep python | grep main
```

查看后台错误：

```bash
tail -f bot_runtime.err.log
```

检查依赖冲突：

```bash
source venv/bin/activate
pip check
```

如果出现 `Conflict: terminated by other getUpdates request`，说明同一个机器人 Token 同时启动了多个 polling：

```bash
pkill -f "python main.py"
systemctl restart emos_magic_bot
```

## 安全提醒

- `.env` 不要提交到 GitHub。
- `local_database.db`、日志、锁文件不要提交。
- 如果 Token、R2 Key、数据库密码曾经发到公开地方，建议去对应平台重新生成一套。
