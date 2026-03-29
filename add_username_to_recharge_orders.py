import pymysql
import logging
from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset=DB_CONFIG['charset'],
            cursorclass=pymysql.cursors.DictCursor
        )
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

def add_username_column():
    """给recharge_orders表添加username字段"""
    conn = get_db_connection()
    if not conn:
        logger.error("数据库连接失败")
        return False
    
    try:
        with conn.cursor() as cursor:
            # 检查字段是否已存在
            cursor.execute("DESCRIBE recharge_orders")
            columns = [col['Field'] for col in cursor.fetchall()]
            
            if 'username' in columns:
                logger.info("username字段已存在，无需添加")
                return True
            
            # 添加username字段
            logger.info("正在添加username字段...")
            cursor.execute("""
                ALTER TABLE recharge_orders 
                ADD COLUMN username VARCHAR(255) 
                COMMENT 'EMOS用户名（从API返回的username）'
                AFTER user_id
            """)
            logger.info("username字段添加成功")
            
            # 添加username索引
            logger.info("正在添加username索引...")
            cursor.execute("""
                CREATE INDEX idx_username 
                ON recharge_orders (username)
            """)
            logger.info("username索引添加成功")
            
            # 尝试从users表更新现有记录的username
            logger.info("正在更新现有充值订单的username...")
            cursor.execute("""
                UPDATE recharge_orders ro
                INNER JOIN users u ON ro.user_id = u.user_id
                SET ro.username = u.username
                WHERE ro.username IS NULL OR ro.username = ''
            """)
            updated_count = cursor.rowcount
            logger.info(f"已更新 {updated_count} 条充值订单的username")
            
            conn.commit()
            logger.info("所有操作完成！")
            return True
            
    except Exception as e:
        logger.error(f"添加username字段失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    success = add_username_column()
    if success:
        print("✅ 数据库更新成功！")
    else:
        print("❌ 数据库更新失败！")
