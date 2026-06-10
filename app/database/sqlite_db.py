import sqlite3
import os
from datetime import date, datetime

DB_PATH = 'local_database.db'

def get_db_connection():
    """获取SQLite数据库连接"""
    try:
        conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def init_db():
    """初始化数据库表结构"""
    connection = get_db_connection()
    if not connection:
        print("数据库连接失败")
        return False
    
    try:
        cursor = connection.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                telegram_id INTEGER,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                token TEXT,
                total_recharge INTEGER DEFAULT 0,
                total_withdraw INTEGER DEFAULT 0,
                current_cycle_score INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS balances (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                balance INTEGER DEFAULT 0,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS checkins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                checkin_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(user_id, checkin_date)
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                game_type TEXT NOT NULL,
                bet_amount INTEGER NOT NULL,
                result TEXT NOT NULL,
                win_amount INTEGER DEFAULT 0,
                username TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recharge_orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT,
                telegram_user_id INTEGER,
                carrot_amount INTEGER NOT NULL,
                game_coin_amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                platform_order_no TEXT,
                pay_url TEXT,
                expire_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS withdrawal_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_no TEXT UNIQUE NOT NULL,
                user_id TEXT NOT NULL,
                username TEXT,
                telegram_user_id INTEGER,
                game_coin_amount INTEGER NOT NULL,
                carrot_amount INTEGER NOT NULL,
                status TEXT DEFAULT 'pending',
                transfer_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS jackpot_pool (
                id INTEGER PRIMARY KEY DEFAULT 1,
                pool_amount INTEGER DEFAULT 0,
                total_contributions INTEGER DEFAULT 0,
                total_payouts INTEGER DEFAULT 0,
                last_winner_telegram_id INTEGER,
                last_win_amount INTEGER DEFAULT 0,
                last_win_time TIMESTAMP,
                last_update TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('INSERT OR IGNORE INTO jackpot_pool (id, pool_amount) VALUES (1, 0)')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS game_counter (
                id INTEGER PRIMARY KEY DEFAULT 1,
                counter INTEGER DEFAULT 1,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        cursor.execute('INSERT OR IGNORE INTO game_counter (id, counter) VALUES (1, 1)')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS daily_win_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT UNIQUE NOT NULL,
                username TEXT,
                win_amount INTEGER DEFAULT 0,
                win_date TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        connection.commit()
        print("SQLite数据库表初始化成功")
        return True
    except Exception as e:
        print(f"数据库初始化失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_user_by_telegram_id(telegram_id):
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            SELECT u.*, b.balance 
            FROM users u 
            LEFT JOIN balances b ON u.user_id = b.user_id 
            WHERE u.telegram_id = ?
        ''', (telegram_id,))
        result = cursor.fetchone()
        return dict(result) if result else None
    except Exception as e:
        print(f"获取用户信息失败: {e}")
        return None
    finally:
        connection.close()

def get_user_by_user_id(user_id):
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            SELECT u.*, b.balance 
            FROM users u 
            LEFT JOIN balances b ON u.user_id = b.user_id 
            WHERE u.user_id = ?
        ''', (user_id,))
        result = cursor.fetchone()
        return dict(result) if result else None
    except Exception as e:
        print(f"获取用户信息失败: {e}")
        return None
    finally:
        connection.close()

def add_user(user_id, telegram_id=None, username=None, first_name=None, last_name=None, token=None):
    if isinstance(telegram_id, dict):
        user_data = telegram_id
        telegram_id = user_data.get('telegram_id')
        username = user_data.get('username')
        first_name = user_data.get('first_name')
        last_name = user_data.get('last_name')
        token = user_data.get('token')
    
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        cursor.execute('''
            INSERT OR REPLACE INTO users (user_id, telegram_id, username, first_name, last_name, token, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
        ''', (user_id, telegram_id, username, first_name, last_name, token))
        
        cursor.execute('''
            INSERT OR IGNORE INTO balances (user_id, balance, username)
            VALUES (?, 100, ?)
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
    return add_user(user_id, telegram_id, username, first_name, last_name, token)

def get_balance(user_id):
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result['balance'] if result else 0
    except Exception as e:
        print(f"获取余额失败: {e}")
        return 0
    finally:
        connection.close()

def update_balance(user_id, amount):
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        if amount < 0:
            cursor.execute('SELECT balance FROM balances WHERE user_id = ?', (user_id,))
            result = cursor.fetchone()
            if result:
                current_balance = result['balance']
                if current_balance < abs(amount):
                    return False
        
        cursor.execute('''
            UPDATE balances 
            SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?
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
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            SELECT checkin_date FROM checkins 
            WHERE user_id = ? 
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
    if checkin_date is None:
        checkin_date = date.today().isoformat()
    
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO checkins (user_id, checkin_date)
            VALUES (?, ?)
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
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO game_records (user_id, game_type, bet_amount, result, win_amount, username)
            VALUES (?, ?, ?, ?, ?, ?)
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
    connection = get_db_connection()
    if not connection:
        return {'streak': 0, 'total_games': 0, 'total_wins': 0, 'total_losses': 0}
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            SELECT result FROM game_records 
            WHERE user_id = ? AND game_type = ?
            ORDER BY created_at DESC
        ''', (user_id, game_type))
        
        records = cursor.fetchall()
        
        if not records:
            return {'streak': 0, 'total_games': 0, 'total_wins': 0, 'total_losses': 0}
        
        total_games = len(records)
        total_wins = sum(1 for r in records if r['result'] == 'win')
        total_losses = sum(1 for r in records if r['result'] == 'lose')
        
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
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE users 
            SET token = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE user_id = ?
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
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO recharge_orders 
            (order_no, user_id, username, telegram_user_id, carrot_amount, game_coin_amount, 
             status, platform_order_no, pay_url, expire_time, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
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
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT * FROM recharge_orders WHERE platform_order_no = ?', (platform_order_no,))
        result = cursor.fetchone()
        return dict(result) if result else None
    except Exception as e:
        print(f"获取充值订单失败: {e}")
        return None
    finally:
        connection.close()

def update_recharge_order_status(platform_order_no, status, game_coin_amount=None):
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        
        if game_coin_amount is not None:
            cursor.execute('''
                UPDATE recharge_orders 
                SET status = ?, game_coin_amount = ?, updated_at = CURRENT_TIMESTAMP
                WHERE platform_order_no = ?
            ''', (status, game_coin_amount, platform_order_no))
        else:
            cursor.execute('''
                UPDATE recharge_orders 
                SET status = ?, updated_at = CURRENT_TIMESTAMP
                WHERE platform_order_no = ?
            ''', (status, platform_order_no))
        
        if status == 'success' and game_coin_amount is not None:
            cursor.execute('''
                SELECT user_id, carrot_amount FROM recharge_orders 
                WHERE platform_order_no = ?
            ''', (platform_order_no,))
            result = cursor.fetchone()
            if result:
                emos_user_id = result['user_id']
                carrot_amount = result['carrot_amount']
                
                cursor.execute('''
                    UPDATE balances 
                    SET balance = balance + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
                ''', (game_coin_amount, emos_user_id))
                
                cursor.execute('''
                    UPDATE users 
                    SET total_recharge = total_recharge + ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
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
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            INSERT INTO withdrawal_records 
            (order_no, user_id, username, telegram_user_id, game_coin_amount, carrot_amount, status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
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
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            SELECT * FROM recharge_orders 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        results = cursor.fetchall()
        return [dict(r) for r in results]
    except Exception as e:
        print(f"获取充值记录失败: {e}")
        return []
    finally:
        connection.close()

def get_withdrawal_history(user_id, limit=10):
    connection = get_db_connection()
    if not connection:
        return []
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            SELECT * FROM withdrawal_records 
            WHERE user_id = ? 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (user_id, limit))
        results = cursor.fetchall()
        return [dict(r) for r in results]
    except Exception as e:
        print(f"获取提现记录失败: {e}")
        return []
    finally:
        connection.close()

def get_user_total_recharge(user_id):
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT total_recharge FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result['total_recharge'] if result else 0
    except Exception as e:
        print(f"获取累计充值失败: {e}")
        return 0
    finally:
        connection.close()

def update_user_total_recharge(user_id, amount):
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE users 
            SET total_recharge = total_recharge + ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
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
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT total_withdraw FROM users WHERE user_id = ?', (user_id,))
        result = cursor.fetchone()
        return result['total_withdraw'] if result else 0
    except Exception as e:
        print(f"获取累计提现失败: {e}")
        return 0
    finally:
        connection.close()

def update_user_total_withdraw(user_id, amount):
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE users 
            SET total_withdraw = total_withdraw + ?, updated_at = CURRENT_TIMESTAMP
            WHERE user_id = ?
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
    connection = get_db_connection()
    if not connection:
        return {'amount': 0, 'date': None}
    
    try:
        today = date.today().isoformat()
        cursor = connection.cursor()
        cursor.execute('''
            SELECT win_amount, win_date 
            FROM daily_win_records 
            WHERE user_id = ?
        ''', (str(user_id),))
        
        result = cursor.fetchone()
        if result:
            record_date = result['win_date']
            if record_date != today:
                cursor.execute('''
                    UPDATE daily_win_records 
                    SET win_amount = 0, win_date = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE user_id = ?
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
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        today = date.today().isoformat()
        cursor = connection.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO daily_win_records (user_id, username, win_amount, win_date)
            VALUES (?, ?, ?, ?)
        ''', (str(user_id), username, amount, today))
        connection.commit()
        return True
    except Exception as e:
        print(f"更新每日赢取记录失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_game_counter():
    connection = get_db_connection()
    if not connection:
        return 1
    
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT counter FROM game_counter WHERE id = 1')
        result = cursor.fetchone()
        return result['counter'] if result else 1
    except Exception as e:
        print(f"获取游戏编号失败: {e}")
        return 1
    finally:
        connection.close()

def increment_game_counter():
    connection = get_db_connection()
    if not connection:
        return 1
    
    try:
        cursor = connection.cursor()
        cursor.execute('SELECT counter FROM game_counter WHERE id = 1')
        result = cursor.fetchone()
        current = result['counter'] if result else 1
        
        new_counter = current + 1
        cursor.execute('UPDATE game_counter SET counter = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1', (new_counter,))
        connection.commit()
        return current
    except Exception as e:
        print(f"递增游戏编号失败: {e}")
        return 1
    finally:
        connection.close()

def init_daily_win_record(user_id, username):
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        today = date.today().isoformat()
        cursor = connection.cursor()
        cursor.execute('''
            INSERT OR IGNORE INTO daily_win_records (user_id, username, win_amount, win_date)
            VALUES (?, ?, 0, ?)
        ''', (str(user_id), username, today))
        connection.commit()
        return True
    except Exception as e:
        print(f"初始化每日赢取记录失败: {e}")
        return False
    finally:
        connection.close()