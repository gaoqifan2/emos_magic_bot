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
    user_info = user_tokens.get(user_id)
    
    if not user_info:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查user_info是字典还是字符串
    if isinstance(user_info, dict):
        token = user_info.get('token')
    else:
        token = user_info
    
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
            user_token_info = user_tokens.get(update.effective_user.id, '未知')
            # 检查user_token_info是字典还是字符串
            if isinstance(user_token_info, dict):
                token = user_token_info.get('token', '未知')
            else:
                token = user_token_info
            emya_password = str(user_data.get('emya_password', '未知'))
            emya_url = str(user_data.get('emya_url', '未知'))
            pseudonym = str(user_data.get('pseudonym', '未设置'))
            carrot = user_data.get('carrot', 0)
            invite_remaining = user_data.get('invite_remaining', 0)
            watch_slot_remaining = user_data.get('watch_slot_remaining', 0)
            
            # 根据萝卜数量计算修仙境界
            def calculate_cultivation_level(carrot):
                if carrot < 10:
                    return "凡人期"
                elif 10 <= carrot <= 19:
                    return "练气期一层"
                elif 20 <= carrot <= 29:
                    return "练气期二层"
                elif 30 <= carrot <= 39:
                    return "练气期三层"
                elif 40 <= carrot <= 49:
                    return "练气期四层"
                elif 50 <= carrot <= 59:
                    return "练气期五层"
                elif 60 <= carrot <= 69:
                    return "练气期六层"
                elif 70 <= carrot <= 79:
                    return "练气期七层"
                elif 80 <= carrot <= 89:
                    return "练气期八层"
                elif 90 <= carrot <= 99:
                    return "练气期九层"
                elif 100 <= carrot <= 149:
                    return "筑基初期"
                elif 150 <= carrot <= 299:
                    return "筑基中期"
                elif 300 <= carrot <= 599:
                    return "筑基后期"
                elif 600 <= carrot <= 999:
                    return "筑基圆满"
                elif 1000 <= carrot <= 1999:
                    return "结丹初期"
                elif 2000 <= carrot <= 3499:
                    return "结丹中期"
                elif 3500 <= carrot <= 5999:
                    return "结丹后期"
                elif 6000 <= carrot <= 9999:
                    return "结丹圆满"
                elif 10000 <= carrot <= 19999:
                    return "元婴初期"
                elif 20000 <= carrot <= 34999:
                    return "元婴中期"
                elif 35000 <= carrot <= 59999:
                    return "元婴后期"
                elif 60000 <= carrot <= 99999:
                    return "元婴圆满"
                elif 100000 <= carrot <= 499999:
                    return "化神"
                elif 500000 <= carrot <= 999999:
                    return "炼虚"
                elif 1000000 <= carrot <= 9999999:
                    return "合体"
                elif 10000000 <= carrot <= 99999999:
                    return "大乘"
                else:
                    return "真仙"
            
            cultivation_level = calculate_cultivation_level(carrot)
            
            # 构建用户信息消息
            message = (
                f"🎬 用户名: `{username}`\n\n"
                f"• 🆔 用户ID: `{user_id}`\n\n"
                f"• 🔑 Token: `{token}`\n\n"
                f"• 📝 笔名: {pseudonym}\n\n"
                f"• 🥕 萝卜余额: {carrot}\n\n"
                f"• 🎋 修仙境界: {cultivation_level}\n\n"
                f"• 🎭 角色: 普通用户\n\n"
            )
            
            # 显示签到信息
            sign_info = user_data.get('sign')
            if sign_info:
                message += f"• 📅 签到状态: ✅ 已签到\n\n"
            else:
                message += f"• 📅 签到状态: ❌ 未签到\n\n"
            
            message += (
                f"• 📁 显示空库: ✅ 显示\n\n"
                f"• 📎 上传总量: {size_display}\n\n"
                f"• 🎫 剩余邀请: {invite_remaining}个\n\n"
                f"• 📋 片单卡槽: {watch_slot_remaining}个\n\n"
                f"\n绑定信息\n"
                f"• 🤖 Telegram: ✅ 已绑定\n"
                f"• 🌐 Emby服务器: `{emya_url}`\n"
            )
            
            message_obj = await loading.edit_text(message, parse_mode="Markdown")
            # 30秒后自动消失
            import asyncio
            from utils.message_utils import auto_delete_message
            # 使用message_obj作为消息对象
            asyncio.create_task(auto_delete_message(update, context, message_obj, 30))
        else:
            error_text = response.text[:200] if response.text else "无响应内容"
            logger.error(f"获取个人信息API错误: 状态码={response.status_code}")
            await loading.edit_text(f"❌ 获取失败，状态码：{response.status_code}\n{error_text}")
    except httpx.HTTPStatusError as e:
        logger.error(f"获取个人信息HTTP错误: {e.response.status_code}")
        await loading.edit_text(f"❌ 获取失败，HTTP错误：{e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"获取个人信息请求错误: {type(e).__name__}")
        await loading.edit_text("❌ 获取失败，网络请求错误，请检查网络连接")
    except Exception as e:
        logger.error(f"获取个人信息异常: {type(e).__name__}")
        await loading.edit_text("❌ 获取失败，请稍后重试")
    
    # 显示操作菜单 - 四个按钮
    keyboard = [
        [
            InlineKeyboardButton("⚙️ 账号设置", callback_data="menu_account_settings"),
            InlineKeyboardButton("🔑 密码管理", callback_data="menu_password_management")
        ],
        [
            InlineKeyboardButton("🔒 权限信息", callback_data="menu_permission_info"),
            InlineKeyboardButton("🎋 修仙境界", callback_data="menu_cultivation_level")
        ],
        [
            InlineKeyboardButton("📨 邀请好友", callback_data="menu_user_invite"),
            InlineKeyboardButton("✏️ 更改笔名", callback_data="menu_user_pseudonym")
        ],
        [
            InlineKeyboardButton("❌ 撤销邀请", callback_data="menu_revoke_invite"),
            InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.message.reply_text("个人信息查询完成", reply_markup=reply_markup)

async def user_sign(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """用户签到"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    
    if not user_info:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查user_info是字典还是字符串
    if isinstance(user_info, dict):
        token = user_info.get('token')
    else:
        token = user_info
    
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
            error_text = response.text[:200] if response.text else "无响应内容"
            logger.error(f"签到API错误: 状态码={response.status_code}")
            await loading.edit_text(f"❌ 签到失败，状态码：{response.status_code}\n{error_text}")
    except httpx.HTTPStatusError as e:
        logger.error(f"签到HTTP错误: {e.response.status_code}")
        await loading.edit_text(f"❌ 签到失败，HTTP错误：{e.response.status_code}")
    except httpx.RequestError as e:
        logger.error(f"签到请求错误: {type(e).__name__}")
        await loading.edit_text("❌ 签到失败，网络请求错误，请检查网络连接")
    except Exception as e:
        logger.error(f"签到异常: {type(e).__name__}")
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
    user_info = user_tokens.get(user_id)
    
    if not user_info:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查user_info是字典还是字符串
    if isinstance(user_info, dict):
        token = user_info.get('token')
    else:
        token = user_info
    
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
                # 显示返回按钮
                keyboard = [
                    [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.callback_query.message.reply_text("等待输入被邀请人ID...", reply_markup=reply_markup)
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
            error_text = response.text[:200] if response.text else "无响应内容"
            logger.error(f"获取邀请信息API错误: 状态码={response.status_code}")
            await loading.edit_text(f"❌ 获取邀请信息失败，状态码：{response.status_code}\n{error_text}")
            
            # 显示操作菜单
            keyboard = [
                [InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")],
                [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.callback_query.message.reply_text("邀请信息查询完成", reply_markup=reply_markup)
    except httpx.HTTPStatusError as e:
        logger.error(f"获取邀请信息HTTP错误: {e.response.status_code}")
        await loading.edit_text(f"❌ 获取邀请信息失败，HTTP错误：{e.response.status_code}")
        
        # 显示操作菜单
        keyboard = [
            [InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("邀请信息查询完成", reply_markup=reply_markup)
    except httpx.RequestError as e:
        logger.error(f"获取邀请信息请求错误: {type(e).__name__}")
        await loading.edit_text("❌ 获取邀请信息失败，网络请求错误，请检查网络连接")
        
        # 显示操作菜单
        keyboard = [
            [InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")],
            [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.callback_query.message.reply_text("邀请信息查询完成", reply_markup=reply_markup)
    except Exception as e:
        logger.error(f"获取邀请信息异常: {type(e).__name__}")
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
    user_info = user_tokens.get(user_id)
    
    if not user_info:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查user_info是字典还是字符串
    if isinstance(user_info, dict):
        token = user_info.get('token')
    else:
        token = user_info
    
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

async def user_revoke_invite(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """撤销邀请"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    
    if not user_info:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 检查user_info是字典还是字符串
    if isinstance(user_info, dict):
        token = user_info.get('token')
    else:
        token = user_info
    
    if not token:
        await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return
    
    # 提示用户输入被撤销邀请的用户ID
    await update.callback_query.edit_message_text("📨 撤销邀请\n\n请输入要撤销邀请的用户ID（10位字符串，以e开头s结尾）：")
    
    # 存储当前状态，等待用户输入
    context.user_data['current_operation'] = 'revoke_invite'
    context.user_data['token'] = token
    
    # 返回一个状态码，用于后续处理用户输入
    return 109  # 自定义状态码，用于处理撤销邀请输入