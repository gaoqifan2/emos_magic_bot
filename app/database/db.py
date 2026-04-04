import pymysql
import socks
import socket
import os
from config import DB_CONFIG
from queue import Queue
import threading
from utils.http_client import http_client

# 代理配置（从环境变量读取，默认使用 Clash 端口）
PROXY_HOST = os.getenv('DB_PROXY_HOST', '127.0.0.1')
PROXY_PORT = int(os.getenv('DB_PROXY_PORT', '7890'))

class DatabaseConnectionPool:
    def __init__(self, max_connections=5):
        self.max_connections = max_connections
        self.pool = Queue(maxsize=max_connections)
        self.lock = threading.Lock()
        # 只初始化2个连接，避免阻塞
        self._initialize_pool(2)
    
    def _initialize_pool(self, initial_connections=2):
        """初始化连接池"""
        for _ in range(initial_connections):
            connection = self._create_connection()
            if connection:
                self.pool.put(connection)
    
    def _create_connection(self):
        """创建数据库连接"""
        try:
            # 尝试直接连接
            connection = pymysql.connect(
                **DB_CONFIG,
                cursorclass=pymysql.cursors.DictCursor,
                connect_timeout=5,
                read_timeout=5,
                write_timeout=5
            )
            return connection
        except Exception:
            try:
                # 尝试通过代理连接
                original_socket = socket.socket
                socks.set_default_proxy(socks.SOCKS5, PROXY_HOST, PROXY_PORT)
                socket.socket = socks.socksocket
                
                connection = pymysql.connect(
                    **DB_CONFIG,
                    cursorclass=pymysql.cursors.DictCursor,
                    connect_timeout=5
                )
                
                socket.socket = original_socket
                return connection
            except Exception:
                socket.socket = original_socket
                return None
    
    def get_connection(self):
        """从连接池获取连接"""
        try:
            # 尝试从池中获取连接
            connection = self.pool.get(block=False)
            # 检查连接是否有效
            if self._is_connection_valid(connection):
                return connection
            else:
                # 连接无效，创建新连接
                new_connection = self._create_connection()
                if new_connection:
                    return new_connection
                # 如果创建失败，尝试再次从池中获取
                return self.pool.get()
        except Exception:
            # 池为空，创建新连接
            return self._create_connection()
    
    def _is_connection_valid(self, connection):
        """检查连接是否有效"""
        if not connection:
            return False
        try:
            with connection.cursor() as cursor:
                cursor.execute('SELECT 1')
                return True
        except Exception:
            return False
    
    def return_connection(self, connection):
        """将连接返回池"""
        try:
            if connection and self._is_connection_valid(connection):
                if not self.pool.full():
                    self.pool.put(connection)
                else:
                    connection.close()
            else:
                if connection:
                    connection.close()
        except Exception:
            pass
    
    def close_all_connections(self):
        """关闭所有连接"""
        while not self.pool.empty():
            try:
                connection = self.pool.get()
                connection.close()
            except Exception:
                pass

# 创建全局连接池实例（延迟初始化）
connection_pool = None

def init_connection_pool():
    """初始化连接池"""
    global connection_pool
    if connection_pool is None:
        # 根据VPS资源调整连接池大小
        # 建议: 2-4核CPU -> 20-50连接, 4-8核CPU -> 50-100连接
        import os
        max_conn = int(os.getenv('DB_MAX_CONNECTIONS', '50'))
        connection_pool = DatabaseConnectionPool(max_connections=max_conn)
    return connection_pool

# 延迟初始化
# init_connection_pool()  # 注释掉这行代码，避免在模块导入时执行

def get_db_connection():
    """从连接池获取数据库连接"""
    global connection_pool
    if connection_pool is None:
        init_connection_pool()
    return connection_pool.get_connection()

def return_db_connection(connection):
    """将连接返回池"""
    global connection_pool
    if connection_pool is not None:
        connection_pool.return_connection(connection)


def init_db():
    """初始化数据库表结构"""
    connection = get_db_connection()
    if not connection:
        print("数据库连接失败")
        return False
    
    try:
        with connection.cursor() as cursor:
            # 创建用户表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) UNIQUE NOT NULL,
                    telegram_id BIGINT UNIQUE,
                    username VARCHAR(255),
                    first_name VARCHAR(255),
                    last_name VARCHAR(255),
                    token VARCHAR(512),
                    total_recharge INT DEFAULT 0,
                    total_withdraw INT DEFAULT 0,
                    current_cycle_score INT DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建余额表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS balances (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) UNIQUE NOT NULL,
                    balance INT DEFAULT 0,
                    username VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建签到记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS checkins (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    checkin_date DATE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY unique_user_checkin (user_id, checkin_date)
                )
            ''')
            
            # 创建游戏记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS game_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    user_id VARCHAR(255) NOT NULL,
                    game_type VARCHAR(50) NOT NULL,
                    bet_amount INT NOT NULL,
                    result VARCHAR(20) NOT NULL,
                    win_amount INT DEFAULT 0,
                    username VARCHAR(255),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建充值订单表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS recharge_orders (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_no VARCHAR(255) UNIQUE NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    username VARCHAR(255),
                    telegram_user_id BIGINT,
                    carrot_amount INT NOT NULL,
                    game_coin_amount INT NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    platform_order_no VARCHAR(255),
                    pay_url TEXT,
                    expire_time TIMESTAMP NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建提现记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS withdrawal_records (
                    id INT AUTO_INCREMENT PRIMARY KEY,
                    order_no VARCHAR(255) UNIQUE NOT NULL,
                    user_id VARCHAR(255) NOT NULL,
                    username VARCHAR(255),
                    telegram_user_id BIGINT,
                    game_coin_amount INT NOT NULL,
                    carrot_amount INT NOT NULL,
                    status VARCHAR(50) DEFAULT 'pending',
                    transfer_result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            
            # 创建奖池表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS jackpot_pool (
                    id INT PRIMARY KEY DEFAULT 1,
                    pool_amount INT DEFAULT 0,
                    total_contributions INT DEFAULT 0,
                    total_payouts INT DEFAULT 0,
                    last_winner_telegram_id BIGINT,
                    last_win_amount INT DEFAULT 0,
                    last_win_time TIMESTAMP NULL,
                    last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                )
            ''')
            
            # 初始化奖池记录
            cursor.execute('''
                INSERT IGNORE INTO jackpot_pool (id, pool_amount) VALUES (1, 0)
            ''')
            
            connection.commit()
            print("数据库表初始化成功")
            return True
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_user_by_telegram_id(telegram_id):
    """根据Telegram ID获取用户信息"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT u.*, b.balance 
                FROM users u 
                LEFT JOIN balances b ON u.user_id = b.user_id 
                WHERE u.telegram_id = %s
            ''', (telegram_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"获取用户信息失败: {e}")
        return None
    finally:
        connection.close()


def get_user_by_user_id(user_id):
    """根据用户ID获取用户信息"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT u.*, b.balance 
                FROM users u 
                LEFT JOIN balances b ON u.user_id = b.user_id 
                WHERE u.user_id = %s
            ''', (user_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"获取用户信息失败: {e}")
        return None
    finally:
        connection.close()


def add_user(user_id, telegram_id=None, username=None, first_name=None, last_name=None, token=None):
    """添加新用户"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            # 插入用户
            cursor.execute('''
                INSERT INTO users (user_id, telegram_id, username, first_name, last_name, token)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    telegram_id = COALESCE(VALUES(telegram_id), telegram_id),
                    username = COALESCE(VALUES(username), username),
                    first_name = COALESCE(VALUES(first_name), first_name),
                    last_name = COALESCE(VALUES(last_name), last_name),
                    token = COALESCE(VALUES(token), token)
            ''', (user_id, telegram_id, username, first_name, last_name, token))
            
            # 创建余额记录
            cursor.execute('''
                INSERT IGNORE INTO balances (user_id, balance, username)
                VALUES (%s, 0, %s)
            ''', (user_id, username))
            
            connection.commit()
            return True
    except Exception as e:
        print(f"添加用户失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def ensure_user_exists(user_id, telegram_id=None, username=None, first_name=None, last_name=None, token=None):
    """确保用户存在，如果不存在则创建"""
    return add_user(user_id, telegram_id, username, first_name, last_name, token)


def get_balance(user_id):
    """获取用户余额"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT balance FROM balances WHERE user_id = %s', (user_id,))
            result = cursor.fetchone()
            return result['balance'] if result else 0
    except Exception as e:
        print(f"获取余额失败: {e}")
        return 0
    finally:
        connection.close()


def update_balance(user_id, amount):
    """更新用户余额"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE balances 
                SET balance = balance + %s 
                WHERE user_id = %s
            ''', (amount, user_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新余额失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_last_checkin(user_id):
    """获取用户上次签到时间"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT checkin_date FROM checkins 
                WHERE user_id = %s 
                ORDER BY checkin_date DESC 
                LIMIT 1
            ''', (user_id,))
            result = cursor.fetchone()
            return result['checkin_date'] if result else None
    except Exception as e:
        print(f"获取签到记录失败: {e}")
        return None
    finally:
        connection.close()


def update_checkin_time(user_id, checkin_date=None):
    """更新用户签到时间"""
    from datetime import date
    
    if checkin_date is None:
        checkin_date = date.today()
    
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO checkins (user_id, checkin_date)
                VALUES (%s, %s)
                ON DUPLICATE KEY UPDATE checkin_date = VALUES(checkin_date)
            ''', (user_id, checkin_date))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新签到记录失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def add_game_record(user_id, game_type, bet_amount, result, win_amount=0, username=None):
    """添加游戏记录"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO game_records (user_id, game_type, bet_amount, result, win_amount, username)
                VALUES (%s, %s, %s, %s, %s, %s)
            ''', (user_id, game_type, bet_amount, result, win_amount, username))
            connection.commit()
            return True
    except Exception as e:
        print(f"添加游戏记录失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_user_streak(user_id, game_type):
    """获取用户连胜/连败记录
    
    返回: {
        'streak': 连胜/连败次数（正数为连胜，负数为连败）,
        'total_games': 总游戏次数,
        'total_wins': 总胜场,
        'total_losses': 总败场
    }
    """
    connection = get_db_connection()
    if not connection:
        return {'streak': 0, 'total_games': 0, 'total_wins': 0, 'total_losses': 0}
    
    try:
        with connection.cursor() as cursor:
            # 获取该游戏类型的所有记录（按时间倒序）
            cursor.execute('''
                SELECT result FROM game_records 
                WHERE user_id = %s AND game_type = %s
                ORDER BY created_at DESC
            ''', (user_id, game_type))
            
            records = cursor.fetchall()
            
            if not records:
                return {'streak': 0, 'total_games': 0, 'total_wins': 0, 'total_losses': 0}
            
            total_games = len(records)
            total_wins = sum(1 for r in records if r['result'] == 'win')
            total_losses = sum(1 for r in records if r['result'] == 'lose')
            
            # 计算连胜/连败
            streak = 0
            if records:
                first_result = records[0]['result']
                for record in records:
                    if record['result'] == first_result and record['result'] in ['win', 'lose']:
                        if first_result == 'win':
                            streak += 1
                        else:
                            streak -= 1
                    else:
                        break
            
            return {
                'streak': streak,
                'total_games': total_games,
                'total_wins': total_wins,
                'total_losses': total_losses
            }
    except Exception as e:
        print(f"获取连胜记录失败: {e}")
        return {'streak': 0, 'total_games': 0, 'total_wins': 0, 'total_losses': 0}
    finally:
        connection.close()


def update_user_token(user_id, token):
    """更新用户token"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE users 
                SET token = %s 
                WHERE user_id = %s
            ''', (token, user_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新用户token失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def add_recharge_order(order_no, user_id, username, telegram_user_id, carrot_amount, game_coin_amount, 
                       platform_order_no=None, pay_url=None, expire_time=None):
    """添加充值订单"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO recharge_orders 
                (order_no, user_id, username, telegram_user_id, carrot_amount, game_coin_amount, 
                 status, platform_order_no, pay_url, expire_time, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ''', (order_no, user_id, username, telegram_user_id, carrot_amount, game_coin_amount, 
                  'pending', platform_order_no, pay_url, expire_time))
            connection.commit()
            return True
    except Exception as e:
        print(f"添加充值订单失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_recharge_order_by_platform_no(platform_order_no):
    """根据平台订单号获取充值订单"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM recharge_orders 
                WHERE platform_order_no = %s
            ''', (platform_order_no,))
            return cursor.fetchone()
    except Exception as e:
        print(f"获取充值订单失败: {e}")
        return None
    finally:
        connection.close()


def update_recharge_order_status(platform_order_no, status, game_coin_amount=None):
    """更新充值订单状态"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            if game_coin_amount is not None:
                cursor.execute('''
                    UPDATE recharge_orders 
                    SET status = %s, game_coin_amount = %s, updated_at = NOW()
                    WHERE platform_order_no = %s
                ''', (status, game_coin_amount, platform_order_no))
            else:
                cursor.execute('''
                    UPDATE recharge_orders 
                    SET status = %s, updated_at = NOW()
                    WHERE platform_order_no = %s
                ''', (status, platform_order_no))
            
            # 如果订单成功，更新用户余额和累计充值金额
            if status == 'success' and game_coin_amount is not None:
                cursor.execute('''
                    SELECT user_id, carrot_amount FROM recharge_orders 
                    WHERE platform_order_no = %s
                ''', (platform_order_no,))
                result = cursor.fetchone()
                if result:
                    emos_user_id = result['user_id']
                    carrot_amount = result['carrot_amount']
                    
                    # 更新用户余额
                    cursor.execute('''
                        UPDATE balances 
                        SET balance = balance + %s 
                        WHERE user_id = %s
                    ''', (game_coin_amount, emos_user_id))
                    
                    # 更新用户累计充值金额
                    cursor.execute('''
                        UPDATE users 
                        SET total_recharge = total_recharge + %s 
                        WHERE user_id = %s
                    ''', (carrot_amount, emos_user_id))
            
            connection.commit()
            return True
    except Exception as e:
        print(f"更新充值订单状态失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def add_withdrawal_record(order_no, user_id, username, telegram_user_id, game_coin_amount, carrot_amount):
    """添加提现记录"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO withdrawal_records 
                (order_no, user_id, username, telegram_user_id, game_coin_amount, carrot_amount, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
            ''', (order_no, user_id, username, telegram_user_id, game_coin_amount, carrot_amount, 'pending'))
            connection.commit()
            return True
    except Exception as e:
        print(f"添加提现记录失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_recharge_history(user_id, limit=10):
    """获取用户充值记录"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM recharge_orders 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            ''', (user_id, limit))
            return cursor.fetchall()
    except Exception as e:
        print(f"获取充值记录失败: {e}")
        return []
    finally:
        connection.close()


def get_withdrawal_history(user_id, limit=10):
    """获取用户提现记录"""
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM withdrawal_records 
                WHERE user_id = %s 
                ORDER BY created_at DESC 
                LIMIT %s
            ''', (user_id, limit))
            return cursor.fetchall()
    except Exception as e:
        print(f"获取提现记录失败: {e}")
        return []
    finally:
        connection.close()


def get_user_total_recharge(user_id):
    """获取用户累计充值金额"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT total_recharge FROM users WHERE user_id = %s
            ''', (user_id,))
            result = cursor.fetchone()
            return result['total_recharge'] if result else 0
    except Exception as e:
        print(f"获取累计充值失败: {e}")
        return 0
    finally:
        connection.close()


def update_user_total_recharge(user_id, amount):
    """更新用户累计充值金额"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE users 
                SET total_recharge = total_recharge + %s 
                WHERE user_id = %s
            ''', (amount, user_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新累计充值失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_user_total_withdraw(user_id):
    """获取用户累计提现金额"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT total_withdraw FROM users WHERE user_id = %s
            ''', (user_id,))
            result = cursor.fetchone()
            return result['total_withdraw'] if result else 0
    except Exception as e:
        print(f"获取累计提现失败: {e}")
        return 0
    finally:
        connection.close()


def update_user_total_withdraw(user_id, amount):
    """更新用户累计提现金额"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE users 
                SET total_withdraw = total_withdraw + %s 
                WHERE user_id = %s
            ''', (amount, user_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新累计提现失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def get_daily_win(user_id):
    """获取用户今日从AI游戏赢取的金额"""
    connection = get_db_connection()
    if not connection:
        return {'amount': 0, 'date': None}
    
    try:
        from datetime import datetime
        today = datetime.now().date()
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT win_amount, win_date 
                FROM daily_win_records 
                WHERE user_id = %s
            ''', (str(user_id),))
            
            result = cursor.fetchone()
            if result:
                record_date = result['win_date']
                if record_date != today:
                    cursor.execute('''
                        UPDATE daily_win_records 
                        SET win_amount = 0, win_date = %s 
                        WHERE user_id = %s
                    ''', (today, str(user_id)))
                    connection.commit()
                    return {'amount': 0, 'date': today}
                return {'amount': result['win_amount'], 'date': record_date}
            else:
                return None
    except Exception as e:
        print(f"获取每日赢取记录失败: {e}")
        return {'amount': 0, 'date': None}
    finally:
        connection.close()


def update_daily_win(user_id, username, amount):
    """更新用户今日从AI游戏赢取的金额"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        from datetime import datetime
        today = datetime.now().date()
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO daily_win_records (user_id, username, win_amount, win_date)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    win_amount = win_amount + %s, 
                    win_date = %s,
                    username = %s
            ''', (str(user_id), username, amount, today, amount, today, username))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新每日赢取记录失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


def init_daily_win_record(user_id, username):
    """初始化用户每日赢取记录"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        from datetime import datetime
        today = datetime.now().date()
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT IGNORE INTO daily_win_records (user_id, username, win_amount, win_date)
                VALUES (%s, %s, 0, %s)
            ''', (str(user_id), username, today))
            connection.commit()
            return True
    except Exception as e:
        print(f"初始化每日赢取记录失败: {e}")
        return False
    finally:
        connection.close()
