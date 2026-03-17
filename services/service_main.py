import logging
import httpx
import uuid
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import user_tokens, Config

logger = logging.getLogger(__name__)

async def show_service_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """服务商主菜单"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查用户是否为服务商
    is_service = False
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{Config.API_BASE_URL}/pay/base",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            service_info = response.json()
            status = service_info.get('status')
            if status == 'pass':
                is_service = True
        elif response.status_code == 404:
            # API不存在，暂时将用户视为普通用户
            logger.warning("服务商检查API不存在，暂时将用户视为普通用户")
            is_service = False
    except Exception as e:
        logger.error(f"检查服务商状态失败: {e}")
    
    if is_service:
        # 服务商界面
        keyboard = [
            [
                InlineKeyboardButton("🏢 服务商信息", callback_data="service_manage"),
                InlineKeyboardButton("💰 游戏币充值", callback_data="service_recharge")
            ],
            [
                InlineKeyboardButton("💸 转账给用户", callback_data="service_fund_transfer"),
                InlineKeyboardButton("💎 提现", callback_data="service_withdraw")
            ],
            [
                InlineKeyboardButton("🔍 订单查询", callback_data="service_pay_query"),
                InlineKeyboardButton("❌ 关闭订单", callback_data="service_pay_close")
            ],
            [
                InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "💳 支付中心\n\n✅ 您是服务商\n\n请选择操作：",
            reply_markup=reply_markup
        )
    else:
        # 普通用户界面 - 所有用户都可以充值和提现，不需要成为服务商
        keyboard = [
            [
                InlineKeyboardButton("💰 游戏币充值", callback_data="service_recharge"),
                InlineKeyboardButton("💎 提现", callback_data="service_withdraw")
            ],
            [
                InlineKeyboardButton("🔍 订单查询", callback_data="service_pay_query"),
                InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "💳 支付中心\n\n👤 您是普通用户\n\n请选择操作：",
            reply_markup=reply_markup
        )

async def service_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """服务商管理"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取服务商信息...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{Config.API_BASE_URL}/pay/base",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            service_info = response.json()
            status = service_info.get('status', 'review')
            status_text = {
                'review': '审核中',
                'pass': '已通过'
            }
            
            message = f"🏢 服务商信息\n\n"
            message += f"状态：{status_text.get(status, status)}\n"
            if 'name' in service_info:
                message += f"服务商名称：{service_info.get('name')}\n"
            if 'description' in service_info:
                message += f"服务商描述：{service_info.get('description')}\n"
            if 'total_revenue' in service_info:
                message += f"总收入：{service_info.get('total_revenue')} 萝卜\n"
            if 'total_expenditure' in service_info:
                message += f"总支出：{service_info.get('total_expenditure')} 萝卜\n"
            if 'notify_url' in service_info:
                message += f"回调地址：{service_info.get('notify_url', '未设置')}\n"
            
            # 显示操作菜单
            keyboard = []
            if status == 'pass':
                # 审核通过的服务商可以更新信息
                keyboard.append([InlineKeyboardButton("✏️ 更新服务商信息", callback_data="service_update")])
            keyboard.append([InlineKeyboardButton("🔙 返回支付中心", callback_data="menu_service")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await loading.edit_text(message, reply_markup=reply_markup)
        else:
            # 可能还没有服务商资格，显示申请成为服务商选项
            await loading.edit_text("🏢 您还没有服务商资格，是否申请成为服务商？")
            
            keyboard = [
                [InlineKeyboardButton("✅ 申请成为服务商", callback_data="service_apply")],
                [InlineKeyboardButton("🔙 返回支付中心", callback_data="menu_service")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.reply_text("服务商管理", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"获取服务商信息失败: {e}")
        await loading.edit_text("❌ 获取服务商信息失败，请稍后重试")

async def service_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """更新服务商信息"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入服务商名称
    await update.callback_query.edit_message_text("🏢 请输入服务商名称（10字以内）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_update_name'
    context.user_data['token'] = token

async def service_apply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """申请成为服务商"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入服务商名称
    await update.callback_query.edit_message_text("🏢 请输入服务商名称（10字以内）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_apply_name'
    context.user_data['token'] = token

async def service_pay(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """支付核心"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 显示支付核心菜单
    keyboard = [
        [InlineKeyboardButton("➕ 创建订单", callback_data="service_pay_create")],
        [InlineKeyboardButton("🔍 查询订单", callback_data="service_pay_query")],
        [InlineKeyboardButton("❌ 关闭订单", callback_data="service_pay_close")],
        [InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "💳 支付核心\n\n请选择操作：",
        reply_markup=reply_markup
    )

async def service_pay_create(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建订单"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入订单金额
    await update.callback_query.edit_message_text("💳 请输入订单金额（1-50000萝卜）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_pay_create_amount'
    context.user_data['token'] = token

async def service_pay_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询订单"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入订单号
    await update.callback_query.edit_message_text("💳 请输入订单号：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_pay_query_no'
    context.user_data['token'] = token

async def service_pay_close(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """关闭订单"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入订单号
    await update.callback_query.edit_message_text("💳 请输入订单号：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_pay_close_no'
    context.user_data['token'] = token

async def service_fund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """资金操作"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 显示资金操作菜单
    keyboard = [
        [InlineKeyboardButton("💸 转账给用户", callback_data="service_fund_transfer")],
        [InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "💰 资金操作\n\n请选择操作：",
        reply_markup=reply_markup
    )

async def service_fund_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """转账给用户"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入对方用户ID
    await update.callback_query.edit_message_text("💸 请输入对方用户ID（10位字符串，以e开头s结尾）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_fund_transfer_user_id'
    context.user_data['token'] = token

async def service_user_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户管理"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取用户信息...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{Config.API_BASE_URL}/user",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            user_info = response.json()
            message = "👥 个人信息\n\n"
            message += f"用户ID：{user_info.get('user_id', '未知')}\n"
            message += f"用户名：{user_info.get('username', '未知')}\n"
            message += f"笔名：{user_info.get('pseudonym', '未设置')}\n"
            message += f"萝卜余额：{user_info.get('carrot', 0)}\n"
            message += f"注册时间：{user_info.get('created_at', '未知')}\n"
            
            # 显示操作菜单
            keyboard = [
                [InlineKeyboardButton("💸 充值", callback_data="service_recharge")],
                [InlineKeyboardButton("💎 提现", callback_data="service_withdraw")],
                [InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await loading.edit_text(message, reply_markup=reply_markup)
        else:
            await loading.edit_text("❌ 获取用户信息失败")
    except Exception as e:
        logger.error(f"获取用户信息失败: {e}")
        await loading.edit_text("❌ 获取用户信息失败，请稍后重试")

async def service_recharge(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """充值中心"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入充值金额
    await update.callback_query.edit_message_text("💸 请输入充值金额（1-50000萝卜）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_recharge_amount'
    context.user_data['token'] = token

async def service_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """提现专区"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在查询游戏余额...")
    
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
            # 提示用户输入提现金额
            await loading.edit_text(f"💎 您的游戏余额：{game_balance} 游戏币\n\n请输入提现金额（10-50000游戏币，必须是10的倍数）：")
            
            # 存储当前状态，等待用户输入
            context.user_data['current_operation'] = 'service_withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = game_balance
            context.user_data['local_user_id'] = local_user_id
        else:
            # 如果本地数据库查询失败，使用默认值
            await loading.edit_text("💎 请输入提现金额（10-50000游戏币，必须是10的倍数）：")
            context.user_data['current_operation'] = 'service_withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = 50000  # 默认最大值
            context.user_data['local_user_id'] = local_user_id
    except Exception as e:
        logger.error(f"查询游戏余额失败: {e}")
        # 即使查询失败，也允许用户输入提现金额
        await loading.edit_text("💎 请输入提现金额（10-50000游戏币，必须是10的倍数）：")
        context.user_data['current_operation'] = 'service_withdraw_amount'
        context.user_data['token'] = token
        context.user_data['game_balance'] = 50000  # 默认最大值

async def service_game_center(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """游戏中心"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取游戏列表...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{Config.API_BASE_URL}/game/list",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            games = response.json()
            keyboard = []
            for game in games:
                game_id = game.get('game_id')
                game_name = game.get('name')
                keyboard.append([InlineKeyboardButton(f"🎮 {game_name}", callback_data=f"service_game_select_{game_id}")])
            keyboard.append([InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await loading.edit_text("🎮 游戏中心\n\n请选择游戏：", reply_markup=reply_markup)
        else:
            await loading.edit_text("❌ 获取游戏列表失败")
    except Exception as e:
        logger.error(f"获取游戏列表失败: {e}")
        await loading.edit_text("❌ 获取游戏列表失败，请稍后重试")

async def create_recharge_order(user_id, carrot_amount, game_id="1"):
    """创建充值订单
    
    Args:
        user_id: 用户ID
        carrot_amount: 萝卜数量
        game_id: 游戏ID
    
    Returns:
        dict: 订单信息
    """
    try:
        # 生成唯一订单号
        order_no = f"R{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # 调用平台API
        token = user_tokens.get(user_id)
        if not token:
            return {"success": False, "error": "用户未登录"}
        
        headers = {"Authorization": f"Bearer {token}"}
        data = {"game_id": game_id, "carrot_amount": carrot_amount}
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{Config.API_BASE_URL}/game/recharge",
                headers=headers,
                json=data,
                timeout=10
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "order_no": order_no,
                "platform_order_no": result.get('order_no'),
                "game_coin": result.get('game_coin'),
                "payment_url": result.get('payment_url'),
                "qr_code": result.get('qr_code')
            }
        else:
            return {"success": False, "error": f"API调用失败: {response.status_code}"}
    except Exception as e:
        logger.error(f"创建充值订单失败: {e}")
        return {"success": False, "error": str(e)}

async def process_withdraw_order(user_id, game_coin_amount):
    """处理提现订单
    
    Args:
        user_id: 用户ID
        game_coin_amount: 游戏币数量
    
    Returns:
        dict: 提现结果
    """
    try:
        # 生成提现订单号
        order_no = f"W{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # 调用转账API
        token = user_tokens.get(user_id)
        if not token:
            return {"success": False, "error": "用户未登录"}
        
        headers = {"Authorization": f"Bearer {token}"}
        # 假设1游戏币=1萝卜
        carrot_amount = game_coin_amount
        data = {"user_id": user_id, "carrot": carrot_amount}
        
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{Config.API_BASE_URL}/carrot/transfer",
                headers=headers,
                json=data,
                timeout=10
            )
        
        if response.status_code == 200:
            result = response.json()
            return {
                "success": True,
                "order_no": order_no,
                "carrot_amount": carrot_amount,
                "remaining_carrot": result.get('carrot')
            }
        else:
            return {"success": False, "error": f"转账失败: {response.status_code}"}
    except Exception as e:
        logger.error(f"处理提现订单失败: {e}")
        return {"success": False, "error": str(e)}
