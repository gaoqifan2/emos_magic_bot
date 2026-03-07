import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import user_tokens, Config

logger = logging.getLogger(__name__)

async def show_service_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """服务商主菜单"""
    keyboard = [
        [InlineKeyboardButton("👥 用户管理", callback_data="service_user_manage")],
        [InlineKeyboardButton("� 充值中心", callback_data="service_recharge")],
        [InlineKeyboardButton("� 提现专区", callback_data="service_withdraw")],
        [InlineKeyboardButton("🎮 游戏中心", callback_data="service_game_center")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🛠️ 服务商管理\n\n请选择操作：",
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
            
            await loading.edit_text(message)
        else:
            # 可能还没有服务商资格，显示申请成为服务商选项
            await loading.edit_text("🏢 您还没有服务商资格，是否申请成为服务商？")
            
            keyboard = [
                [InlineKeyboardButton("✅ 申请成为服务商", callback_data="service_apply")],
                [InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.reply_text("服务商管理", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"获取服务商信息失败: {e}")
        await loading.edit_text("❌ 获取服务商信息失败，请稍后重试")

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
    
    # 提示用户输入提现金额
    await update.callback_query.edit_message_text("💎 请输入提现金额（1-50000游戏币）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_withdraw_amount'
    context.user_data['token'] = token

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
