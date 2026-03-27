import logging
import pymysql
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes, ConversationHandler, Application

from config import Config, BOT_COMMANDS, user_tokens, SERVICE_PROVIDER_TOKEN
from utils.db_helper import update_recharge_order_status

logger = logging.getLogger(__name__)

# 对话状态
WAITING_REDPACKET_ID = 20
WAITING_LOTTERY_CANCEL_ID = 21

async def post_init(application: Application) -> None:
    """机器人启动后执行的钩子函数"""
    from telegram import BotCommandScopeAllPrivateChats, BotCommandScopeAllGroupChats
    from config import GROUP_ALLOWED_COMMANDS
    
    # 为私聊设置完整的命令菜单
    private_commands = [BotCommand(cmd, desc) for cmd, desc in BOT_COMMANDS]
    await application.bot.set_my_commands(private_commands, scope=BotCommandScopeAllPrivateChats())
    
    # 为群聊设置只包含允许命令的菜单
    group_commands = [BotCommand(cmd, desc) for cmd, desc in BOT_COMMANDS if cmd in GROUP_ALLOWED_COMMANDS]
    await application.bot.set_my_commands(group_commands, scope=BotCommandScopeAllGroupChats())
    
    logger.info(f"机器人命令菜单已设置：私聊显示完整菜单，群聊只显示允许的命令: {GROUP_ALLOWED_COMMANDS}")

def add_cancel_button(keyboard=None, show_back=False):
    """添加取消按钮"""
    if keyboard is None:
        keyboard = []
    # 确保 keyboard 是可变的列表
    if not isinstance(keyboard, list):
        keyboard = []
    
    # 添加返回上一步按钮（如果需要）
    if show_back:
        keyboard.append([
            InlineKeyboardButton("⬅️ 返回上一步", callback_data="back_to_previous"),
            InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")
        ])
    else:
        keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")])
    return keyboard

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理取消按钮回调"""
    query = update.callback_query
    await query.answer()
    # 只清理红包创建相关的数据，保留登录信息和其他缓存
    # 清理红包创建数据
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    # 清理当前操作状态
    if 'current_operation' in context.user_data:
        del context.user_data['current_operation']
    # 保留uploaded_files，以便下次使用
    # 保留user_tokens，确保用户登录状态不被影响
    # 直接显示菜单，避免重复编辑消息
    try:
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    except Exception as e:
        logger.error(f"编辑消息失败: {e}")
        # 如果编辑失败，发送新消息
        await query.message.reply_text("✅ 操作已取消")
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理/start命令 - 登录"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 发送 /start 命令")
    
    text = update.message.text
    logger.info(f"完整的start命令文本: {text}")
    
    # 处理OAuth回调
    if text.startswith('/start oauth_callback'):
        # 提取回调参数
        callback_params = text.split('oauth_callback', 1)[1].strip()
        logger.info(f"OAuth回调参数: {callback_params}")
        
        # 解析参数
        params = {}
        if callback_params:
            # 移除开头的?
            if callback_params.startswith('?'):
                callback_params = callback_params[1:]
            # 分割参数
            param_pairs = callback_params.split('&')
            for pair in param_pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)
                    params[key] = value
        
        logger.info(f"解析后的参数: {params}")
        
        # 提取token
        token = params.get('token')
        if token:
            logger.info(f"收到授权Token: {token}")
            logger.info(f"Token长度: {len(token)}")
            # Token完整性检查
            if len(token) < 10:
                logger.error(f"Token不完整，长度: {len(token)}")
                await update.message.reply_text(f"❌ Token不完整，请重新尝试登录。")
                return
            # 确保token被完整存储
            # 存储为字典类型，以匹配游戏模块的期望格式
            user_tokens[user_id] = {'token': token, 'user_id': str(user_id), 'username': update.effective_user.username, 'first_name': update.effective_user.first_name, 'last_name': update.effective_user.last_name}
            try:
                logger.info(f"Token已存储到user_tokens: {user_tokens[user_id]}")
            except UnicodeEncodeError:
                logger.info(f"Token已存储到user_tokens: 包含非ASCII字符")
            
            # 获取用户信息
            import requests
            try:
                api_url = f"{Config.API_BASE_URL}/user"
                headers = {"Authorization": f"Bearer {token}"}
                logger.info(f"API请求头: {headers}")
                response = requests.get(api_url, headers=headers, timeout=10)
                logger.info(f"API响应状态码: {response.status_code}")
                if response.status_code == 200:
                    user_data = response.json()
                    try:
                        logger.info(f"用户数据: {user_data}")
                    except UnicodeEncodeError:
                        logger.info(f"用户数据: 包含非ASCII字符")
                    username = user_data.get('username', '用户')
                    user_id_api = user_data.get('user_id', '未知')
                    
                    # 更新user_tokens中的用户信息
                    user_tokens[user_id] = {'token': token, 'user_id': user_id_api, 'username': username, 'first_name': update.effective_user.first_name, 'last_name': update.effective_user.last_name}
                    try:
                        logger.info(f"用户信息已更新到user_tokens: {user_tokens[user_id]}")
                    except UnicodeEncodeError:
                        logger.info(f"用户信息已更新到user_tokens: 包含非ASCII字符")
                    
                    # 确保用户存在于数据库中
                    from utils.db_helper import ensure_user_exists
                    local_user_id = ensure_user_exists(
                        emos_user_id=user_id_api,
                        token=token,
                        telegram_id=user_id,
                        username=username,
                        first_name=update.effective_user.first_name,
                        last_name=update.effective_user.last_name
                    )
                    logger.info(f"用户 {user_id} 数据库操作结果: local_user_id={local_user_id}")
                    
                    # 删除登录面板消息
                    if 'login_message_id' in context.user_data and 'login_chat_id' in context.user_data:
                        try:
                            await context.bot.delete_message(
                                chat_id=context.user_data['login_chat_id'],
                                message_id=context.user_data['login_message_id']
                            )
                            # 清理存储的消息ID
                            del context.user_data['login_message_id']
                            del context.user_data['login_chat_id']
                        except Exception as e:
                            # 忽略删除失败的错误
                            pass
                    
                    await show_menu(update, f"✅ 授权成功！\n\n欢迎 {username} 使用综合机器人，你的ID是\n`{user_id_api}`\n\n请选择功能：")
                else:
                    logger.info(f"API响应内容: {response.text}")
                    await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
            except Exception as e:
                logger.error(f"获取用户信息失败: {e}")
                await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        else:
            logger.error("OAuth回调中没有token参数")
            await update.message.reply_text("❌ 授权失败，请重新尝试登录。")
        return
    # 处理用户同意授权的情况
    elif text.startswith('/start emosLinkAgree-'):
        # 提取完整的token，确保不会被截断
        token = text.split('/start emosLinkAgree-', 1)[1].strip()
        logger.info(f"收到授权Token: {token}")
        logger.info(f"Token长度: {len(token)}")
        # Token完整性检查
        if len(token) < 10:
            logger.error(f"Token不完整，长度: {len(token)}")
            await update.message.reply_text(f"❌ Token不完整，请重新尝试登录。")
            return
        # 确保token被完整存储
        # 存储为字典类型，以匹配游戏模块的期望格式
        user_tokens[user_id] = {'token': token, 'user_id': str(user_id), 'username': update.effective_user.username, 'first_name': update.effective_user.first_name, 'last_name': update.effective_user.last_name}
        try:
            logger.info(f"Token已存储到user_tokens: {user_tokens[user_id]}")
        except UnicodeEncodeError:
            logger.info(f"Token已存储到user_tokens: 包含非ASCII字符")
        # 获取用户信息
        import requests
        try:
            api_url = f"{Config.API_BASE_URL}/user"
            headers = {"Authorization": f"Bearer {token}"}
            logger.info(f"API请求头: {headers}")
            response = requests.get(api_url, headers=headers, timeout=10)
            logger.info(f"API响应状态码: {response.status_code}")
            if response.status_code == 200:
                user_data = response.json()
                try:
                    logger.info(f"用户数据: {user_data}")
                except UnicodeEncodeError:
                    logger.info(f"用户数据: 包含非ASCII字符")
                username = user_data.get('username', '用户')
                user_id_api = user_data.get('user_id', '未知')
                
                # 更新user_tokens中的用户信息
                user_tokens[user_id] = {'token': token, 'user_id': user_id_api, 'username': username, 'first_name': update.effective_user.first_name, 'last_name': update.effective_user.last_name}
                
                # 确保用户存在于数据库中
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=user_id_api,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name
                )
                logger.info(f"用户 {user_id} 数据库操作结果: local_user_id={local_user_id}")
                
                # 删除登录面板消息
                if 'login_message_id' in context.user_data and 'login_chat_id' in context.user_data:
                    try:
                        await context.bot.delete_message(
                            chat_id=context.user_data['login_chat_id'],
                            message_id=context.user_data['login_message_id']
                        )
                        # 清理存储的消息ID
                        del context.user_data['login_message_id']
                        del context.user_data['login_chat_id']
                    except Exception as e:
                        # 忽略删除失败的错误
                        pass
                
                await show_menu(update, f"✅ 授权成功！\n\n欢迎 {username} 使用综合机器人，你的ID是\n`{user_id_api}`\n\n请选择功能：")
            else:
                logger.info(f"API响应内容: {response.text}")
                await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        return
    # 处理用户拒绝授权的情况
    elif text.startswith('/start emosLinkRefuse-'):
        # 提取Telegram ID
        telegram_id = text.split('/start emosLinkRefuse-', 1)[1].strip()
        logger.info(f"用户 {user_id} 拒绝授权，Telegram ID: {telegram_id}")
        await update.message.reply_text("❌ 授权已拒绝，您可以稍后重新尝试登录。")
        return
    # 处理支付成功回调
    elif text.startswith('/start emosPayAgree-'):
        # 解析回调参数：emosPayAgree-订单号-参数-TgId
        callback_parts = text.split('/start emosPayAgree-', 1)[1].strip().split('-')
        order_no = callback_parts[0] if len(callback_parts) > 0 else ''
        param = callback_parts[1] if len(callback_parts) > 1 else ''
        tg_id = callback_parts[2] if len(callback_parts) > 2 else ''
        
        logger.info(f"收到支付成功回调 - 订单号: {order_no}, 参数: {param}, TgId: {tg_id}")
        
        loading = await update.message.reply_text("🔄 正在核实订单...")
        
        try:
            import httpx
            from utils.db_helper import get_order_by_platform_no
            
            # 首先从本地数据库查询订单信息
            order_info_db = get_order_by_platform_no(order_no)
            if not order_info_db:
                # 尝试在order_no字段中查询
                from utils.db_helper import get_db_connection
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                            cursor.execute(
                                "SELECT * FROM recharge_orders WHERE order_no = %s",
                                (order_no,)
                            )
                            order_info_db = cursor.fetchone()
                    finally:
                        conn.close()
                
                if not order_info_db:
                    await loading.edit_text(f"❌ 找不到订单信息：{order_no}")
                    return
            
            local_user_id = order_info_db.get('user_id')
            logger.info(f"订单归属用户ID: {local_user_id}")
            
            # 使用服务商token查询平台订单状态
            service_headers = {"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"}
            
            # 查询订单状态
            logger.info(f"查询订单状态: {order_no}")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{Config.API_BASE_URL}/pay/query?no={order_no}",
                    headers=service_headers,
                    timeout=10
                )
            
            logger.info(f"订单查询响应状态码: {response.status_code}")
            logger.info(f"订单查询响应内容: {response.text}")
            
            if response.status_code == 200:
                order_info = response.json()
                status = order_info.get('pay_status')
                
                if status == 'success':
                    # 支付成功，从本地数据库获取用户token
                    # 需要从users表获取用户的token
                    from utils.db_helper import get_db_connection
                    conn = get_db_connection()
                    user_token = None
                    actual_user_id = None
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute(
                                "SELECT id, token, telegram_id FROM users WHERE id = %s",
                                (local_user_id,)
                            )
                            user_result = cursor.fetchone()
                            if user_result:
                                actual_user_id = user_result[0]
                                user_token = user_result[1]
                                user_telegram_id = user_result[2]
                    finally:
                        conn.close()
                    
                    if not user_token:
                        await loading.edit_text("❌ 找不到用户token，请先登录")
                        return
                    
                    price = order_info.get('price_order', 0)
                    
                    logger.info(f"支付成功，开始兑换游戏币，金额: {price}, 用户ID: {actual_user_id}")
                    
                    # 直接计算游戏币（1萝卜=10游戏币）
                    game_coin = price * 10
                    
                    # 更新本地数据库订单状态
                    try:
                        update_recharge_order_status(
                            platform_order_no=order_no,
                            status='success',
                            game_coin_amount=game_coin
                        )
                    except Exception as db_error:
                        logger.error(f"更新本地订单失败: {db_error}")
                    
                    message = f"✅ 充值成功！\n\n"
                    message += f"订单号：`{order_no}`\n"
                    message += f"支付萝卜：{price} 🥕\n"
                    message += f"兑换游戏币：{game_coin} 🎮"
                    
                    logger.info(f"用户 {actual_user_id} 充值成功，订单号：{order_no}")
                    await loading.edit_text(message, parse_mode="Markdown")
                else:
                    await loading.edit_text(f"❌ 订单状态：{status}，支付可能未完成")
            else:
                await loading.edit_text(f"❌ 查询订单失败，状态码：{response.status_code}")
        except Exception as e:
            logger.error(f"处理支付回调失败: {e}")
            await loading.edit_text(f"❌ 处理支付回调失败，请稍后重试\n错误：{str(e)}")
        return
    
    # 处理支付失败回调
    elif text.startswith('/start emosPayRefuse-'):
        # 解析回调参数：emosPayRefuse-订单号-参数-TgId
        callback_parts = text.split('/start emosPayRefuse-', 1)[1].strip().split('-')
        order_no = callback_parts[0] if len(callback_parts) > 0 else ''
        
        logger.info(f"收到支付失败回调 - 订单号: {order_no}")
        
        await update.message.reply_text(f"❌ 支付已取消\n订单号：`{order_no}`\n", parse_mode="Markdown")
        return
    
    # 处理直接的token链接（兼容旧格式）
    elif text.startswith('/start link_e0E446ZE6s-'):
        # 提取完整的token，确保不会被截断
        token = text.split('/start link_e0E446ZE6s-', 1)[1].strip()
        logger.info(f"收到授权Token: {token}")
        logger.info(f"Token长度: {len(token)}")
        # Token完整性检查
        if len(token) < 10:
            logger.error(f"Token不完整，长度: {len(token)}")
            await update.message.reply_text(f"❌ Token不完整，请重新尝试登录。")
            return
        # 确保token被完整存储
        # 存储为字典类型，以匹配游戏模块的期望格式
        user_tokens[user_id] = {'token': token, 'user_id': str(user_id), 'username': update.effective_user.username, 'first_name': update.effective_user.first_name, 'last_name': update.effective_user.last_name}
        # 获取用户信息
        import requests
        try:
            api_url = f"{Config.API_BASE_URL}/user"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('username', '用户')
                user_id_api = user_data.get('user_id', '未知')
                
                # 更新user_tokens中的用户信息
                user_tokens[user_id] = {'token': token, 'user_id': user_id_api, 'username': username, 'first_name': update.effective_user.first_name, 'last_name': update.effective_user.last_name}
                
                # 确保用户存在于数据库中
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=user_id_api,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                last_name=update.effective_user.last_name
                )
                logger.info(f"用户 {user_id} 数据库操作结果: local_user_id={local_user_id}")
                
                # 删除登录面板消息
                if 'login_message_id' in context.user_data and 'login_chat_id' in context.user_data:
                    try:
                        await context.bot.delete_message(
                            chat_id=context.user_data['login_chat_id'],
                            message_id=context.user_data['login_message_id']
                        )
                        # 清理存储的消息ID
                        del context.user_data['login_message_id']
                        del context.user_data['login_chat_id']
                    except Exception as e:
                        # 忽略删除失败的错误
                        pass
                
                await show_menu(update, f"✅ 授权成功！\n\n欢迎 {username} 使用综合机器人，你的ID是\n`{user_id_api}`\n\n请选择功能：")
            else:
                await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        return
    
    if user_id in user_tokens:
        # 获取用户信息
        user_info = user_tokens[user_id]
        # 检查user_info是字典还是字符串
        if isinstance(user_info, dict):
            token = user_info.get('token')
        else:
            token = user_info
        import requests
        try:
            api_url = f"{Config.API_BASE_URL}/user"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('username', '用户')
                user_id_api = user_data.get('user_id', '未知')
                
                # 确保用户存在于数据库中并更新信息
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=user_id_api,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                logger.info(f"用户 {user_id} 数据库操作结果: local_user_id={local_user_id}")
                
                await show_menu(update, f"👋 欢迎回来 {username}！\n\n你的ID是\n`{user_id_api}`\n\n请选择功能：")
            else:
                # token可能已过期，提示用户重新登录
                await update.message.reply_text("❌ 登录已过期，请重新登录！")
                # 移除过期的token
                del user_tokens[user_id]
                # 显示登录选项
                await show_login_options(update, context)
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            # 移除可能无效的token
            if user_id in user_tokens:
                del user_tokens[user_id]
            # 显示登录选项
            await show_login_options(update, context)
    else:
        # 显示登录选项，要求用户使用正式token登录
        await show_login_options(update, context)

async def show_login_options(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示登录选项"""
    # 使用开发者的emos user_id来生成登录链接
    developer_emos_id = "e0E446ZE6s"
    auth_link_bot = f"https://t.me/emospg_bot?start=link_{developer_emos_id}-{Config.BOT_USERNAME}"
    keyboard = [
        [InlineKeyboardButton("🤖 机器人授权登录", url=auth_link_bot)],
        [InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await update.message.reply_text(
        "👋 欢迎使用综合机器人！\n\n使用前请先登录EMOS账号：",
        reply_markup=reply_markup
    )
    # 存储登录面板消息ID，以便登录成功后删除
    context.user_data['login_message_id'] = message.message_id
    context.user_data['login_chat_id'] = message.chat_id
    # 1分钟后自动消失（作为后备）
    import asyncio
    from utils.message_utils import auto_delete_message
    asyncio.create_task(auto_delete_message(update, context, message, 60))

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理/menu命令"""
    user_id = update.effective_user.id
    if user_id not in user_tokens:
        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        return
    await show_menu(update, "📱 功能菜单\n\n请选择功能：")

async def show_menu(update, message_text: str):
    """显示主菜单"""
    keyboard = [
        [
            InlineKeyboardButton("👤 我的信息", callback_data="menu_user_main"),
            InlineKeyboardButton("📝 签到", callback_data="menu_user_sign"),
            InlineKeyboardButton("💸 转账", callback_data="menu_transfer_main")
        ],
        [
            InlineKeyboardButton("🧧 红包", callback_data="menu_redpacket_main"),
            InlineKeyboardButton("🎲 抽奖", callback_data="menu_lottery_main"),
            InlineKeyboardButton("🏆 排行榜", callback_data="menu_rank_main")
        ],
        [
            InlineKeyboardButton("🎮 游戏厅", callback_data="games"),
            InlineKeyboardButton("🛠️ 服务商", callback_data="menu_service"),
            InlineKeyboardButton("🛒 商城", callback_data="menu_shop")
        ],
        [
            InlineKeyboardButton("📨 邀请", callback_data="menu_invite"),
            InlineKeyboardButton("👀 视奸", callback_data="admin_check_playing"),
            InlineKeyboardButton("🔍 大调查", callback_data="admin_user_info")
        ],
        [
            InlineKeyboardButton("❓ 帮助", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查消息中是否包含Markdown格式
    has_markdown = '`' in message_text or '```' in message_text
    parse_mode = "Markdown" if has_markdown else None
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=parse_mode)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有按钮回调"""
    query = update.callback_query
    data = query.data
    user_id = update.effective_user.id
    username = update.effective_user.username or "未知"
    try:
        logger.info(f"用户 {user_id} ({username}) 点击按钮: {data}")
    except UnicodeEncodeError:
        logger.info(f"用户 {user_id} 点击按钮: {data}")
    
    # 定义已知的回调前缀
    known_prefixes = ('type_', 'menu_', 'cancel_', 'back_', 'games', 'help', 'add_more_prizes', 'finish_prizes',
                      'service_', 'end_time_', 'need_bodys_', 'cancel_recharge')
    known_callbacks = ('games', 'help', 'add_more_prizes', 'finish_prizes', 'cancel_recharge')
    
    # menu_redpocket 直接处理，启动红包创建流程
    if data == 'menu_redpocket':
        logger.info(f"处理 menu_redpocket 按钮")
        from handlers.redpacket import redpocket_command
        return await redpocket_command(update, context)
    
    # 红包类型选择回调直接处理
    if data.startswith('type_'):
        logger.info(f"处理红包类型回调: {data}")
        from handlers.redpacket import handle_type
        return await handle_type(update, context)
    
    # 图片/语音红包口令选择回调
    if data in ('image_no_password', 'image_with_password', 'audio_no_password', 'audio_with_password'):
        logger.info(f"处理红包口令选择回调: {data}")
        from handlers.redpacket import handle_type
        return await handle_type(update, context)
    
    # 处理视奸按钮（移到游戏回调之前）
    if data == "admin_check_playing":
        logger.info(f"处理视奸按钮")
        await query.answer()
        # 显示命令并提供跳转按钮
        keyboard = [
            [InlineKeyboardButton("👥 跳转到 emospg 群", url="https://t.me/emospg")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "👀 **视奸功能**\n\n"  
            "请复制以下命令，然后点击下方按钮跳转到群并发送：\n\n"  
            "`/admin_check_playing`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        # 1分钟后自动消失
        import asyncio
        from utils.message_utils import auto_delete_message
        asyncio.create_task(auto_delete_message(update, context, None, 60))
        logger.info(f"显示视奸功能信息")
        return
    
    # 处理大调查按钮（移到游戏回调之前）
    if data == "admin_user_info":
        logger.info(f"处理大调查按钮")
        await query.answer()
        # 显示命令并提供跳转按钮
        keyboard = [
            [InlineKeyboardButton("👥 跳转到 emospg 群", url="https://t.me/emospg")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🔍 **大调查功能**\n\n"  
            "1. 先在群里**引用回复**一条用户的消息\n"  
            "2. 然后复制以下命令并发送：\n\n"  
            "`/admin_user_info`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        # 1分钟后自动消失
        import asyncio
        from utils.message_utils import auto_delete_message
        asyncio.create_task(auto_delete_message(update, context, None, 60))
        logger.info(f"显示大调查功能信息")
        return
    
    # 先 answer 回调
    await query.answer()
    logger.info(f"已响应回调: {data}")
    
    # 处理游戏相关的按钮回调
    from app.handlers.command_handlers import callback_handler as game_callback_handler
    # 将魔盒的 user_tokens 传递给游戏回调处理器
    from app.config import user_tokens as game_user_tokens
    # 同步魔盒的 user_tokens 到游戏模块
    for key, value in user_tokens.items():
        game_user_tokens[key] = value
    # 调用游戏回调处理器
    game_handled = await game_callback_handler(update, context)
    if game_handled:
        return
    
    # menu_redpocket 由 redpocket_conv 的 entry_points 处理，这里不处理
    
    if data == "cancel_operation":
        logger.info(f"处理取消操作按钮")
        return await cancel_callback(update, context)
    
    # 处理返回上一步
    if data == "back_to_previous":
        logger.info(f"处理返回上一步按钮")
        return await handle_back_to_previous(update, context)
    
    # 处理返回主菜单
    if data == "back_to_main":
        logger.info(f"处理返回主菜单按钮")
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
        return
    
    # 红包二级菜单
    if data == "menu_redpacket_main":
        logger.info(f"处理红包二级菜单按钮")
        await show_redpacket_menu(update, context)
        return
    
    # 抽奖二级菜单
    if data == "menu_lottery_main":
        logger.info(f"处理抽奖二级菜单按钮")
        await show_lottery_menu(update, context)
        return
    
    # 排行榜二级菜单
    if data == "menu_rank_main":
        logger.info(f"处理排行榜二级菜单按钮")
        await show_rank_menu(update, context)
        return
    
    # 转账二级菜单
    if data == "menu_transfer_main":
        logger.info(f"处理转账二级菜单按钮")
        await show_transfer_menu(update, context)
        return
    
    # 个人信息功能
    if data == "menu_user_main":
        logger.info(f"处理个人信息功能按钮")
        from user.user_info import get_user_info
        await get_user_info(update, context)
        return
    
    # 撤销邀请按钮
    if data == "menu_revoke_invite":
        logger.info(f"处理撤销邀请按钮")
        from user.user_info import user_revoke_invite
        return await user_revoke_invite(update, context)
    
    # 转赠功能
    if data == "menu_transfer":
        logger.info(f"处理转赠功能按钮")
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        
        # 检查user_info是字典还是字符串
        if isinstance(user_info, dict):
            token = user_info.get('token')
        else:
            token = user_info
        
        if not token:
            logger.info(f"用户未登录，提示登录")
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
            return
        
        # 提示用户输入对方用户ID
        logger.info(f"提示用户输入对方用户ID")
        await update.callback_query.edit_message_text("💸 请输入对方用户ID（10位字符串，以e开头s结尾）：")
        
        # 存储当前状态，等待用户输入
        context.user_data['current_operation'] = 'transfer_user_id'
        context.user_data['token'] = token
        logger.info(f"存储转赠操作状态")
        return 102  # 自定义状态码，用于处理转赠用户ID输入
    
    # 服务商转账功能
    if data == "menu_service_transfer":
        logger.info(f"处理服务商转账功能按钮")
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        
        # 检查user_info是字典还是字符串
        if isinstance(user_info, dict):
            token = user_info.get('token')
        else:
            token = user_info
        
        if not token:
            logger.info(f"用户未登录，提示登录")
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
            return
        
        # 检查用户是否为服务商
        is_service = False
        try:
            import httpx
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{Config.API_BASE_URL}/pay/base",
                    headers=headers,
                    timeout=10
                )
            
            if response.status_code == 200:
                is_service = True
                logger.info(f"用户是服务商")
            else:
                logger.info(f"用户不是服务商，状态码: {response.status_code}")
        except Exception as e:
            # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
            logger.error("检查服务商状态失败")
        
        if is_service:
            # 提示用户输入对方用户ID
            logger.info(f"提示服务商输入对方用户ID")
            await update.callback_query.edit_message_text("🏢 请输入对方用户ID（10位字符串，以e开头s结尾）：")
            
            # 存储当前状态，等待用户输入
            context.user_data['current_operation'] = 'service_fund_transfer_user_id'
            context.user_data['token'] = token
            logger.info(f"存储服务商转账操作状态")
            return 107  # 自定义状态码，用于处理服务商转账用户ID输入
        else:
            logger.info(f"用户不是服务商，提示无权限")
            await update.callback_query.edit_message_text("❌ 只有服务商才能使用此功能！")
            # 1分钟后自动消失
            import asyncio
            from utils.message_utils import auto_delete_message
            asyncio.create_task(auto_delete_message(update, context, None, 60))
            return
    
    # 服务商功能
    if data == "menu_service":
        logger.info(f"处理服务商功能按钮")
        from services.service_main import show_service_menu
        await show_service_menu(update, context)
        return
    
    # 商城功能
    if data == "menu_shop":
        logger.info(f"处理商城功能按钮")
        from shop.shop_main import show_shop_menu
        await show_shop_menu(update, context)
        return
    
    # 邀请功能
    if data == "menu_invite":
        logger.info(f"处理邀请功能按钮")
        # 跳转到个人信息的邀请功能
        from user.user_info import user_invite
        await user_invite(update, context)
        return
    
    # 猜拳功能
    if data == "menu_rock_paper_scissors":
        logger.info(f"处理猜拳功能按钮")
        await update.callback_query.edit_message_text("✊ 猜拳功能开发中，敬请期待！")
        # 显示返回菜单
        keyboard = [
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("猜拳功能", reply_markup=reply_markup)
        return
    
    # 处理游戏按钮
    if data == "menu_game":
        logger.info(f"处理游戏按钮")
        from app.handlers.command_handlers import start_handler
        return await start_handler(update, context)
    
    # 处理具体的功能按钮
    # menu_redpocket 由 redpocket_conv 的 entry_point 处理，这里不处理
    
    if data == "menu_check_redpacket":
        logger.info(f"处理查询红包按钮")
        from handlers.redpacket_query import check_redpacket_command
        return await check_redpacket_command(update, context)
    
    if data == "menu_lottery":
        logger.info(f"处理创建抽奖按钮")
        from games.lottery import lottery_command
        return await lottery_command(update, context)
    
    if data == "menu_lottery_cancel":
        logger.info(f"处理取消抽奖按钮")
        from games.lottery_cancel import lottery_cancel_command
        return await lottery_cancel_command(update, context)
    
    if data == "menu_lottery_win":
        logger.info(f"处理查询中奖列表按钮")
        from services.service_main import service_lottery_win
        await service_lottery_win(update, context)
        return
    
    if data == "menu_rank_carrot":
        logger.info(f"处理萝卜榜按钮")
        from ranks.carrot_rank import rank_carrot_command
        await rank_carrot_command(update, context)
        return
    
    if data == "menu_rank_upload":
        logger.info(f"处理上传榜按钮")
        from ranks.upload_rank import rank_upload_command
        await rank_upload_command(update, context)
        return
    
    if data == "menu_playing":
        logger.info(f"处理正在播放按钮")
        from ranks.playing_rank import playing_command
        await playing_command(update, context)
        return
    
    if data == "menu_user_info":
        logger.info(f"处理用户信息按钮")
        from user.user_info import get_user_info
        await get_user_info(update, context)
        return
    
    if data == "menu_user_sign":
        logger.info(f"处理签到按钮")
        from user.user_info import user_sign
        await user_sign(update, context)
        return
    
    if data == "menu_user_invite":
        logger.info(f"处理用户邀请按钮")
        from user.user_info import user_invite
        await user_invite(update, context)
        return
    
    if data == "menu_user_pseudonym":
        logger.info(f"处理修改笔名按钮")
        from user.user_info import user_pseudonym
        return await user_pseudonym(update, context)
    
    # 账号设置按钮
    if data == "menu_account_settings":
        logger.info(f"处理账号设置按钮")
        # 显示账号设置菜单
        keyboard = [
            [
                InlineKeyboardButton("❌ 隐藏空媒体库", callback_data="menu_hide_empty_library"),
                InlineKeyboardButton("✏️ 修改笔名", callback_data="menu_user_pseudonym")
            ],
            [InlineKeyboardButton("🔙 返回", callback_data="menu_user_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "⚙️ 账号设置",
            reply_markup=reply_markup
        )
        return
    
    # 隐藏空媒体库按钮
    if data == "menu_hide_empty_library":
        logger.info(f"处理隐藏空媒体库按钮")
        await update.callback_query.edit_message_text("✅ 已隐藏空媒体库")
        # 显示返回菜单
        keyboard = [[InlineKeyboardButton("🔙 返回账号设置", callback_data="menu_account_settings")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("操作成功", reply_markup=reply_markup)
        return
    
    # 密码管理按钮
    if data == "menu_password_management":
        logger.info(f"处理密码管理按钮")
        # 显示密码管理菜单
        keyboard = [
            [
                InlineKeyboardButton("👁️ 查看临时密码", callback_data="menu_view_temp_password"),
                InlineKeyboardButton("🔄 重置永久密码", callback_data="menu_reset_permanent_password")
            ],
            [
                InlineKeyboardButton("✏️ 自定义密码", callback_data="menu_custom_password")
            ],
            [InlineKeyboardButton("🔙 返回", callback_data="menu_user_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "🔑 密码管理",
            reply_markup=reply_markup
        )
        return
    
    # 自定义密码按钮
    if data == "menu_custom_password":
        logger.info(f"处理自定义密码按钮")
        # 提示用户输入自定义密码
        await update.callback_query.edit_message_text("✏️ 请输入自定义密码：")
        # 存储当前状态，等待用户输入
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        if isinstance(user_info, dict):
            token = user_info.get('token')
        else:
            token = user_info
        context.user_data['current_operation'] = 'custom_password'
        context.user_data['token'] = token
        return
    
    # 查看临时密码按钮
    if data == "menu_view_temp_password":
        logger.info(f"处理查看临时密码按钮")
        # 生成临时密码
        import random
        import string
        temp_password = ''.join(random.choices(string.ascii_letters + string.digits, k=8))
        await update.callback_query.edit_message_text(f"🔑 临时密码：`{temp_password}`")
        # 显示返回菜单
        keyboard = [[InlineKeyboardButton("🔙 返回密码管理", callback_data="menu_password_management")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("临时密码已生成", reply_markup=reply_markup)
        return
    
    # 重置永久密码按钮
    if data == "menu_reset_permanent_password":
        logger.info(f"处理重置永久密码按钮")
        # 生成新的永久密码
        import random
        import string
        new_password = ''.join(random.choices(string.ascii_letters + string.digits, k=12))
        await update.callback_query.edit_message_text(f"✅ 永久密码已重置：`{new_password}`")
        # 显示返回菜单
        keyboard = [[InlineKeyboardButton("🔙 返回密码管理", callback_data="menu_password_management")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("密码重置成功", reply_markup=reply_markup)
        return
    
    # 权限信息按钮
    if data == "menu_permission_info":
        logger.info(f"处理权限信息按钮")
        # 显示权限信息
        permission_message = (
            "🔒 权限信息\n\n"
            "基础权限：\n"
            "• 🎬 观影权限: ✅ 有权限\n"
            "• 📤 上传权限: ❌ 无权限\n"
            "• 📥 下载权限: ❌ 无权限\n\n"
            "其他信息：\n"
            "• 🎭 角色: 普通用户\n"
            "• 🖼️ 原图模式: ❌ 关闭\n\n"
            "说明：\n"
            "• 观影权限：是否可以观看视频\n"
            "• 上传权限：是否可以上传资源\n"
            "• 下载权限：是否可以下载资源"
        )
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="menu_user_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            permission_message,
            reply_markup=reply_markup
        )
        return
    
    # 修仙境界按钮
    if data == "menu_cultivation_level":
        logger.info(f"处理修仙境界按钮")
        # 获取用户信息
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        carrot = 0
        
        if user_info:
            # 检查user_info是字典还是字符串
            if isinstance(user_info, dict):
                # 尝试从API获取用户信息
                token = user_info.get('token')
                if token:
                    try:
                        import requests
                        api_url = f"{Config.API_BASE_URL}/user"
                        headers = {"Authorization": f"Bearer {token}"}
                        response = requests.get(api_url, headers=headers, timeout=10)
                        if response.status_code == 200:
                            user_data = response.json()
                            carrot = user_data.get('carrot', 0)
                    except Exception as e:
                        logger.error(f"获取用户信息失败: {e}")
        
        # 计算修仙境界和进度
        def calculate_cultivation_info(carrot):
            levels = [
                ("凡人期", 0, 9),
                ("练气期一层", 10, 19),
                ("练气期二层", 20, 29),
                ("练气期三层", 30, 39),
                ("练气期四层", 40, 49),
                ("练气期五层", 50, 59),
                ("练气期六层", 60, 69),
                ("练气期七层", 70, 79),
                ("练气期八层", 80, 89),
                ("练气期九层", 90, 99),
                ("筑基初期", 100, 149),
                ("筑基中期", 150, 299),
                ("筑基后期", 300, 599),
                ("筑基圆满", 600, 999),
                ("结丹初期", 1000, 1999),
                ("结丹中期", 2000, 3499),
                ("结丹后期", 3500, 5999),
                ("结丹圆满", 6000, 9999),
                ("元婴初期", 10000, 19999),
                ("元婴中期", 20000, 34999),
                ("元婴后期", 35000, 59999),
                ("元婴圆满", 60000, 99999),
                ("化神", 100000, 499999),
                ("炼虚", 500000, 999999),
                ("合体", 1000000, 9999999),
                ("大乘", 10000000, 99999999),
                ("真仙", 100000000, float('inf'))
            ]
            
            for i, (level_name, min_carrot, max_carrot) in enumerate(levels):
                if min_carrot <= carrot <= max_carrot:
                    if i < len(levels) - 1:
                        next_level = levels[i + 1]
                        next_level_name = next_level[0]
                        next_level_min = next_level[1]
                        remaining = next_level_min - carrot
                        total = next_level_min - min_carrot
                        if total > 0:
                            progress = min(100, int(((carrot - min_carrot) / total) * 100))
                        else:
                            progress = 100
                    else:
                        next_level_name = "无"
                        remaining = 0
                        progress = 100
                    
                    # 确定所属大境界
                    if level_name == "凡人期":
                        big_level = "凡尘俗世"
                        description = "凡人期，尚未踏入修仙之路"
                    elif "练气期" in level_name:
                        big_level = "炼气九重"
                        description = "炼气九重，打基础，炼精化气"
                    elif "筑基" in level_name:
                        big_level = "筑基四境"
                        description = "筑基四境，奠定道基"
                    elif "结丹" in level_name:
                        big_level = "结丹四境"
                        description = "结丹四境，凝结金丹"
                    elif "元婴" in level_name:
                        big_level = "元婴四境"
                        description = "元婴四境，修炼元婴"
                    else:
                        big_level = "上五境"
                        description = "上五境，超脱凡俗"
                    
                    return level_name, big_level, description, next_level_name, progress, remaining
            
            return "凡人期", "凡尘俗世", "凡人期，尚未踏入修仙之路", "练气期一层", 0, 10
        
        current_level, big_level, description, next_level, progress, remaining_carrot = calculate_cultivation_info(carrot)
        
        # 构建进度条
        progress_bar = "[" + "■" * (progress // 10) + "□" * (10 - progress // 10) + "]"
        
        # 显示修仙境界信息
        cultivation_message = (
            "🎋 修仙境界\n\n"
            f"🏛️ {current_level}\n\n"
            f"所属境界: {big_level}\n"
            f"境界描述: {description}\n"
            f"当前萝卜: {carrot} 🥕\n"
            f"境界进度: {progress_bar} {progress}%\n\n"
        )
        
        if next_level != "无":
            cultivation_message += (
                f"下一境界: {next_level}\n"
                f"还需萝卜: {remaining_carrot} 🥕\n\n"
            )
        else:
            cultivation_message += "已是最高境界！\n\n"
        
        cultivation_message += "多多签到、上传资源，积累萝卜提升境界！"
        keyboard = [[InlineKeyboardButton("🔙 返回", callback_data="menu_user_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            cultivation_message,
            reply_markup=reply_markup
        )
        return
    
    if data == "help":
        logger.info(f"处理帮助按钮")
        await help_command(update, context)
        return
    
    if data in ["add_more_prizes", "finish_prizes"]:
        logger.info(f"处理奖品选择按钮: {data}")
        from games.lottery import handle_prize_choice
        return await handle_prize_choice(update, context)
    
    # 服务商新功能回调
    if data == "service_user_manage":
        logger.info(f"处理服务商用户管理按钮")
        from services.service_main import service_user_manage
        await service_user_manage(update, context)
        return
    
    if data == "service_recharge":
        logger.info(f"处理服务商充值按钮")
        from services.service_main import service_recharge
        await service_recharge(update, context)
        return
    
    if data == "service_withdraw":
        logger.info(f"处理服务商提现按钮")
        from services.service_main import service_withdraw
        await service_withdraw(update, context)
        return
    
    if data == "service_game_center":
        logger.info(f"处理服务商游戏中心按钮")
        from services.service_main import service_game_center
        await service_game_center(update, context)
        return
    
    if data == "service_manage":
        logger.info(f"处理服务商管理按钮")
        from services.service_main import service_manage
        await service_manage(update, context)
        return
    
    if data == "service_apply":
        logger.info(f"处理服务商申请按钮")
        from services.service_main import service_apply
        await service_apply(update, context)
        return
    
    if data == "service_update":
        logger.info(f"处理服务商更新按钮")
        from services.service_main import service_update
        await service_update(update, context)
        return
    
    if data == "service_pay_create":
        logger.info(f"处理服务商创建支付订单按钮")
        from services.service_main import service_pay_create
        await service_pay_create(update, context)
        return
    
    if data == "service_pay_query":
        logger.info(f"处理服务商查询支付订单按钮")
        from services.service_main import service_pay_query
        await service_pay_query(update, context)
        return
    
    if data == "service_pay_close":
        logger.info(f"处理服务商关闭支付订单按钮")
        from services.service_main import service_pay_close
        await service_pay_close(update, context)
        return
    
    if data == "service_lottery_win":
        logger.info(f"处理服务商查询中奖列表按钮")
        from services.service_main import service_lottery_win
        await service_lottery_win(update, context)
        return
    
    if data == "service_fund_transfer":
        logger.info(f"处理服务商资金转账按钮")
        from services.service_main import service_fund_transfer
        await service_fund_transfer(update, context)
        return
    
    if data == "service_pay_create_telegram_bot":
        logger.info(f"处理Telegram机器人支付方式选择")
        # 处理Telegram机器人支付方式选择
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        
        # 检查user_info是字典还是字符串
        if isinstance(user_info, dict):
            token = user_info.get('token')
        else:
            token = user_info
        
        if token:
            # 获取存储的数据
            amount = context.user_data.get('amount')
            name = context.user_data.get('name')
            logger.info(f"创建Telegram机器人支付订单，金额: {amount}, 商品: {name}")
            
            loading = await update.callback_query.edit_message_text("🔄 正在创建订单...")
            
            try:
                import httpx
                headers = {"Authorization": f"Bearer {token}"}
                data = {"pay_way": "telegram_bot", "price": amount, "name": name}
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{Config.API_BASE_URL}/pay/create",
                        headers=headers,
                        json=data,
                        timeout=10
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    order_no = result.get('no', '未知')
                    logger.info(f"Telegram机器人支付订单创建成功，订单号: {order_no}")
                    await loading.edit_text(f"✅ 订单创建成功！\n订单号：`{order_no}`\n", parse_mode="Markdown")
                else:
                    logger.info(f"Telegram机器人支付订单创建失败，状态码: {response.status_code}")
                    await loading.edit_text(f"❌ 创建失败，状态码：{response.status_code}")
            except Exception as e:
                logger.error(f"创建订单失败: {e}")
                await loading.edit_text("❌ 创建失败，请稍后重试")
            
            # 清理用户数据
            # 只清理红包和当前操作相关数据，保留用户登录信息
            if 'redpacket' in context.user_data:
                del context.user_data['redpacket']
            if 'current_operation' in context.user_data:
                del context.user_data['current_operation']
            logger.info(f"清理用户数据")
        else:
            logger.info(f"用户未登录，提示登录")
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    if data == "service_pay_create_web":
        logger.info(f"处理网页支付方式选择")
        # 处理网页支付方式选择
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        
        # 检查user_info是字典还是字符串
        if isinstance(user_info, dict):
            token = user_info.get('token')
        else:
            token = user_info
        
        if token:
            amount = context.user_data.get('amount')
            name = context.user_data.get('name')
            logger.info(f"创建网页支付订单，金额: {amount}, 商品: {name}")
            
            loading = await update.callback_query.edit_message_text("🔄 正在创建订单...")
            
            try:
                import httpx
                headers = {"Authorization": f"Bearer {token}"}
                data = {"pay_way": "web", "price": amount, "name": name}
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{Config.API_BASE_URL}/pay/create",
                        headers=headers,
                        json=data,
                        timeout=10
                    )
                
                if response.status_code == 200:
                    result = response.json()
                    order_no = result.get('no', '未知')
                    pay_url = f"https://emos.best/pay/{order_no}"
                    logger.info(f"网页支付订单创建成功，订单号: {order_no}")
                    keyboard = [[InlineKeyboardButton("🌐 前往支付", url=pay_url)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await loading.edit_text(f"✅ 订单创建成功！\n订单号：`{order_no}`\n", reply_markup=reply_markup, parse_mode="Markdown")
                else:
                    logger.info(f"网页支付订单创建失败，状态码: {response.status_code}")
                    await loading.edit_text(f"❌ 创建失败，状态码：{response.status_code}")
            except Exception as e:
                logger.error(f"创建订单失败: {e}")
                await loading.edit_text("❌ 创建失败，请稍后重试")
            
            # 清理用户数据
            # 只清理红包和当前操作相关数据，保留用户登录信息
            if 'redpacket' in context.user_data:
                del context.user_data['redpacket']
            if 'current_operation' in context.user_data:
                del context.user_data['current_operation']
            logger.info(f"清理用户数据")
        else:
            logger.info(f"用户未登录，提示登录")
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 游戏选择回调
    if data.startswith("service_game_select_"):
        game_id = data.split("_")[-1]
        logger.info(f"处理游戏选择回调，游戏ID: {game_id}")
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        
        # 检查user_info是字典还是字符串
        if isinstance(user_info, dict):
            token = user_info.get('token')
        else:
            token = user_info
        
        if not token:
            logger.info(f"用户未登录，提示登录")
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
            return
        
        # 提示用户输入充值金额
        logger.info(f"提示用户输入充值金额")
        await update.callback_query.edit_message_text(f"🎮 选择游戏：{game_id}\n\n请输入充值金额（1-50000萝卜）：")
        
        # 存储当前状态，等待用户输入
        context.user_data['current_operation'] = 'service_game_recharge_amount'
        context.user_data['token'] = token
        context.user_data['game_id'] = game_id
        logger.info(f"存储游戏充值操作状态")
        return
    
    # 处理充值取消
    if data == "cancel_recharge":
        logger.info(f"处理充值取消按钮")
        await update.callback_query.edit_message_text("✅ 充值已取消")
        # 清理用户数据
        # 只清理红包和当前操作相关数据，保留用户登录信息
        if 'redpacket' in context.user_data:
            del context.user_data['redpacket']
        if 'current_operation' in context.user_data:
            del context.user_data['current_operation']
        logger.info(f"清理用户数据")
        return
    
    # 对于其他不认识的回调，不做处理，让其他处理器继续处理
    logger.info(f"未识别的按钮回调: {data}")
    # 返回None，让Telegram Bot API继续尝试其他处理器
    return None

async def show_redpacket_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """红包二级菜单"""
    keyboard = [
        [
            InlineKeyboardButton("🧧 创建红包", callback_data="menu_redpocket"),
            InlineKeyboardButton("📊 查询红包", callback_data="menu_check_redpacket")
        ],
        [
            InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🧧 红包功能\n\n请选择操作：",
        reply_markup=reply_markup
    )

async def show_lottery_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """抽奖二级菜单"""
    keyboard = [
        [
            InlineKeyboardButton("🎲 创建抽奖", callback_data="menu_lottery"),
            InlineKeyboardButton("❌ 取消抽奖", callback_data="menu_lottery_cancel")
        ],
        [
            InlineKeyboardButton("🏆 查询中奖列表", callback_data="menu_lottery_win")
        ],
        [
            InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🎲 抽奖功能\n\n请选择操作：",
        reply_markup=reply_markup
    )

async def show_rank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """排行榜二级菜单"""
    keyboard = [
        [
            InlineKeyboardButton("🥕 萝卜榜", callback_data="menu_rank_carrot"),
            InlineKeyboardButton("📤 上传榜", callback_data="menu_rank_upload")
        ],
        [
            InlineKeyboardButton("🎬 正在播放", callback_data="menu_playing"),
            InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🏆 排行榜\n\n请选择类型：",
        reply_markup=reply_markup
    )

async def show_transfer_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """转账二级菜单"""
    keyboard = [
        [
            InlineKeyboardButton("💸 普通转增", callback_data="menu_transfer"),
            InlineKeyboardButton("🏢 服务商转账", callback_data="menu_service_transfer")
        ],
        [
            InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "💸 转账\n\n请选择类型：",
        reply_markup=reply_markup
    )



async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    help_text = (
        "📖 **使用帮助**\n\n"
        "**红包功能**\n"
        "• /redpocket - 创建红包\n"
        "• /check_redpacket - 查询红包记录\n\n"
        "**抽奖功能**\n"
        "• /lottery - 创建抽奖\n"
        "• /lottery_cancel - 取消抽奖\n\n"
        "**排行榜**\n"
        "• /rank_carrot - 萝卜排行榜\n"
        "• /rank_upload - 上传排行榜\n"
        "• /playing - 正在播放\n\n"
        "**其他**\n"
        "• /menu - 打开菜单\n"
        "• /cancel - 取消当前操作"
    )
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消操作"""
    await update.message.reply_text("✅ 操作已取消")
    # 只清理红包相关的数据，保留登录信息和uploaded_files
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    # 清理当前操作状态
    if 'current_operation' in context.user_data:
        del context.user_data['current_operation']
    # 显示主菜单
    await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    # 保留uploaded_files，以便下次使用
    return ConversationHandler.END

async def handle_back_to_previous(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理返回上一步"""
    user_id = update.effective_user.id
    
    # 检查是否正在创建红包
    if 'redpacket' in context.user_data:
        redpacket_data = context.user_data['redpacket']
        current_step = redpacket_data.get('step', 'carrot')
        
        # 定义步骤顺序和上一步映射
        step_order = ['carrot', 'number', 'blessing', 'password']
        if current_step in step_order:
            current_index = step_order.index(current_step)
            if current_index > 0:
                # 返回到上一步
                previous_step = step_order[current_index - 1]
                redpacket_data['step'] = previous_step
                context.user_data['redpacket'] = redpacket_data
                
                # 显示上一步的提示信息
                step_messages = {
                    'carrot': "💰 请输入红包总金额（萝卜）：\n（1 - 50000 之间）",
                    'number': "👥 请输入可领人数：\n（1 - 1000 之间）",
                    'blessing': "💬 请输入祝福语（最多50字）：",
                    'password': "🔑 请输入红包口令\n（输入0则为手气红包，无需口令）："
                }
                
                keyboard = add_cancel_button([[]], show_back=True)
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.callback_query.edit_message_text(
                    f"🧧 创建红包\n\n{step_messages[previous_step]}",
                    reply_markup=reply_markup
                )
                
                # 返回对应的状态
                step_to_state = {
                    'carrot': 0,  # WAITING_CARROT
                    'number': 1,  # WAITING_NUMBER
                    'blessing': 2,  # WAITING_BLESSING
                    'password': 3   # WAITING_PASSWORD
                }
                return step_to_state[previous_step]
    
    # 检查是否正在创建抽奖
    if 'lottery' in context.user_data:
        lottery_data = context.user_data['lottery']
        current_step = lottery_data.get('step', 'name')
        
        # 定义步骤顺序和上一步映射
        step_order = ['name', 'end', 'amount', 'number', 'rule_carrot', 'rule_sign', 'prizes']
        if current_step in step_order:
            current_index = step_order.index(current_step)
            if current_index > 0:
                # 返回到上一步
                previous_step = step_order[current_index - 1]
                lottery_data['step'] = previous_step
                context.user_data['lottery'] = lottery_data
                
                # 显示上一步的提示信息
                if previous_step == 'end':
                    # 显示结束时间选择按钮
                    from datetime import datetime, timedelta, timezone
                    # 北京时间 UTC+8
                    beijing_tz = timezone(timedelta(hours=8))
                    now = datetime.now(beijing_tz)
                    end_1h = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
                    end_1d = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
                    end_7d = (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
                    
                    # 显示结束时间选择按钮
                    keyboard = [
                        [InlineKeyboardButton("⏱️ 1小时速抽", callback_data=f"end_time_1h_{end_1h}")],
                        [InlineKeyboardButton("📅 1天期限", callback_data=f"end_time_1d_{end_1d}")],
                        [InlineKeyboardButton("📆 1周开奖", callback_data=f"end_time_7d_{end_7d}")],
                        [InlineKeyboardButton("✏️ 自定义时间", callback_data="end_time_custom")]
                    ]
                    keyboard = add_cancel_button(keyboard, show_back=True)
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.callback_query.edit_message_text(
                        "⏰ 请选择开奖时间\n\n"  
                        f"开始时间：`{lottery_data.get('time_start', '')}`",
                        reply_markup=reply_markup,
                        parse_mode="Markdown"
                    )
                else:
                    step_messages = {
                        'name': "请输入抽奖名称（30字内）：",
                        'amount': "💰 请输入每人参与所需萝卜数量（1-50000）：",
                        'number': "👥 请输入开奖人数（0-5000）\n• 输入 **0**：时间开奖模式\n• 输入 **数字**：人数开奖模式",
                        'rule_carrot': "🥕 请输入参与条件（萝卜数量要求，没有则输0）：",
                        'rule_sign': "📅 请输入参与条件（签到天数要求，没有则输0）：",
                        'prizes': "🎁 请输入第1个奖品的名称（50字内）："
                    }
                    
                    keyboard = add_cancel_button([[]], show_back=True)
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    await update.callback_query.edit_message_text(
                        f"🎲 创建抽奖\n\n{step_messages[previous_step]}",
                        reply_markup=reply_markup, 
                        parse_mode="Markdown" if previous_step == 'number' else None
                    )
                
                # 返回对应的状态
                step_to_state = {
                    'name': 10,  # WAITING_LOTTERY_NAME
                    'end': 13,  # WAITING_LOTTERY_END
                    'amount': 14,  # WAITING_LOTTERY_AMOUNT
                    'number': 15,  # WAITING_LOTTERY_NUMBER
                    'rule_carrot': 16,  # WAITING_LOTTERY_RULE_CARROT
                    'rule_sign': 17,  # WAITING_LOTTERY_RULE_SIGN
                    'prizes': 18   # WAITING_LOTTERY_PRIZES
                }
                return step_to_state[previous_step]
    
    # 如果没有正在进行的任务，返回主菜单
    await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    return ConversationHandler.END

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """返回主菜单"""
    if update.callback_query:
        await update.callback_query.answer()
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    else:
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    return ConversationHandler.END

