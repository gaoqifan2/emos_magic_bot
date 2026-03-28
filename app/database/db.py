# 实际数据库连接
import pymysql
import socks
import socket
import os
from config import DB_CONFIG

# 代理配置（从环境变量读取，默认使用 Clash 端口）
PROXY_HOST = os.getenv('DB_PROXY_HOST', '127.0.0.1')
PROXY_PORT = int(os.getenv('DB_PROXY_PORT', '7890'))

def get_db_connection_direct():
    """直接连接数据库（不使用代理）"""
    try:
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        return connection
    except Exception as e:
        return None

def get_db_connection_with_proxy():
    """通过 SOCKS5 代理获取数据库连接"""
    try:
        # 保存原始 socket
        original_socket = socket.socket
        
        # 设置 SOCKS5 代理
        socks.set_default_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
        socket.socket = socks.socksocket
        
        # 创建数据库连接
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=10
        )
        
        # 恢复原始 socket
        socket.socket = original_socket
        
        return connection
    except Exception as e:
        # 恢复原始 socket
        try:
            socket.socket = original_socket
        except:
            pass
        return None

# 建立数据库连接
def get_db_connection():
    """获取数据库连接，优先直接连接，失败则使用代理"""
    # 首先尝试直接连接
    connection = get_db_connection_direct()
    if connection:
        return connection
    
    # 直接连接失败，尝试代理连接
    print(f"尝试通过代理 {PROXY_HOST}:{PROXY_PORT} 连接数据库...")
    connection = get_db_connection_with_proxy()
    if connection:
        print("✅ 通过代理连接数据库成功")
        return connection
    
    print("❌ 数据库连接失败（直接和代理都失败）")
    print(f"提示: 请确保 Clash/V2Ray 等代理工具正在运行，并监听 {PROXY_HOST}:{PROXY_PORT}")
    print("      或设置环境变量 DB_PROXY_HOST 和 DB_PROXY_PORT 指定代理地址")
    return None

# 初始化数据库表
def init_db():
    """初始化数据库表"""
    print("开始初始化数据库表...")
    connection = get_db_connection()
    if not connection:
        print("数据库连接失败，无法初始化表结构")
        return
    
    try:
        with connection.cursor() as cursor:
            # 不删除旧表，只创建不存在的表
            print("检查并创建表结构...")
            
            # 创建用户表，使用递增id作为主键，user_id作为唯一索引
            print("创建用户表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键，内部使用',
                    user_id VARCHAR(50) UNIQUE NOT NULL COMMENT '用户emosid，格式：e开头s结尾（如：e0E446ZE6s）',
                    telegram_id BIGINT UNIQUE COMMENT 'Telegram用户ID',
                    token VARCHAR(255) UNIQUE COMMENT '用户令牌，格式：1047_开头的字符串',
                    username VARCHAR(255) COMMENT '登录用户名',
                    first_name VARCHAR(255) COMMENT 'Telegram名字',
                    last_name VARCHAR(255) COMMENT 'Telegram姓氏',
                    current_cycle_score INT DEFAULT 0 COMMENT '当前周期贡献分（每下注1币增加1分，中奖后归零）',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
                    INDEX idx_user_id (user_id),
                    INDEX idx_telegram_id (telegram_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户信息表'
            ''')
            print("用户表创建成功，使用递增id作为主键，user_id作为唯一索引")
            
            # 为现有用户表添加current_cycle_score字段（如果不存在）
            print("检查并添加current_cycle_score字段...")
            cursor.execute('''
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS current_cycle_score INT DEFAULT 0 COMMENT '当前周期贡献分（每下注1币增加1分，中奖后归零）'
            ''')
            print("current_cycle_score字段添加成功")
            
            # 创建余额表，使用用户表的id作为外键
            print("创建余额表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balances (
                    user_id INT PRIMARY KEY,
                    balance INT DEFAULT 100,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            print("余额表创建成功")
            
            # 创建游戏记录表，使用用户表的id作为外键
            print("创建游戏记录表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    game_type VARCHAR(50),
                    bet_amount INT,
                    result VARCHAR(50),
                    win_amount INT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            print("游戏记录表创建成功")
            
            # 创建提现记录表，使用用户表的id作为外键
            print("创建提现记录表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS withdrawal_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id INT,
                    amount INT,
                    status VARCHAR(50) DEFAULT 'pending',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            print("提现记录表创建成功")
            
            # 创建充值订单表，使用用户表的id作为外键
            print("创建充值订单表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recharge_orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_no VARCHAR(50) UNIQUE NOT NULL,
                    user_id INT,
                    telegram_user_id BIGINT,
                    carrot_amount INT,
                    game_coin_amount INT,
                    status VARCHAR(50) DEFAULT 'pending',
                    platform_order_no VARCHAR(50) UNIQUE,
                    pay_url TEXT,
                    qrcode TEXT,
                    expire_time TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            print("充值订单表创建成功")
            
            # 创建签到表，使用用户表的id作为主键
            print("创建签到表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_checkins (
                    user_id INT PRIMARY KEY,
                    last_checkin TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                )
            ''')
            print("签到表创建成功")
            
            # 创建Jackpot奖池表（全局共享奖池）
            print("创建Jackpot奖池表...")
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jackpot_pool (
                    id INT PRIMARY KEY DEFAULT 1,
                    amount INT DEFAULT 500,
                    total_contributions INT DEFAULT 0,
                    total_payouts INT DEFAULT 0,
                    last_winner_telegram_id BIGINT,
                    last_win_amount INT,
                    last_win_time TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                    CHECK (id = 1)
                )
            ''')
            print("Jackpot奖池表创建成功")
            
            # 初始化Jackpot奖池记录（如果不存在）
            cursor.execute('''
                INSERT INTO jackpot_pool (id, amount) 
                VALUES (1, 0) 
                ON DUPLICATE KEY UPDATE id=id
            ''')
            print("Jackpot奖池初始化完成")
        connection.commit()
        print("数据库表初始化完成")
    except Exception as e:
        print(f"初始化数据库表时出错: {e}")
    finally:
        connection.close()
        print("数据库连接已关闭")

def get_user_by_telegram_id(telegram_id):
    """通过 telegram_id 获取用户信息"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            # 通过 telegram_id 字段查询用户
            cursor.execute('SELECT * FROM users WHERE telegram_id = %s', (telegram_id,))
            user = cursor.fetchone()
            return user
    finally:
        connection.close()

def get_user_by_user_id(user_id):
    """通过 user_id 获取用户信息"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            # 通过 user_id 字段查询用户
            cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
            user = cursor.fetchone()
            return user
    finally:
        connection.close()

def add_user(user_id, user_data):
    """添加用户"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        with connection.cursor() as cursor:
            # 获取用户信息
            token = user_data.get('token')
            username = user_data.get('username', '')
            telegram_id = user_data.get('telegram_id')
            
            # 检查用户是否已存在（通过 user_id）
            cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id,))
            existing_user = cursor.fetchone()
            
            if not existing_user:
                # 添加用户
                cursor.execute('''
                    INSERT INTO users (user_id, telegram_id, token, username, first_name, last_name) 
                    VALUES (%s, %s, %s, %s, %s, %s)
                ''', (user_id, telegram_id, token, username, user_data.get('first_name', ''), user_data.get('last_name', '')))
                
                # 获取生成的用户id
                user_id_db = cursor.lastrowid
                
                # 为新用户初始化余额，默认为0
                cursor.execute('INSERT INTO balances (user_id, balance, username) VALUES (%s, %s, %s)', (user_id_db, 0, username))
                
                connection.commit()
            else:
                # 如果用户已存在，更新信息
                cursor.execute('''
                    UPDATE users SET token = %s, username = %s 
                    WHERE user_id = %s
                ''', (token, username, user_id))
                
                # 确保用户有余额记录
                user_id_db = existing_user['id']
                cursor.execute('SELECT * FROM balances WHERE user_id = %s', (user_id_db,))
                if not cursor.fetchone():
                    # 如果余额记录不存在，创建一个，默认为0
                    cursor.execute('INSERT INTO balances (user_id, balance) VALUES (%s, 0)', (user_id_db,))
                
                connection.commit()
    finally:
        connection.close()

def get_balance(user_id):
    """获取用户余额"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 通过数据库id获取余额
                cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id_db,))
                balance_result = cursor.fetchone()
                if balance_result:
                    return balance_result['balance']
            
            # 如果用户不存在或余额记录不存在，默认为0
            return 0
    finally:
        connection.close()

def update_balance(user_id, amount):
    """更新用户余额"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 检查余额是否存在
                cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id_db,))
                balance_result = cursor.fetchone()
                
                if balance_result:
                    # 更新余额
                    new_balance = balance_result['balance'] + amount
                    cursor.execute('UPDATE balances SET balance = %s WHERE user_id = %s', (new_balance, user_id_db))
                else:
                    # 如果余额不存在，初始化余额
                    new_balance = 0 + amount
                    cursor.execute('INSERT INTO balances (user_id, balance) VALUES (%s, %s)', (user_id_db, new_balance))
            else:
                # 如果用户不存在，创建用户并初始化余额
                cursor.execute('''
                    INSERT INTO users (user_id, token, username, first_name, last_name) 
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id, None, '', '', ''))
                # 获取生成的用户id
                user_id_db = cursor.lastrowid
                # 初始化余额，默认为0
                new_balance = 0 + amount
                cursor.execute('INSERT INTO balances (user_id, balance) VALUES (%s, %s)', (user_id_db, new_balance))
            
            connection.commit()
            return new_balance
    finally:
        connection.close()

def get_last_checkin(user_id):
    """获取用户上次签到时间"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 通过数据库id获取签到记录
                cursor.execute('SELECT last_checkin FROM daily_checkins WHERE user_id = %s', (user_id_db,))
                result = cursor.fetchone()
                if result:
                    return result['last_checkin']
            return None
    finally:
        connection.close()

def update_user_token(telegram_id, token, first_name='', last_name=''):
    """更新用户的 token 信息"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        with connection.cursor() as cursor:
            # 调用 API 获取用户信息
            import requests
            user_data = None
            try:
                api_url = "https://api.emos.best/user"
                headers = {"Authorization": f"Bearer {token}"}
                response = requests.get(api_url, headers=headers, timeout=10)
                if response.status_code == 200:
                    user_data = response.json()
            except Exception as e:
                print(f"获取用户信息失败: {e}")
            
            if user_data:
                # 获取用户信息
                user_id_api = user_data.get('user_id')  # 形如 e0E446ZE6s 的用户ID
                username = user_data.get('username', '')
                telegram_user_id = user_data.get('telegram_user_id', telegram_id)
                
                # 检查用户是否已存在（通过 user_id）
                cursor.execute('SELECT * FROM users WHERE user_id = %s', (user_id_api,))
                existing_user = cursor.fetchone()
                
                if existing_user:
                    # 如果用户存在，更新其信息
                    cursor.execute('''
                        UPDATE users SET token = %s, username = %s, telegram_id = %s, first_name = %s, last_name = %s 
                        WHERE user_id = %s
                    ''', (token, username, telegram_user_id, first_name, last_name, user_id_api))
                    
                    # 确保用户有余额记录
                    user_id_db = existing_user['id']
                    cursor.execute('SELECT * FROM balances WHERE user_id = %s', (user_id_db,))
                    balance_result = cursor.fetchone()
                    if not balance_result:
                        # 如果余额记录不存在，创建一个，默认为0
                        cursor.execute('INSERT INTO balances (user_id, balance, username) VALUES (%s, %s, %s)', (user_id_db, 0, username))
                    else:
                        # 如果余额记录存在，更新username
                        cursor.execute('UPDATE balances SET username = %s WHERE user_id = %s', (username, user_id_db))
                else:
                    # 用户不存在，创建用户
                    cursor.execute('''
                        INSERT INTO users (user_id, telegram_id, token, username, first_name, last_name) 
                        VALUES (%s, %s, %s, %s, %s, %s)
                    ''', (user_id_api, telegram_user_id, token, username, first_name, last_name))
                    # 获取生成的用户id
                    user_id_db = cursor.lastrowid
                    # 为新用户初始化余额，默认为0
                    cursor.execute('INSERT INTO balances (user_id, balance, username) VALUES (%s, %s, %s)', (user_id_db, 0, username))
            
            connection.commit()
    except Exception as e:
        print(f"更新用户 token 时出错: {e}")
    finally:
        if connection:
            connection.close()

def update_checkin_time(user_id, timestamp):
    """更新用户签到时间"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 检查是否存在签到记录
                cursor.execute('SELECT * FROM daily_checkins WHERE user_id = %s', (user_id_db,))
                if cursor.fetchone():
                    # 更新签到时间
                    cursor.execute('UPDATE daily_checkins SET last_checkin = %s WHERE user_id = %s', (timestamp, user_id_db))
                else:
                    # 插入新签到记录
                    cursor.execute('INSERT INTO daily_checkins (user_id, last_checkin) VALUES (%s, %s)', (user_id_db, timestamp))
                
                connection.commit()
    finally:
        connection.close()

def add_game_record(user_id, game_type, bet_amount, result, win_amount):
    """添加游戏记录"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id或telegram_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s OR telegram_id = %s', (user_id, user_id))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 使用数据库id插入游戏记录
                cursor.execute('''
                    INSERT INTO game_records (user_id, game_type, bet_amount, result, win_amount) 
                    VALUES (%s, %s, %s, %s, %s)
                ''', (user_id_db, game_type, bet_amount, result, win_amount))
                connection.commit()
    finally:
        connection.close()

def add_withdrawal_record(user_id, amount):
    """添加提现记录"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 检查余额是否足够
                cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id_db,))
                balance_result = cursor.fetchone()
                
                if balance_result and balance_result['balance'] >= amount:
                    # 扣除余额
                    new_balance = balance_result['balance'] - amount
                    cursor.execute('UPDATE balances SET balance = %s WHERE user_id = %s', (new_balance, user_id_db))
                    
                    # 添加提现记录
                    cursor.execute('''
                        INSERT INTO withdrawal_records (user_id, amount, status) 
                        VALUES (%s, %s, %s)
                    ''', (user_id_db, amount, 'pending'))
                    
                    connection.commit()
                    return True
    except Exception as e:
        print(f"添加提现记录时出错: {e}")
    finally:
        connection.close()
    return False

def get_withdrawal_history(user_id):
    """获取用户的提现历史"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 查询用户的所有提现记录
                cursor.execute('''
                    SELECT amount, created_at 
                    FROM withdrawal_records 
                    WHERE user_id = %s 
                    ORDER BY created_at DESC
                ''', (user_id_db,))
                records = cursor.fetchall()
                return records
    except Exception as e:
        print(f"获取提现历史时出错: {e}")
    finally:
        connection.close()
    return []

def ensure_user_exists(emos_user_id, token, telegram_id=None, username=None, first_name=None, last_name=None):
    """确保用户存在，如果不存在则创建

    Returns:
        用户ID（本地数据库的id）
    """
    print(f"ensure_user_exists 被调用：")
    print(f"  emos_user_id: {emos_user_id} (API返回的用户ID)")
    print(f"  token: {token}")
    print(f"  telegram_id: {telegram_id} (Telegram用户ID)")
    print(f"  username: {username}")
    print(f"  first_name: {first_name}")
    print(f"  last_name: {last_name}")
    
    connection = get_db_connection()
    if not connection:
        print("  数据库连接失败")
        return None
    
    try:
        with connection.cursor() as cursor:
            # 检查用户是否存在
            if telegram_id:
                print(f"  检查用户是否存在：user_id={emos_user_id} 或 telegram_id={telegram_id}")
                cursor.execute("SELECT id, user_id, telegram_id FROM users WHERE user_id = %s OR telegram_id = %s", (emos_user_id, telegram_id))
            else:
                print(f"  检查用户是否存在：user_id={emos_user_id}")
                cursor.execute("SELECT id, user_id, telegram_id FROM users WHERE user_id = %s", (emos_user_id,))
            result = cursor.fetchone()
            
            if result:
                user_id = result['id']
                print(f"  用户已存在：id={user_id}, user_id={result['user_id']}, telegram_id={result['telegram_id']}")
                # 更新用户信息，确保username不为None
                print(f"  更新用户信息：token={token}, telegram_id={telegram_id}, username={username}")
                # 只有当username不为None时才更新
                if username is not None:
                    cursor.execute(
                        "UPDATE users SET token = %s, telegram_id = %s, username = %s, first_name = %s, last_name = %s WHERE id = %s",
                        (token, telegram_id, username, first_name, last_name, user_id)
                    )
                else:
                    # 不更新username字段
                    cursor.execute(
                        "UPDATE users SET token = %s, telegram_id = %s, first_name = %s, last_name = %s WHERE id = %s",
                        (token, telegram_id, first_name, last_name, user_id)
                    )
                connection.commit()
                print(f"  用户更新成功：id={user_id}")
                return user_id
            else:
                # 创建新用户，确保username不为None
                print(f"  用户不存在，创建新用户：user_id={emos_user_id}, telegram_id={telegram_id}")
                # 确保username不为None
                safe_username = username if username is not None else ''
                cursor.execute(
                    "INSERT INTO users (user_id, telegram_id, token, username, first_name, last_name) VALUES (%s, %s, %s, %s, %s, %s)",
                    (emos_user_id, telegram_id, token, safe_username, first_name, last_name)
                )
                user_id = cursor.lastrowid
                print(f"  新用户创建成功：id={user_id}")
                
                # 创建余额记录
                cursor.execute(
                    "INSERT INTO balances (user_id, balance) VALUES (%s, 0)",
                    (user_id,)
                )
                print(f"  余额记录创建成功：user_id={user_id}, balance=0")
                
                connection.commit()
                return user_id
    except Exception as e:
        print(f"  操作用户失败: {e}")
        connection.rollback()
        return None
    finally:
        connection.close()
        print(f"  数据库连接已关闭")


def add_recharge_order(order_no, user_id, telegram_user_id, carrot_amount, game_coin_amount, platform_order_no, pay_url, expire_time):
    """添加充值订单

    Args:
        order_no: 本地订单号
        user_id: 本地用户ID
        telegram_user_id: Telegram用户ID
        carrot_amount: 萝卜数量
        game_coin_amount: 游戏币数量
        platform_order_no: 平台订单号
        pay_url: 支付链接
        expire_time: 过期时间

    Returns:
        bool: 是否添加成功
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO recharge_orders (order_no, user_id, telegram_user_id, carrot_amount, game_coin_amount, platform_order_no, pay_url, expire_time)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (order_no, user_id, telegram_user_id, carrot_amount, game_coin_amount, platform_order_no, pay_url, expire_time))
            connection.commit()
            print(f"订单已保存到本地数据库: {order_no}")
            return True
    except Exception as e:
        print(f"添加充值订单时出错: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_recharge_order_by_platform_no(platform_order_no):
    """通过平台订单号获取充值订单

    Args:
        platform_order_no: 平台订单号

    Returns:
        dict: 订单信息
    """
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM recharge_orders WHERE platform_order_no = %s', (platform_order_no,))
            order = cursor.fetchone()
            return order
    finally:
        connection.close()


def update_recharge_order_status(platform_order_no, status):
    """更新充值订单状态

    Args:
        platform_order_no: 平台订单号
        status: 状态

    Returns:
        bool: 是否更新成功
    """
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('UPDATE recharge_orders SET status = %s WHERE platform_order_no = %s', (status, platform_order_no))
            connection.commit()
            print(f"充值订单状态已更新: {platform_order_no} -> {status}")
            return True
    except Exception as e:
        print(f"更新充值订单状态时出错: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_recharge_history(user_id):
    """获取用户的充值历史"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT id FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                user_id_db = user_result['id']
                # 查询用户的所有充值记录
                cursor.execute('''
                    SELECT carrot_amount, created_at 
                    FROM recharge_orders 
                    WHERE user_id = %s AND status = 'success' 
                    ORDER BY created_at DESC
                ''', (user_id_db,))
                records = cursor.fetchall()
                return records
    except Exception as e:
        print(f"获取充值历史时出错: {e}")
    finally:
        connection.close()
    return []

def get_user_total_recharge(user_id):
    """获取用户的累计充值金额"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT total_recharge FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                return user_result.get('total_recharge', 0)
            return 0
    except Exception as e:
        print(f"获取用户累计充值金额时出错: {e}")
        return 0
    finally:
        connection.close()

def update_user_total_recharge(user_id, amount):
    """更新用户的累计充值金额"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('UPDATE users SET total_recharge = total_recharge + %s WHERE user_id = %s', (amount, user_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新用户累计充值金额时出错: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_user_total_withdraw(user_id):
    """获取用户的累计提现金额"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('SELECT total_withdraw FROM users WHERE user_id = %s', (user_id,))
            user_result = cursor.fetchone()
            
            if user_result:
                return user_result.get('total_withdraw', 0)
            return 0
    except Exception as e:
        print(f"获取用户累计提现金额时出错: {e}")
        return 0
    finally:
        connection.close()

def update_user_total_withdraw(user_id, amount):
    """更新用户的累计提现金额"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # 先通过用户的user_id找到用户在数据库中的id
            cursor.execute('UPDATE users SET total_withdraw = total_withdraw + %s WHERE user_id = %s', (amount, user_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新用户累计提现金额时出错: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()