import logging
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ContextTypes, ConversationHandler

# 北京时间 UTC+8
beijing_tz = timezone(timedelta(hours=8))

from config import user_tokens, Config
from handlers.common import add_cancel_button
from utils.r2_client import r2_client
from utils.message_utils import auto_delete_message

logger = logging.getLogger(__name__)

# 对话状态
WAITING_TYPE, WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD, WAITING_MEDIA = range(6)

async def redpocket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始创建红包"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 开始创建红包")
    
    if user_id not in user_tokens:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return ConversationHandler.END
    
    # 初始化用户数据
    context.user_data['redpacket'] = {
        'user_id': user_id,
        'start_time': datetime.now(beijing_tz).isoformat()
    }
    
    # 初始化上传文件缓存
    if 'uploaded_files' not in context.user_data:
        context.user_data['uploaded_files'] = {}
    
    # 显示红包类型选择菜单
    keyboard = [
        [InlineKeyboardButton("🎲 普通红包", callback_data="type_random")],
        [InlineKeyboardButton("🔐 口令红包", callback_data="type_password")],
        [InlineKeyboardButton("🖼️ 图片红包", callback_data="type_image")],
        [InlineKeyboardButton("🎵 语音红包", callback_data="type_audio")]
    ]
    keyboard = add_cancel_button(keyboard)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "🧧 创建红包\n\n请选择红包类型："
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        try:
            await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
        except Exception as e:
            logger.error(f"编辑消息失败: {e}")
            # 如果编辑失败，发送新消息
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
            'start_time': datetime.now(beijing_tz).isoformat()
        }
    
    redpacket_data = context.user_data['redpacket']
    
    if data == 'type_random':
        redpacket_data['type'] = 'random'
        redpacket_data['step'] = 'carrot'
        await query.edit_message_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）")
        return WAITING_CARROT
    elif data == 'type_password':
        redpacket_data['type'] = 'password'
        redpacket_data['step'] = 'carrot'
        await query.edit_message_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）")
        return WAITING_CARROT
    elif data == 'type_image':
        redpacket_data['type'] = 'image'
        redpacket_data['step'] = 'media'
        await query.edit_message_text("🖼️ 请发送图片作为红包封面：")
        return WAITING_MEDIA
    elif data == 'type_audio':
        redpacket_data['type'] = 'audio'
        redpacket_data['step'] = 'media'
        await query.edit_message_text("🎵 请发送语音作为红包内容：")
        return WAITING_MEDIA
    else:
        await query.edit_message_text("❌ 未知的红包类型")
        return ConversationHandler.END

async def handle_carrot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理红包金额输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入金额: {text}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    try:
        carrot = int(text)
        if carrot <= 0 or carrot > 60000:
            await update.message.reply_text("❌ 金额必须在1-60000之间，请重新输入：")
            return WAITING_CARROT
        
        redpacket_data['carrot'] = carrot
        redpacket_data['step'] = 'number'
        await update.message.reply_text("👥 请输入可领人数：\n（1 - 10000 之间）")
        return WAITING_NUMBER
    except ValueError:
        await update.message.reply_text("❌ 请输入有效的数字：")
        return WAITING_CARROT

async def handle_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理红包人数输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入人数: {text}")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    try:
        number = int(text)
        if number <= 0 or number > 10000:
            await update.message.reply_text("❌ 人数必须在1-10000之间，请重新输入：")
            return WAITING_NUMBER
        
        redpacket_data['number'] = number
        redpacket_data['step'] = 'blessing'
        await update.message.reply_text("💬 请输入祝福语（最多50字）：")
        return WAITING_BLESSING
    except ValueError:
        await update.message.reply_text("❌ 请输入有效的数字：")
        return WAITING_NUMBER

async def handle_blessing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理祝福语输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入祝福语")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    if len(text) > 50:
        await update.message.reply_text("❌ 祝福语不能超过50字，请重新输入：")
        return WAITING_BLESSING
    
    redpacket_data['blessing'] = text
    
    if redpacket_data['type'] == 'password':
        redpacket_data['step'] = 'password'
        await update.message.reply_text("🔑 请输入红包口令：")
        return WAITING_PASSWORD
    else:
        return await create_redpacket(update, context)

async def handle_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理口令输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入口令")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    redpacket_data['password'] = text
    
    return await create_redpacket(update, context)

async def handle_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理媒体上传（图片/音频）"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 上传媒体")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 会话已过期，请重新开始")
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
        redpacket_data['step'] = 'carrot'
        await update.message.reply_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）")
        return WAITING_CARROT
    
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
        redpacket_data['step'] = 'carrot'
        await update.message.reply_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）")
        return WAITING_CARROT
    else:
        await update.message.reply_text("❌ 请发送有效的媒体文件")
        return WAITING_MEDIA

async def create_redpacket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建红包API调用"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 数据不完整，请重新开始")
        return ConversationHandler.END
    
    data = context.user_data['redpacket']
    
    # 检查user_info是字典还是字符串
    if isinstance(user_info, dict):
        token = user_info.get('token')
    else:
        token = user_info
    
    if not token:
        await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END
    
    required_fields = ['carrot', 'number', 'blessing']
    missing = [f for f in required_fields if f not in data]
    if missing:
        await update.message.reply_text(f"❌ 数据不完整，缺少: {missing}，请重新开始")
        return ConversationHandler.END
    
    loading = await update.message.reply_text("🔄 正在创建红包...")
    
    try:
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        # 根据用户选择的红包类型设置类型
        if data.get('type') == 'random':
            redpacket_type = "random"
            redpacket_text = None
        elif data.get('type') == 'password':
            redpacket_type = "password"
            redpacket_text = data.get('password', None)
        elif data.get('type') == 'image':
            redpacket_type = "fixed"
            redpacket_text = None
        elif data.get('type') == 'audio':
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
            
            # 根据红包类型显示不同的标签
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
            
            message = (
                f"✅ 红包创建成功！\n\n"
                f"{redpacket_type_display}\n"
                f"💰 金额: {data['carrot']} 萝卜\n"
                f"👥 人数: {data['number']}\n"
                f"💬 祝福语: `{data['blessing']}`\n"
            )
            if redpacket_type == "password" and redpacket_text:
                message += f"🔑 口令: `{redpacket_text}`\n"
            if data.get('cover_url'):
                if data.get('file_type') == 'image':
                    message += f"🖼️ 封面: 已上传 ✓\n"
                elif data.get('file_type') == 'audio':
                    message += f"🎵 语音: 已上传 ✓\n"
            if result.get('red_packet_id'):
                message += f"🆔 红包ID: `{result['red_packet_id']}`\n"
            
            await loading.edit_text(message, parse_mode="Markdown")
        else:
            await loading.edit_text(f"❌ 创建失败，状态码：{response.status_code}")
            if response.text:
                logger.error(f"API返回: {response.text}")
    except Exception as e:
        logger.error(f"创建红包失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await loading.edit_text("❌ 创建失败，请稍后重试")
    
    # 清理数据
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
