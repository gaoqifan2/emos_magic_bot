# handlers/redpacket.py
import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import user_tokens, Config
from handlers.common import add_cancel_button
from utils.r2_client import r2_client

logger = logging.getLogger(__name__)

# 对话状态
WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD = range(4)

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
        'step': 'carrot',
        'start_time': datetime.now().isoformat()
    }
    
    # 初始化上传文件缓存（如果不存在）
    if 'uploaded_files' not in context.user_data:
        context.user_data['uploaded_files'] = {}
    
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = (
        "🧧 创建红包\n\n"
        "💰 请输入红包总金额（萝卜）：\n"
        "（1 - 50000 之间）\n\n"
        "📸 提示：您可以发送图片作为红包封面，我们会自动上传到云端\n\n"
        "💡 使用 /cancel 可以随时取消"
    )
    
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    return WAITING_CARROT

async def redpocket_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理红包创建流程"""
    user_id = update.effective_user.id
    
    # ===== 详细调试日志 =====
    logger.info("=" * 50)
    logger.info(f"用户 {user_id} 触发 redpocket_process")
    
    # 检查是否有红包数据
    if 'redpacket' not in context.user_data:
        logger.warning(f"用户 {user_id} 的红包数据不存在")
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    current_step = redpacket_data.get('step', 'carrot')
    
    logger.info(f"用户 {user_id} 当前步骤: {current_step}")
    logger.info(f"消息类型: {'图片' if update.message.photo else '文本'}")
    
    # 处理图片上传
    if update.message.photo:
        logger.info(f"用户 {user_id} 发送了图片")
        return await handle_photo_upload(update, context)
    
    # 处理文本消息
    if not update.message.text:
        logger.warning(f"用户 {user_id} 发送了空消息")
        return WAITING_CARROT
    
    text = update.message.text.strip()
    logger.info(f"用户 {user_id} 发送文本: '{text}'")
    
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 正常流程处理
    if current_step == 'carrot':
        try:
            carrot = int(text)
            if carrot <= 0 or carrot > 50000:
                await update.message.reply_text("❌ 金额必须在1-50000之间，请重新输入：", reply_markup=reply_markup)
                return WAITING_CARROT
            redpacket_data['carrot'] = carrot
            redpacket_data['step'] = 'number'
            context.user_data['redpacket'] = redpacket_data
            logger.info(f"用户 {user_id} 设置金额: {carrot}")
            await update.message.reply_text(
                "👥 请输入可领人数：\n"
                "（1 - 1000 之间）\n\n"
                "📸 可以继续发送图片作为红包封面",
                reply_markup=reply_markup
            )
            return WAITING_NUMBER
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_CARROT
    
    elif current_step == 'number':
        try:
            number = int(text)
            if number <= 0 or number > 1000:
                await update.message.reply_text("❌ 人数必须在1-1000之间，请重新输入：", reply_markup=reply_markup)
                return WAITING_NUMBER
            redpacket_data['number'] = number
            redpacket_data['step'] = 'blessing'
            context.user_data['redpacket'] = redpacket_data
            logger.info(f"用户 {user_id} 设置人数: {number}")
            await update.message.reply_text(
                "💬 请输入祝福语（如：恭喜发财）：\n"
                "（最多50字）\n\n"
                "📸 可以继续发送图片作为红包封面",
                reply_markup=reply_markup
            )
            return WAITING_BLESSING
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_NUMBER
    
    elif current_step == 'blessing':
        if len(text) > 50:
            await update.message.reply_text("❌ 祝福语不能超过50字，请重新输入：", reply_markup=reply_markup)
            return WAITING_BLESSING
        redpacket_data['blessing'] = text
        redpacket_data['step'] = 'password'
        context.user_data['redpacket'] = redpacket_data
        logger.info(f"用户 {user_id} 设置祝福语: {text}")
        await update.message.reply_text(
            "🔑 请输入红包口令：\n\n"
            "📸 这是最后一步，还可以发送图片作为红包封面",
            reply_markup=reply_markup
        )
        return WAITING_PASSWORD
    
    elif current_step == 'password':
        logger.info(f"用户 {user_id} 进入口令步骤，输入: '{text}'")
        
        token = user_tokens.get(user_id)
        if not token:
            await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
            return ConversationHandler.END
        
        # 必须输入口令，不能为空
        if not text:
            await update.message.reply_text("❌ 口令不能为空，请重新输入：", reply_markup=reply_markup)
            return WAITING_PASSWORD
        
        password = text
        password_text = text
        
        redpacket_data['password'] = password
        redpacket_data['password_text'] = password_text
        context.user_data['redpacket'] = redpacket_data
        
        return await create_redpacket(update, context)
    
    return ConversationHandler.END

async def handle_photo_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理图片上传 - 带 file_id 缓存"""
    user_id = update.effective_user.id
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 请先开始创建红包")
        return WAITING_CARROT
    
    # 初始化上传文件缓存
    if 'uploaded_files' not in context.user_data:
        context.user_data['uploaded_files'] = {}
    
    loading = await update.message.reply_text("🔄 正在上传图片到云端...")
    
    try:
        # 获取图片
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        # 检查是否已经上传过相同的图片
        if file_id in context.user_data['uploaded_files']:
            cover_url = context.user_data['uploaded_files'][file_id]
            logger.info(f"用户 {user_id} 使用缓存的图片: {file_id}")
            await loading.edit_text("✅ 使用已上传的图片！")
        else:
            # 上传到R2
            file = await context.bot.get_file(file_id)
            file_data = await file.download_as_bytearray()
            
            file_name = f"redpacket_{user_id}_{file_id}.jpg"
            cover_url = r2_client.upload_file(bytes(file_data), file_name, "redpacket")
            
            # 缓存图片URL
            context.user_data['uploaded_files'][file_id] = cover_url
            logger.info(f"用户 {user_id} 上传新图片: {file_id}")
            await loading.edit_text("✅ 图片上传成功！")
        
        # 保存图片URL
        context.user_data['redpacket']['cover_url'] = cover_url
        context.user_data['redpacket']['file_id'] = file_id
        
        # 根据当前步骤返回相应的提示
        current_step = context.user_data['redpacket'].get('step', 'carrot')
        step_messages = {
            'carrot': "💰 请继续输入红包金额：",
            'number': "👥 请继续输入可领人数：",
            'blessing': "💬 请继续输入祝福语：",
            'password': "🔑 请继续输入口令："
        }
        
        keyboard = add_cancel_button([[]])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(step_messages.get(current_step, "请继续"), reply_markup=reply_markup)
        
    except Exception as e:
        logger.error(f"上传图片失败: {e}")
        await loading.edit_text("❌ 图片上传失败，请稍后重试")
    
    # 返回当前状态对应的常量
    step_to_state = {
        'carrot': WAITING_CARROT,
        'number': WAITING_NUMBER,
        'blessing': WAITING_BLESSING,
        'password': WAITING_PASSWORD
    }
    return step_to_state.get(context.user_data['redpacket'].get('step', 'carrot'), WAITING_CARROT)

async def create_redpacket(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建红包API调用 - 使用正确的API格式"""
    user_id = update.effective_user.id
    token = user_tokens.get(user_id)
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 数据不完整，请重新开始")
        return ConversationHandler.END
    
    data = context.user_data['redpacket']
    
    logger.info(f"用户 {user_id} 开始创建红包，数据: {data}")
    
    if not token:
        await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END
    
    # 检查必要字段
    required_fields = ['carrot', 'number', 'blessing', 'password']
    missing = [f for f in required_fields if f not in data]
    if missing:
        await update.message.reply_text(f"❌ 数据不完整，缺少: {missing}，请重新开始")
        return ConversationHandler.END
    
    loading = await update.message.reply_text("🔄 正在创建红包...")
    
    try:
        headers = {"Authorization": f"Bearer {token}"}
        
        # 正确的 payload 格式（根据API文档）
        payload = {
            "type": "password",
            "carrot": data['carrot'],
            "number": data['number'],
            "blessing": data['blessing'],
            "text": data['password'],  # 口令字段名是 text
            "file_id_image": data.get('file_id'),  # 文件ID（如果有）
            "file_url": data.get('cover_url')  # 图片URL
        }
        
        logger.info(f"用户 {user_id} 发送红包请求: {payload}")
        
        response = requests.post(
            Config.REDPACKET_CREATE_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        logger.info(f"用户 {user_id} 红包API响应状态码: {response.status_code}")
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"用户 {user_id} 红包API响应: {result}")
            
            message = (
                f"✅ 红包创建成功！\n\n"
                f"💰 金额: {data['carrot']} 萝卜\n"
                f"👥 人数: {data['number']}\n"
                f"💬 祝福语: {data['blessing']}\n"
                f"🔑 口令: {data['password']}\n"
            )
            if data.get('cover_url'):
                message += f"🖼️ 封面: 已上传 ✓\n"
            if result.get('red_packet_id'):
                message += f"🆔 红包ID: {result['red_packet_id']}\n"
                message += f"📊 查询: /check_redpacket {result['red_packet_id']}\n"
            
            await loading.edit_text(message)
        else:
            # 显示更详细的错误信息
            error_text = f"❌ 创建失败，状态码：{response.status_code}"
            try:
                error_detail = response.json()
                error_text += f"\n错误详情: {error_detail}"
            except:
                error_text += f"\n{response.text}"
            await loading.edit_text(error_text)
            
    except Exception as e:
        logger.error(f"用户 {user_id} 创建红包失败: {e}")
        await loading.edit_text("❌ 创建失败，请稍后重试")
    
    # 清理数据（保留上传文件缓存供以后使用）
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    return ConversationHandler.END

async def cancel_redpacket(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消红包创建"""
    user_id = update.effective_user.id
    # 清理红包数据但保留上传文件缓存
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    await update.message.reply_text("❌ 红包创建已取消")
    return ConversationHandler.END