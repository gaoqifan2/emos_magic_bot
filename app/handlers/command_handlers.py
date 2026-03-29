from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.database import get_balance, update_balance, add_user, add_game_record, ensure_user_exists, get_last_checkin, update_checkin_time
from app.database.jackpot import get_jackpot_pool, add_to_jackpot_pool, reset_jackpot_pool, record_jackpot_win
from app.database.user_score import get_user_score, add_user_score, reset_user_score, get_user_level
from app.database.user_streaks import get_user_streak, update_user_streak, add_user_tag
from app.utils.helpers import check_balance, process_daily_checkin
from app.config import BOT_USERNAME, user_tokens, save_token_to_db, get_user_info, Config, API_BASE_URL, DEFAULT_GROUP_CHAT_ID
import logging
import httpx

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"用户 {user_id} 发送 /start 命令")
    
    # 检查是否是CallbackQuery类型的更新
    if update.callback_query:
        # 通过按钮回调调用，直接显示游戏菜单
        logger.info("通过按钮回调调用start_handler，显示游戏菜单")
        # 检查用户是否已登录（是否有token）
        is_logged_in = False
        # 首先检查telegram_id是否在user_tokens中
        if user_id in user_tokens:
            is_logged_in = True
        else:
            # 遍历user_tokens，查找可能的匹配
            for key, info in user_tokens.items():
                if isinstance(info, dict) and (info.get('username') == user.username or info.get('first_name') == user.first_name):
                    is_logged_in = True
                    break
        
        # 创建按钮菜单，根据登录状态决定是否显示授权登录按钮
        if is_logged_in:
            # 已登录，隐藏授权登录按钮
            keyboard = [
                [InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
                 InlineKeyboardButton("💰 余额", callback_data='balance'),
                 InlineKeyboardButton("📅 每日签到", callback_data='daily')],
                [InlineKeyboardButton("💸 充值", callback_data='recharge'),
                 InlineKeyboardButton("💎 提现", callback_data='withdraw'),
                 InlineKeyboardButton("📝 游戏规则", callback_data='help')],
                [InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
        else:
            # 未登录，显示授权登录按钮
            keyboard = [
                [InlineKeyboardButton("🔐 登录授权", callback_data='login'),
                 InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
                 InlineKeyboardButton("📝 游戏规则", callback_data='help')],
                [InlineKeyboardButton("💰 余额", callback_data='balance'),
                 InlineKeyboardButton("📅 每日签到", callback_data='daily'),
                 InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 编辑回调消息
        await update.callback_query.edit_message_text(
            "点击下方按钮选择游戏或功能：\n",
            reply_markup=reply_markup
        )
        return
    
    # 正常的Message类型更新
    text = update.message.text
    logger.info(f"完整的start命令文本: {text}")
    
    # 处理登录授权逻辑
    if context.args:
        start_param = context.args[0]
        
        # 处理链接登录请求
        if start_param.startswith('link_'):
            # 解析参数：link_[user_id]-[bot_name]-[operation]
            parts = start_param.split('-', 2)
            if len(parts) >= 2:
                unique_id = parts[0].split('_', 1)[1]  # 获取唯一标识符
                bot_name = parts[1]  # 获取机器人名称
                operation = parts[2] if len(parts) == 3 else None  # 获取操作状态
                
                # 生成授权链接
                # 格式：https://t.me/emospg_bot?start=link_[token]-[bot_username]-[operation]
                # 使用固定的token作为唯一标识符
                unique_id = "e0E446ZE6s"
                if operation:
                    auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_name}-{operation}"
                else:
                    auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_name}"
                
                # 创建授权按钮
                keyboard = [
                    [InlineKeyboardButton("🔐 授权登录", url=auth_link)],
                    [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    f"{user.first_name}，请点击下方按钮进行授权登录：\n",
                    reply_markup=reply_markup
                )
                return
        
        # 处理授权同意
        elif start_param.startswith('emosLinkAgree-'):
            # 提取完整的token，确保不会被截断
            token = start_param.split('-', 1)[1]
            logger.info(f"收到授权Token: {token}")
            logger.info(f"Token长度: {len(token)}")
            
            # Token完整性检查
            if len(token) < 10:
                logger.error(f"Token不完整，长度: {len(token)}")
                await update.message.reply_text(f"❌ Token不完整，请重新尝试登录。")
                return
            
            # 暂时存储token，后续会更新为使用telegram_user_id作为键
            user_tokens[user_id] = {'token': token, 'user_id': 'unknown', 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
            logger.info(f"Token已临时存储到user_tokens: {token}")
            
            # 获取用户信息
            import requests
            try:
                from app.config import API_USER_ENDPOINT
                api_url = API_USER_ENDPOINT
                headers = {"Authorization": f"Bearer {token}"}
                logger.info(f"API请求头: {headers}")
                logger.info(f"API请求URL: {api_url}")
                
                response = requests.get(api_url, headers=headers, timeout=10)
                logger.info(f"API响应状态码: {response.status_code}")
                
                if response.status_code == 200:
                    user_data = response.json()
                    logger.info(f"用户数据: {user_data}")
                    
                    # 打印详细的用户信息
                    print("\n=== API返回的用户信息 ===")
                    for key, value in user_data.items():
                        print(f"{key}: {value}")
                    print("======================\n")
                    
                    # 提取用户信息
                    username = user_data.get('username', '用户')
                    user_id_api = user_data.get('user_id', '未知')
                    
                    # 强制使用当前用户的telegram_id，而不是API返回的telegram_user_id
                    # 这样可以确保每个Telegram账号对应独立的用户
                    telegram_user_id = user_id
                    logger.info(f"使用当前用户的telegram_id: {telegram_user_id} (API返回的telegram_user_id: {user_data.get('telegram_user_id')})")
                    
                    # 确保user_tokens字典使用telegram_user_id作为键
                    if user_id in user_tokens:
                        del user_tokens[user_id]
                        logger.info(f"已从user_tokens中删除旧键: {user_id}")
                    
                    # 确保用户存在于数据库中并保存token
                    local_user_id = ensure_user_exists(
                        emos_user_id=user_id_api,
                        token=token,
                        telegram_id=telegram_user_id,
                        username=username,
                        first_name=user.first_name,
                        last_name=user.last_name
                    )
                    
                    # 更新内存中的token
                    user_tokens[telegram_user_id] = {'token': token, 'user_id': user_id_api, 'username': username, 'first_name': user.first_name, 'last_name': user.last_name}
                    logger.info(f"用户 {telegram_user_id} 数据库操作结果: local_user_id={local_user_id}")
                    
                    # 将API返回的carrot转换为游戏币并更新余额
                    carrot_amount = user_data.get('carrot', 0)
                    game_coin_amount = carrot_amount * 10  # 1萝卜=10游戏币
                    logger.info(f"将 {carrot_amount} 萝卜转换为 {game_coin_amount} 游戏币")
                    
                    # 更新用户余额
                    from app.database import update_balance
                    new_balance = update_balance(user_id_api, game_coin_amount)
                    logger.info(f"用户 {user_id_api} 余额已更新为: {new_balance}")
                    
                    # 处理授权成功逻辑
                    await update.message.reply_text(
                        f"{user.first_name}，授权成功！\n\n"
                        f"欢迎 {username} 使用机器人，您的用户ID是\n`{user_id_api}`\n\n"
                        f"🎉 您的初始游戏币余额：{new_balance} 🪙\n\n"
                        "您现在可以使用机器人的所有功能了！"
                    )
                else:
                    # 即使获取用户信息失败，也标记授权成功
                    # 保存token到user_tokens，使用telegram_id作为user_id
                    user_tokens[user_id] = {'token': token, 'user_id': str(user_id), 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
                    logger.info(f"API调用失败，token已保存: {token}")
                    await update.message.reply_text(
                        f"{user.first_name}，授权成功！\n\n"
                        "您现在可以使用机器人的所有功能了！"
                    )
            except Exception as e:
                logger.error(f"获取用户信息失败: {e}")
                # 即使异常，也保存token到user_tokens，使用telegram_id作为user_id
                user_tokens[user_id] = {'token': token, 'user_id': str(user_id), 'username': user.username, 'first_name': user.first_name, 'last_name': user.last_name}
                logger.info(f"异常情况下token已保存: {token}")
                await update.message.reply_text(
                    f"{user.first_name}，授权成功！\n\n"
                    "您现在可以使用机器人的所有功能了！"
                )
            
            # 检查是否有操作状态参数
            # 解析原始的start命令，查找是否有操作状态
            original_start_text = update.message.text
            operation = None
            if 'link_' in original_start_text:
                # 检查是否有操作状态参数
                parts = original_start_text.split('link_')[1].split('-')
                if len(parts) >= 3:
                    operation = parts[2]
                    logger.info(f"检测到操作状态: {operation}")
            
            # 跳转到主菜单或相应操作
            # 设置命令菜单
            from telegram import BotCommand
            commands = [
                BotCommand("start", "开始使用机器人"),
                BotCommand("balance", "查看当前余额"),
                BotCommand("guess", "猜大小游戏"),
                BotCommand("slot", "老虎机游戏"),
                BotCommand("blackjack", "21点游戏"),
                BotCommand("daily", "每日签到"),
                BotCommand("help", "查看帮助信息")
            ]
            await context.bot.set_my_commands(commands)
            
            # 根据操作状态跳转
            if operation == 'recharge':
                # 跳转到充值功能
                await recharge_handler(update, context)
            elif operation == 'withdraw':
                # 跳转到提现功能
                await withdraw_handler(update, context)
            else:
                # 创建按钮菜单（隐藏授权登录按钮）
                keyboard = [
                    [InlineKeyboardButton("� 游戏厅", callback_data='games'),
                     InlineKeyboardButton("💰 余额", callback_data='balance'),
                     InlineKeyboardButton("📅 每日签到", callback_data='daily')],
                    [InlineKeyboardButton("💸 充值", callback_data='recharge'),
                     InlineKeyboardButton("💎 提现", callback_data='withdraw'),
                     InlineKeyboardButton("� 游戏规则", callback_data='help')],
                    [InlineKeyboardButton("🔙 返回", callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "点击下方按钮选择游戏或功能：\n",
                    reply_markup=reply_markup
                )
            return
        
        # 处理授权拒绝
        elif start_param.startswith('emosLinkRefuse-'):
            # 解析参数：emosLinkRefuse-[TelegramID]
            refused_id = start_param.split('-', 1)[1]
            
            # 处理授权拒绝逻辑
            await update.message.reply_text(
                f"{user.first_name}，授权已拒绝。\n"
                f"拒绝的用户 ID：{refused_id}\n\n"
                "您仍然可以使用机器人的基本功能，但某些需要授权的功能将不可用。"
            )
        
        # 处理支付成功回调
        elif start_param.startswith('emosPayAgree-'):
            # 解析参数：emosPayAgree-[订单号]-[其他参数]-[TgId]
            parts = start_param.split('-', 3)
            if len(parts) >= 2:
                order_no = parts[1]
                param = parts[2] if len(parts) >= 3 else None
                tg_id = parts[3] if len(parts) >= 4 else None
                
                logger.info(f"收到支付成功回调 - 订单号: {order_no}, 参数: {param}, TgId: {tg_id}")
                
                # 查询本地数据库中的订单
                from app.database import get_recharge_order_by_platform_no
                order = get_recharge_order_by_platform_no(order_no)
                
                if order:
                    logger.info(f"订单找到: {order}")
                    local_user_id = order.get('user_id')
                    carrot_amount = order.get('carrot_amount')
                    game_coin_amount = order.get('game_coin_amount')
                    
                    # 获取API用户ID
                    from app.database import get_db_connection
                    connection = get_db_connection()
                    api_user_id = None
                    if connection:
                        try:
                            with connection.cursor() as cursor:
                                cursor.execute('SELECT user_id FROM users WHERE id = %s', (local_user_id,))
                                user_result = cursor.fetchone()
                                if user_result:
                                    api_user_id = user_result['user_id']
                        finally:
                            connection.close()
                    
                    if not api_user_id:
                        logger.error(f"无法获取用户的API ID，本地用户ID: {local_user_id}")
                        await update.message.reply_text(
                            f"{user.first_name}，获取用户信息失败，请联系客服。\n\n"
                            f"订单号：{order_no}"
                        )
                        return
                    
                    # 调用查询订单接口确认支付状态
                    import httpx
                    headers = {
                        "Authorization": "Bearer 1047_ow2NHeo3HyzDSxvl",
                        "Content-Type": "application/json"
                    }
                    
                    try:
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                f"https://emos.best/api/pay/query?no={order_no}",
                                headers=headers,
                                timeout=10
                            )
                        
                        logger.info(f"订单查询响应状态码: {response.status_code}")
                        logger.info(f"订单查询响应内容: {response.text}")
                        
                        if response.status_code == 200:
                            order_info = response.json()
                            pay_status = order_info.get('pay_status')
                            
                            if pay_status == 'success':
                                # 支付成功，更新订单状态并兑换游戏币
                                from app.database import update_recharge_order_status
                                update_recharge_order_status(order_no, 'success')
                                
                                # 增加用户游戏币
                                update_balance(api_user_id, game_coin_amount)
                                
                                # 更新用户累计充值金额
                                from app.database import update_user_total_recharge
                                update_user_total_recharge(api_user_id, carrot_amount)
                                
                                logger.info(f"用户 {api_user_id} 充值成功，订单号：{order_no}")
                                
                                # 将用户信息添加到user_tokens，标记为已登录
                                from app.database import get_db_connection
                                connection = get_db_connection()
                                if connection:
                                    try:
                                        with connection.cursor() as cursor:
                                            cursor.execute('SELECT * FROM users WHERE user_id = %s', (api_user_id,))
                                            user_result = cursor.fetchone()
                                            if user_result:
                                                # 提取用户信息
                                                username = user_result.get('username')
                                                first_name = user_result.get('first_name')
                                                last_name = user_result.get('last_name')
                                                # 将用户信息添加到user_tokens
                                                user_tokens[user_id] = {
                                                    'token': '1047_ow2NHeo3HyzDSxvl',  # 使用固定token
                                                    'user_id': api_user_id,
                                                    'username': username,
                                                    'first_name': first_name,
                                                    'last_name': last_name
                                                }
                                                logger.info(f"用户 {api_user_id} 已标记为已登录")
                                    finally:
                                        connection.close()
                                
                                await update.message.reply_text(
                                    f"{user.first_name}，充值成功！\n\n"
                                    f"订单号：{order_no}\n"
                                    f"充值萝卜：{carrot_amount} 萝卜\n"
                                    f"获得游戏币：{game_coin_amount} 游戏币\n\n"
                                    "您的游戏币已到账，可以开始游戏了！"
                                )
                            else:
                                await update.message.reply_text(
                                    f"{user.first_name}，支付状态异常，请联系客服。\n\n"
                                    f"订单号：{order_no}\n"
                                    f"支付状态：{pay_status}"
                                )
                        else:
                            await update.message.reply_text(
                                f"{user.first_name}，查询订单状态失败，请联系客服。\n\n"
                                f"订单号：{order_no}"
                            )
                    except Exception as e:
                        logger.error(f"查询订单状态失败: {e}")
                        await update.message.reply_text(
                            f"{user.first_name}，查询订单状态失败，请联系客服。\n\n"
                            f"订单号：{order_no}"
                        )
                else:
                    await update.message.reply_text(
                        f"{user.first_name}，未找到订单信息。\n\n"
                        f"订单号：{order_no}"
                    )
        
        # 处理支付失败回调
        elif start_param.startswith('emosPayRefuse-'):
            # 解析参数：emosPayRefuse-[订单号]-[其他参数]-[TgId]
            parts = start_param.split('-', 3)
            if len(parts) >= 2:
                order_no = parts[1]
                
                logger.info(f"收到支付失败回调 - 订单号: {order_no}")
                
                # 更新订单状态为失败
                from app.database import update_recharge_order_status
                update_recharge_order_status(order_no, 'failed')
                
                await update.message.reply_text(
                    f"{user.first_name}，支付失败。\n\n"
                    f"订单号：{order_no}\n\n"
                    "请重新尝试支付或联系客服。"
                )
            
            # 跳转到主菜单
            # 设置命令菜单
            from telegram import BotCommand
            commands = [
                BotCommand("start", "开始使用机器人"),
                BotCommand("balance", "查看当前余额"),
                BotCommand("guess", "猜大小游戏"),
                BotCommand("slot", "老虎机游戏"),
                BotCommand("blackjack", "21点游戏"),
                BotCommand("daily", "每日签到"),
                BotCommand("help", "查看帮助信息")
            ]
            await context.bot.set_my_commands(commands)
            
            # 创建按钮菜单
            keyboard = [
                [InlineKeyboardButton("🔐 登录授权", callback_data='login'),
                 InlineKeyboardButton("🎮 游戏厅", callback_data='games')],
                [InlineKeyboardButton("🎰 老虎机", callback_data='slot'),
                 InlineKeyboardButton("🎲 猜大小", callback_data='guess'),
                 InlineKeyboardButton("🃏 21点", callback_data='blackjack')],
                [InlineKeyboardButton("💰 余额", callback_data='balance'),
                 InlineKeyboardButton("📅 每日签到", callback_data='daily'),
                 InlineKeyboardButton("❓ 帮助", callback_data='help')],
                [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                "点击下方按钮选择游戏或功能：\n",
                reply_markup=reply_markup
            )
            return
    
    # 设置命令菜单
    from telegram import BotCommand
    commands = [
        BotCommand("start", "开始使用机器人"),
        BotCommand("balance", "查看当前余额"),
        BotCommand("guess", "猜大小游戏"),
        BotCommand("slot", "老虎机游戏"),
        BotCommand("blackjack", "21点游戏"),
        BotCommand("daily", "每日签到"),
        BotCommand("help", "查看帮助信息")
    ]
    await context.bot.set_my_commands(commands)
    
    # 检查用户是否已登录（是否有token）
    is_logged_in = False
    # 首先检查telegram_id是否在user_tokens中
    if user_id in user_tokens:
        is_logged_in = True
    else:
        # 遍历user_tokens，查找可能的匹配
        for key, info in user_tokens.items():
            if isinstance(info, dict) and (info.get('username') == user.username or info.get('first_name') == user.first_name):
                is_logged_in = True
                break
    
    # 创建按钮菜单，根据登录状态决定是否显示授权登录按钮
    if is_logged_in:
        # 已登录，隐藏授权登录按钮
        keyboard = [
            [InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
             InlineKeyboardButton("💰 余额", callback_data='balance'),
             InlineKeyboardButton("📅 每日签到", callback_data='daily')],
            [InlineKeyboardButton("💸 充值", callback_data='recharge'),
             InlineKeyboardButton("💎 提现", callback_data='withdraw'),
             InlineKeyboardButton("📝 游戏规则", callback_data='help')],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
    else:
        # 未登录，显示授权登录按钮
        keyboard = [
            [InlineKeyboardButton("🔐 登录授权", callback_data='login'),
             InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
             InlineKeyboardButton("📝 游戏规则", callback_data='help')],
            [InlineKeyboardButton("💰 余额", callback_data='balance'),
             InlineKeyboardButton("📅 每日签到", callback_data='daily'),
             InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 欢迎消息
    welcome_message = (
        f"欢迎来到 TG游戏机器人，{user.first_name}！\n\n"
        f"点击下方按钮选择游戏或功能：\n"
    )
    
    # 在群聊中使用 reply_text 会@用户，在私聊中则直接回复
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /balance 命令"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再查询余额：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再查询余额：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    user_id_str = user_info.get('user_id', telegram_id)
    # 优先从user_info中获取username，而不是从user.username中获取
    user_info_username = user_info.get('username', '用户') if isinstance(user_info, dict) else '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    from app.database import get_user_by_telegram_id, get_user_by_user_id
    user_from_db = get_user_by_telegram_id(telegram_id)
    if not user_from_db:
        # 如果通过 telegram_id 找不到，尝试通过 user_id_str 查找
        user_from_db = get_user_by_user_id(user_id_str)
    
    if user_from_db:
        user_id = user_from_db['id']  # 使用数据库自增ID
        user_id_db = user_from_db.get('user_id', user_id_str)  # 用于add_user的字符串ID
        logger.info(f"[余额查询] 找到用户: id={user_id}, user_id={user_id_db}, telegram_id={user_from_db.get('telegram_id')}")
    else:
        user_id = user_id_str  # 回退到字符串ID
        user_id_db = user_id_str
        logger.warning(f"[余额查询] 未找到用户，回退到字符串ID: {user_id}")
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id_db,
        'username': user_info_username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    add_user(user_id_db, user_data)
    
    # 从user表获取用户信息（用于显示用户名）
    if not user_from_db:
        user_from_db = get_user_by_user_id(user_id_db)
    user_name = user_from_db.get('username', '用户') if user_from_db else '用户'
    # 确保用户名不为空
    user_name = user_name if user_name else "用户"
    
    # 新用户初始余额为0，无需额外添加
    
    balance = get_balance(user_id_db)
    
    # 创建返回按钮
    keyboard = [
        [InlineKeyboardButton("🔙 返回", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查是否是CallbackQuery类型的更新
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"{user_name} 当前的游戏币余额：{balance}",
            reply_markup=reply_markup
        )
    else:
        # 在群聊中显示用户信息，让其他群友知道是谁在查询余额
        await update.message.reply_text(f"{user_name} 当前的游戏币余额：{balance}")


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理回调查询（按钮点击）"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    # 标记是否处理了回调
    handled = False
    
    # 处理登录授权
    if query.data == 'login':
        # 登录授权
        user_id = user.id
        # 使用固定的标识符 link_e0E446ZE6s
        # 这样 emospg_bot 就能正确识别用户
        unique_id = "e0E446ZE6s"
        
        # 使用机器人的实际用户名
        bot_username = BOT_USERNAME
        
        # 生成授权链接
        # 格式：https://t.me/emospg_bot?start=link_e0E446ZE6s-[bot_username]
        # 注意：这里使用 emospg_bot 作为授权机器人
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建授权按钮
        keyboard = [
            [InlineKeyboardButton("🔐 授权登录", url=auth_link)],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "请点击下方按钮进行授权登录：\n",
            reply_markup=reply_markup
        )
        handled = True
    
    elif query.data == 'back':
        # 返回主菜单
        # 检查用户是否已登录（是否有token）
        is_logged_in = user_id in user_tokens
        
        # 创建按钮菜单，根据登录状态决定是否显示授权登录按钮
        if is_logged_in:
            # 已登录，隐藏授权登录按钮
            keyboard = [
                [InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
                 InlineKeyboardButton("💰 余额", callback_data='balance'),
                 InlineKeyboardButton("📅 每日签到", callback_data='daily')],
                [InlineKeyboardButton("💸 充值", callback_data='recharge'),
                 InlineKeyboardButton("💎 提现", callback_data='withdraw'),
                 InlineKeyboardButton("📝 游戏规则", callback_data='help')],
                [InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
        else:
            # 未登录，显示授权登录按钮
            keyboard = [
                [InlineKeyboardButton("🔐 登录授权", callback_data='login'),
                 InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
                 InlineKeyboardButton("📝 游戏规则", callback_data='help')],
                [InlineKeyboardButton("💰 余额", callback_data='balance'),
                 InlineKeyboardButton("📅 每日签到", callback_data='daily'),
                 InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "点击下方按钮选择游戏或功能：\n",
            reply_markup=reply_markup
        )
        handled = True
    
    elif query.data == 'balance':
        # 处理余额查询
        # 检查用户是否已绑定 token
        user_info = None
        # 只基于 telegram_id 进行用户识别
        if user_id in user_tokens:
            user_info = user_tokens[user_id]
        
        if not user_info:
            # 生成授权链接
            unique_id = "e0E446ZE6s"
            bot_username = BOT_USERNAME
            auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
            
            # 创建绑定提示按钮
            keyboard = [
                [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
                [InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "您还未绑定账号，请先绑定后再查询余额：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
            handled = True
            return handled
        
        # 从 user_info 中获取用户信息
        user_id_api = user_info.get('user_id', user_id)
        
        # 检查用户是否存在，不存在则添加
        user_data = {
            'id': user_id_api,
            'username': user_info.get('username', '用户') if isinstance(user_info, dict) else '用户',
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        add_user(user_id_api, user_data)
        
        # 从user表获取用户信息
        from app.database import get_user_by_user_id
        user_from_db = get_user_by_user_id(user_id_api)
        user_name = user_from_db.get('username', '用户') if user_from_db else '用户'
        # 确保用户名不为空
        user_name = user_name if user_name else "用户"
        
        # 新用户初始余额为0，无需额外添加
        
        balance = get_balance(user_id_api)
        # 显示余额信息
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"💰 {user_name} 的游戏余额\n🪙 当前余额：{balance} 🪙",
            reply_markup=reply_markup
        )
        handled = True
    
    elif query.data == 'daily':
        # 处理每日签到
        # 检查用户是否已绑定 token
        user_info = None
        # 只基于 telegram_id 进行用户识别
        if user_id in user_tokens:
            user_info = user_tokens[user_id]
        
        if not user_info:
            # 生成授权链接
            unique_id = "e0E446ZE6s"
            bot_username = BOT_USERNAME
            auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
            
            # 创建绑定提示按钮
            keyboard = [
                [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
                [InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "您还未绑定账号，请先绑定后再签到：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
            handled = True
            return handled
        
        # 从 user_info 中获取用户信息
        user_id_api = user_info.get('user_id', user_id)
        
        # 检查用户是否存在，不存在则添加
        user_data = {
            'id': user_id_api,
            'username': user_info.get('username', '用户') if isinstance(user_info, dict) else '用户',
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        add_user(user_id_api, user_data)
        
        # 处理签到逻辑
        import datetime
        today = datetime.date.today()
        last_checkin = get_last_checkin(user_id_api)
        
        if last_checkin and last_checkin.date() == today:
            # 今天已经签到过了
            keyboard = [
                [InlineKeyboardButton("🔙 返回", callback_data='games')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                "✨ 您今天已经签到过了～\n🌈 明天再来吧！",
                reply_markup=reply_markup
            )
        else:
            # 签到成功，随机获得1-5游戏币
            import random
            reward = random.randint(1, 5)
            
            # 更新余额
            new_balance = update_balance(user_id_api, reward)
            
            # 更新签到时间
            update_checkin_time(user_id_api, datetime.datetime.now())
            
            keyboard = [
                [InlineKeyboardButton("🔙 返回", callback_data='games')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"🎉 签到成功！获得 {reward} 🪙\n💰 当前余额：{new_balance} 🪙",
                reply_markup=reply_markup
            )
        handled = True
    
    elif query.data == 'withdraw':
        # 处理提现回调
        await withdraw_handler(update, context)
        handled = True
        handled = True
    
    elif query.data == 'help':
        # 显示帮助信息
        help_text = (
            "📋 命令列表：\n\n"
            "💰 /balance - 查看当前余额\n"
            "🎲 /guess [金额] [大/小] - 猜大小游戏\n"
            "🎰 /slot [金额] - 老虎机游戏\n"
            "🃏 /blackjack [金额] - 21点游戏\n"
            "📅 /daily - 每日签到（获得1-5游戏币）\n"
            "💸 /withdraw [金额] - 提现\n"
            "❓ /help - 查看帮助信息\n\n"
            "🎮 游戏规则：\n\n"
            "🎲 猜大小：\n" 
            "  - 掷骰子（1-6点）\n" 
            "  - 4-6点为'大'，1-3点为'小'\n" 
            "  - 赢：得2倍下注，输：扣掉下注\n\n"
            "🎰 老虎机：\n"
            "  - 两个相同：赢0.5倍（不抽水）\n"
            "  - 三个相同：赢10倍（抽水10%）\n"
            "  - 7️⃣-BAR-7️⃣：触发Jackpot大奖！\n"
            "  - 全不同：输\n\n"
            "🎁 Jackpot等级梯度：\n"
            "  - 青铜（1-10）：固定50倍 + 10%奖池\n"
            "  - 白银（11-50）：固定50倍 + 30%奖池\n"
            "  - 黄金（51-200）：固定50倍 + 60%奖池\n"
            "  - 钻石（200+）：固定50倍 + 100%奖池\n"
            "  - 奖池保护期：奖池不满500时，钻石等级暂不触发100%获取\n\n"
            "💰 抽水规则：\n"
            "  - 三个相同或Jackpot中奖时，扣除10%\n"
            "  - 5%给服务器利润，5%注入Jackpot奖池\n\n"
            "🃏 21点：\n" 
            "  - 不超过21点的前提下，让手牌点数比庄家大\n" 
            "  - 2-10：按牌面数值\n" 
            "  - J/Q/K：10点\n" 
            "  - A：1点或11点\n" 
            "  - 黑杰克：初始A+10点牌，立即获胜，赔率1.5倍\n" 
            "  - 五龙：5张牌未爆牌，直接获胜，赔率1.5倍\n" 
            "  - 庄家：固定17点停牌\n\n" 
            "💰 下注档位：\n" 
            "  - 10 / 50 / 100 / 500 / 自定义\n\n" 
            "🏆 连胜奖励：\n" 
            "  - 3连胜：+50 🪙\n" 
            "  - 5连胜：+100 🪙\n" 
            "  - 7连胜：+200 🪙 + 获得头衔\n" 
            "  - 7胜后每+1胜：+50 🪙（上限到15胜）\n\n" 
            "🏷️ 头衔系统：\n" 
            "  - 7连胜：点王\n" 
            "  - 8连胜：不爆狂人\n" 
            "  - 9连胜：牌桌幽灵\n" 
            "  - 10连胜：天命之子\n" 
            "  - 11连胜：庄家克星\n" 
            "  - 12连胜：21点魔\n" 
            "  - 13连胜：不灭赌徒\n" 
            "  - 14连胜：神之一手\n" 
            "  - 15连胜及以上：不败神话\n\n" 
            "💸 抽成规则：\n" 
            "  - 获胜时扣除10%抽成\n"
        )
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            help_text,
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        handled = True
    
    elif query.data == 'games':
        # 显示游戏厅，直接包含游戏列表
        keyboard = [
            [InlineKeyboardButton("🎰 老虎机", callback_data='slot'),
             InlineKeyboardButton("🎲 猜大小", callback_data='guess'),
             InlineKeyboardButton("🃏 21点", callback_data='blackjack')],
            [InlineKeyboardButton("💰 余额", callback_data='balance'),
             InlineKeyboardButton("📅 签到", callback_data='daily'),
             InlineKeyboardButton("💸 充值", callback_data='recharge')],
            [InlineKeyboardButton("💎 提现", callback_data='withdraw'),
             InlineKeyboardButton("📝 游戏规则", callback_data='help')],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🎮 游戏厅\n\n选择游戏或功能：\n",
            reply_markup=reply_markup
        )
        handled = True
    
    elif query.data == 'slot':
        # 处理老虎机游戏
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "请输入下注金额，例如：`/slot 10`\n\n直接复制：`/slot 10`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        handled = True
    
    elif query.data == 'guess':
        # 处理猜大小游戏
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "请输入下注金额和猜测的大小，例如：`/guess 10 大`\n\n直接复制：`/guess 10 大`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        handled = True
    
    elif query.data == 'blackjack':
        # 处理21点游戏
        # 显示下注档位选择
        keyboard = [
            [InlineKeyboardButton("10 🪙", callback_data='blackjack_bet_10'),
             InlineKeyboardButton("50 🪙", callback_data='blackjack_bet_50')],
            [InlineKeyboardButton("100 🪙", callback_data='blackjack_bet_100'),
             InlineKeyboardButton("500 🪙", callback_data='blackjack_bet_500')],
            [InlineKeyboardButton("自定义金额", callback_data='blackjack_bet_custom'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🃏 21点游戏\n\n请选择下注金额：",
            reply_markup=reply_markup
        )
        handled = True
    
    elif query.data.startswith('blackjack_bet_'):
        # 处理21点下注
        bet_amount = query.data.split('_')[-1]
        if bet_amount == 'custom':
            # 进入自定义金额输入
            context.user_data['awaiting_blackjack'] = True
            await query.edit_message_text("请输入自定义下注金额，例如：`100`\n\n直接复制：`100`", parse_mode='Markdown')
        else:
            # 直接处理固定金额
            await process_blackjack(update, context, bet_amount)
        handled = True
    
    elif query.data == 'slot_again':
        # 处理老虎机再来一局
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "请输入下注金额，例如：`/slot 10`\n\n直接复制：`/slot 10`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        handled = True
    
    elif query.data == 'blackjack_again':
        # 处理21点再来一局
        # 显示下注档位选择
        keyboard = [
            [InlineKeyboardButton("10 🪙", callback_data='blackjack_bet_10'),
             InlineKeyboardButton("50 🪙", callback_data='blackjack_bet_50')],
            [InlineKeyboardButton("100 🪙", callback_data='blackjack_bet_100'),
             InlineKeyboardButton("500 🪙", callback_data='blackjack_bet_500')],
            [InlineKeyboardButton("自定义金额", callback_data='blackjack_bet_custom'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "🃏 21点游戏\n\n请选择下注金额：",
            reply_markup=reply_markup
        )
        handled = True
    
    elif query.data == 'guess_again':
        # 处理猜大小再来一局
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "请输入下注金额和猜测的大小，例如：`/guess 10 大`\n\n直接复制：`/guess 10 大`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
        handled = True
    
    elif query.data == 'cancel':
        # 取消操作
        await query.edit_message_text("操作已取消")
        handled = True
    
    elif query.data == 'hit':
        # 处理要牌回调
        await hit_handler(update, context)
        handled = True
    
    elif query.data == 'stand':
        # 处理停牌回调
        await stand_handler(update, context)
        handled = True
    
    elif query.data == 'recharge':
        # 处理充值回调
        await recharge_handler(update, context)
        handled = True
    
    elif query.data == 'withdraw':
        # 处理提现回调
        await withdraw_handler(update, context)
        handled = True
    
    return handled


async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /guess 命令"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    # 注意：user_info可能是字符串（token）或字典
    if isinstance(user_info, dict):
        user_id = user_info.get('user_id', telegram_id)
        token = user_info.get('token', '')
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id = telegram_id
        token = user_info
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'token': token,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': telegram_id
    }
    add_user(user_id, user_data)
    
    # 新用户初始余额为0，无需额外添加
    
    # 检查是否有参数
    if len(context.args) == 2:
        # 直接处理参数
        await process_guess(update, context, context.args[0], context.args[1])
    else:
        # 进入二级会话，等待用户输入
        context.user_data['awaiting_guess'] = True
        await update.message.reply_text("请输入下注金额和猜测的大小，例如：`10 大`\n\n直接复制：`10 大`", parse_mode='Markdown')


async def process_guess(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str, guess: str):
    """处理猜大小游戏的逻辑"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再玩游戏：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    user_id_str = user_info.get('user_id', telegram_id)
    username = user_info.get('username', '用户') if isinstance(user_info, dict) else '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    from app.database import get_user_by_telegram_id, get_user_by_user_id
    user_from_db = get_user_by_telegram_id(telegram_id)
    if not user_from_db:
        # 如果通过 telegram_id 找不到，尝试通过 user_id_str 查找
        user_from_db = get_user_by_user_id(user_id_str)
    
    if user_from_db:
        user_id = user_from_db['id']  # 数据库自增ID（用于 add_game_record）
        user_id_api = user_from_db.get('user_id', user_id_str)  # 字符串格式的 user_id（用于余额操作）
        logger.info(f"找到用户: id={user_id}, user_id={user_id_api}, telegram_id={user_from_db.get('telegram_id')}")
    else:
        user_id = user_id_str  # 回退到字符串ID
        user_id_api = user_id_str
        logger.warning(f"未找到用户，回退到字符串ID: {user_id}")
    
    try:
        bet_amount = int(amount)
        if bet_amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字作为下注金额")
        return
    
    # 检查猜测的大小
    guess = guess.lower()
    if guess not in ['大', '小']:
        await update.message.reply_text("请输入正确的猜测，只能是 '大' 或 '小'")
        return
    
    # 检查余额
    is_sufficient, current_balance = check_balance(user_id_api, bet_amount)
    if not is_sufficient:
        await update.message.reply_text(f"余额不足！当前余额：{current_balance}")
        return
    
    # 发送 TG 内置骰子
    dice_message = await update.message.reply_dice(emoji="🎲")
    
    # 等待骰子结果
    import asyncio
    await asyncio.sleep(1)  # 等待 1 秒确保骰子结果已生成
    
    # 获取骰子点数
    dice_value = dice_message.dice.value
    
    # 判断大小
    if dice_value in [4, 5, 6]:
        actual_result = "大"
    else:
        actual_result = "小"
    
    # 判断用户是否猜对
    if guess == actual_result:
        is_win = True
        win_amount = bet_amount  # 赢了获得下注金额的1倍
    else:
        is_win = False
        win_amount = -bet_amount  # 输了失去下注金额
    
    # 构建结果消息
    result = f"🎲 骰子点数: {dice_value} ({actual_result})\n你猜的是: {guess}"
    
    # 更新余额
    if win_amount > 0:
        # 计算1%的服务器费用，最少1游戏币
        service_fee = max(1, int(win_amount * 0.01))
        # 扣除服务器费用
        actual_win = win_amount - service_fee
        new_balance = update_balance(user_id_api, actual_win)
        # 保存游戏记录
        game_result = "win" if is_win else "lose"
        add_game_record(user_id, "guess", bet_amount, game_result, actual_win if is_win else 0, username)
        # 更新结果消息，添加服务器费用信息
        result += f"\n💸 服务器费用：{service_fee} 🪙"
    else:
        new_balance = update_balance(user_id_api, win_amount)  # 输了不需要扣除费用
        # 保存游戏记录
        game_result = "win" if is_win else "lose"
        add_game_record(user_id, "guess", bet_amount, game_result, win_amount if is_win else 0, username)
    if is_win:
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🎲 再来一局", callback_data='guess_again'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🎉 {user.first_name} 🎲\n{result}\n\n✨ 恭喜你赢了！获得 {win_amount} 🪙\n💰 当前余额：{new_balance} 🪙", reply_markup=reply_markup)
    else:
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🎲 再来一局", callback_data='guess_again'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🎲 {user.first_name} 🎲\n{result}\n\n😢 很遗憾，你输了 {bet_amount} 🪙\n💰 当前余额：{new_balance} 🪙", reply_markup=reply_markup)


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户消息，用于二级会话"""
    user = update.effective_user
    user_id = user.id
    message_text = update.message.text
    
    # 检查是否在等待猜大小游戏的输入
    if 'awaiting_guess' in context.user_data and context.user_data['awaiting_guess']:
        # 解析输入
        parts = message_text.split()
        if len(parts) == 2:
            amount, guess = parts
            await process_guess(update, context, amount, guess)
        else:
            await update.message.reply_text("请输入正确的格式，例如：10 大")
        # 清除等待状态
        context.user_data['awaiting_guess'] = False
    
    # 检查是否在等待老虎机游戏的输入
    elif 'awaiting_slot' in context.user_data and context.user_data['awaiting_slot']:
        # 处理老虎机游戏输入
        await process_slot(update, context, message_text)
        # 清除等待状态
        context.user_data['awaiting_slot'] = False
    
    # 检查是否在等待21点游戏的输入
    elif 'awaiting_blackjack' in context.user_data and context.user_data['awaiting_blackjack']:
        # 处理21点游戏输入
        await process_blackjack(update, context, message_text)
        # 清除等待状态
        context.user_data['awaiting_blackjack'] = False
    
    # 检查是否在等待提现金额的输入
    elif 'awaiting_withdraw' in context.user_data and context.user_data['awaiting_withdraw']:
        # 处理提现金额输入
        await process_withdraw(update, context, message_text)
        # 清除等待状态
        context.user_data['awaiting_withdraw'] = False
    
    # 检查是否在等待充值金额的输入
    elif 'current_operation' in context.user_data and context.user_data['current_operation'] == 'recharge_amount':
        # 处理充值金额输入
        try:
            carrot_amount = int(message_text)
            if carrot_amount < 1 or carrot_amount > 50000:
                await update.message.reply_text("充值萝卜数量必须在1-50000之间")
                return
            
            # 检查累计充值限额
            total_recharge = context.user_data.get('total_recharge', 0)
            remaining_recharge = context.user_data.get('remaining_recharge', 100)
            
            if total_recharge + carrot_amount > 100:
                remaining = 100 - total_recharge
                await update.message.reply_text(f"充值限额为100萝卜，您已累计充值{total_recharge}萝卜，还可充值{remaining}萝卜")
                return
            
            # 从context中获取用户信息
            token = context.user_data.get('token')
            local_user_id = context.user_data.get('local_user_id')
            telegram_id = user.id
            
            if not token:
                # 生成授权链接，添加操作状态参数
                unique_id = "e0E446ZE6s"
                bot_username = BOT_USERNAME
                # 添加操作状态参数，以便绑定后恢复
                auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}-recharge"
                
                # 创建绑定提示按钮
                keyboard = [
                    [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
                    [InlineKeyboardButton("🔙 返回", callback_data='back')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "您还未绑定账号，请先绑定后再充值：\n" 
                    "绑定后可以获得更多游戏功能和福利！",
                    reply_markup=reply_markup
                )
                return
            
            # 生成唯一订单号
            from datetime import datetime, timedelta, timezone
            import uuid
            beijing_tz = timezone(timedelta(hours=8))
            order_no = f"R{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
            
            # 调用平台API创建充值订单
            import httpx
            
            headers = {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json"
            }
            from app.config import BOT_USERNAME
            data = {
                "pay_way": "telegram_bot",
                "price": carrot_amount,
                "name": "游戏币充值",
                "param": None,
                "callback_telegram_bot_name": BOT_USERNAME
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://emos.best/api/pay/create",
                    headers=headers,
                    json=data,
                    timeout=10
                )
            
            if response.status_code == 200:
                result = response.json()
                payment_url = result.get('pay_url')
                platform_order_no = result.get('no')
                game_coin = carrot_amount * 10  # 假设1萝卜=10游戏币
                
                if payment_url:
                    # 计算过期时间（5分钟后）
                    from datetime import datetime, timedelta, timezone
                    beijing_tz = timezone(timedelta(hours=8))
                    expire_time = datetime.now(beijing_tz) + timedelta(minutes=5)
                    
                    # 保存订单到数据库
                    from app.database import add_recharge_order
                    add_recharge_order(
                        order_no=order_no,
                        user_id=local_user_id,
                        telegram_user_id=telegram_id,
                        carrot_amount=carrot_amount,
                        game_coin_amount=game_coin,
                        platform_order_no=platform_order_no,
                        pay_url=payment_url,
                        expire_time=expire_time
                    )
                    
                    # 创建支付按钮
                    keyboard = [
                        [InlineKeyboardButton("💳 前往支付", url=payment_url)],
                        [InlineKeyboardButton("🔙 返回", callback_data='back')]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    message = f"{user.first_name} 充值订单创建成功！\n\n"
                    message += f"订单号：{order_no}\n"
                    message += f"平台订单号：{platform_order_no}\n"
                    message += f"充值萝卜：{carrot_amount} 萝卜\n"
                    message += f"获得游戏币：{game_coin} 游戏币\n\n"
                    message += "请点击下方按钮前往支付："
                    
                    await update.message.reply_text(message, reply_markup=reply_markup)
                else:
                    await update.message.reply_text("❌ 充值订单创建失败，无法获取支付链接")
            else:
                await update.message.reply_text(f"❌ API调用失败: {response.status_code}")
        except ValueError:
            await update.message.reply_text("请输入有效的数字作为充值萝卜数量")
        except Exception as e:
            await update.message.reply_text(f"❌ 充值失败：{str(e)}")
        finally:
            # 清除当前操作状态
            if 'current_operation' in context.user_data:
                del context.user_data['current_operation']
            if 'token' in context.user_data:
                del context.user_data['token']
            if 'local_user_id' in context.user_data:
                del context.user_data['local_user_id']
            if 'total_recharge' in context.user_data:
                del context.user_data['total_recharge']
            if 'remaining_recharge' in context.user_data:
                del context.user_data['remaining_recharge']
    
    # 检查是否在等待提现金额的输入
    elif 'current_operation' in context.user_data and context.user_data['current_operation'] == 'withdraw_amount':
        # 处理提现金额输入
        try:
            withdraw_amount = int(message_text)
            if withdraw_amount < 1 or withdraw_amount > 50000:
                await update.message.reply_text("提现金额必须在1-50000萝卜之间")
                return
            
            # 从context中获取用户信息
            token = context.user_data.get('token')
            game_balance = context.user_data.get('game_balance', 0)
            local_user_id = context.user_data.get('local_user_id')
            
            # 检查用户累计充值和提现记录
            from app.database import get_user_total_recharge, get_user_total_withdraw
            total_recharge = get_user_total_recharge(local_user_id)
            total_withdraw = get_user_total_withdraw(local_user_id)
            
            # 计算最大可提现萝卜数（不超过累计充值的3倍）
            max_withdraw_from_recharge = int(total_recharge * 3)
            remaining_withdraw = max_withdraw_from_recharge - total_withdraw
            
            if withdraw_amount > remaining_withdraw:
                await update.message.reply_text(f"提现金额不能超过累计充值金额的3倍，您已提现{total_withdraw}萝卜，还可提现{remaining_withdraw}萝卜")
                return
            
            # 计算实际需要扣除的游戏币（11游戏币=1萝卜，包含1%手续费）
            base_game_coin = withdraw_amount * 10  # 基础游戏币
            fee_game_coin = withdraw_amount * 1     # 手续费1游戏币/萝卜
            total_game_coin = base_game_coin + fee_game_coin  # 总扣除游戏币
            
            if total_game_coin > game_balance:
                await update.message.reply_text(f"余额不足！当前余额：{game_balance} 游戏币，需要 {total_game_coin} 游戏币（基础 {base_game_coin} 游戏币 + 手续费 {fee_game_coin} 游戏币）")
                return
            
            # 调用平台API处理提现
            import httpx
            from app.config import API_BASE_URL
            
            headers = {"Authorization": f"Bearer {token}"}
            data = {"user_id": local_user_id, "carrot": withdraw_amount}
            
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{API_BASE_URL}/carrot/transfer",
                    headers=headers,
                    json=data,
                    timeout=10
                )
            
            if response.status_code == 200:
                # 扣除游戏币 - 先获取字符串格式的 user_id
                from app.database import get_user_by_telegram_id, get_user_by_user_id
                from app.database import get_db_connection
                conn = get_db_connection()
                emos_user_id = None
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT user_id FROM users WHERE id = %s", (local_user_id,))
                            result = cursor.fetchone()
                            if result:
                                if isinstance(result, dict):
                                    emos_user_id = result.get('user_id')
                                else:
                                    emos_user_id = result[0]
                    finally:
                        conn.close()
                
                if emos_user_id:
                    new_balance = update_balance(emos_user_id, -total_game_coin)
                else:
                    new_balance = 0
                
                # 生成提现订单号
                from datetime import datetime, timedelta, timezone
                import uuid
                beijing_tz = timezone(timedelta(hours=8))
                order_no = f"W{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                
                # 添加提现记录
                from app.database import add_withdrawal_record
                add_withdrawal_record(local_user_id, withdraw_amount)
                
                # 更新用户累计提现金额
                from app.database import update_user_total_withdraw
                update_user_total_withdraw(local_user_id, withdraw_amount)
                
                await update.message.reply_text(f"{user.first_name} 提现申请成功！\n\n订单号：{order_no}\n提现萝卜：{withdraw_amount} 萝卜\n基础游戏币：{base_game_coin} 游戏币\n手续费：{fee_game_coin} 游戏币\n扣除游戏币：{total_game_coin} 游戏币\n当前余额：{new_balance} 游戏币")
            else:
                await update.message.reply_text(f"❌ 提现失败：API调用失败，状态码：{response.status_code}")
        except ValueError:
            await update.message.reply_text("请输入有效的数字作为提现萝卜数量")
        except Exception as e:
            await update.message.reply_text(f"❌ 提现失败：{str(e)}")
        finally:
            # 清除当前操作状态
            if 'current_operation' in context.user_data:
                del context.user_data['current_operation']
            if 'game_balance' in context.user_data:
                del context.user_data['game_balance']
            if 'local_user_id' in context.user_data:
                del context.user_data['local_user_id']
            if 'token' in context.user_data:
                del context.user_data['token']


async def slot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /slot 命令"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    # 注意：user_info可能是字符串（token）或字典
    if isinstance(user_info, dict):
        user_id = user_info.get('user_id', telegram_id)
        token = user_info.get('token', '')
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id = telegram_id
        token = user_info
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'token': token,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': telegram_id
    }
    add_user(user_id, user_data)
    
    # 新用户初始余额为0，无需额外添加
    
    # 检查是否有参数
    if len(context.args) == 1:
        # 直接处理参数
        await process_slot(update, context, context.args[0])
    else:
        # 进入二级会话，等待用户输入
        context.user_data['awaiting_slot'] = True
        await update.message.reply_text("请输入下注金额，例如：`10`\n\n直接复制：`10`", parse_mode='Markdown')


async def process_slot(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str):
    """处理老虎机游戏的逻辑"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再玩游戏：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    user_id_str = user_info.get('user_id', telegram_id)
    username = user_info.get('username', '用户') if isinstance(user_info, dict) else '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    from app.database import get_user_by_telegram_id, get_user_by_user_id
    user_from_db = get_user_by_telegram_id(telegram_id)
    if not user_from_db:
        # 如果通过 telegram_id 找不到，尝试通过 user_id_str 查找
        user_from_db = get_user_by_user_id(user_id_str)
    
    if user_from_db:
        user_id = user_from_db['id']  # 数据库自增ID（用于 add_game_record）
        user_id_api = user_from_db.get('user_id', user_id_str)  # 字符串格式的 user_id（用于余额操作）
        logger.info(f"[老虎机] 找到用户: id={user_id}, user_id={user_id_api}, telegram_id={user_from_db.get('telegram_id')}")
    else:
        user_id = user_id_str  # 回退到字符串ID
        user_id_api = user_id_str
        logger.warning(f"[老虎机] 未找到用户，回退到字符串ID: {user_id}")
    
    try:
        bet_amount = int(amount)
        if bet_amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字作为下注金额")
        return
    
    # 检查余额
    is_sufficient, current_balance = check_balance(user_id_api, bet_amount)
    if not is_sufficient:
        await update.message.reply_text(f"余额不足！当前余额：{current_balance}")
        return
    
    # 增加用户贡献分（每下注1币增加1分）
    add_user_score(telegram_id, bet_amount)
    
    # 发送 TG 内置老虎机
    slot_message = await update.message.reply_dice(emoji="🎰")
    
    # 等待老虎机结果
    import asyncio
    await asyncio.sleep(1)  # 等待 1 秒确保老虎机结果已生成
    
    # 获取老虎机结果
    slot_value = slot_message.dice.value
    
    # 老虎机中奖规则
    # Telegram 老虎机结果范围是 1-64
    # 基于 4 进制位移计算的精准映射逻辑
    
    # 图案定义
    symbols = ["BAR", "🍇", "🍋", "7️⃣"]  # 0: BAR, 1: 葡萄, 2: 柠檬, 3: 7
    
    # 计算老虎机图案组合
    x = slot_value - 1  # 转换为 0-63
    left = x // 16  # 左轴
    middle = (x % 16) // 4  # 中轴
    right = x % 4  # 右轴
    
    # 获取图案组合
    left_symbol = symbols[left]
    middle_symbol = symbols[middle]
    right_symbol = symbols[right]
    
    # 根据下注金额确定用户等级（用于Jackpot奖励比例）
    def get_bet_level(bet_amount):
        if bet_amount >= 200:
            return "钻石", 0.5, 1.0  # 固定50倍，100%奖池
        elif bet_amount >= 51:
            return "黄金", 0.5, 0.6  # 固定50倍，60%奖池
        elif bet_amount >= 11:
            return "白银", 0.5, 0.3  # 固定50倍，30%奖池
        else:
            return "青铜", 0.5, 0.1  # 固定50倍，10%奖池
    
    level, _, _ = get_bet_level(bet_amount)
    
    # 获取当前奖池金额
    jackpot_pool = get_jackpot_pool()
    
    # 构建结果字符串
    result = f"#老虎机 结果\n\n"
    result += f"🎰 结果: {left_symbol} {middle_symbol} {right_symbol}\n"
    
    # 判断中奖情况
    is_win = False
    win_amount = -bet_amount  # 默认输
    is_jackpot = False
    jackpot_win = 0
    needs_rake = False  # 是否需要抽水（赔率>1的情况）
    
    # 检查是否触发Jackpot（7️⃣-BAR-7️⃣组合，概率1/256）
    # 需要 left=3 (7️⃣), middle=0 (BAR), right=3 (7️⃣)
    # 额外添加随机概率检查，确保实际概率接近1/256
    is_jackpot_triggered = False
    if left == 3 and middle == 0 and right == 3:
        # 1/4的概率实际触发Jackpot，这样总概率约为1/256
        import random
        if random.random() < 0.25:
            is_jackpot = True
            is_win = True
            is_jackpot_triggered = True
            needs_rake = True  # Jackpot需要抽水
            
            # 根据下注金额获取等级
            level, fixed_multiplier, pool_ratio = get_bet_level(bet_amount)
            
            # 从全局获取Jackpot奖池金额（重新获取，因为可能在计算过程中有变化）
            jackpot_pool = get_jackpot_pool()
            
            # 检查奖池保护期：奖池不满500时，钻石等级不触发100%获取
            if level == "钻石" and jackpot_pool < 500:
                pool_ratio = 0.0  # 只给固定倍数，不拿走奖池
                result += f"⚠️ 奖池保护期：奖池不足500，暂不触发100%获取\n"
            
            # 计算Jackpot奖金
            # 固定50倍奖励 + 奖池按比例拿走
            fixed_bonus = bet_amount * 50
            pool_bonus = int(jackpot_pool * pool_ratio)
            jackpot_win = fixed_bonus + pool_bonus
            win_amount = jackpot_win
            
            # 构建结果消息
            result += f"🎉🎉🎉 JACKPOT大奖！🎉🎉🎉\n"
            result += f"💰 奖池金额：{jackpot_pool} 🪙\n"
            result += f"🏆 下注等级：{level}\n"
            result += f"🎁 固定奖励：{fixed_bonus} 🪙（50倍下注）\n"
            if pool_bonus > 0:
                result += f"🏦 奖池奖励：{pool_bonus} 🪙（{int(pool_ratio*100)}%奖池）\n"
            
            # 记录Jackpot中奖信息
            record_jackpot_win(telegram_id, jackpot_win)
            
            # 更新Jackpot奖池
            if pool_ratio == 1.0:
                # 钻石用户拿走全部奖池，重置为0
                reset_jackpot_pool()
            elif pool_ratio > 0:
                # 其他等级用户只拿走部分，更新奖池
                from app.database.jackpot import set_jackpot_pool
                new_pool_amount = jackpot_pool - pool_bonus
                set_jackpot_pool(new_pool_amount)
        else:
            # 不触发Jackpot，视为普通组合
            is_jackpot = False
            is_win = False
            win_amount = -bet_amount
            result += "全不同！\n"
    # 大奖：三个相同图案（统一10倍）
    elif left == middle == right:
        is_win = True
        needs_rake = True  # 三个一样需要抽水
        win_amount = bet_amount * 10
        result += "🎊 三个相同！🎊\n"
    # 小奖：两个相同图案（0.5倍，不抽水）
    elif left == middle or middle == right or left == right:
        is_win = True
        win_amount = int(bet_amount * 0.5)
        result += "两个相同！\n"
    # 未中奖：全不同图案
    else:
        result += "全不同！\n"
    
    # 添加等级和奖池信息
    result += f"🏆 下注等级：{level}\n"
    result += f"💰 累计奖池：{jackpot_pool} 🪙\n"
    
    # 抽水逻辑（仅在赔率>1时触发：三个一样或Jackpot）
    server_profit = 0
    jackpot_contribution = 0
    if needs_rake and win_amount > 0:
        # 10%抽水：5%给服务器，5%注入奖池
        total_rake = int(win_amount * 0.10)
        server_profit = int(total_rake * 0.5)  # 5%给服务器
        jackpot_contribution = int(total_rake * 0.5)  # 5%注入奖池
        
        # 扣除抽水后的实际奖金
        win_amount = win_amount - total_rake
        
        # 更新奖池
        if jackpot_contribution > 0:
            add_to_jackpot_pool(jackpot_contribution)
        
        # 在结果消息中显示抽水信息
        result += f"💸 服务器利润：{server_profit} 🪙（5%）\n"
        result += f"🏦 奖池注入：{jackpot_contribution} 🪙（5%）\n"

    # 更新余额
    if win_amount > 0:
        new_balance = update_balance(user_id_api, int(win_amount))
    else:
        new_balance = update_balance(user_id_api, int(win_amount))  # 输了不需要扣除费用

    # 保存游戏记录
    game_result = "win" if is_win else "lose"
    add_game_record(user_id, "slot", bet_amount, game_result, win_amount if is_win else 0, username)

    # 发送结果
    if is_win:
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🎰 再来一局", callback_data='slot_again'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_jackpot:
            await update.message.reply_text(f"🎉 {user.first_name} 🎰\n{result}\n\n🎊🎊🎊 恭喜中得JACKPOT！🎊🎊🎊\n✨ 获得 {win_amount} 🪙\n💰 当前余额：{new_balance} 🪙", reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"🎉 {user.first_name} 🎰\n{result}\n\n✨ 恭喜你赢了！获得 {win_amount} 🪙\n💰 当前余额：{new_balance} 🪙", reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🎰 再来一局", callback_data='slot_again'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(f"🎰 {user.first_name} 🎰\n{result}\n\n😢 很遗憾，你输了 {bet_amount} 🪙\n💰 当前余额：{new_balance} 🪙", reply_markup=reply_markup, parse_mode="Markdown")


async def blackjack_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /blackjack 命令"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    # 注意：user_info可能是字符串（token）或字典
    if isinstance(user_info, dict):
        user_id = user_info.get('user_id', telegram_id)
        token = user_info.get('token', '')
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id = telegram_id
        token = user_info
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'token': token,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': telegram_id
    }
    add_user(user_id, user_data)
    
    # 新用户初始余额为0，无需额外添加
    
    # 检查是否有参数
    if len(context.args) == 1:
        # 直接处理参数
        await process_blackjack(update, context, context.args[0])
    else:
        # 显示下注档位选择
        keyboard = [
            [InlineKeyboardButton("10 🪙", callback_data='blackjack_bet_10'),
             InlineKeyboardButton("50 🪙", callback_data='blackjack_bet_50')],
            [InlineKeyboardButton("100 🪙", callback_data='blackjack_bet_100'),
             InlineKeyboardButton("500 🪙", callback_data='blackjack_bet_500')],
            [InlineKeyboardButton("自定义金额", callback_data='blackjack_bet_custom'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "🃏 21点游戏\n\n请选择下注金额：",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "🃏 21点游戏\n\n请选择下注金额：",
                reply_markup=reply_markup
            )


async def process_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str):
    """处理21点游戏的逻辑"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    user_id_str = user_info.get('user_id', telegram_id)
    username = user_info.get('username', '用户') if isinstance(user_info, dict) else '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    from app.database import get_user_by_telegram_id, get_user_by_user_id
    user_from_db = get_user_by_telegram_id(telegram_id)
    if not user_from_db:
        # 如果通过 telegram_id 找不到，尝试通过 user_id_str 查找
        user_from_db = get_user_by_user_id(user_id_str)
    
    if user_from_db:
        user_id = user_from_db['id']  # 数据库自增ID（用于 add_game_record）
        user_id_api = user_from_db.get('user_id', user_id_str)  # 字符串格式的 user_id（用于余额操作）
        logger.info(f"[21点] 找到用户: id={user_id}, user_id={user_id_api}, telegram_id={user_from_db.get('telegram_id')}")
    else:
        user_id = user_id_str  # 回退到字符串ID
        user_id_api = user_id_str
        logger.warning(f"[21点] 未找到用户，回退到字符串ID: {user_id}")
    
    try:
        bet_amount = int(amount)
        if bet_amount <= 0:
            if hasattr(update, 'callback_query') and update.callback_query:
                await update.callback_query.edit_message_text("下注金额必须大于0")
            else:
                await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("请输入有效的数字作为下注金额")
        else:
            await update.message.reply_text("请输入有效的数字作为下注金额")
        return
    
    # 检查余额
    is_sufficient, current_balance = check_balance(user_id_api, bet_amount)
    if not is_sufficient:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"余额不足！当前余额：{current_balance}")
        else:
            await update.message.reply_text(f"余额不足！当前余额：{current_balance}")
        return
    
    # 初始化游戏状态
    import random
    
    # 发牌函数（带花色）
    def deal_card():
        # 花色和牌面
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        # 随机选择花色和牌面
        suit = random.choice(suits)
        rank = random.choice(ranks)
        # 计算点数
        if rank == 'A':
            value = 11
        elif rank in ['J', 'Q', 'K']:
            value = 10
        else:
            value = int(rank)
        return (f"{suit}{rank}", value)
    
    # 计算手牌点数
    def calculate_hand(hand):
        # 提取所有点数
        values = [card[1] for card in hand]
        total = sum(values)
        # 如果有A且总点数超过21，将A视为1
        while total > 21 and 11 in values:
            idx = values.index(11)
            values[idx] = 1
            total = sum(values)
        return total
    
    # 初始化游戏
    player_hand = [deal_card(), deal_card()]
    dealer_hand = [deal_card(), deal_card()]
    
    player_total = calculate_hand(player_hand)
    dealer_total = calculate_hand(dealer_hand)
    
    # 存储游戏状态
    context.user_data['blackjack'] = {
        'bet_amount': bet_amount,
        'player_hand': player_hand,
        'dealer_hand': dealer_hand,
        'player_total': player_total,
        'dealer_total': dealer_total,
        'game_active': True
    }
    
    # 获取连胜次数和头衔
    win_streak = context.user_data.get('blackjack_win_streak', 0)
    user_title = context.user_data.get('blackjack_title', '')
    
    # 构建游戏状态消息
    game_state = f"🃏 21点游戏开始！\n\n"
    if user_title:
        game_state += f"🏷️ 你当前头衔：【{user_title}】\n\n"
    game_state += f"连胜次数：{win_streak}\n\n"
    # 显示带花色的手牌
    player_cards_str = ' '.join([card[0] for card in player_hand])
    game_state += f"您的手牌：{player_cards_str} (总点数: {player_total})\n"
    game_state += f"庄家手牌：{dealer_hand[0][0]} ? (可见点数: {dealer_hand[0][1]})\n\n"
    
    # 检查是否黑杰克
    if player_total == 21:
        # 黑杰克，直接结算
        win_amount = bet_amount * 1.5  # 黑杰克1.5倍赔率
        
        # 计算10%抽成
        service_fee = max(1, int(win_amount * 0.10))
        actual_win = int(win_amount - service_fee)
        
        new_balance = update_balance(user_id_api, actual_win)
        
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, "win", actual_win, username)
        
        # 更新连胜记录（使用数据库）
        win_streak = update_user_streak(user_id_api, telegram_id, 'blackjack', is_win=True)
        context.user_data['blackjack_win_streak'] = win_streak
        
        # 检查连胜奖励
        bonus = 0
        bonus_message = ""
        tag_name = None
        
        if win_streak == 1:
            bonus_message = "\n🎉 恭喜获得首胜！"
            tag_name = "新手村"
        elif win_streak == 3:
            bonus = 50
            bonus_message = "\n🎉 3连胜奖励：+50 🪙"
            tag_name = "连胜达人"
        elif win_streak == 5:
            bonus = 100
            bonus_message = "\n🎉 5连胜奖励：+100 🪙"
            tag_name = "连胜大师"
        elif win_streak == 7:
            bonus = 200
            bonus_message = "\n🎉 7连胜奖励：+200 🪙\n🏆 获得头衔：【点王】"
            context.user_data['blackjack_title'] = "点王"
            tag_name = "点王"
        elif win_streak > 7 and win_streak <= 15:
            bonus = 50
            bonus_message = f"\n🎉 {win_streak}连胜奖励：+50 🪙"
            
            # 更新头衔
            title_map = {
                8: "不爆狂人",
                9: "牌桌幽灵",
                10: "天命之子",
                11: "庄家克星",
                12: "21点魔",
                13: "不灭赌徒",
                14: "神之一手",
                15: "不败神话"
            }
            if win_streak in title_map:
                new_title = title_map[win_streak]
                context.user_data['blackjack_title'] = new_title
                bonus_message += f"\n🏆 头衔升级：【{new_title}】"
                tag_name = new_title
        elif win_streak > 15:
            bonus = 50
            bonus_message = "\n🎉 连胜奖励：+50 🪙"
            context.user_data['blackjack_title'] = "不败神话"
            tag_name = "不败神话"
        
        # 尝试设置群标签（如果达标）
        if tag_name:
            try:
                # 获取当前聊天ID
                chat_id = update.effective_chat.id if update.effective_chat else None
                chat_type = update.effective_chat.type if update.effective_chat else None
                
                logger.info(f"标签处理 - tag_name: {tag_name}, win_streak: {win_streak}, chat_id: {chat_id}, chat_type: {chat_type}")
                
                # 记录标签到数据库（无论是否在群聊中）
                add_user_tag(user_id_api, telegram_id, DEFAULT_GROUP_CHAT_ID, tag_name, tag_level=win_streak)
                logger.info(f"已记录标签到数据库 - user_id: {user_id}, tag: {tag_name}, chat_id: {DEFAULT_GROUP_CHAT_ID}")
                
                # 尝试使用默认群聊ID设置标签
                try:
                    logger.info(f"尝试设置群标签 - chat_id: {DEFAULT_GROUP_CHAT_ID}, user_id: {telegram_id}, tag: {tag_name}")
                    # 使用 Bot API 9.5 的 set_chat_member_tag 方法
                    result = await context.bot.set_chat_member_tag(
                        chat_id=DEFAULT_GROUP_CHAT_ID,
                        user_id=telegram_id,
                        tag=tag_name
                    )
                    logger.info(f"设置标签结果: {result}")
                    
                    if result:
                        bonus_message += f"\n🏷️ 已设置群标签：【{tag_name}】"
                    else:
                        bonus_message += f"\n⚠️ 标签记录成功，但群标签设置失败"
                except Exception as api_error:
                    logger.error(f"API设置标签失败: {api_error}")
                    # 检查是否是权限问题
                    error_str = str(api_error).lower()
                    if 'rights' in error_str or 'permission' in error_str or 'admin' in error_str:
                        bonus_message += f"\n⚠️ 机器人需要【管理标签】权限才能在群里显示标签"
                    elif 'not found' in error_str or 'member' in error_str:
                        bonus_message += f"\n⚠️ 你还不在群里，无法设置群标签"
                    else:
                        bonus_message += f"\n⚠️ 标签已记录，但群标签设置失败: {api_error}"
                
                # 无论是否在群聊，都显示标签获得信息
                if chat_id:
                    bonus_message += f"\n🏷️ 获得标签：【{tag_name}】"
            except Exception as e:
                # 记录日志并给用户反馈
                logger.error(f"设置群标签失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                bonus_message += f"\n⚠️ 标签记录失败，请联系管理员"
        
        # 发放奖励
        if bonus > 0:
            update_balance(user_id_api, bonus)
            new_balance += bonus
        
        game_state += "🎉 恭喜！您拿到了黑杰克！\n"
        game_state += f"✨ 获得：{int(win_amount)} 🪙\n"
        game_state += f"💸 抽成：{service_fee} 🪙 (10%)\n"
        game_state += f"💰 实际获得：{actual_win} 🪙\n"
        if bonus_message:
            game_state += bonus_message
        game_state += f"\n💰 当前余额：{new_balance}"
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"{user.first_name} {game_state}", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"{user.first_name} {game_state}", parse_mode='Markdown')
        
        # 游戏结束，清除状态
        del context.user_data['blackjack']
    else:
        # 游戏继续，提示用户操作
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("要牌", callback_data='hit'),
             InlineKeyboardButton("停牌", callback_data='stand')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        game_state += "请选择操作："
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"{user.first_name} {game_state}", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"{user.first_name} {game_state}", reply_markup=reply_markup, parse_mode='Markdown')


async def hit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /hit 命令（要牌）"""
    # 处理不同类型的update
    if hasattr(update, 'callback_query') and update.callback_query:
        # 回调类型
        query = update.callback_query
        await query.answer()  # 先确认收到回调
        user = query.from_user
        telegram_id = user.id
    else:
        # 命令类型
        user = update.effective_user
        telegram_id = user.id
    
    # 检查用户是否已绑定 token
    if telegram_id not in user_tokens:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_tokens 中获取用户信息
    user_info = user_tokens.get(telegram_id, {})
    user_id_str = user_info.get('user_id', telegram_id)
    username = user_info.get('username', '用户') if isinstance(user_info, dict) else '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    from app.database import get_user_by_telegram_id, get_user_by_user_id
    user_from_db = get_user_by_telegram_id(telegram_id)
    if not user_from_db:
        # 如果通过 telegram_id 找不到，尝试通过 user_id_str 查找
        user_from_db = get_user_by_user_id(user_id_str)
    
    if user_from_db:
        user_id = user_from_db['id']  # 数据库自增ID（用于 add_game_record）
        user_id_api = user_from_db.get('user_id', user_id_str)  # 字符串格式的 user_id（用于余额操作）
        logger.info(f"[五龙] 找到用户: id={user_id}, user_id={user_id_api}, telegram_id={user_from_db.get('telegram_id')}")
    else:
        user_id = user_id_str  # 回退到字符串ID
        user_id_api = user_id_str
        logger.warning(f"[五龙] 未找到用户，回退到字符串ID: {user_id}")
    
    # 检查游戏是否激活
    if 'blackjack' not in context.user_data or not context.user_data['blackjack']['game_active']:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("您当前没有进行中的21点游戏，请先使用 /blackjack 命令开始游戏")
        else:
            await update.message.reply_text("您当前没有进行中的21点游戏，请先使用 /blackjack 命令开始游戏")
        return
    
    # 获取游戏状态
    game_state = context.user_data['blackjack']
    bet_amount = game_state['bet_amount']
    player_hand = game_state['player_hand']
    dealer_hand = game_state['dealer_hand']
    
    # 发牌函数（带花色）
    import random
    def deal_card():
        # 花色和牌面
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        # 随机选择花色和牌面
        suit = random.choice(suits)
        rank = random.choice(ranks)
        # 计算点数
        if rank == 'A':
            value = 11
        elif rank in ['J', 'Q', 'K']:
            value = 10
        else:
            value = int(rank)
        return (f"{suit}{rank}", value)
    
    # 计算手牌点数
    def calculate_hand(hand):
        # 提取所有点数
        values = [card[1] for card in hand]
        total = sum(values)
        # 如果有A且总点数超过21，将A视为1
        while total > 21 and 11 in values:
            idx = values.index(11)
            values[idx] = 1
            total = sum(values)
        return total
    
    # 玩家要牌
    player_hand.append(deal_card())
    player_total = calculate_hand(player_hand)
    
    # 更新游戏状态
    game_state['player_hand'] = player_hand
    game_state['player_total'] = player_total
    
    # 构建游戏状态消息
    response = f"🃏 21点游戏\n\n"
    # 显示带花色的手牌
    player_cards_str = ' '.join([card[0] for card in player_hand])
    response += f"您的手牌：{player_cards_str} (总点数: {player_total})\n"
    response += f"庄家手牌：{dealer_hand[0][0]} ? (可见点数: {dealer_hand[0][1]})\n\n"
    
    # 检查是否爆牌
    if player_total > 21:
        # 玩家爆牌，游戏结束
        win_amount = -bet_amount
        new_balance = update_balance(user_id_api, win_amount)
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, "lose", 0, username)
        
        # 重置连胜记录（使用数据库）
        update_user_streak(user_id_api, telegram_id, 'blackjack', is_win=False)
        context.user_data['blackjack_win_streak'] = 0
        
        response += "😢 您爆牌了！\n\n"
        response += f"😢 很遗憾，你输了 {bet_amount} 🪙\n"
        response += f"💰 当前余额：{new_balance} 🪙\n\n"
        response += "🎯 再接再厉！"
        
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🃏 再来一局", callback_data='blackjack_again'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
        
        # 游戏结束，清除状态
        del context.user_data['blackjack']
    # 检查五龙规则（5张牌未爆牌）
    elif len(player_hand) == 5 and player_total <= 21:
        # 五龙，直接获胜
        win_amount = bet_amount * 1.5  # 五龙1.5倍赔率
        
        # 计算10%抽成
        service_fee = max(1, int(win_amount * 0.10))
        actual_win = int(win_amount - service_fee)
        
        new_balance = update_balance(user_id_api, actual_win)
        
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, "win", actual_win, username)
        
        # 更新连胜记录（使用数据库）
        win_streak = update_user_streak(user_id_api, telegram_id, 'blackjack', is_win=True)
        context.user_data['blackjack_win_streak'] = win_streak
        
        # 检查连胜奖励
        bonus = 0
        bonus_message = ""
        tag_name = None
        
        if win_streak == 1:
            bonus_message = "\n🎉 恭喜获得首胜！"
            tag_name = "新手村"
        elif win_streak == 3:
            bonus = 50
            bonus_message = "\n🎉 3连胜奖励：+50 🪙"
            tag_name = "连胜达人"
        elif win_streak == 5:
            bonus = 100
            bonus_message = "\n🎉 5连胜奖励：+100 🪙"
            tag_name = "连胜大师"
        elif win_streak == 7:
            bonus = 200
            bonus_message = "\n🎉 7连胜奖励：+200 🪙\n🏆 获得头衔：【点王】"
            context.user_data['blackjack_title'] = "点王"
            tag_name = "点王"
        elif win_streak > 7 and win_streak <= 15:
            bonus = 50
            bonus_message = f"\n🎉 {win_streak}连胜奖励：+50 🪙"
            
            # 更新头衔
            title_map = {
                8: "不爆狂人",
                9: "牌桌幽灵",
                10: "天命之子",
                11: "庄家克星",
                12: "21点魔",
                13: "不灭赌徒",
                14: "神之一手",
                15: "不败神话"
            }
            if win_streak in title_map:
                new_title = title_map[win_streak]
                context.user_data['blackjack_title'] = new_title
                bonus_message += f"\n🏆 头衔升级：【{new_title}】"
                tag_name = new_title
        elif win_streak > 15:
            bonus = 50
            bonus_message = "\n🎉 连胜奖励：+50 🪙"
            context.user_data['blackjack_title'] = "不败神话"
            tag_name = "不败神话"
        
        # 尝试设置群标签（如果达标）
        if tag_name:
            try:
                chat_id = update.effective_chat.id if update.effective_chat else None
                chat_type = update.effective_chat.type if update.effective_chat else None
                
                logger.info(f"[五龙] 标签处理 - tag_name: {tag_name}, win_streak: {win_streak}, chat_id: {chat_id}, chat_type: {chat_type}")
                
                # 记录标签到数据库（无论是否在群聊中）
                add_user_tag(user_id_api, telegram_id, DEFAULT_GROUP_CHAT_ID, tag_name, tag_level=win_streak)
                logger.info(f"[五龙] 已记录标签到数据库 - user_id: {user_id}, tag: {tag_name}, chat_id: {DEFAULT_GROUP_CHAT_ID}")
                
                # 尝试使用默认群聊ID设置标签
                try:
                    logger.info(f"[五龙] 尝试设置群标签 - chat_id: {DEFAULT_GROUP_CHAT_ID}, user_id: {telegram_id}, tag: {tag_name}")
                    result = await context.bot.set_chat_member_tag(
                        chat_id=DEFAULT_GROUP_CHAT_ID,
                        user_id=telegram_id,
                        tag=tag_name
                    )
                    logger.info(f"[五龙] 设置标签结果: {result}")
                    
                    if result:
                        bonus_message += f"\n🏷️ 已设置群标签：【{tag_name}】"
                    else:
                        bonus_message += f"\n⚠️ 标签记录成功，但群标签设置失败"
                except Exception as api_error:
                    logger.error(f"[五龙] API设置标签失败: {api_error}")
                    error_str = str(api_error).lower()
                    if 'rights' in error_str or 'permission' in error_str or 'admin' in error_str:
                        bonus_message += f"\n⚠️ 机器人需要【管理标签】权限才能在群里显示标签"
                    elif 'not found' in error_str or 'member' in error_str:
                        bonus_message += f"\n⚠️ 你还不在群里，无法设置群标签"
                    else:
                        bonus_message += f"\n⚠️ 标签已记录，但群标签设置失败"
                
                # 无论是否在群聊，都显示标签获得信息
                if chat_id:
                    bonus_message += f"\n🏷️ 获得标签：【{tag_name}】"
            except Exception as e:
                logger.error(f"[五龙] 设置群标签失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                bonus_message += f"\n⚠️ 标签记录失败，请联系管理员"
        
        # 发放奖励
        if bonus > 0:
            update_balance(user_id_api, bonus)
            new_balance += bonus
        
        response += "🎉 恭喜！您拿到了五龙！\n"
        response += f"✨ 获得：{int(win_amount)} 🪙\n"
        response += f"💸 抽成：{service_fee} 🪙 (10%)\n"
        response += f"💰 实际获得：{actual_win} 🪙\n"
        if bonus_message:
            response += bonus_message
        response += f"\n💰 当前余额：{new_balance}"
        
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🃏 再来一局", callback_data='blackjack_again'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
        
        # 游戏结束，清除状态
        del context.user_data['blackjack']
    else:
        # 游戏继续，提示用户操作
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("要牌", callback_data='hit'),
             InlineKeyboardButton("停牌", callback_data='stand')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        response += "请选择操作："
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')


async def stand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /stand 命令（停牌）"""
    # 处理不同类型的update
    if hasattr(update, 'callback_query') and update.callback_query:
        # 回调类型
        query = update.callback_query
        await query.answer()  # 先确认收到回调
        user = query.from_user
        telegram_id = user.id
    else:
        # 命令类型
        user = update.effective_user
        telegram_id = user.id
    
    # 检查用户是否已绑定 token
    if telegram_id not in user_tokens:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_tokens 中获取用户信息
    user_info = user_tokens.get(telegram_id, {})
    user_id_str = user_info.get('user_id', telegram_id)
    username = user_info.get('username', '用户') if isinstance(user_info, dict) else '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    from app.database import get_user_by_telegram_id, get_user_by_user_id
    user_from_db = get_user_by_telegram_id(telegram_id)
    if not user_from_db:
        # 如果通过 telegram_id 找不到，尝试通过 user_id_str 查找
        user_from_db = get_user_by_user_id(user_id_str)
    
    if user_from_db:
        user_id = user_from_db['id']  # 数据库自增ID（用于 add_game_record）
        user_id_api = user_from_db.get('user_id', user_id_str)  # 字符串格式的 user_id（用于余额操作）
        logger.info(f"[停牌] 找到用户: id={user_id}, user_id={user_id_api}, telegram_id={user_from_db.get('telegram_id')}")
    else:
        user_id = user_id_str  # 回退到字符串ID
        user_id_api = user_id_str
        logger.warning(f"[停牌] 未找到用户，回退到字符串ID: {user_id}")
    
    # 检查游戏是否激活
    if 'blackjack' not in context.user_data or not context.user_data['blackjack']['game_active']:
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("您当前没有进行中的21点游戏，请先使用 /blackjack 命令开始游戏")
        else:
            await update.message.reply_text("您当前没有进行中的21点游戏，请先使用 /blackjack 命令开始游戏")
        return
    
    # 获取游戏状态
    game_state = context.user_data['blackjack']
    bet_amount = game_state['bet_amount']
    player_hand = game_state['player_hand']
    dealer_hand = game_state['dealer_hand']
    player_total = game_state['player_total']
    
    # 计算手牌点数
    def calculate_hand(hand):
        # 提取所有点数
        values = [card[1] for card in hand]
        total = sum(values)
        # 如果有A且总点数超过21，将A视为1
        while total > 21 and 11 in values:
            idx = values.index(11)
            values[idx] = 1
            total = sum(values)
        return total
    
    # 发牌函数（带花色）
    import random
    def deal_card():
        # 花色和牌面
        suits = ['♠', '♥', '♦', '♣']
        ranks = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']
        # 随机选择花色和牌面
        suit = random.choice(suits)
        rank = random.choice(ranks)
        # 计算点数
        if rank == 'A':
            value = 11
        elif rank in ['J', 'Q', 'K']:
            value = 10
        else:
            value = int(rank)
        return (f"{suit}{rank}", value)
    
    # 庄家回合：如果点数小于17则继续要牌
    while calculate_hand(dealer_hand) < 17:
        dealer_hand.append(deal_card())
    
    dealer_total = calculate_hand(dealer_hand)
    
    # 构建游戏状态消息
    response = f"🃏 21点游戏\n\n"
    # 显示带花色的手牌
    player_cards_str = ' '.join([card[0] for card in player_hand])
    dealer_cards_str = ' '.join([card[0] for card in dealer_hand])
    response += f"您的手牌：{player_cards_str} (总点数: {player_total})\n"
    response += f"庄家手牌：{dealer_cards_str} (总点数: {dealer_total})\n\n"
    
    # 判断胜负
    win_amount = 0
    game_result = "tie"
    
    if dealer_total > 21:
        # 庄家爆牌
        win_amount = bet_amount
        game_result = "win"
        response += "🎉 庄家爆牌了！您赢了！\n"
    elif player_total > dealer_total:
        # 玩家点数大
        win_amount = bet_amount
        game_result = "win"
        response += "🎉 您的点数比庄家大！您赢了！\n"
    elif player_total < dealer_total:
        # 庄家点数大
        win_amount = -bet_amount
        game_result = "lose"
        response += "😢 庄家的点数比您大！您输了！\n"
    else:
        # 和局
        win_amount = 0
        game_result = "tie"
        response += "🤝 和局！\n"
    
    # 处理胜利情况
    if win_amount > 0:
        # 计算10%抽成
        service_fee = max(1, int(win_amount * 0.10))
        actual_win = int(win_amount - service_fee)
        
        new_balance = update_balance(user_id_api, actual_win)
        
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, game_result, actual_win, username)
        
        # 更新连胜记录（使用数据库）
        win_streak = update_user_streak(user_id_api, telegram_id, 'blackjack', is_win=True)
        context.user_data['blackjack_win_streak'] = win_streak
        
        # 检查连胜奖励
        bonus = 0
        bonus_message = ""
        tag_name = None
        
        if win_streak == 1:
            bonus_message = "\n🎉 恭喜获得首胜！"
            tag_name = "新手村"
        elif win_streak == 3:
            bonus = 50
            bonus_message = "\n🎉 3连胜奖励：+50 🪙"
            tag_name = "连胜达人"
        elif win_streak == 5:
            bonus = 100
            bonus_message = "\n🎉 5连胜奖励：+100 🪙"
            tag_name = "连胜大师"
        elif win_streak == 7:
            bonus = 200
            bonus_message = "\n🎉 7连胜奖励：+200 🪙\n🏆 获得头衔：【点王】"
            context.user_data['blackjack_title'] = "点王"
            tag_name = "点王"
        elif win_streak > 7 and win_streak <= 15:
            bonus = 50
            bonus_message = f"\n🎉 {win_streak}连胜奖励：+50 🪙"
            
            # 更新头衔
            title_map = {
                8: "不爆狂人",
                9: "牌桌幽灵",
                10: "天命之子",
                11: "庄家克星",
                12: "21点魔",
                13: "不灭赌徒",
                14: "神之一手",
                15: "不败神话"
            }
            if win_streak in title_map:
                new_title = title_map[win_streak]
                context.user_data['blackjack_title'] = new_title
                bonus_message += f"\n🏆 头衔升级：【{new_title}】"
                tag_name = new_title
        elif win_streak > 15:
            bonus = 50
            tag_name = "不败神话"
            bonus_message = "\n🎉 连胜奖励：+50 🪙"
            context.user_data['blackjack_title'] = "不败神话"
        
        # 发放奖励
        if bonus > 0:
            update_balance(user_id_api, bonus)
            new_balance += bonus
        
        response += f"✨ 获得：{win_amount} 🪙\n"
        response += f"💸 抽成：{service_fee} 🪙 (10%)\n"
        response += f"💰 实际获得：{actual_win} 🪙\n"
        
        # 尝试设置群标签（如果达标）
        if tag_name:
            try:
                chat_id = update.effective_chat.id if update.effective_chat else None
                chat_type = update.effective_chat.type if update.effective_chat else None
                
                logger.info(f"[停牌] 标签处理 - tag_name: {tag_name}, win_streak: {win_streak}, chat_id: {chat_id}, chat_type: {chat_type}")
                
                # 记录标签到数据库（无论是否在群聊中）
                add_user_tag(user_id_api, telegram_id, DEFAULT_GROUP_CHAT_ID, tag_name, tag_level=win_streak)
                logger.info(f"[停牌] 已记录标签到数据库 - user_id: {user_id}, tag: {tag_name}, chat_id: {DEFAULT_GROUP_CHAT_ID}")
                
                # 尝试使用默认群聊ID设置标签
                try:
                    logger.info(f"[停牌] 尝试设置群标签 - chat_id: {DEFAULT_GROUP_CHAT_ID}, user_id: {telegram_id}, tag: {tag_name}")
                    result = await context.bot.set_chat_member_tag(
                        chat_id=DEFAULT_GROUP_CHAT_ID,
                        user_id=telegram_id,
                        tag=tag_name
                    )
                    logger.info(f"[停牌] 设置标签结果: {result}")
                    
                    if result:
                        bonus_message += f"\n🏷️ 已设置群标签：【{tag_name}】"
                    else:
                        bonus_message += f"\n⚠️ 标签记录成功，但群标签设置失败"
                except Exception as api_error:
                    logger.error(f"[停牌] API设置标签失败: {api_error}")
                    error_str = str(api_error).lower()
                    if 'rights' in error_str or 'permission' in error_str or 'admin' in error_str:
                        bonus_message += f"\n⚠️ 机器人需要【管理标签】权限才能在群里显示标签"
                    elif 'not found' in error_str or 'member' in error_str:
                        bonus_message += f"\n⚠️ 你还不在群里，无法设置群标签"
                    else:
                        bonus_message += f"\n⚠️ 标签记录成功，但群标签设置失败"
                
                # 无论是否在群聊，都显示标签获得信息
                if chat_id:
                    bonus_message += f"\n🏷️ 获得标签：【{tag_name}】"
            except Exception as e:
                logger.error(f"[停牌] 设置群标签失败: {e}")
                import traceback
                logger.error(traceback.format_exc())
                bonus_message += f"\n⚠️ 标签记录失败，请联系管理员"
        
        if bonus_message:
            response += bonus_message
        response += f"\n💰 当前余额：{new_balance}"
    elif win_amount < 0:
        # 处理失败情况
        new_balance = update_balance(user_id_api, win_amount)
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, game_result, 0, username)
        
        # 重置连胜记录（使用数据库）
        update_user_streak(user_id_api, telegram_id, 'blackjack', is_win=False)
        context.user_data['blackjack_win_streak'] = 0
        
        response += f"😢 很遗憾，你输了 {bet_amount} 🪙\n"
        response += f"💰 当前余额：{new_balance} 🪙"
    else:
        # 处理和局情况
        new_balance = update_balance(user_id_api, win_amount)
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, game_result, 0, username)
        
        # 和局不影响连胜次数
        
        response += f"💰 当前余额：{new_balance} 🪙"
    
    # 创建按钮
    keyboard = [
        [InlineKeyboardButton("🃏 再来一局", callback_data='blackjack_again'),
         InlineKeyboardButton("🔙 返回", callback_data='games')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
    
    # 游戏结束，清除状态
    del context.user_data['blackjack']


async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /daily 命令"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再签到：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再签到：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    # 注意：user_info可能是字符串（token）或字典
    if isinstance(user_info, dict):
        user_id = user_info.get('user_id', telegram_id)
        token = user_info.get('token', '')
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id = telegram_id
        token = user_info
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'token': token,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': telegram_id
    }
    add_user(user_id, user_data)
    
    # 新用户初始余额为0，无需额外添加
    
    success, message = process_daily_checkin(user_id)
    
    # 创建返回按钮
    keyboard = [
        [InlineKeyboardButton("🔙 返回", callback_data='back')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查是否是CallbackQuery类型的更新
    if update.callback_query:
        await update.callback_query.edit_message_text(
            f"{user.first_name} {message}",
            reply_markup=reply_markup
        )
    else:
        # 在群聊中显示用户信息，让其他群友知道是谁在签到
        await update.message.reply_text(f"{user.first_name} {message}")


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /help 命令"""
    user = update.effective_user
    
    help_text = (
        "📋 游戏机器人命令帮助\n\n"
        "💰 余额相关\n"
        "/balance - 查看当前游戏币余额\n"
        "/daily - 每日签到领取游戏币\n\n"
        "🎲 游戏相关\n"
        "/guess [金额] [大/小] - 猜大小游戏\n"
        "/slot [金额] - 老虎机游戏\n"
        "/blackjack [金额] - 21点游戏\n\n"
        "💸 其他功能\n"
        "/withdraw [金额] - 提现\n"
        "/start - 开始使用机器人\n\n"
        "📝 游戏规则\n"
        "1. 猜大小：4-6点为大，1-3点为小，赢了获得2倍下注\n"
        "2. 老虎机：\n"
        "   - 三个7️⃣：30倍 | 三个🍋：6倍 | 三个🍇：2倍\n"
        "   - 三个BAR：0.5倍 | 两个相同：0.3倍\n"
        "   - 7️⃣-BAR-7️⃣：触发Jackpot（奖池+60倍下注）\n"
        "   - 每局15%进入Jackpot奖池\n"
        "3. 21点：接近21点但不超过，点数比庄家大\n\n"
        "🎮 提示\n"
        "- 所有游戏使用游戏币，需要先绑定账号\n"
        "- 每日签到可以获得1-5个游戏币\n"
        "- 游戏结果由Telegram官方骰子决定，公平公正\n"
    )
    
    await update.message.reply_text(help_text)


async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /withdraw 命令"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再提现：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    user_id = user_info.get('user_id', telegram_id)
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'username': user.username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    add_user(user_id, user_data)
    
    # 检查是否有参数
    if len(context.args) == 1:
        # 直接处理参数
        await process_withdraw(update, context, context.args[0])
    else:
        # 进入二级会话，等待用户输入
        context.user_data['awaiting_withdraw'] = True
        await update.message.reply_text("请输入提现金额，例如：`10`\n\n直接复制：`10`", parse_mode='Markdown')


async def process_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str):
    """处理提现逻辑"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 首先检查telegram_id是否在user_tokens中
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    else:
        # 遍历user_tokens，查找可能的匹配
        for key, info in user_tokens.items():
            if isinstance(info, dict) and info.get('first_name') == user.first_name:
                user_info = info
                break
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再提现：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    user_id_api = user_info.get('user_id', telegram_id)
    token = user_info.get('token')
    
    try:
        withdraw_amount = int(amount)
        if withdraw_amount < 1 or withdraw_amount > 50000:
            await update.message.reply_text("提现金额必须在1-50000之间")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字作为提现金额")
        return
    
    # 检查提现限制
    from config import WITHDRAW_LIMITS
    from app.database import get_withdrawal_history
    from datetime import datetime, timedelta
    
    # 获取用户提现历史
    withdrawal_history = get_withdrawal_history(user_id_api)
    
    # 计算各时间段的提现总额
    today = datetime.now().date()
    this_month = today.month
    this_year = today.year
    
    daily_withdrawal = 0
    monthly_withdrawal = 0
    lifetime_withdrawal = 0
    
    for record in withdrawal_history:
        record_date = record['created_at'].date()
        record_amount = record['amount']
        
        # 累计终身提现
        lifetime_withdrawal += record_amount
        
        # 累计本月提现
        if record_date.month == this_month and record_date.year == this_year:
            monthly_withdrawal += record_amount
        
        # 累计今日提现
        if record_date == today:
            daily_withdrawal += record_amount
    
    # 检查提现限制
    if daily_withdrawal + withdraw_amount > WITHDRAW_LIMITS['daily']:
        await update.message.reply_text(f"今日提现已达上限！今日已提现 {daily_withdrawal} 萝卜，最多可提现 {WITHDRAW_LIMITS['daily']} 萝卜")
        return
    
    if monthly_withdrawal + withdraw_amount > WITHDRAW_LIMITS['monthly']:
        await update.message.reply_text(f"本月提现已达上限！本月已提现 {monthly_withdrawal} 萝卜，最多可提现 {WITHDRAW_LIMITS['monthly']} 萝卜")
        return
    
    if lifetime_withdrawal + withdraw_amount > WITHDRAW_LIMITS['lifetime']:
        await update.message.reply_text(f"终身提现已达上限！已累计提现 {lifetime_withdrawal} 萝卜，最多可提现 {WITHDRAW_LIMITS['lifetime']} 萝卜")
        return
    
    # 检查余额
    balance = get_balance(user_id_api)
    
    # 计算实际需要扣除的游戏币（10游戏币=1萝卜，包含1%手续费）
    base_amount = withdraw_amount * 10
    fee_amount = int(base_amount * 0.01)
    actual_amount = base_amount + fee_amount
    
    if balance < actual_amount:
        await update.message.reply_text(f"余额不足！当前余额：{balance} 游戏币，需要 {actual_amount} 游戏币（基础 {base_amount} 游戏币 + 手续费 {fee_amount} 游戏币）")
        return
    
    # 调用平台API处理提现
    import httpx
    from app.config import API_BASE_URL
    
    headers = {"Authorization": f"Bearer {token}"}
    data = {"user_id": user_id_api, "carrot": withdraw_amount}
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{API_BASE_URL}/carrot/transfer",
                headers=headers,
                json=data,
                timeout=10
            )
        
        if response.status_code == 200:
            # 扣除游戏币
            new_balance = update_balance(user_id_api, -actual_amount)
            
            # 生成提现订单号
            from datetime import datetime, timedelta, timezone
            import uuid
            beijing_tz = timezone(timedelta(hours=8))
            order_no = f"W{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
            
            # 添加提现记录
            from app.database import add_withdrawal_record
            add_withdrawal_record(user_id_api, withdraw_amount)
            
            await update.message.reply_text(f"{user.first_name} 提现申请成功！\n\n订单号：{order_no}\n提现萝卜：{withdraw_amount} 萝卜\n基础游戏币：{base_amount} 游戏币\n手续费：{fee_amount} 游戏币\n扣除游戏币：{actual_amount} 游戏币\n当前余额：{new_balance} 游戏币")
        else:
            await update.message.reply_text(f"❌ 提现失败：API调用失败，状态码：{response.status_code}")
    except Exception as e:
        await update.message.reply_text(f"❌ 提现失败：{str(e)}")
    
    # 清除等待状态
    if 'awaiting_withdraw' in context.user_data:
        del context.user_data['awaiting_withdraw']


async def recharge_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """充值中心"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        # 生成授权链接，添加操作状态参数
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        # 添加操作状态参数，以便绑定后恢复
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}-recharge"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ 请先登录！发送 /start 登录",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "❌ 请先登录！发送 /start 登录",
                reply_markup=reply_markup
            )
        return
    
    loading = None
    if hasattr(update, 'callback_query') and update.callback_query:
        loading = await update.callback_query.edit_message_text("🔄 正在查询充值限额...")
    else:
        loading = await update.message.reply_text("🔄 正在查询充值限额...")
    
    try:
        # 尝试从本地数据库获取用户信息
        local_user_id = context.user_data.get('local_user_id')
        if not local_user_id:
            # 从用户信息中获取本地用户ID
            user_headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    f"{Config.API_BASE_URL}/user",
                    headers=user_headers,
                    timeout=10
                )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                emos_user_id = user_info.get('user_id')
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=emos_user_id,
                    token=token,
                    telegram_id=user_id,
                    username=user_info.get('username'),
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                context.user_data['local_user_id'] = local_user_id
        
        # 获取用户累计充值记录
        from app.database import get_user_total_recharge
        total_recharge = get_user_total_recharge(local_user_id)
        
        # 计算剩余可充值萝卜数
        max_recharge = 100  # 累计充值限额为100萝卜
        remaining_recharge = max_recharge - total_recharge
        
        # 记录日志，方便调试
        print(f"Debug: local_user_id={local_user_id}, total_recharge={total_recharge}, remaining_recharge={remaining_recharge}")
        
        # 提示用户输入充值金额
        message = f"💸 充值中心\n\n"
        message += f"📊 充值限额：\n"
        message += f"• 累计充值：{total_recharge} 萝卜\n"
        message += f"• 充值上限：{max_recharge} 萝卜\n"
        message += f"• 剩余可充：{remaining_recharge} 萝卜\n\n"
        message += "请输入充值金额（1-50000萝卜）："
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await loading.edit_text(message)
        else:
            await loading.edit_text(message)
        
        # 存储当前状态，等待用户输入
        context.user_data['current_operation'] = 'recharge_amount'
        context.user_data['token'] = token
        context.user_data['local_user_id'] = local_user_id
        context.user_data['total_recharge'] = total_recharge
        context.user_data['remaining_recharge'] = remaining_recharge
    except Exception as e:
        # 即使查询失败，也允许用户输入充值金额
        error_message = "💸 请输入充值金额（1-50000萝卜）："
        if hasattr(update, 'callback_query') and update.callback_query:
            await loading.edit_text(error_message)
        else:
            await loading.edit_text(error_message)
        context.user_data['current_operation'] = 'recharge_amount'
        context.user_data['token'] = token


async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """提现专区"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        # 生成授权链接，添加操作状态参数
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        # 添加操作状态参数，以便绑定后恢复
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}-withdraw"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ 请先登录！发送 /start 登录",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "❌ 请先登录！发送 /start 登录",
                reply_markup=reply_markup
            )
        return
    
    loading = None
    if hasattr(update, 'callback_query') and update.callback_query:
        loading = await update.callback_query.edit_message_text("🔄 正在查询游戏余额...")
    else:
        loading = await update.message.reply_text("🔄 正在查询游戏余额...")
    
    try:
        # 尝试从本地数据库获取游戏余额
        from utils.db_helper import get_user_balance
        local_user_id = context.user_data.get('local_user_id')
        if not local_user_id:
            # 从用户信息中获取本地用户ID
            user_headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    f"{Config.API_BASE_URL}/user",
                    headers=user_headers,
                    timeout=10
                )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                emos_user_id = user_info.get('user_id')
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=emos_user_id,
                    token=token,
                    telegram_id=user_id,
                    username=user_info.get('username'),
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                context.user_data['local_user_id'] = local_user_id
        
        # 获取游戏余额
        game_balance = get_user_balance(local_user_id)
        
        if game_balance is not None:
            # 获取用户累计充值和提现记录
            from app.database import get_user_total_recharge, get_user_total_withdraw
            total_recharge = get_user_total_recharge(local_user_id)
            total_withdraw = get_user_total_withdraw(local_user_id)
            
            # 计算最大可提现萝卜数（不超过累计充值的3倍）
            max_withdraw_from_recharge = int(total_recharge * 3)
            remaining_withdraw = max_withdraw_from_recharge - total_withdraw
            
            # 计算基于游戏余额的最大可提现萝卜数（11游戏币=1萝卜，包含1%手续费）
            max_carrot_from_balance = game_balance // 11  # 11游戏币=1萝卜
            
            # 检查累计充值3倍的提现限额
            from utils.db_helper import check_withdraw_limits
            limit_check = check_withdraw_limits(local_user_id, 0)  # 传入0表示检查当前状态
            
            if limit_check['success']:
                # 取游戏余额和累计充值3倍限制中的较小值
                max_carrot = min(
                    max_carrot_from_balance,
                    remaining_withdraw
                )
            else:
                max_carrot = 0
            
            if max_carrot > 0:
                # 计算游戏币
                base_game_coin = max_carrot * 10  # 基础游戏币
                fee_game_coin = max_carrot * 1     # 手续费1游戏币/萝卜
                
                # 计算税费（假设税率为0%，如需添加税率可在此修改）
                tax_rate = 0
                tax_carrot = int(max_carrot * tax_rate)  # 税费萝卜数量
                tax_game_coin = tax_carrot * 10  # 税费游戏币数量
                
                total_game_coin = base_game_coin + fee_game_coin + tax_game_coin  # 总扣除游戏币
                after_tax_carrot = max_carrot - tax_carrot  # 税后萝卜数量
            else:
                base_game_coin = 0
                fee_game_coin = 0
                total_game_coin = 0
                tax_carrot = 0
                after_tax_carrot = 0
            
            # 计算建议提现萝卜数
            suggested_carrots = [10, 50, 100, 500]
            valid_suggestions = [carrot for carrot in suggested_carrots if carrot <= max_carrot]
            
            # 提示用户输入提现萝卜数
            message = f"💎 您的游戏余额：{game_balance} 🪙\n"
            message += f"💰 可兑换萝卜：{after_tax_carrot} 萝卜（已扣税）\n"
            message += f"💸 手续费：{fee_game_coin} 🪙\n"
            message += f"💼 税费：{tax_game_coin} 🪙（{tax_rate*100}%）\n"
            message += f"🪙 总计扣除：{total_game_coin} 🪙\n"
            message += f"🎁 实际到账：{after_tax_carrot} 萝卜\n\n"
            
            # 显示提现限额信息
            message += "📊 提现限额：\n"
            message += f"• 累计充值：{total_recharge} 萝卜\n"
            message += f"• 累计提现：{total_withdraw} 萝卜\n"
            message += f"• 可提现上限：{max_withdraw_from_recharge} 萝卜（累计充值的3倍）\n"
            message += f"• 剩余可提现：{remaining_withdraw} 萝卜\n\n"
            
            message += "请输入您要提现的萝卜数量："
            
            if valid_suggestions:
                message += "\n💡 建议金额："
                message += ", ".join(map(str, valid_suggestions))
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await loading.edit_text(message)
            else:
                await loading.edit_text(message)
            
            # 存储当前状态，等待用户输入
            context.user_data['current_operation'] = 'withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = game_balance
            context.user_data['local_user_id'] = local_user_id
        else:
            # 如果本地数据库查询失败，使用默认值
            message = "💎 请输入提现金额（1-5000萝卜）：\n\n"
            message += "📊 提现规则：\n"
            message += "• 11游戏币 = 1萝卜（包含手续费）\n"
            message += "• 提现限额：累计充值的3倍\n"
            message += "• 实际到账为税后金额\n"
            if hasattr(update, 'callback_query') and update.callback_query:
                await loading.edit_text(message)
            else:
                await loading.edit_text(message)
            context.user_data['current_operation'] = 'withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = 50000  # 默认最大值
            context.user_data['local_user_id'] = local_user_id
    except Exception as e:
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("查询游戏余额失败")
        # 即使查询失败，也允许用户输入提现金额
        message = "💎 请输入提现金额（1-5000萝卜）：\n\n"
        message += "📊 提现规则：\n"
        message += "• 11游戏币 = 1萝卜（包含手续费）\n"
        message += "• 提现限额：累计充值的3倍\n"
        message += "• 实际到账为税后金额\n"
        if hasattr(update, 'callback_query') and update.callback_query:
            await loading.edit_text(message)
        else:
            await loading.edit_text(message)
        context.user_data['current_operation'] = 'withdraw_amount'
        context.user_data['token'] = token
        context.user_data['game_balance'] = 50000  # 默认最大值