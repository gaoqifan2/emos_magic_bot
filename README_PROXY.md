# 数据库代理连接说明

## 问题
数据库服务器 `66.235.105.125` 在晚上可能被墙，导致无法直接连接。

## 解决方案

### 1. 启动 Clash/V2Ray 代理

确保您的代理工具正在运行，并监听 SOCKS5 端口（默认 7890）。

### 2. 配置 Clash 规则

在您的 Clash 配置文件 (`config.yaml`) 的 `rules` 部分添加：

```yaml
rules:
  # 数据库服务器走代理
  - IP-CIDR,66.235.105.125/32,PROXY
  
  # 您的其他规则...
  - GEOIP,CN,DIRECT
  - MATCH,PROXY
```

### 3. 启动机器人

#### 方式一：使用批处理脚本（推荐）
```bash
start_bot.bat
```

#### 方式二：手动设置环境变量后启动
```bash
set DB_PROXY_HOST=127.0.0.1
set DB_PROXY_PORT=7890
python main.py
```

#### 方式三：使用 PowerShell
```powershell
$env:DB_PROXY_HOST="127.0.0.1"
$env:DB_PROXY_PORT="7890"
python main.py
```

### 4. 自定义代理端口

如果您的 Clash 使用不同端口（如 1080、7891 等），请修改：

**Windows CMD:**
```bash
set DB_PROXY_PORT=1080
python main.py
```

**Windows PowerShell:**
```powershell
$env:DB_PROXY_PORT="1080"
python main.py
```

**或者修改 `start_bot.bat` 文件中的端口设置**

## 检查代理是否正常工作

### 检查 Clash 端口
```bash
netstat -an | findstr 7890
```

### 测试数据库连接
```bash
python test_db.py
```

## 常见 Clash 端口

| 工具 | SOCKS5 端口 | HTTP 端口 |
|------|------------|-----------|
| Clash | 7890 | 7891 |
| Clash Verge | 7890 | 7891 |
| Clash for Windows | 7890 | 7891 |
| v2rayN | 10808 | 10809 |
| Shadowsocks | 1080 | - |

## 故障排除

1. **连接超时**
   - 检查 Clash 是否正在运行
   - 检查端口是否正确
   - 检查 Clash 规则是否配置正确

2. **代理连接失败**
   - 确认 `pysocks` 已安装: `pip install pysocks`
   - 检查防火墙设置

3. **仍然无法连接**
   - 尝试更换代理节点
   - 检查数据库服务器是否真的可用
