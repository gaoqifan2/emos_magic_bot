import logging
import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from config import user_tokens, Config

logger = logging.getLogger(__name__)

async def show_user_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """个人信息二级菜单"""
    keyboard = [
        [
            InlineKeyboardButton("📋 查看个人信息", callback_data="menu_user_info"),
            InlineKeyboardButton("📝 每日签到", callback_data="menu_user_sign")
        ],
        [
            InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "👤 个人信息\n\n请选择操作：",
        reply_markup=reply_markup
    )

async def get_user_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """获取用户信息"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取个人信息...")
    
    try:
        logger.info(f"用户 {user_id} 正在获取个人信息")
        api_url = f"{Config.API_BASE_URL}/user"
        logger.info(f"API地址: {api_url}")
        
        headers = {"Authorization": f"Bearer {token}"}
        logger.info(f"请求头: {headers}")
        
        # 使用同步的 requests 库
        import requests
        logger.info("开始发送请求...")
        response = requests.get(api_url, headers=headers, timeout=10)
        logger.info(f"请求完成，状态码: {response.status_code}")
        
        logger.info(f"响应内容: {response.text}")
        
        if response.status_code == 200:
            user_data = response.json()
            logger.info(f"用户数据: {user_data}")
            
            # 格式化上传总量
            size_upload = user_data.get('size_upload', 0)
            if size_upload >= 1099511627776:
                size_display = f"{size_upload / 1099511627776:.2f} TB"
            elif size_upload >= 1073741824:
                size_display = f"{size_upload / 1073741824:.2f} GB"
            elif size_upload >= 1048576:
                size_display = f"{size_upload / 1048576:.2f} MB"
            else:
                size_display = f"{size_upload / 1024:.2f} KB"
            
            # 构建用户信息消息（宽体显示）
            user_id = user_data.get('user_id', '未知')
            
            # 获取各个字段
            username = str(user_data.get('username', '未知'))
            token = user_tokens.get(update.effective_user.id, '未知')
            emya_password = str(user_data.get('emya_password', '未知'))
            emya_url = str(user_data.get('emya_url', '未知'))
            pseudonym = str(user_data.get('pseudonym', '未设置'))
            
            message = (
                f"📋 个人信息\n\n"
                f"👤 用户名：`{username}`\n\n"
                f"🔑 Token：\n```\n{token}\n```\n\n"
                f"🆔 ID：```\n{user_id}\n```\n\n"
                f"🎭 笔名：{pseudonym}\n\n"
                f"💰 萝卜总数：{user_data.get('carrot', 0)}\n\n"
                f"📤 上传总量：{size_display}\n\n"
                f"🎁 邀请剩余：{user_data.get('invite_remaining', 0)}\n\n"
                f"🎬 片单剩余：{user_data.get('watch_slot_remaining', 0)}\n\n"
                f"🔐 Emby密码：`{emya_password}`\n\n"
                f"🚪 Emby地址：`{emya_url}`\n"
            )
            
            # 显示签到信息
            sign_info = user_data.get('sign')
            if sign_info:
                message += f"\n📅 签到信息\n"
                message += f"• 连续签到：{sign_info.get('continuous_days', 0)} 天\n"
                message += f"• 今日获得：{sign_info.get('earn_point', 0)} 萝卜\n"
                message += f"• 签到时间：{sign_info.get('sign_at', '未知')}\n"
            else:
                message += "\n📅 签到信息：今日未签到\n"
            
            message_obj = await loading.edit_text(message, parse_mode="Markdown")
            # 30秒后自动消失
            import asyncio
            from utils.message_utils import auto_delete_message
            # 使用message_obj作为消息对象
            asyncio.create_task(auto_delete_message(update, context, message_obj, 30))
        else:
            await loading.edit_text(f"❌ 获取失败，状态码：{response.status_code}")
    except Exception as e:
        logger.error(f"获取个人信息失败: {e}")
        await loading.edit_text("❌ 获取失败，请稍后重试")
    
    # 显示操作菜单
    keyboard = [
        [InlineKeyboardButton("📨 邀请好友", callback_data="menu_user_invite")],
        [InlineKeyboardButton("✏️ 更改笔名", callback_data="menu_user_pseudonym")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("个人信息查询完成", reply_markup=reply_markup)

async def user_sign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户签到"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在签到...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{Config.API_BASE_URL}/user/sign?content=1",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            result = response.json()
            await loading.edit_text(f"✅ 签到成功！获得 {result.get('earn_point', 0)} 萝卜")
        else:
            await loading.edit_text(f"❌ 签到失败，状态码：{response.status_code}")
    except Exception as e:
        logger.error(f"签到失败: {e}")
        await loading.edit_text("❌ 签到失败，请稍后重试")
    
    # 显示返回菜单
    keyboard = [
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("签到完成", reply_markup=reply_markup)

async def user_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """邀请好友"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    loading = await update.callback_query.edit_message_text("🔄 正在获取邀请信息...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{Config.API_BASE_URL}/invite/info",
                headers=headers,
                timeout=10
            )
        
        if response.status_code == 200:
            result = response.json()
            invite_remaining = result.get('invite_remaining', 0)
            
            if invite_remaining > 0:
                # 有邀请资格，提示用户输入被邀请人的ID
                await loading.edit_text(f"📨 邀请信息\n\n剩余邀请次数：{invite_remaining}\n\n请输入被邀请人的用户ID（10位字符串，以e开头s结尾）：")
                # 存储当前状态，等待用户输入
                context.user_data['current_operation'] = 'invite_user'
                context.user_data['token'] = token
                return 101  # 自定义状态码，用于处理邀请输入
            else:
                # 没有邀请资格
                message = f"📨 邀请信息\n\n"
                message += f"剩余邀请次数：{invite_remaining}\n"
                message += "❌ 您当前没有邀请资格，请稍后再试！\n"
                if 'invite_at' in result:
                    message += f"邀请时间：{result.get('invite_at')}\n"
                if 'invite_count' in result:
                    message += f"邀请人数：{result.get('invite_count')}\n"
                if 'parent' in result and result['parent']:
                    message += f"邀请人：{result['parent'].get('pseudonym', '未知')}\n"
                
                await loading.edit_text(message)
                
                # 显示操作菜单
                keyboard = [
                    [InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")],
                    [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.callback_query.message.reply_text("邀请信息查询完成", reply_markup=reply_markup)
        else:
            await loading.edit_text(f"❌ 获取邀请信息失败，状态码：{response.status_code}")
            
            # 显示操作菜单
            keyboard = [
                [InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")],
                [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.reply_text("邀请信息查询完成", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"获取邀请信息失败: {e}")
        await loading.edit_text("❌ 获取邀请信息失败，请稍后重试")
        
        # 显示操作菜单
        keyboard = [
            [InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("邀请信息查询完成", reply_markup=reply_markup)

async def user_pseudonym(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """更改笔名"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入新笔名
    await update.callback_query.edit_message_text("✏️ 请输入新的笔名：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'change_pseudonym'
    context.user_data['token'] = token
    
    # 返回一个状态码，用于后续处理用户输入
    return 100  # 自定义状态码，用于处理笔名输入