# emos_magic_bot 部署说明

这是 Telegram 综合机器人项目。当前代码已经做了敏感信息脱敏，Token、数据库密码、R2 Key 等都从 `.env` 或系统环境变量读取，不再写死在代码里。

## 关键结论

- 不要用 Python 3.13 跑当前机器人，容易触发 `python-telegram-bot` 兼容问题。
- 推荐使用 Python 3.11 或 Docker `python:3.11-slim`。
- 不要提交 `.env`、`local_database.db`、日志、锁文件。
- 修改代码后先跑 `py_compile`，启动后用实时日志确认。

## 配置文件

第一次部署时复制模板：

```bash
cd /opt/emos_magic_bot
cp .env.example .env
nano .env
chmod 600 .env
```

需要填写的关键项：

```env
BOT_TOKEN=
BOT_USERNAME=
SERVICE_PROVIDER_TOKEN=

API_BASE_URL=https://emos.best/api
API_USER_ENDPOINT=https://emos.best/api/user
DEFAULT_GROUP_CHAT_ID=

DB_HOST=
DB_PORT=3306
DB_USER=root
DB_PASSWORD=
DB_NAME=game_db_test

R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_BUCKET_NAME=redpacket-images
R2_PUBLIC_URL=
R2_ENDPOINT=

TELEGRAM_PROXY=
HTTP_PROXY_URL=
```

VPS 如果能直连 Telegram，`TELEGRAM_PROXY` 和 `HTTP_PROXY_URL` 留空。只有网络必须走代理时才填写代理地址，例如 `http://127.0.0.1:7890`。

## 推荐部署方式：Docker

Docker 可以避开系统源没有 Python 3.11 的问题。

创建 `Dockerfile`：

```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
CMD ["python", "main.py"]
```

构建并运行：

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
```

实时日志：

```bash
docker logs -f emos-bot
```

重启：

```bash
docker restart emos-bot
```

## 本地 venv 部署方式

如果系统能安装 Python 3.11：

```bash
cd /opt/emos_magic_bot
pkill -f "python main.py" || true
rm -rf venv

apt update
apt install -y python3.11 python3.11-venv python3.11-dev

python3.11 -m venv venv
source venv/bin/activate
python -V

pip install -U pip setuptools wheel
pip install -r requirements.txt
pip check
```

如果系统源没有 Python 3.11，优先使用 Docker。

## 语法检查

```bash
cd /opt/emos_magic_bot
source venv/bin/activate
python -m py_compile main.py config.py handlers/*.py utils/*.py app/*.py app/database/*.py
```

## 前台测试运行

```bash
cd /opt/emos_magic_bot
source venv/bin/activate
python main.py
```

确认无错误后按 `Ctrl+C` 停止，再后台运行。

## 后台运行与实时日志

```bash
cd /opt/emos_magic_bot
source venv/bin/activate

pkill -f "python main.py" || true
nohup python main.py > bot_runtime.log 2> bot_runtime.err.log &

tail -f bot_runtime.log bot_runtime.err.log
```

停止后台进程：

```bash
pkill -f "python main.py"
```

## systemd 运行

创建服务：

```bash
nano /etc/systemd/system/emos_magic_bot.service
```

示例内容：

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

查看最近日志：

```bash
journalctl -u emos_magic_bot -n 100 --no-pager
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

检查后台错误：

```bash
tail -f bot_runtime.err.log
```

检查依赖冲突：

```bash
source venv/bin/activate
pip check
```

强制拉取 GitHub 最新代码，会丢弃 VPS 本地代码改动：

```bash
cd /opt/emos_magic_bot
git fetch origin master
git reset --hard origin/master
git clean -fd
```

`.env` 在 `.gitignore` 中，正常不会被 `git clean -fd` 删除。

## 常见问题

`AttributeError: 'Updater' object has no attribute '_Updater__polling_cleanup_cb'`

原因：Python 3.13 与当前 `python-telegram-bot` 组合不兼容。解决：换 Python 3.11，或直接使用 Docker。

`Conflict: terminated by other getUpdates request`

原因：同一个 bot token 启动了多个 polling 实例。解决：

```bash
pkill -f "python main.py"
```

然后只启动一个实例。

Telegram 连接超时：

- VPS 能直连时，`.env` 中 `TELEGRAM_PROXY=` 留空。
- 必须走代理时，填写 `TELEGRAM_PROXY=http://host:port`。

## 安全提醒

- `.env` 不要提交到 GitHub。
- `local_database.db` 会缓存用户 token，不要提交。
- 旧 commit 历史里如果曾经出现过 token、R2 key、数据库密码，建议去对应平台轮换这些密钥。
