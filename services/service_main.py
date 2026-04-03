import logging
import httpx
import uuid
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import user_tokens, Config, WITHDRAW_LIMITS
from utils.message_utils import auto_delete_message
from utils.http_client import http_client
from utils.http_client import http_client

logger = logging.getLogger(__name__)

async def show_service_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """服务商主菜单"""
    user_id = update.effective_user.id
    try:
        user_info = user_tokens.get(user_id)
        token = user_info.get('token') if isinstance(user_info, dict) else user_info
    except UnicodeEncodeError:
        token = None
        logger.error("获取用户token时发生编码错误")
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查用户是否为服务商
    is_service = False
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await http_client.get(
                f"{Config.API_BASE_URL}/pay/base",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            service_info = response.json()
            is_service = service_info.get('status') == 'pass'
        elif response.status_code == 404:
            # API不存在，暂时将用户视为普通用户
            logger.warning("服务商检查API不存在，暂时将用户视为普通用户")
            is_service = False
    except Exception as e:
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("检查服务商状态失败")
    
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
        # 普通用户界面 - 询问是否申请成为服务商
        keyboard = [
            [
                InlineKeyboardButton("✅ 申请成为服务商", callback_data="service_apply"),
                InlineKeyboardButton("💰 游戏币充值", callback_data="service_recharge")
            ],
            [
                InlineKeyboardButton("💎 提现", callback_data="service_withdraw"),
                InlineKeyboardButton("🔍 订单查询", callback_data="service_pay_query")
            ],
            [
                InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.edit_message_text(
            "💳 支付中心\n\n👤 您不是服务商\n\n是否申请成为服务商？\n\n普通用户也可以使用充值和提现功能",
            reply_markup=reply_markup
        )

async def service_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """服务商管理"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取服务商信息...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await http_client.get(
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
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("获取服务商信息失败")
        await loading.edit_text("❌ 获取服务商信息失败，请稍后重试")

async def service_update(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """更新服务商信息"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
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
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
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
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 显示支付核心菜单
    keyboard = [
        [InlineKeyboardButton("➕ 创建订单", callback_data="service_pay_create")],
        [InlineKeyboardButton("🔍 查询订单", callback_data="service_pay_query")],
        [InlineKeyboardButton("🏆 查询中奖列表", callback_data="service_lottery_win")],
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
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
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
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
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
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入订单号
    await update.callback_query.edit_message_text("💳 请输入订单号：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_pay_close_no'
    context.user_data['token'] = token

async def service_lottery_win(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询中奖列表"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入lottery_id
    await update.callback_query.edit_message_text("🏆 请输入抽奖ID：")
    
    # 5秒后自动消失
    import asyncio
    asyncio.create_task(auto_delete_message(update, context, None, 5))
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_lottery_win_id'
    context.user_data['token'] = token

async def service_fund(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """资金操作"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
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
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查用户是否为服务商
    is_service = False
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await http_client.get(
                f"{Config.API_BASE_URL}/pay/base",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            service_info = response.json()
            is_service = service_info.get('status') == 'pass'
        else:
            is_service = False
    except Exception as e:
        logger.error(f"检查服务商状态失败: {e}")
        is_service = False
    
    if not is_service:
        await update.callback_query.edit_message_text("❌ 只有服务商才能使用此功能！")
        # 30秒后自动消失
        import asyncio
        from utils.message_utils import auto_delete_message
        asyncio.create_task(auto_delete_message(update, context, None, 30))
        return
    
    # 提示用户输入对方用户ID
    await update.callback_query.edit_message_text("💸 请输入对方用户ID（10位字符串，以e开头s结尾）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'service_fund_transfer_user_id'
    context.user_data['token'] = token

async def service_user_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户管理"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取用户信息...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await http_client.get(
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
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("获取用户信息失败")
        await loading.edit_text("❌ 获取用户信息失败，请稍后重试")

async def service_recharge(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    
    # 初始化变量，确保except块可以访问
    local_user_id = context.user_data.get('local_user_id')
    emos_user_id = context.user_data.get('emos_user_id')
    
    try:
        # 尝试从本地数据库获取用户信息
        if not local_user_id or not emos_user_id:
            # 从用户信息中获取本地用户ID
            user_headers = {"Authorization": f"Bearer {token}"}
            user_response = await http_client.get(
                    f"{Config.API_BASE_URL}/user",
                    headers=user_headers,
                    timeout=10
                )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                emos_user_id = user_info.get('user_id')
                username = user_info.get('username')
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=emos_user_id,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                context.user_data['local_user_id'] = local_user_id
                context.user_data['emos_user_id'] = emos_user_id
                context.user_data['username'] = username
            else:
                logger.error(f"获取用户信息失败: status={user_response.status_code}, body={user_response.text}")
                if hasattr(update, 'callback_query') and update.callback_query:
                    await loading.edit_text("❌ 获取用户信息失败，请重新登录后重试")
                else:
                    await loading.edit_text("❌ 获取用户信息失败，请重新登录后重试")
                return
        
        # 获取用户累计充值记录
        from app.database import get_user_total_recharge
        total_recharge = get_user_total_recharge(emos_user_id)
        
        # 计算剩余可充值萝卜数
        max_recharge = 100  # 累计充值限额为100萝卜
        remaining_recharge = max_recharge - total_recharge
        
        # 记录日志，方便调试
        print(f"Debug: emos_user_id={emos_user_id}, local_user_id={local_user_id}, total_recharge={total_recharge}, remaining_recharge={remaining_recharge}")
        
        # 提示用户输入充值金额
        message = f"💸 充值中心\n\n"
        message += f"📊 充值限额：\n"
        message += f"• 累计充值：{total_recharge} 萝卜\n"
        message += f"• 充值上限：{max_recharge} 萝卜\n"
        message += f"• 剩余可充：{remaining_recharge} 萝卜\n\n"
        message += "请输入充值金额（1-50000萝卜）："
        
        # 创建按钮：返回上一步
        keyboard = [
            [InlineKeyboardButton("🔙 返回上一步", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await loading.edit_text(message, reply_markup=reply_markup)
        else:
            await loading.edit_text(message, reply_markup=reply_markup)
        
        # 存储当前状态，等待用户输入
        context.user_data['current_operation'] = 'service_recharge_amount'
        context.user_data['token'] = token
        context.user_data['local_user_id'] = local_user_id
        context.user_data['emos_user_id'] = emos_user_id
        context.user_data['total_recharge'] = total_recharge
        context.user_data['remaining_recharge'] = remaining_recharge
    except Exception as e:
        # 即使查询失败，也允许用户输入充值金额
        logger.error(f"充值中心查询失败: {e}")
        error_message = "💸 请输入充值金额（1-50000萝卜）："
        if hasattr(update, 'callback_query') and update.callback_query:
            await loading.edit_text(error_message)
        else:
            await loading.edit_text(error_message)
        context.user_data['current_operation'] = 'service_recharge_amount'
        context.user_data['token'] = token
        # 如果之前有emos_user_id，保留它
        if emos_user_id:
            context.user_data['emos_user_id'] = emos_user_id
        if local_user_id:
            context.user_data['local_user_id'] = local_user_id

async def service_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
        emos_user_id = context.user_data.get('emos_user_id')
        
        if not local_user_id or not emos_user_id:
            # 从用户信息中获取本地用户ID
            user_headers = {"Authorization": f"Bearer {token}"}
            user_response = await http_client.get(
                    f"{Config.API_BASE_URL}/user",
                    headers=user_headers,
                    timeout=10
                )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                emos_user_id = user_info.get('user_id')
                username = user_info.get('username')
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=emos_user_id,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                context.user_data['local_user_id'] = local_user_id
                context.user_data['emos_user_id'] = emos_user_id
                context.user_data['username'] = username
        
        # 获取游戏余额
        game_balance = get_user_balance(local_user_id)
        
        if game_balance is not None:
            # 获取用户累计充值和提现记录（使用emos_user_id）
            from app.database import get_user_total_recharge, get_user_total_withdraw
            total_recharge = get_user_total_recharge(emos_user_id)
            total_withdraw = get_user_total_withdraw(emos_user_id)
            
            # 确保值为整数（处理Decimal类型）
            total_recharge = int(total_recharge) if total_recharge else 0
            total_withdraw = int(total_withdraw) if total_withdraw else 0
            
            # 计算最大可提现萝卜数（不超过累计充值的3倍）
            max_withdraw_from_recharge = total_recharge * 3
            remaining_withdraw = max_withdraw_from_recharge - total_withdraw
            
            # 计算基于游戏余额的最大可提现萝卜数（11游戏币=1萝卜，包含1%手续费）
            max_carrot_from_balance = game_balance // 11  # 11游戏币=1萝卜
            
            # 检查累计充值3倍的提现限额
            from utils.db_helper import check_withdraw_limits
            limit_check = check_withdraw_limits(emos_user_id, 0)  # 传入0表示检查当前状态
            
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
                base_game_coin = int(max_carrot) * 10  # 基础游戏币
                fee_game_coin = int(max_carrot) * 1     # 手续费1游戏币/萝卜
                
                # 计算税费（1%税率）
                tax_rate = 0.01
                tax_carrot = int(int(max_carrot) * tax_rate)  # 税费萝卜数量
                tax_game_coin = tax_carrot * 10  # 税费游戏币数量
                
                total_game_coin = base_game_coin + fee_game_coin + tax_game_coin  # 总扣除游戏币
                after_tax_carrot = int(max_carrot) - tax_carrot  # 税后萝卜数量
            else:
                base_game_coin = 0
                fee_game_coin = 0
                total_game_coin = 0
                tax_carrot = 0
                after_tax_carrot = 0
            
            # 计算建议提现萝卜数
            suggested_carrots = [10, 50, 100, 500]
            valid_suggestions = [carrot for carrot in suggested_carrots if carrot <= int(max_carrot)]
            
            # 提示用户输入提现萝卜数
            message = f"💎 您的游戏余额：{int(game_balance)} 🪙\n"
            message += f"💰 可兑换萝卜：{int(max_carrot)} 萝卜\n"
            message += f"💼 税费：{int(tax_carrot)} 萝卜（1%）\n"
            message += f"🎁 税后可兑换：{int(after_tax_carrot)} 萝卜\n"
            message += f"💸 手续费：{int(fee_game_coin)} 🪙\n"
            message += f"🪙 总计扣除：{int(total_game_coin)} 🪙\n\n"
            
            # 显示提现限额信息
            message += "📊 提现限额：\n"
            message += f"• 累计充值：{int(total_recharge)} 萝卜\n"
            message += f"• 累计提现：{int(total_withdraw)} 萝卜\n"
            message += f"• 可提现上限：{int(max_withdraw_from_recharge)} 萝卜（累计充值的3倍）\n"
            message += f"• 剩余可提现：{int(remaining_withdraw)} 萝卜\n"
            message += f"• 实际可提现：{int(min(after_tax_carrot, remaining_withdraw))} 萝卜\n\n"
            
            message += "请输入您要提现的萝卜数量："
            
            if valid_suggestions:
                message += "\n💡 建议金额："
                message += ", ".join(map(str, valid_suggestions))
            
            # 创建按钮：取消提现
            keyboard = [
                [InlineKeyboardButton("❌ 取消提现", callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await loading.edit_text(message, reply_markup=reply_markup)
            else:
                await loading.edit_text(message, reply_markup=reply_markup)
            
            # 存储当前状态，等待用户输入
            context.user_data['current_operation'] = 'service_withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = game_balance
            context.user_data['local_user_id'] = local_user_id
            context.user_data['total_recharge'] = total_recharge
            context.user_data['total_withdraw'] = total_withdraw
            context.user_data['remaining_withdraw'] = remaining_withdraw
            # 确保emos_user_id也被保存
            if 'emos_user_id' not in context.user_data:
                from app.database import get_db_connection
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT user_id FROM users WHERE id = %s", (local_user_id,))
                            result = cursor.fetchone()
                            if result:
                                emos_user_id = result['user_id'] if isinstance(result, dict) else result[0]
                                context.user_data['emos_user_id'] = emos_user_id
                    finally:
                        conn.close()
        else:
            # 如果本地数据库查询失败，使用默认值
            message = "💎 请输入提现金额（1-5000萝卜）：\n\n"
            message += "📊 提现规则：\n"
            message += "• 11游戏币 = 1萝卜（包含手续费）\n"
            message += "• 提现限额：累计充值的3倍\n"
            message += "• 实际到账为税后金额\n"
            
            # 创建按钮：取消提现
            keyboard = [
                [InlineKeyboardButton("❌ 取消提现", callback_data='back')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await loading.edit_text(message, reply_markup=reply_markup)
            else:
                await loading.edit_text(message, reply_markup=reply_markup)
            context.user_data['current_operation'] = 'service_withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = 50000  # 默认最大值
            context.user_data['local_user_id'] = local_user_id
    except Exception as e:
        # 记录详细的错误信息
        logger.error(f"查询游戏余额失败: {type(e).__name__}: {e}")
        import traceback
        logger.error(f"错误堆栈:\n{traceback.format_exc()}")
        # 即使查询失败，也允许用户输入提现金额
        message = "💎 请输入提现金额（1-5000萝卜）：\n\n"
        message += "📊 提现规则：\n"
        message += "• 11游戏币 = 1萝卜（包含手续费）\n"
        message += "• 提现限额：累计充值的3倍\n"
        message += "• 实际到账为税后金额\n"
        
        # 创建按钮：取消提现
        keyboard = [
            [InlineKeyboardButton("❌ 取消提现", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await loading.edit_text(message, reply_markup=reply_markup)
        else:
            await loading.edit_text(message, reply_markup=reply_markup)
        context.user_data['current_operation'] = 'service_withdraw_amount'
        context.user_data['token'] = token
        context.user_data['game_balance'] = 50000  # 默认最大值
        context.user_data['local_user_id'] = local_user_id

async def service_game_center(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """游戏中心"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取游戏列表...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = await http_client.get(
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
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("获取游戏列表失败")
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
        from datetime import datetime, timedelta, timezone
        beijing_tz = timezone(timedelta(hours=8))
        order_no = f"R{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # 调用平台API
        user_info = user_tokens.get(user_id)
        token = user_info.get('token') if isinstance(user_info, dict) else user_info
        if not token:
            return {"success": False, "error": "用户未登录"}
        
        headers = {"Authorization": f"Bearer {token}"}
        data = {"game_id": game_id, "carrot_amount": carrot_amount}
        
        response = await http_client.post(
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
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("创建充值订单失败")
        return {"success": False, "error": "创建订单失败，请稍后重试"}

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
        from datetime import datetime, timedelta, timezone
        beijing_tz = timezone(timedelta(hours=8))
        order_no = f"W{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
        
        # 调用转账API
        user_info = user_tokens.get(user_id)
        token = user_info.get('token') if isinstance(user_info, dict) else user_info
        if not token:
            return {"success": False, "error": "用户未登录"}
        
        headers = {"Authorization": f"Bearer {token}"}
        # 10游戏币=1萝卜
        carrot_amount = game_coin_amount // 10
        data = {"user_id": user_id, "carrot": carrot_amount}
        
        response = await http_client.put(
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
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("处理提现订单失败")
        return {"success": False, "error": "处理提现订单失败，请稍后重试"}
