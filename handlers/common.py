import logging
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
    commands = [BotCommand(cmd, desc) for cmd, desc in BOT_COMMANDS]
    await application.bot.set_my_commands(commands)
    logger.info("机器人命令菜单已设置")

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
    await query.edit_message_text("✅ 操作已取消")
    # 清理用户数据
    context.user_data.clear()
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
            user_tokens[user_id] = token
            logger.info(f"Token已存储到user_tokens: {user_tokens[user_id]}")
            
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
                    logger.info(f"用户数据: {user_data}")
                    username = user_data.get('username', '用户')
                    user_id_api = user_data.get('user_id', '未知')
                    
                    # 确保用户存在于数据库中
                    from utils.db_helper import ensure_user_exists
                    ensure_user_exists(
                        emos_user_id=user_id_api,
                        token=token,
                        username=username,
                        first_name=update.effective_user.first_name,
                        last_name=update.effective_user.last_name
                    )
                    
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
        user_tokens[user_id] = token
        logger.info(f"Token已存储到user_tokens: {user_tokens[user_id]}")
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
                logger.info(f"用户数据: {user_data}")
                username = user_data.get('username', '用户')
                user_id_api = user_data.get('user_id', '未知')
                
                # 确保用户存在于数据库中
                from utils.db_helper import ensure_user_exists
                ensure_user_exists(
                    emos_user_id=user_id_api,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                
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
                    
                    # 调用游戏充值API（使用订单归属用户的token）
                    user_headers = {"Authorization": f"Bearer {user_token}"}
                    game_recharge_data = {"game_id": "1", "carrot_amount": price}
                    async with httpx.AsyncClient() as client:
                        game_response = await client.post(
                            f"{Config.API_BASE_URL}/game/recharge",
                            headers=user_headers,
                            json=game_recharge_data,
                            timeout=10
                        )
                    
                    logger.info(f"游戏充值API响应状态码: {game_response.status_code}")
                    logger.info(f"游戏充值API响应内容: {game_response.text}")
                    
                    # 无论游戏充值API是否成功，只要支付成功就标记订单为成功
                    # 计算游戏币（1萝卜=10游戏币）
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
                    
                    if game_response.status_code == 200:
                        game_result = game_response.json()
                        actual_game_coin = game_result.get('game_coin', game_coin)
                        
                        message = f"✅ 充值成功！\n\n"
                        message += f"订单号：{order_no}\n"
                        message += f"支付萝卜：{price}\n"
                        message += f"兑换游戏币：{actual_game_coin}"
                        
                        logger.info(f"用户 {actual_user_id} 充值成功，订单号：{order_no}")
                    else:
                        message = f"✅ 充值成功！\n\n"
                        message += f"订单号：{order_no}\n"
                        message += f"支付萝卜：{price}\n"
                        message += f"兑换游戏币：{game_coin}\n"
                        message += f"（系统自动计算，实际到账以平台为准）"
                        
                        logger.warning(f"订单 {order_no} 支付成功，但游戏币兑换API调用失败，状态码：{game_response.status_code}")
                    
                    await loading.edit_text(message)
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
        
        await update.message.reply_text(f"❌ 支付已取消\n订单号：{order_no}")
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
        user_tokens[user_id] = token
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
                
                # 确保用户存在于数据库中
                from utils.db_helper import ensure_user_exists
                ensure_user_exists(
                    emos_user_id=user_id_api,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                
                await show_menu(update, f"✅ 授权成功！\n\n欢迎 {username} 使用综合机器人，你的ID是\n`{user_id_api}`\n\n请选择功能：")
            else:
                await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        return
    
    if user_id in user_tokens:
        # 获取用户信息
        token = user_tokens[user_id]
        import requests
        try:
            api_url = f"{Config.API_BASE_URL}/user"
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(api_url, headers=headers, timeout=10)
            if response.status_code == 200:
                user_data = response.json()
                username = user_data.get('username', '用户')
                user_id_api = user_data.get('user_id', '未知')
                await show_menu(update, f"👋 欢迎回来 {username}！\n\n你的ID是\n`{user_id_api}`\n\n请选择功能：")
            else:
                # token可能已过期，提示用户重新登录
                await update.message.reply_text("❌ 登录已过期，请重新登录！")
                # 移除过期的token
                del user_tokens[user_id]
                # 显示登录选项
                await show_login_options(update)
        except Exception as e:
            logger.error(f"获取用户信息失败: {e}")
            # 移除可能无效的token
            if user_id in user_tokens:
                del user_tokens[user_id]
            # 显示登录选项
            await show_login_options(update)
    else:
        # 显示登录选项，要求用户使用正式token登录
        await show_login_options(update)

async def show_login_options(update: Update):
    """显示登录选项"""
    # 使用开发者的emos user_id来生成登录链接
    developer_emos_id = "e0E446ZE6s"
    auth_link_bot = f"https://t.me/emospg_bot?start=link_{developer_emos_id}-{Config.BOT_USERNAME}"
    keyboard = [
        [InlineKeyboardButton("🤖 机器人授权登录", url=auth_link_bot)],
        [InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        "👋 欢迎使用综合机器人！\n\n使用前请先登录EMOS账号：",
        reply_markup=reply_markup
    )

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
            InlineKeyboardButton("📝 签到", callback_data="menu_user_sign")
        ],
        [
            InlineKeyboardButton("💸 普通转增", callback_data="menu_transfer"),
            InlineKeyboardButton("🏢 服务商转账", callback_data="menu_service_transfer")
        ],
        [
            InlineKeyboardButton("🧧 红包", callback_data="menu_redpacket_main"),
            InlineKeyboardButton("🎲 抽奖", callback_data="menu_lottery_main"),
            InlineKeyboardButton("🏆 排行榜", callback_data="menu_rank_main")
        ],
        [
            InlineKeyboardButton("🛠️ 服务商", callback_data="menu_service"),
            InlineKeyboardButton("🛒 商城", callback_data="menu_shop"),
            InlineKeyboardButton("📨 邀请", callback_data="menu_invite")
        ],
        [
            InlineKeyboardButton("❓ 帮助", callback_data="help")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查消息中是否包含Markdown格式
    has_markdown = '`' in message_text
    parse_mode = "Markdown" if has_markdown else None
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup, parse_mode=parse_mode)
    else:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup, parse_mode=parse_mode)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有按钮回调"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"按钮回调: {data}")
    
    if data == "cancel_operation":
        return await cancel_callback(update, context)
    
    # 处理返回上一步
    if data == "back_to_previous":
        return await handle_back_to_previous(update, context)
    
    # 处理返回主菜单
    if data == "back_to_main":
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
        return
    
    # 红包二级菜单
    if data == "menu_redpacket_main":
        await show_redpacket_menu(update, context)
        return
    
    # 抽奖二级菜单
    if data == "menu_lottery_main":
        await show_lottery_menu(update, context)
        return
    
    # 排行榜二级菜单
    if data == "menu_rank_main":
        await show_rank_menu(update, context)
        return
    
    # 个人信息功能
    if data == "menu_user_main":
        from user.user_info import get_user_info
        await get_user_info(update, context)
        return
    
    # 转赠功能
    if data == "menu_transfer":
        user_id = update.effective_user.id
        token = user_tokens.get(user_id)
        
        if not token:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
            return
        
        # 提示用户输入对方用户ID
        await update.callback_query.edit_message_text("💸 请输入对方用户ID（10位字符串，以e开头s结尾）：")
        
        # 存储当前状态，等待用户输入
        context.user_data['current_operation'] = 'transfer_user_id'
        context.user_data['token'] = token
        return 102  # 自定义状态码，用于处理转赠用户ID输入
    
    # 服务商转账功能
    if data == "menu_service_transfer":
        user_id = update.effective_user.id
        token = user_tokens.get(user_id)
        
        if not token:
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
        except Exception as e:
            logger.error(f"检查服务商状态失败: {e}")
        
        if is_service:
            # 提示用户输入对方用户ID
            await update.callback_query.edit_message_text("🏢 请输入对方用户ID（10位字符串，以e开头s结尾）：")
            
            # 存储当前状态，等待用户输入
            context.user_data['current_operation'] = 'service_fund_transfer_user_id'
            context.user_data['token'] = token
            return 107  # 自定义状态码，用于处理服务商转账用户ID输入
        else:
            await update.callback_query.edit_message_text("❌ 只有服务商才能使用此功能！")
    
    # 服务商功能
    if data == "menu_service":
        from services.service_main import show_service_menu
        await show_service_menu(update, context)
        return
    
    # 商城功能
    if data == "menu_shop":
        from shop.shop_main import show_shop_menu
        await show_shop_menu(update, context)
        return
    
    # 邀请功能
    if data == "menu_invite":
        # 跳转到个人信息的邀请功能
        from user.user_info import user_invite
        await user_invite(update, context)
        return
    
    # 猜拳功能
    if data == "menu_rock_paper_scissors":
        await update.callback_query.edit_message_text("✊ 猜拳功能开发中，敬请期待！")
        # 显示返回菜单
        keyboard = [
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("猜拳功能", reply_markup=reply_markup)
        return
    
    # 处理具体的功能按钮
    if data == "menu_redpocket":
        from handlers.redpacket import redpocket_command
        return await redpocket_command(update, context)
    
    elif data == "menu_check_redpacket":
        from handlers.redpacket_query import check_redpacket_command
        return await check_redpacket_command(update, context)
    
    elif data == "menu_lottery":
        from games.lottery import lottery_command
        return await lottery_command(update, context)
    
    elif data == "menu_lottery_cancel":
        from games.lottery_cancel import lottery_cancel_command
        return await lottery_cancel_command(update, context)
    
    elif data == "menu_rank_carrot":
        from ranks.carrot_rank import rank_carrot_command
        await rank_carrot_command(update, context)
    
    elif data == "menu_rank_upload":
        from ranks.upload_rank import rank_upload_command
        await rank_upload_command(update, context)
    
    elif data == "menu_playing":
        from ranks.playing_rank import playing_command
        await playing_command(update, context)
    
    elif data == "menu_user_info":
        from user.user_info import get_user_info
        await get_user_info(update, context)
    
    elif data == "menu_user_sign":
        from user.user_info import user_sign
        await user_sign(update, context)
    
    elif data == "menu_user_invite":
        from user.user_info import user_invite
        await user_invite(update, context)
    
    elif data == "menu_user_pseudonym":
        from user.user_info import user_pseudonym
        return await user_pseudonym(update, context)
    
    elif data == "help":
        await help_command(update, context)
    
    elif data in ["add_more_prizes", "finish_prizes"]:
        from games.lottery import handle_prize_choice
        return await handle_prize_choice(update, context)
    
    # 服务商新功能回调
    elif data == "service_user_manage":
        from services.service_main import service_user_manage
        await service_user_manage(update, context)
    
    elif data == "service_recharge":
        from services.service_main import service_recharge
        await service_recharge(update, context)
    
    elif data == "service_withdraw":
        from services.service_main import service_withdraw
        await service_withdraw(update, context)
    
    elif data == "service_game_center":
        from services.service_main import service_game_center
        await service_game_center(update, context)
    
    elif data == "service_manage":
        from services.service_main import service_manage
        await service_manage(update, context)
    
    elif data == "service_apply":
        from services.service_main import service_apply
        await service_apply(update, context)
    
    elif data == "service_update":
        from services.service_main import service_update
        await service_update(update, context)
    
    elif data == "service_pay_create":
        from services.service_main import service_pay_create
        await service_pay_create(update, context)
    
    elif data == "service_pay_query":
        from services.service_main import service_pay_query
        await service_pay_query(update, context)
    
    elif data == "service_pay_close":
        from services.service_main import service_pay_close
        await service_pay_close(update, context)
    
    elif data == "service_fund_transfer":
        from services.service_main import service_fund_transfer
        await service_fund_transfer(update, context)
    
    elif data == "service_pay_create_telegram_bot":
        # 处理Telegram机器人支付方式选择
        user_id = update.effective_user.id
        token = user_tokens.get(user_id)
        if token:
            # 获取存储的数据
            amount = context.user_data.get('amount')
            name = context.user_data.get('name')
            
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
                    await loading.edit_text(f"✅ 订单创建成功！\n订单号：{order_no}")
                else:
                    await loading.edit_text(f"❌ 创建失败，状态码：{response.status_code}")
            except Exception as e:
                logger.error(f"创建订单失败: {e}")
                await loading.edit_text("❌ 创建失败，请稍后重试")
            
            # 清理用户数据
            context.user_data.clear()
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
    
    elif data == "service_pay_create_web":
        # 处理网页支付方式选择
        user_id = update.effective_user.id
        token = user_tokens.get(user_id)
        if token:
            amount = context.user_data.get('amount')
            name = context.user_data.get('name')
            
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
                    keyboard = [[InlineKeyboardButton("🌐 前往支付", url=pay_url)]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await loading.edit_text(f"✅ 订单创建成功！\n订单号：{order_no}", reply_markup=reply_markup)
                else:
                    await loading.edit_text(f"❌ 创建失败，状态码：{response.status_code}")
            except Exception as e:
                logger.error(f"创建订单失败: {e}")
                await loading.edit_text("❌ 创建失败，请稍后重试")
            
            # 清理用户数据
            context.user_data.clear()
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
    
    # 游戏选择回调
    elif data.startswith("service_game_select_"):
        game_id = data.split("_")[-1]
        user_id = update.effective_user.id
        token = user_tokens.get(user_id)
        
        if not token:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
            return
        
        # 提示用户输入充值金额
        await update.callback_query.edit_message_text(f"🎮 选择游戏：{game_id}\n\n请输入充值金额（1-50000萝卜）：")
        
        # 存储当前状态，等待用户输入
        context.user_data['current_operation'] = 'service_game_recharge_amount'
        context.user_data['token'] = token
        context.user_data['game_id'] = game_id
    
    # 处理充值取消
    elif data == "cancel_recharge":
        await update.callback_query.edit_message_text("✅ 充值已取消")
        # 清理用户数据
        context.user_data.clear()

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
    context.user_data.clear()
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
                step_messages = {
                    'name': "请输入抽奖名称（30字内）：",
                    'end': f"⏰ 请输入结束时间\n格式：`YYYY-MM-DD HH:MM:SS`\n开始时间：`{lottery_data.get('time_start', '')}`",
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
                    parse_mode="Markdown" if previous_step == 'end' or previous_step == 'number' else None
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

