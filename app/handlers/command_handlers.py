from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.database import get_balance, update_balance, add_user, add_game_record, ensure_user_exists, get_last_checkin, update_checkin_time
from app.database.jackpot import get_jackpot_pool, add_to_jackpot_pool, reset_jackpot_pool, record_jackpot_win
from app.database.user_score import get_user_score, add_user_score, reset_user_score, get_user_level
from app.utils.helpers import check_balance, process_daily_checkin
from app.config import BOT_USERNAME, user_tokens, save_token_to_db, get_user_info
import logging

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
                    
                    # 优先使用API返回的telegram_user_id，如果没有则使用当前用户的telegram_id
                    telegram_user_id = user_data.get('telegram_user_id')
                    if telegram_user_id is None:
                        telegram_user_id = user_id
                        logger.info(f"API未返回telegram_user_id，使用当前用户的telegram_id: {telegram_user_id}")
                    else:
                        logger.info(f"使用API返回的telegram_user_id: {telegram_user_id}")
                    
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
                    
                    # 处理授权成功逻辑
                    await update.message.reply_text(
                        f"{user.first_name}，授权成功！\n\n"
                        f"欢迎 {username} 使用机器人，您的用户ID是\n`{user_id_api}`\n\n"
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
    user_id = user_info.get('user_id', telegram_id)
    # 优先从user_info中获取username，而不是从user.username中获取
    user_info_username = user_info.get('username', user.username) if isinstance(user_info, dict) else user.username
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'username': user_info_username,
        'first_name': user.first_name,
        'last_name': user.last_name
    }
    add_user(user_id, user_data)
    
    # 从user表获取用户信息
    from app.database import get_user_by_user_id
    user_from_db = get_user_by_user_id(user_id)
    user_name = user_from_db.get('username', user.username) if user_from_db else user.username
    # 确保用户名不为空
    user_name = user_name if user_name else "用户"
    
    # 新用户初始余额为0，无需额外添加
    
    balance = get_balance(user_id)
    
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
            'username': user.username,
            'first_name': user.first_name,
            'last_name': user.last_name
        }
        add_user(user_id_api, user_data)
        
        # 从user表获取用户信息
        from app.database import get_user_by_user_id
        user_from_db = get_user_by_user_id(user_id_api)
        user_name = user_from_db.get('username', user.username) if user_from_db else user.username
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
            'username': user.username,
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
            "  - 三个7️⃣：赢30倍\n"
            "  - 三个🍋：赢6倍\n"
            "  - 三个🍇：赢2倍\n"
            "  - 三个BAR：赢0.5倍\n"
            "  - 两个相同：赢0.3倍\n"
            "  - 7️⃣-BAR-7️⃣：触发Jackpot大奖！\n"
            "  - 全不同：输\n"
            "  - Jackpot：每局15%进入奖池，触发可获得奖池+60倍下注\n\n"
            "🃏 21点：\n" 
            "  - 不超过21点的前提下，让手牌点数比庄家大\n" 
            "  - 2-10：按牌面数值\n" 
            "  - J/Q/K：10点\n" 
            "  - A：1点或11点\n" 
            "  - /hit - 要牌\n" 
            "  - /stand - 停牌\n"
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
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "请输入下注金额，例如：`/blackjack 10`\n\n直接复制：`/blackjack 10`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
        )
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
        keyboard = [
            [InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            "请输入下注金额，例如：`/blackjack 10`\n\n直接复制：`/blackjack 10`",
            reply_markup=reply_markup,
            parse_mode='Markdown'
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
        if update.callback_query:
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
    user_id = user_info.get('user_id', telegram_id)
    
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
    is_sufficient, current_balance = check_balance(user_id, bet_amount)
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
        new_balance = update_balance(user_id, actual_win)
        # 保存游戏记录
        game_result = "win" if is_win else "lose"
        add_game_record(user_id, "guess", bet_amount, game_result, actual_win if is_win else 0)
        # 更新结果消息，添加服务器费用信息
        result += f"\n💸 服务器费用：{service_fee} 🪙"
    else:
        new_balance = update_balance(user_id, win_amount)  # 输了不需要扣除费用
        # 保存游戏记录
        game_result = "win" if is_win else "lose"
        add_game_record(user_id, "guess", bet_amount, game_result, win_amount if is_win else 0)
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
            
            # 检查累计充值限额（默认100萝卜）
            from app.database import get_user_total_recharge
            total_recharge = get_user_total_recharge(user_id_api)
            if total_recharge + carrot_amount > 100:
                remaining = 100 - total_recharge
                await update.message.reply_text(f"充值限额为100萝卜，您已累计充值{total_recharge}萝卜，还可充值{remaining}萝卜")
                return
            
            # 从user_tokens中获取用户信息
            telegram_id = user.id
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
            
            user_id_api = user_info.get('user_id', telegram_id)
            token = user_info.get('token')
            
            # 检查用户是否存在，不存在则添加
            user_data = {
                'id': user_id_api,
                'username': user.username,
                'first_name': user.first_name,
                'last_name': user.last_name
            }
            add_user(user_id_api, user_data)
            
            # 生成唯一订单号
            from datetime import datetime, timedelta, timezone
            import uuid
            beijing_tz = timezone(timedelta(hours=8))
            order_no = f"R{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
            
            # 调用平台API创建充值订单
            import httpx
            
            headers = {
                "Authorization": "Bearer 1047_ow2NHeo3HyzDSxvl",
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
                    
                    # 获取本地用户ID
                    from app.database import ensure_user_exists
                    local_user_id = ensure_user_exists(
                        emos_user_id=user_id_api,
                        token=token,
                        telegram_id=telegram_id,
                        username=user.username,
                        first_name=user.first_name,
                        last_name=user.last_name
                    )
                    
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
    
    # 检查是否在等待提现金额的输入
    elif 'current_operation' in context.user_data and context.user_data['current_operation'] == 'withdraw_amount':
        # 处理提现金额输入
        try:
            withdraw_amount = int(message_text)
            if withdraw_amount < 1 or withdraw_amount > 50000:
                await update.message.reply_text("提现金额必须在1-50000萝卜之间")
                return
            
            # 检查提现限额（不超过累计充值金额的3倍）
            from app.database import get_user_total_recharge, get_user_total_withdraw
            total_recharge = get_user_total_recharge(user_id_api)
            total_withdraw = get_user_total_withdraw(user_id_api)
            max_withdraw = total_recharge * 3
            remaining_withdraw = max_withdraw - total_withdraw
            
            if withdraw_amount > remaining_withdraw:
                await update.message.reply_text(f"提现金额不能超过累计充值金额的3倍，您已提现{total_withdraw}萝卜，还可提现{remaining_withdraw}萝卜")
                return
            
            # 从context中获取用户信息
            user_id_api = context.user_data.get('user_id', user.id)
            balance = context.user_data.get('game_balance', 0)
            token = context.user_data.get('token')
            
            # 计算实际需要扣除的游戏币（11游戏币=1萝卜，包含10%手续费）
            actual_amount = withdraw_amount * 11
            
            if actual_amount > balance:
                await update.message.reply_text(f"余额不足！当前余额：{balance} 游戏币，需要 {actual_amount} 游戏币（包含手续费）")
                return
            
            # 调用平台API处理提现
            import httpx
            from app.config import API_BASE_URL
            
            headers = {"Authorization": f"Bearer {token}"}
            data = {"user_id": user_id_api, "carrot": withdraw_amount}
            
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
                # 传递实际扣除的游戏币数量（包含手续费）
                add_withdrawal_record(user_id_api, actual_amount)
                
                # 更新用户累计提现金额
                from app.database import update_user_total_withdraw
                update_user_total_withdraw(user_id_api, withdraw_amount)
                
                await update.message.reply_text(f"{user.first_name} 提现申请成功！\n\n订单号：{order_no}\n提现萝卜：{withdraw_amount} 萝卜\n扣除游戏币：{actual_amount} 游戏币\n当前余额：{new_balance} 游戏币")
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
            if 'user_id' in context.user_data:
                del context.user_data['user_id']
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
        if update.callback_query:
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
    user_id = user_info.get('user_id', telegram_id)
    
    try:
        bet_amount = int(amount)
        if bet_amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字作为下注金额")
        return
    
    # 检查余额
    is_sufficient, current_balance = check_balance(user_id, bet_amount)
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
    
    # 获取用户贡献分和等级
    user_score = get_user_score(telegram_id)
    level, _, _ = get_user_level(user_score)
    
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
            # 获取用户贡献分和等级（重新获取，因为可能在计算过程中有变化）
            user_score = get_user_score(telegram_id)
            level, multiplier, pool_ratio = get_user_level(user_score)
            
            # 从全局获取Jackpot奖池金额（重新获取，因为可能在计算过程中有变化）
            jackpot_pool = get_jackpot_pool()
            
            # 计算Jackpot奖金
            # 固定额外奖励 + 奖池按比例拿走
            fixed_bonus = bet_amount * multiplier
            pool_bonus = int(jackpot_pool * pool_ratio)
            jackpot_win = fixed_bonus + pool_bonus
            win_amount = jackpot_win
            
            # 构建结果消息
            result += f"🎉🎉🎉 JACKPOT大奖！🎉🎉🎉\n"
            result += f"💰 奖池金额：{jackpot_pool} 🪙\n"
            result += f"🏆 您的等级：{level}\n"
            result += f"🎁 固定奖励：{fixed_bonus} 🪙（{multiplier}倍下注）\n"
            result += f"🏦 奖池奖励：{pool_bonus} 🪙（{int(pool_ratio*100)}%奖池）\n"
            
            # 记录Jackpot中奖信息
            record_jackpot_win(telegram_id, jackpot_win)
            
            # 重置用户贡献分
            reset_user_score(telegram_id)
            
            # 重置Jackpot奖池（如果被钻石用户100%拿走，重置为0）
            if pool_ratio == 1.0:
                # 钻石用户拿走全部奖池，重置为0
                reset_jackpot_pool()
            else:
                # 其他等级用户只拿走部分，更新奖池
                from app.database.jackpot import set_jackpot_pool
                new_pool_amount = jackpot_pool - pool_bonus
                set_jackpot_pool(new_pool_amount)
        else:
            # 不触发Jackpot，视为普通组合
            is_jackpot = False
            is_win = False
            win_amount = -bet_amount
            # 不显示Jackpot消息
            result += "全不同！\n"
    # 大奖：三个相同图案
    elif left == middle == right:
        is_win = True
        # 进一步调整赔率：降低三个相同的倍率
        if left == 3:  # 7️⃣7️⃣7️⃣
            win_amount = bet_amount * 6  # 7倍
            result += "特等奖！\n"
        elif left == 2:  # 🍋🍋🍋
            win_amount = bet_amount * 1.5  # 2.5倍
            result += "大奖！\n"
        elif left == 1:  # 🍇🍇🍇
            win_amount = bet_amount * 0.5  # 1.5倍
            result += "中奖！\n"
        else:  # BAR BAR BAR
            win_amount = int(bet_amount * 0.1)  # 1.1倍
            result += "小奖！\n"
    # 小奖：两个相同图案
    elif left == middle or middle == right or left == right:
        is_win = True
        win_amount = int(bet_amount * 0.3)  # 0.3倍（提高两个相同的倍率）
        result += "两个相同！\n"
    # 未中奖：全不同图案
    else:
        result += "全不同！\n"
    
    # 添加等级和奖池信息
    result += f"🏆 当前等级：{level}\n"
    result += f"💰 累计奖池：{jackpot_pool} 🪙\n"
    
    # 更新Jackpot奖池（每局抽水10%进入奖池，5%服务器费用）
    if not is_jackpot and win_amount > 0:
        jackpot_contribution = int(win_amount * 0.10)  # 10%抽水入池（基于赢取金额）
        add_to_jackpot_pool(jackpot_contribution)
        # 在结果消息中显示奖池抽水信息
        result += f"🏦 奖池抽水：{jackpot_contribution} 🪙（10%）\n"

    # 更新余额
    if win_amount > 0:
        # 计算服务器费用（5%），最少1游戏币
        service_fee = max(1, int(win_amount * 0.05))  # 5%服务器费用
        # 扣除服务器费用
        actual_win = win_amount - service_fee
        new_balance = update_balance(user_id, int(actual_win))
        # 更新结果消息，添加费用信息
        result += f"💸 服务器费用：{service_fee} 🪙\n"
    else:
        new_balance = update_balance(user_id, int(win_amount))  # 输了不需要扣除费用

    # 保存游戏记录
    game_result = "win" if is_win else "lose"
    add_game_record(user_id, "slot", bet_amount, game_result, win_amount if is_win else 0)

    # 发送结果
    if is_win:
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("🎰 再来一局", callback_data='slot_again'),
             InlineKeyboardButton("🔙 返回", callback_data='games')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if is_jackpot:
            await update.message.reply_text(f"🎉 {user.first_name} 🎰\n{result}\n\n🎊🎊🎊 恭喜中得JACKPOT！🎊🎊🎊\n✨ 获得 {actual_win} 🪙（已扣除服务器费用）\n💰 当前余额：{new_balance} 🪙", reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await update.message.reply_text(f"🎉 {user.first_name} 🎰\n{result}\n\n✨ 恭喜你赢了！获得 {actual_win} 🪙（已扣除服务器费用）\n💰 当前余额：{new_balance} 🪙", reply_markup=reply_markup, parse_mode="Markdown")
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
        if update.callback_query:
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
        # 进入二级会话，等待用户输入
        context.user_data['awaiting_blackjack'] = True
        await update.message.reply_text("请输入下注金额，例如：`10`\n\n直接复制：`10`", parse_mode='Markdown')


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
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再玩游戏：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    user_id = user_info.get('user_id', telegram_id)
    
    try:
        bet_amount = int(amount)
        if bet_amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字作为下注金额")
        return
    
    # 检查余额
    is_sufficient, current_balance = check_balance(user_id, bet_amount)
    if not is_sufficient:
        await update.message.reply_text(f"余额不足！当前余额：{current_balance}")
        return
    
    # 初始化游戏状态
    import random
    
    # 发牌函数
    def deal_card():
        # 牌面值：2-10为对应数值，J/Q/K为10，A为11
        cards = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
        return random.choice(cards)
    
    # 计算手牌点数
    def calculate_hand(hand):
        total = sum(hand)
        # 如果有A且总点数超过21，将A视为1
        while total > 21 and 11 in hand:
            hand.remove(11)
            hand.append(1)
            total = sum(hand)
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
    
    # 构建游戏状态消息
    game_state = f"🎲 21点游戏开始！\n\n"
    game_state += f"您的手牌：{player_hand} (总点数: {player_total})\n"
    game_state += f"庄家手牌：[{dealer_hand[0]}, ?] (可见点数: {dealer_hand[0]})\n\n"
    
    # 检查是否黑杰克
    if player_total == 21:
        # 黑杰克，直接结算
        win_amount = bet_amount * 1.5  # 黑杰克通常是1.5倍赔率
        new_balance = update_balance(user_id, int(win_amount))
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, "win", int(win_amount))
        game_state += "🎉 恭喜！您拿到了黑杰克！\n\n"
        game_state += f"当前余额：{new_balance}"
        await update.message.reply_text(f"{user.first_name} {game_state}", parse_mode='Markdown')
        # 游戏结束，清除状态
        del context.user_data['blackjack']
    else:
        # 游戏继续，提示用户操作
        # 创建按钮
        keyboard = [
            [InlineKeyboardButton("要牌 (/hit)", callback_data='hit'),
             InlineKeyboardButton("停牌 (/stand)", callback_data='stand')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        game_state += "请选择操作："
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
    user_id = user_info.get('user_id', telegram_id)
    
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
    
    # 发牌函数
    import random
    def deal_card():
        cards = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
        return random.choice(cards)
    
    # 计算手牌点数
    def calculate_hand(hand):
        total = sum(hand)
        # 如果有A且总点数超过21，将A视为1
        while total > 21 and 11 in hand:
            hand.remove(11)
            hand.append(1)
            total = sum(hand)
        return total
    
    # 玩家要牌
    player_hand.append(deal_card())
    player_total = calculate_hand(player_hand)
    
    # 更新游戏状态
    game_state['player_hand'] = player_hand
    game_state['player_total'] = player_total
    
    # 构建游戏状态消息
    response = f"🎲 21点游戏\n\n"
    response += f"您的手牌：{player_hand} (总点数: {player_total})\n"
    response += f"庄家手牌：[{dealer_hand[0]}, ?] (可见点数: {dealer_hand[0]})\n\n"
    
    # 检查是否爆牌
    if player_total > 21:
        # 玩家爆牌，游戏结束
        win_amount = -bet_amount
        new_balance = update_balance(user_id, win_amount)
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, "lose", 0)
        response += "😢 您爆牌了！\n\n"
        response += f"😢 很遗憾，你输了 {bet_amount} 🪙\n"
        response += f"💰 当前余额：{new_balance} 🪙\n\n"
        response += "🎯 再接再厉！"
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(f"{user.first_name} {response}", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"{user.first_name} {response}", parse_mode='Markdown')
        # 游戏结束，清除状态
        del context.user_data['blackjack']
    else:
        # 游戏继续，提示用户操作
        response += "请选择操作：\n"
        response += "/hit - 要牌\n"
        response += "/stand - 停牌"
        if hasattr(update, 'callback_query') and update.callback_query:
            # 创建按钮
            keyboard = [
                [InlineKeyboardButton("要牌 (/hit)", callback_data='hit'),
                 InlineKeyboardButton("停牌 (/stand)", callback_data='stand')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.edit_message_text(f"{user.first_name} {response}", reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await update.message.reply_text(f"{user.first_name} {response}", parse_mode='Markdown')


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
    user_id = user_info.get('user_id', telegram_id)
    
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
        total = sum(hand)
        # 如果有A且总点数超过21，将A视为1
        while total > 21 and 11 in hand:
            hand.remove(11)
            hand.append(1)
            total = sum(hand)
        return total
    
    # 发牌函数
    import random
    def deal_card():
        cards = [2, 3, 4, 5, 6, 7, 8, 9, 10, 10, 10, 10, 11]
        return random.choice(cards)
    
    # 庄家回合：如果点数小于17则继续要牌
    while calculate_hand(dealer_hand) < 17:
        dealer_hand.append(deal_card())
    
    dealer_total = calculate_hand(dealer_hand)
    
    # 构建游戏状态消息
    response = f"🎲 21点游戏\n\n"
    response += f"您的手牌：{player_hand} (总点数: {player_total})\n"
    response += f"庄家手牌：{dealer_hand} (总点数: {dealer_total})\n\n"
    
    # 判断胜负
    if dealer_total > 21:
        # 庄家爆牌
        win_amount = bet_amount
        if win_amount > 0:
            # 计算1%的服务器费用，最少1游戏币
            service_fee = max(1, int(win_amount * 0.01))
            # 扣除服务器费用
            actual_win = win_amount - service_fee
            new_balance = update_balance(user_id, actual_win)
            # 保存游戏记录
            add_game_record(user_id, "blackjack", bet_amount, "win", actual_win)
            response += "🎉 庄家爆牌了！您赢了！\n\n"
            response += f"✨ 恭喜你赢了！获得 {win_amount} 🪙\n"
            response += f"💸 服务器费用：{service_fee} 🪙\n"
            response += f"💰 当前余额：{new_balance} 🪙"
        else:
            new_balance = update_balance(user_id, win_amount)
            # 保存游戏记录
            add_game_record(user_id, "blackjack", bet_amount, "win", win_amount)
            response += "🎉 庄家爆牌了！您赢了！\n\n"
            response += f"✨ 恭喜你赢了！获得 {win_amount} 🪙\n"
            response += f"💰 当前余额：{new_balance} 🪙"
    elif player_total > dealer_total:
        # 玩家点数大
        win_amount = bet_amount
        if win_amount > 0:
            # 计算1%的服务器费用，最少1游戏币
            service_fee = max(1, int(win_amount * 0.01))
            # 扣除服务器费用
            actual_win = win_amount - service_fee
            new_balance = update_balance(user_id, actual_win)
            # 保存游戏记录
            add_game_record(user_id, "blackjack", bet_amount, "win", actual_win)
            response += "🎉 您的点数比庄家大！您赢了！\n\n"
            response += f"✨ 恭喜你赢了！获得 {win_amount} 🪙\n"
            response += f"💸 服务器费用：{service_fee} 🪙\n"
            response += f"💰 当前余额：{new_balance} 🪙"
        else:
            new_balance = update_balance(user_id, win_amount)
            # 保存游戏记录
            add_game_record(user_id, "blackjack", bet_amount, "win", win_amount)
            response += "🎉 您的点数比庄家大！您赢了！\n\n"
            response += f"✨ 恭喜你赢了！获得 {win_amount} 🪙\n"
            response += f"💰 当前余额：{new_balance} 🪙"
    elif player_total < dealer_total:
        # 庄家点数大
        win_amount = -bet_amount
        new_balance = update_balance(user_id, win_amount)
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, "lose", 0)
        response += "😢 庄家的点数比您大！您输了！\n\n"
        response += f"😢 很遗憾，你输了 {bet_amount} 🪙\n"
        response += f"💰 当前余额：{new_balance} 🪙"
    else:
        # 和局
        win_amount = 0  # 和局，返还下注
        new_balance = update_balance(user_id, win_amount)
        # 保存游戏记录
        add_game_record(user_id, "blackjack", bet_amount, "tie", 0)
        response += "🤝 和局！\n\n"
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
    """处理充值功能"""
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
                "您还未绑定账号，请先绑定后再充值：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再充值：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 提示用户输入充值金额（萝卜数量）
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text("💸 请输入充值萝卜数量（1-50000萝卜）：")
    else:
        await update.message.reply_text("💸 请输入充值萝卜数量（1-50000萝卜）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'recharge_amount'


async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理提现功能"""
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
                "您还未绑定账号，请先绑定后再提现：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        else:
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
    
    # 获取游戏余额
    balance = get_balance(user_id)
    
    # 计算最大可提现金额（假设10游戏币=1单位）
    max_withdraw = balance // 10
    if max_withdraw > 50000:
        max_withdraw = 50000
    
    # 计算手续费
    if max_withdraw > 0:
        base_amount = max_withdraw * 10
        fee = int(base_amount * 0.1)
        total_deduct = base_amount + fee
    else:
        base_amount = 0
        fee = 0
        total_deduct = 0
    
    # 提示用户输入提现金额
    message = f"💎 您的游戏余额：{balance} 🪙\n"
    message += f"💰 可提现金额：{max_withdraw} 单位\n"
    message += f"💸 手续费：{fee} 🪙\n"
    message += f"🪙 总计扣除：{total_deduct} 🪙\n"
    message += f"🎁 实际到账：{max_withdraw} 单位\n\n"
    message += "请输入提现金额（1-50000单位）："
    
    # 建议金额
    suggested_amounts = [10, 50, 100, 500]
    valid_suggestions = [amount for amount in suggested_amounts if amount <= max_withdraw]
    
    if valid_suggestions:
        message += "\n💡 建议金额："
        message += ", ".join(map(str, valid_suggestions))
    
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(message)
    else:
        await update.message.reply_text(message)
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'withdraw_amount'
    context.user_data['game_balance'] = balance
    context.user_data['user_id'] = user_id
    context.user_data['token'] = user_info.get('token')