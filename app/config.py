# 配置文件 - 使用魔盒的配置

# 从魔盒导入配置
from config import Config, user_tokens, SERVICE_PROVIDER_TOKEN, DEFAULT_GROUP_CHAT_ID

# 机器人配置
BOT_USERNAME = Config.BOT_USERNAME

# API 配置
API_BASE_URL = Config.API_BASE_URL
API_USER_ENDPOINT = Config.API_USER_ENDPOINT

# 从数据库加载 token
def load_tokens_from_db():
    """从数据库加载所有用户的 token 到内存"""
    try:
        from app.database import get_db_connection
        
        connection = get_db_connection()
        if not connection:
            print("数据库连接失败，跳过加载 token")
            return
        
        try:
            with connection.cursor() as cursor:
                # 查询所有用户的 token
                cursor.execute('SELECT user_id, telegram_id, token, username, first_name, last_name FROM users WHERE token IS NOT NULL')
                results = cursor.fetchall()
                
                # 打印结果数量
                print(f"查询到 {len(results)} 个用户记录")
                
                # 填充到 user_tokens 字典
                count = 0
                for result in results:
                    try:
                        # 打印每条记录的内容
                        print(f"处理记录: {result}")
                        
                        # 检查必要字段
                        if 'telegram_id' not in result or 'token' not in result:
                            print(f"记录缺少必要字段: {result}")
                            continue
                        
                        telegram_id = result['telegram_id']
                        token = result['token']
                        user_id = result.get('user_id', '')
                        username = result.get('username', '')
                        first_name = result.get('first_name', '')
                        last_name = result.get('last_name', '')
                        
                        # 确保 telegram_id 是整数
                        if isinstance(telegram_id, str):
                            try:
                                telegram_id = int(telegram_id)
                            except:
                                print(f"telegram_id 不是有效的整数: {telegram_id}")
                                continue
                        
                        user_tokens[telegram_id] = {'token': token, 'user_id': user_id, 'username': username, 'first_name': first_name, 'last_name': last_name}
                        count += 1
                    except Exception as e:
                        print(f"处理单条记录时出错: {e}")
                        import traceback
                        print(f"错误堆栈: {traceback.format_exc()}")
                
                print(f"从数据库加载了 {count} 个用户的 token")
        except Exception as e:
            print(f"加载 token 时出错: {e}")
            import traceback
            print(f"错误堆栈: {traceback.format_exc()}")
        finally:
            connection.close()
    except Exception as e:
        print(f"导入数据库模块时出错: {e}")
        import traceback
        print(f"错误堆栈: {traceback.format_exc()}")

# 保存 token 到数据库
def save_token_to_db(telegram_id, token, user_id=None, username=None, first_name='', last_name=''):
    """将用户的 token 保存到数据库"""
    try:
        from app.database import update_user_token
        update_user_token(telegram_id, token, first_name, last_name)
    except Exception as e:
        print(f"保存 token 到数据库时出错: {e}")
    # 同时更新内存中的 token
    user_tokens[telegram_id] = {'token': token, 'user_id': user_id, 'username': username, 'first_name': first_name, 'last_name': last_name}

# 获取用户信息
def get_user_info(token):
    """使用 token 获取用户信息"""
    import requests
    try:
        api_url = API_USER_ENDPOINT
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(api_url, headers=headers, timeout=10)
        
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        return None
