import pymysql
import socks
import socket
import os
from config import DB_CONFIG
from queue import Queue
import threading

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
        connection_pool = DatabaseConnectionPool(max_connections=10)
    return connection_pool

# 延迟初始化
init_connection_pool()

def get_db_connection():
    """从连接池获取数据库连接"""
    return connection_pool.get_connection()

def return_db_connection(connection):
    """将连接返回池"""
    connection_pool.return_connection(connection)