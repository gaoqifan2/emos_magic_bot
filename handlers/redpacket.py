import logging
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

# 北京时间 UTC+8
beijing_tz = timezone(timedelta(hours=8))

from config import user_tokens, Config, get_user_token
from handlers.common import add_cancel_button
from utils.r2_client import r2_client
from utils.message_utils import auto_delete_message
from utils.http_client import http_client
from utils.http_client import http_client

logger = logging.getLogger(__name__)

# 对话状态 (从1开始，避免与 ConversationHandler.END=0 冲突)
WAITING_TYPE, WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD, WAITING_MEDIA, WAITING_SCENE, WAITING_CUSTOM_BLESSING = range(1, 9)

# 步骤顺序，用于返回上一步
STEP_ORDER = ['type', 'carrot', 'number', 'blessing', 'password', 'media']

def get_step_keyboard(current_step):
    """获取当前步骤的键盘，包含返回上一步按钮"""
    keyboard = []
    
    # 找到当前步骤在顺序中的位置
    if current_step in STEP_ORDER:
        current_index = STEP_ORDER.index(current_step)
        # 如果有上一步，添加返回按钮和取消按钮在同一行
        if current_index > 0:
            prev_step = STEP_ORDER[current_index - 1]
            keyboard.append([
                InlineKeyboardButton("⬅️ 返回上一步", callback_data=f"back_{prev_step}"),
                InlineKeyboardButton("🔄 取消", callback_data="cancel_operation")
            ])
        else:
            # 没有上一步，只添加取消按钮
            keyboard.append([InlineKeyboardButton("🔄 取消", callback_data="cancel_operation")])
    else:
        keyboard.append([InlineKeyboardButton("🔄 取消", callback_data="cancel_operation")])
    
    return InlineKeyboardMarkup(keyboard)

async def redpocket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始创建红包"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 开始创建红包")
    
    if user_id not in user_tokens:
        if update.message:
            message = await update.message.reply_text("🔑 请先登录！发送 /start 登录")
            # 5秒后自动消失
            import asyncio
            from utils.message_utils import auto_delete_message
            asyncio.create_task(auto_delete_message(update, context, message, 5))
        else:
            await update.callback_query.edit_message_text("🔑 请先登录！发送 /start 登录")
            # 5秒后自动消失
            import asyncio
            from utils.message_utils import auto_delete_message
            asyncio.create_task(auto_delete_message(update, context, None, 5))
        return ConversationHandler.END
    
    # 初始化用户数据
    context.user_data['redpacket'] = {
        'user_id': user_id,
        'start_time': datetime.now(beijing_tz).isoformat(),
        'current_step': 'type'
    }
    
    # 初始化上传文件缓存
    if 'uploaded_files' not in context.user_data:
        context.user_data['uploaded_files'] = {}
    
    # 显示红包类型选择菜单
    keyboard = [
        [InlineKeyboardButton("🎲 普通红包　　　　　　", callback_data="type_random")],
        [InlineKeyboardButton("🔐 口令红包　　　　　　", callback_data="type_password")],
        [InlineKeyboardButton("💝 私包　　　　　　　　", callback_data="type_private")],
        [InlineKeyboardButton("🖼️ 图片红包　　　　　　", callback_data="type_image")],
        [InlineKeyboardButton("🎵 语音红包　　　　　　", callback_data="type_audio")],
        [InlineKeyboardButton("⬅️ 返回上一步", callback_data="back_prev")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "🧧 创建红包\n\n请选择红包类型："
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        try:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"编辑消息失败: {e}")
            await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
    
    return WAITING_TYPE

async def handle_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理红包类型选择"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"用户 {user_id} 选择了红包类型: {data}")
    
    if 'redpacket' not in context.user_data:
        context.user_data['redpacket'] = {
            'user_id': user_id,
            'start_time': datetime.now(beijing_tz).isoformat(),
            'current_step': 'type'
        }
    
    redpacket_data = context.user_data['redpacket']
    
    if data == 'type_random':
        redpacket_data['type'] = 'random'
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data == 'type_password':
        redpacket_data['type'] = 'password'
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data == 'type_image':
        redpacket_data['type'] = 'image'
        redpacket_data['current_step'] = 'password_choice'
        # 显示口令选择菜单
        keyboard = [
            [InlineKeyboardButton("🚫 无口令 (手气红包)　　", callback_data="image_no_password")],
            [InlineKeyboardButton("🔐 有口令　　　　　　　", callback_data="image_with_password")]
        ]
        keyboard = add_cancel_button(keyboard)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🖼️ 图片红包\n\n请选择是否需要口令：", reply_markup=reply_markup)
        return WAITING_TYPE
    elif data == 'type_audio':
        redpacket_data['type'] = 'audio'
        redpacket_data['current_step'] = 'password_choice'
        # 显示口令选择菜单
        keyboard = [
            [InlineKeyboardButton("🚫 无口令 (手气红包)　　", callback_data="audio_no_password")],
            [InlineKeyboardButton("🔐 有口令　　　　　　　", callback_data="audio_with_password")]
        ]
        keyboard = add_cancel_button(keyboard)
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎵 语音红包\n\n请选择是否需要口令：", reply_markup=reply_markup)
        return WAITING_TYPE
    elif data == 'type_private':
        redpacket_data['type'] = 'password'
        redpacket_data['has_password'] = True
        redpacket_data['private'] = True
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("💝 私包\n\n💰 请输入红包金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data == 'image_no_password':
        redpacket_data['has_password'] = False
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("🖼️ 图片红包 - 无口令\n\n💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data == 'image_with_password':
        redpacket_data['has_password'] = True
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("🖼️ 图片红包 - 有口令\n\n💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data == 'audio_no_password':
        redpacket_data['has_password'] = False
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("🎵 语音红包 - 无口令\n\n💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data == 'audio_with_password':
        redpacket_data['has_password'] = True
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("🎵 语音红包 - 有口令\n\n💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data.startswith('back_'):
        # 处理返回上一步
        return await handle_back(update, context, data)
    else:
        await query.edit_message_text("⚠️ 未知的红包类型")
        # 5秒后自动消失
        import asyncio
        from utils.message_utils import auto_delete_message
        asyncio.create_task(auto_delete_message(update, context, None, 5))
        return ConversationHandler.END

async def handle_back(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """处理返回上一步"""
    query = update.callback_query
    redpacket_data = context.user_data.get('redpacket')
    prev_step = data.replace('back_', '')
    
    logger.info(f"用户返回上一步到: {prev_step}")
    
    if prev_step == 'to_main':
        # 返回主菜单
        keyboard = [
            [
                InlineKeyboardButton("👤 个人信息", callback_data="menu_user_main"),
                InlineKeyboardButton("🧧 红包", callback_data="menu_redpacket_main")
            ],
            [
                InlineKeyboardButton("🎲 抽奖", callback_data="menu_lottery_main"),
                InlineKeyboardButton("🏆 排行榜", callback_data="menu_rank_main")
            ],
            [
                InlineKeyboardButton("💰 转账", callback_data="menu_transfer_main"),
                InlineKeyboardButton("🛒 商城", callback_data="menu_shop_main")
            ],
            [
                InlineKeyboardButton("🎵 点歌", callback_data="menu_music_main"),
                InlineKeyboardButton("🎁 兑换", callback_data="menu_exchange_main")
            ],
            [
                InlineKeyboardButton("📱 其他", callback_data="menu_other_main")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("📱 功能菜单\n\n请选择功能：", reply_markup=reply_markup)
        return ConversationHandler.END
    elif prev_step == 'prev':
        # 返回到红包功能菜单
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
        await query.edit_message_text("🧧 红包功能\n\n请选择操作：", reply_markup=reply_markup)
        return ConversationHandler.END
    elif prev_step == 'type':
        redpacket_data['current_step'] = 'type'
        keyboard = [
            [InlineKeyboardButton("🎲 普通红包　　　　　　", callback_data="type_random")],
            [InlineKeyboardButton("🔐 口令红包　　　　　　", callback_data="type_password")],
            [InlineKeyboardButton("💝 私包　　　　　　　　", callback_data="type_private")],
            [InlineKeyboardButton("🖼️ 图片红包　　　　　　", callback_data="type_image")],
            [InlineKeyboardButton("🎵 语音红包　　　　　　", callback_data="type_audio")],
            [InlineKeyboardButton("⬅️ 返回上一步", callback_data="back_prev")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🧧 创建红包\n\n请选择红包类型：", reply_markup=reply_markup)
        return WAITING_TYPE
    elif prev_step == 'carrot':
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif prev_step == 'number':
        redpacket_data['current_step'] = 'number'
        message = await query.edit_message_text("👥 请输入可领人数：\n（1 - 10000 之间）", reply_markup=get_step_keyboard('number'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_NUMBER
    elif prev_step == 'blessing':
        redpacket_data['current_step'] = 'blessing'
        message = await query.edit_message_text("💬 请输入祝福语（最多50字）：", reply_markup=get_step_keyboard('blessing'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BLESSING
    elif prev_step == 'password':
        redpacket_data['current_step'] = 'password'
        message = await query.edit_message_text("🔑 请输入红包口令：", reply_markup=get_step_keyboard('password'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_PASSWORD
    elif prev_step == 'media':
        redpacket_data['current_step'] = 'media'
        media_type = "图片" if redpacket_data.get('type') == 'image' else "语音"
        message = await query.edit_message_text(f"🖼️ 请发送{media_type}作为红包封面：", reply_markup=get_step_keyboard('media'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_MEDIA
    else:
        return WAITING_TYPE

async def handle_carrot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理红包金额输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入金额: {text}")
    
    # 删除之前的提示消息
    if 'current_prompt_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['current_prompt_message']
            )
            del context.user_data['current_prompt_message']
        except Exception as e:
            logger.error(f"删除提示消息失败: {e}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    try:
        carrot = int(text)
        if carrot <= 0 or carrot > 60000:
            message = await update.message.reply_text("⚠️ 金额必须在1-60000之间，请重新输入：", reply_markup=get_step_keyboard('carrot'))
            context.user_data['current_prompt_message'] = message.message_id
            return WAITING_CARROT
        
        redpacket_data['carrot'] = carrot
        
        # 处理私包逻辑
        if redpacket_data.get('private'):
            # 自动设置为私包
            redpacket_data['number'] = 1
            
            # 显示场景选择菜单
            keyboard = [
                [InlineKeyboardButton("🎂 生日红包", callback_data="scene_birthday")],
                [InlineKeyboardButton("🎊 节日红包", callback_data="scene_festival")],
                [InlineKeyboardButton("✨ 自定义", callback_data="scene_custom")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await update.message.reply_text("💝 请选择私包场景：", reply_markup=reply_markup)
            context.user_data['current_prompt_message'] = message.message_id
            return WAITING_SCENE
        
        # 普通红包流程
        redpacket_data['current_step'] = 'number'
        
        # 图片/语音红包提示可以上传媒体
        if redpacket_data['type'] in ['image', 'audio']:
            media_type = "图片" if redpacket_data['type'] == 'image' else "语音"
            message = await update.message.reply_text(f"👥 请输入可领人数：\n（1 - 10000 之间）\n\n📎 你也可以随时发送{media_type}作为红包封面", reply_markup=get_step_keyboard('number'))
            context.user_data['current_prompt_message'] = message.message_id
        else:
            message = await update.message.reply_text("👥 请输入可领人数：\n（1 - 10000 之间）", reply_markup=get_step_keyboard('number'))
            context.user_data['current_prompt_message'] = message.message_id
        return WAITING_NUMBER
    except ValueError:
        message = await update.message.reply_text("⚠️ 请输入有效的数字：", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT

async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理红包人数输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入人数: {text}")
    
    # 删除之前的提示消息
    if 'current_prompt_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['current_prompt_message']
            )
            del context.user_data['current_prompt_message']
        except Exception as e:
            logger.error(f"删除提示消息失败: {e}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    try:
        number = int(text)
        if number <= 0 or number > 10000:
            message = await update.message.reply_text("⚠️ 人数必须在1-10000之间，请重新输入：", reply_markup=get_step_keyboard('number'))
            context.user_data['current_prompt_message'] = message.message_id
            return WAITING_NUMBER
        
        redpacket_data['number'] = number
        redpacket_data['current_step'] = 'blessing'
        
        # 图片/语音红包提示可以上传媒体
        if redpacket_data['type'] in ['image', 'audio']:
            media_type = "图片" if redpacket_data['type'] == 'image' else "语音"
            message = await update.message.reply_text(f"💬 请输入祝福语（最多50字）：\n\n📎 你也可以随时发送{media_type}作为红包封面", reply_markup=get_step_keyboard('blessing'))
            context.user_data['current_prompt_message'] = message.message_id
        else:
            message = await update.message.reply_text("💬 请输入祝福语（最多50字）：", reply_markup=get_step_keyboard('blessing'))
            context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BLESSING
    except ValueError:
        message = await update.message.reply_text("⚠️ 请输入有效的数字：", reply_markup=get_step_keyboard('number'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_NUMBER

async def handle_blessing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理祝福语输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入祝福语")
    
    # 删除之前的提示消息
    if 'current_prompt_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['current_prompt_message']
            )
            del context.user_data['current_prompt_message']
        except Exception as e:
            logger.error(f"删除提示消息失败: {e}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    if len(text) > 50:
        message = await update.message.reply_text("⚠️ 祝福语不能超过50字，请重新输入：", reply_markup=get_step_keyboard('blessing'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BLESSING
    
    redpacket_data['blessing'] = text
    redpacket_data['current_step'] = 'password' if redpacket_data.get('has_password') or redpacket_data['type'] == 'password' else 'media' if redpacket_data['type'] in ['image', 'audio'] else 'complete'
    
    if redpacket_data['type'] == 'password':
        message = await update.message.reply_text("🔑 请输入红包口令：", reply_markup=get_step_keyboard('password'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_PASSWORD
    elif redpacket_data['type'] in ['image', 'audio']:
        if redpacket_data.get('has_password'):
            message = await update.message.reply_text("🔑 请输入红包口令：", reply_markup=get_step_keyboard('password'))
            context.user_data['current_prompt_message'] = message.message_id
            return WAITING_PASSWORD
        else:
            # 检查是否已经上传了媒体
            if redpacket_data.get('cover_url'):
                return await create_redpacket(update, context)
            else:
                media_type = "图片" if redpacket_data['type'] == 'image' else "语音"
                message = await update.message.reply_text(f"🖼️ 请发送{media_type}作为红包封面：", reply_markup=get_step_keyboard('media'))
                context.user_data['current_prompt_message'] = message.message_id
                return WAITING_MEDIA
    else:
        return await create_redpacket(update, context)

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理口令输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入口令")
    
    # 删除之前的提示消息
    if 'current_prompt_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['current_prompt_message']
            )
            del context.user_data['current_prompt_message']
        except Exception as e:
            logger.error(f"删除提示消息失败: {e}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    redpacket_data['password'] = text
    redpacket_data['current_step'] = 'media' if redpacket_data['type'] in ['image', 'audio'] else 'complete'
    
    if redpacket_data['type'] in ['image', 'audio']:
        # 检查是否已经上传了媒体
        if redpacket_data.get('cover_url'):
            return await create_redpacket(update, context)
        else:
            media_type = "图片" if redpacket_data['type'] == 'image' else "语音"
            message = await update.message.reply_text(f"🖼️ 请发送{media_type}作为红包封面：", reply_markup=get_step_keyboard('media'))
            context.user_data['current_prompt_message'] = message.message_id
            return WAITING_MEDIA
    else:
        return await create_redpacket(update, context)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理媒体上传（图片/音频）"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 上传媒体")
    
    # 删除之前的提示消息
    if 'current_prompt_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['current_prompt_message']
            )
            del context.user_data['current_prompt_message']
        except Exception as e:
            logger.error(f"删除提示消息失败: {e}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    # 检查文件类型
    if update.message.photo:
        # 处理图片
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        if file_id in context.user_data['uploaded_files']:
            cover_url = context.user_data['uploaded_files'][file_id]
            await update.message.reply_text("✅ 使用已上传的图片！")
        else:
            loading = await update.message.reply_text("🔄 正在上传图片到云端...")
            try:
                file = await context.bot.get_file(file_id)
                file_data = await file.download_as_bytearray()
                file_name = f"redpacket_{user_id}_{file_id}.jpg"
                
                logger.info(f"开始上传图片: {file_name}, 大小: {len(file_data)} bytes")
                cover_url = r2_client.upload_file(bytes(file_data), file_name, "redpacket")
                logger.info(f"图片上传成功: {cover_url}")
                
                context.user_data['uploaded_files'][file_id] = cover_url
                await loading.edit_text("✅ 图片上传成功！")
            except Exception as e:
                logger.error(f"上传图片失败: {e}")
                await loading.edit_text("❌ 图片上传失败，请稍后重试")
                return WAITING_MEDIA
        
        redpacket_data['cover_url'] = cover_url
        redpacket_data['file_type'] = 'image'
        
        # 根据当前步骤继续
        return await continue_after_media(update, context)
    
    elif update.message.voice or update.message.audio or update.message.document:
        # 处理音频
        file_id = None
        file_extension = 'ogg'
        file_size = 0
        
        if update.message.voice:
            audio_source = update.message.voice
            file_id = audio_source.file_id
            file_extension = 'ogg'
            file_size = audio_source.file_size
        elif update.message.audio:
            audio_source = update.message.audio
            file_id = audio_source.file_id
            mime_type = audio_source.mime_type
            if mime_type == 'audio/mpeg':
                file_extension = 'mp3'
            elif mime_type == 'audio/ogg':
                file_extension = 'ogg'
            elif mime_type == 'audio/wav':
                file_extension = 'wav'
            elif mime_type == 'audio/mp4':
                file_extension = 'm4a'
            else:
                file_extension = 'ogg'
            file_size = audio_source.file_size
        elif update.message.document:
            document = update.message.document
            file_id = document.file_id
            mime_type = document.mime_type
            file_name = document.file_name
            if file_name and '.' in file_name:
                ext_from_name = file_name.split('.')[-1].lower()
                if ext_from_name in ['mp3', 'ogg', 'wav', 'm4a', 'aac', 'flac', 'opus', 'webm']:
                    file_extension = ext_from_name
            file_size = document.file_size
        
        # 检查文件大小（限制为10MB）
        max_file_size = 10 * 1024 * 1024
        if file_size > max_file_size:
            await update.message.reply_text(f"❌ 文件大小超过限制（{max_file_size // 1024 // 1024}MB），请上传更小的文件")
            return WAITING_MEDIA
        
        if file_id in context.user_data['uploaded_files']:
            audio_url = context.user_data['uploaded_files'][file_id]
            await update.message.reply_text("✅ 使用已上传的音频！")
        else:
            loading = await update.message.reply_text("🔄 正在上传音频到云端...")
            try:
                file = await context.bot.get_file(file_id)
                file_data = await file.download_as_bytearray()
                file_name = f"redpacket_{user_id}_{file_id}.{file_extension}"
                
                logger.info(f"开始上传音频: {file_name}, 大小: {len(file_data)} bytes")
                audio_url = r2_client.upload_file(bytes(file_data), file_name, "redpacket")
                logger.info(f"音频上传成功: {audio_url}")
                
                context.user_data['uploaded_files'][file_id] = audio_url
                await loading.edit_text("✅ 音频上传成功！")
            except Exception as e:
                logger.error(f"上传音频失败: {e}")
                await loading.edit_text("❌ 音频上传失败，请稍后重试")
                return WAITING_MEDIA
        
        redpacket_data['cover_url'] = audio_url
        redpacket_data['file_type'] = 'audio'
        
        # 根据当前步骤继续
        return await continue_after_media(update, context)
    else:
        await update.message.reply_text("❌ 请发送有效的媒体文件")
        return WAITING_MEDIA

async def continue_after_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """上传媒体后根据当前步骤继续"""
    redpacket_data = context.user_data['redpacket']
    current_step = redpacket_data.get('current_step', 'carrot')
    
    if current_step == 'carrot':
        message = await update.message.reply_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif current_step == 'number':
        message = await update.message.reply_text("👥 请输入可领人数：\n（1 - 10000 之间）", reply_markup=get_step_keyboard('number'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_NUMBER
    elif current_step == 'blessing':
        message = await update.message.reply_text("💬 请输入祝福语（最多50字）：", reply_markup=get_step_keyboard('blessing'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BLESSING
    elif current_step == 'password':
        if redpacket_data.get('has_password'):
            if 'password' in redpacket_data:
                return await create_redpacket(update, context)
            else:
                message = await update.message.reply_text("🔑 请输入红包口令：", reply_markup=get_step_keyboard('password'))
                context.user_data['current_prompt_message'] = message.message_id
                return WAITING_PASSWORD
        else:
            return await create_redpacket(update, context)
    else:
        required_fields = ['carrot', 'number', 'blessing']
        if all(field in redpacket_data for field in required_fields):
            if redpacket_data.get('has_password') and 'password' not in redpacket_data:
                message = await update.message.reply_text("🔑 请输入红包口令：", reply_markup=get_step_keyboard('password'))
                context.user_data['current_prompt_message'] = message.message_id
                return WAITING_PASSWORD
            return await create_redpacket(update, context)
        else:
            if 'carrot' not in redpacket_data:
                message = await update.message.reply_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
                context.user_data['current_prompt_message'] = message.message_id
                return WAITING_CARROT
            elif 'number' not in redpacket_data:
                message = await update.message.reply_text("👥 请输入可领人数：\n（1 - 10000 之间）", reply_markup=get_step_keyboard('number'))
                context.user_data['current_prompt_message'] = message.message_id
                return WAITING_NUMBER
            elif 'blessing' not in redpacket_data:
                message = await update.message.reply_text("💬 请输入祝福语（最多50字）：", reply_markup=get_step_keyboard('blessing'))
                context.user_data['current_prompt_message'] = message.message_id
                return WAITING_BLESSING
            else:
                return await create_redpacket(update, context)

async def create_redpacket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建红包API调用"""
    user_id = update.effective_user.id
    token = get_user_token(user_id)
    user_info = user_tokens.get(user_id)
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 数据不完整，请重新开始")
        return ConversationHandler.END
    
    data = context.user_data['redpacket']
    
    if not token:
        # 处理回调查询的情况
        if update.message:
            await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        else:
            await update.callback_query.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END
    
    required_fields = ['carrot', 'number', 'blessing']
    missing = [f for f in required_fields if f not in data]
    if missing:
        # 处理回调查询的情况
        if update.message:
            await update.message.reply_text(f"❌ 数据不完整，缺少: {missing}，请重新开始")
        else:
            await update.callback_query.message.reply_text(f"❌ 数据不完整，缺少: {missing}，请重新开始")
        return ConversationHandler.END
    
    # 处理回调查询的情况
    if update.message:
        loading = await update.message.reply_text("🔄 正在创建红包...")
    else:
        loading = await update.callback_query.message.reply_text("🔄 正在创建红包...")
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        if data.get('type') == 'random':
            redpacket_type = "random"
            redpacket_text = None
        elif data.get('type') == 'password':
            redpacket_type = "password"
            redpacket_text = data.get('password', None)
        elif data.get('type') in ['image', 'audio']:
            if data.get('has_password'):
                redpacket_type = "password"
                redpacket_text = data.get('password', None)
            else:
                redpacket_type = "fixed"
                redpacket_text = None
        else:
            redpacket_type = "random"
            redpacket_text = None
        
        payload = {
            "type": redpacket_type,
            "carrot": data['carrot'],
            "number": data['number'],
            "blessing": data['blessing'],
            "text": redpacket_text,
            "file_url": data.get('cover_url', None),
            "file_type": data.get('file_type', None)
        }
        
        logger.info(f"创建红包: type={redpacket_type}, carrot={data['carrot']}, number={data['number']}")
        
        response = requests.post(
            Config.REDPACKET_CREATE_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"API返回结果: {result}")
            
            if redpacket_type == "random":
                redpacket_type_display = "🎲 普通红包"
            elif redpacket_type == "password":
                redpacket_type_display = "🔐 口令红包"
            elif data.get('file_type') == 'image':
                redpacket_type_display = "🖼️ 图片红包"
            elif data.get('file_type') == 'audio':
                redpacket_type_display = "🎵 语音红包"
            else:
                redpacket_type_display = "🧧 红包"
            
            # 获取用户余额 - 使用user接口获取
            balance = 0
            try:
                user_response = requests.get(
                    Config.API_USER_ENDPOINT,
                    headers=headers,
                    timeout=5
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    balance = user_data.get('carrot', 0)
            except Exception as e:
                logger.error(f"获取用户余额失败: {e}")
            
            message = (
                f"#红包凭证\n\n"
                f"✅ 红包创建成功！\n\n"
                f"{redpacket_type_display}\n"
                f"💰 金额: {data['carrot']} 萝卜\n"
                f"👥 人数: {data['number']}\n"
                f"💬 祝福语: `{data['blessing']}`\n"
                f"💎 当前余额: {balance} 萝卜\n"
            )
            if redpacket_text:
                message += f"🔑 口令: `{redpacket_text}`\n"
            if data.get('cover_url'):
                if data.get('file_type') == 'image':
                    message += f"🖼️ 封面: 已上传 ✓\n"
                elif data.get('file_type') == 'audio':
                    message += f"🎵 语音: 已上传 ✓\n"
            if result.get('red_packet_id'):
                message += f"🆔 红包ID: `{result['red_packet_id']}`\n"
            
            # 添加操作按钮
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            keyboard = [
                [InlineKeyboardButton("👥 跳转到 emospg 群", url="https://t.me/emospg")],
                [InlineKeyboardButton("🔄 再创建一个", callback_data="create_another_redpacket"),
                 InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # 尝试编辑消息显示红包凭证
            try:
                await loading.edit_text(message, parse_mode="Markdown", reply_markup=reply_markup)
            except Exception as edit_error:
                logger.error(f"编辑消息失败: {edit_error}")
                # 尝试发送新消息
                if update.message:
                    await update.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
                else:
                    await update.callback_query.message.reply_text(message, parse_mode="Markdown", reply_markup=reply_markup)
        else:
            # 尝试编辑消息显示失败信息
            try:
                await loading.edit_text(f"❌ 创建失败，状态码：{response.status_code}")
            except Exception as edit_error:
                logger.error(f"编辑消息失败: {edit_error}")
                # 尝试发送新消息
                if update.message:
                    await update.message.reply_text(f"❌ 创建失败，状态码：{response.status_code}")
                else:
                    await update.callback_query.message.reply_text(f"❌ 创建失败，状态码：{response.status_code}")
            if response.text:
                logger.error(f"API返回: {response.text}")
    except Exception as e:
        logger.error(f"创建红包失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        try:
            await loading.edit_text("❌ 创建失败，请稍后重试")
        except Exception as edit_error:
            logger.error(f"编辑消息失败: {edit_error}")
            # 尝试发送新消息
            if update.message:
                await update.message.reply_text("❌ 创建失败，请稍后重试")
            else:
                await update.callback_query.message.reply_text("❌ 创建失败，请稍后重试")
    
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    
    return ConversationHandler.END

async def cancel_redpacket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消红包创建"""
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    if 'current_operation' in context.user_data:
        del context.user_data['current_operation']
    await update.message.reply_text("✅ 红包创建已取消")
    return ConversationHandler.END

async def handle_create_another(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理再创建一个红包"""
    query = update.callback_query
    await query.answer()
    
    # 清理之前的红包数据
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    
    # 跳转到选择红包类型的界面
    await redpocket_command(update, context)
    return ConversationHandler.END

async def handle_scene(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理私包场景选择"""
    user_id = update.effective_user.id
    query = update.callback_query
    await query.answer()
    data = query.data
    
    # 删除之前的提示消息
    if 'current_prompt_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['current_prompt_message']
            )
            del context.user_data['current_prompt_message']
        except Exception as e:
            logger.error(f"删除提示消息失败: {e}")
    
    if 'redpacket' not in context.user_data:
        await update.callback_query.edit_message_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    # 生成随机口令
    import string
    import random
    password_length = 6
    password = ''.join(random.choices(string.ascii_letters + string.digits, k=password_length))
    redpacket_data['password'] = password
    
    # 根据场景生成祝福语
    if data == 'scene_birthday':
        # 生日祝福语
        birthday_blessings = [
            "🎂 生日快乐！愿你年年有今日，岁岁有今朝！",
            "🎁 生日大快乐！愿你在新的一岁里心想事成！",
            "🎉 生日快乐！愿你的每一天都充满阳光和快乐！",
            "🎈 生日祝福送到，愿你永远年轻，永远快乐！",
            "🎊 生日快乐！愿你在未来的日子里一切顺利！"
        ]
        redpacket_data['blessing'] = random.choice(birthday_blessings)
        # 直接创建红包
        return await create_redpacket(update, context)
    elif data == 'scene_festival':
        # 节日祝福语
        # 获取当前日期（北京时间）
        import datetime
        today = datetime.datetime.now(beijing_tz)
        month = today.month
        day = today.day
        
        # 根据日期判断节日
        festival_blessings = []
        
        # 春节 (农历正月初一，这里简化为公历1月或2月)
        if (month == 1 and day >= 20) or (month == 2 and day <= 20):
            festival_blessings = [
                "🧧 新年快乐！祝你在新的一年里万事如意！",
                "🎊 春节快乐！愿你阖家幸福，财源广进！",
                "🎉 新年大吉！愿你在新的一年里心想事成！",
                "✨ 新春快乐！愿你在新的一年里事业有成！",
                "🎈 过年好！愿你在新的一年里身体健康！"
            ]
        # 元宵节 (农历正月十五，公历2月或3月)
        elif (month == 2 and day >= 10) or (month == 3 and day <= 10):
            festival_blessings = [
                "🏮 元宵节快乐！愿你团团圆圆，幸福美满！",
                "🎊 元宵佳节，愿你阖家欢乐，万事顺意！",
                "🎉 元宵节快乐！愿你在新的一年里事事如意！",
                "✨ 元宵快乐！愿你在新的一年里心想事成！",
                "🎈 元宵节到，愿你平安吉祥，幸福安康！"
            ]
        # 情人节 (2月14日)
        elif month == 2 and day == 14:
            festival_blessings = [
                "💖 情人节快乐！愿你和爱人甜甜蜜蜜！",
                "💕 情人节快乐！愿你爱情美满，幸福长久！",
                "💝 情人节快乐！愿你和心爱的人永远在一起！",
                "🌹 情人节快乐！愿你的爱情如玫瑰般美丽！",
                "💌 情人节快乐！愿你收到心仪的人的表白！"
            ]
        # 清明节 (4月4日-6日)
        elif month == 4 and 4 <= day <= 6:
            festival_blessings = [
                "🌿 清明节安康！愿逝者安息，生者珍惜！",
                "🌸 清明时节，愿你缅怀先人，珍惜当下！",
                "🌱 清明节到，愿你心怀感恩，珍惜生活！",
                "🍃 清明安康！愿你在春天里收获希望！",
                "🌾 清明节快乐！愿你珍惜眼前人，过好每一天！"
            ]
        # 劳动节 (5月1日)
        elif month == 5 and day == 1:
            festival_blessings = [
                "🏃 劳动节快乐！愿你工作顺利，生活愉快！",
                "💪 劳动节快乐！愿你在工作中收获成长！",
                "🎉 劳动节快乐！愿你在假期里好好休息！",
                "✨ 劳动节到，愿你劳逸结合，事半功倍！",
                "🎊 劳动节快乐！愿你在劳动中创造价值！"
            ]
        # 端午节 (农历五月初五，公历6月)
        elif month == 6:
            festival_blessings = [
                "🌿 端午节快乐！愿你端午安康，百病不侵！",
                "🐲 端午节快乐！愿你如龙般矫健，如粽般香甜！",
                "🏮 端午节到，愿你平安吉祥，幸福安康！",
                "🎉 端午节快乐！愿你在节日里收获快乐！",
                "✨ 端午安康！愿你在夏天里一切顺利！"
            ]
        # 中秋节 (农历八月十五，公历9月或10月)
        elif (month == 9 and day >= 15) or (month == 10 and day <= 15):
            festival_blessings = [
                "🌙 中秋节快乐！愿你月圆人圆，事事圆满！",
                "🥮 中秋节快乐！愿你和家人团团圆圆！",
                "🎑 中秋节到，愿你阖家欢乐，幸福美满！",
                "✨ 中秋快乐！愿你在节日里收获团圆和快乐！",
                "🎊 中秋节快乐！愿你心想事成，万事如意！"
            ]
        # 国庆节 (10月1日)
        elif month == 10 and day == 1:
            festival_blessings = [
                "🇨🇳 国庆节快乐！愿祖国繁荣昌盛！",
                "🎉 国庆节快乐！愿你在假期里玩得开心！",
                "✨ 国庆佳节，愿你和家人共度美好时光！",
                "🎊 国庆节到，愿你在假期里收获快乐！",
                "🏮 国庆节快乐！愿你生活美满，万事如意！"
            ]
        # 圣诞节 (12月25日)
        elif month == 12 and day == 25:
            festival_blessings = [
                "🎅 圣诞节快乐！愿你收到心仪的礼物！",
                "🎄 圣诞节快乐！愿你在节日里收获快乐！",
                "🌟 圣诞节到，愿你和家人共度美好时光！",
                "✨ 圣诞快乐！愿你在新的一年里心想事成！",
                "🎊 圣诞节快乐！愿你生活美满，万事如意！"
            ]
        else:
            # 当天不是节日，跳转到自定义祝福语
            try:
                message = await update.callback_query.edit_message_text("💬 请输入自定义祝福语（最多50字）：")
                context.user_data['current_prompt_message'] = message.message_id
            except Exception as e:
                # 消息不存在，发送新消息
                message = await update.effective_message.reply_text("💬 请输入自定义祝福语（最多50字）：")
                context.user_data['current_prompt_message'] = message.message_id
            return WAITING_CUSTOM_BLESSING
    elif data == 'scene_custom':
        # 自定义祝福语
        try:
            message = await update.callback_query.edit_message_text("💬 请输入自定义祝福语（最多50字）：")
            context.user_data['current_prompt_message'] = message.message_id
        except Exception as e:
            # 消息不存在，发送新消息
            message = await update.effective_message.reply_text("💬 请输入自定义祝福语（最多50字）：")
            context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CUSTOM_BLESSING

async def handle_custom_blessing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理自定义祝福语输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # 删除之前的提示消息
    if 'current_prompt_message' in context.user_data:
        try:
            await context.bot.delete_message(
                chat_id=update.effective_chat.id,
                message_id=context.user_data['current_prompt_message']
            )
            del context.user_data['current_prompt_message']
        except Exception as e:
            logger.error(f"删除提示消息失败: {e}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    # 检查祝福语长度
    if len(text) > 50:
        message = await update.message.reply_text("⚠️ 祝福语不能超过50字，请重新输入：")
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CUSTOM_BLESSING
    
    # 存储祝福语
    redpacket_data['blessing'] = text
    
    # 直接创建红包
    return await create_redpacket(update, context)
