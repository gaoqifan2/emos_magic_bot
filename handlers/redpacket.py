import logging
import requests
import random
import html
import textwrap
import asyncio
from io import BytesIO
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

# # 代理配置
# proxies = {
#     "http": "http://127.0.0.1:7890",
#     "https": "http://127.0.0.1:7890"
# }

# 对话状态 (从1开始，避免与 ConversationHandler.END=0 冲突)
WAITING_TYPE, WAITING_RECEIVE, WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD, WAITING_MEDIA, WAITING_SCENE, WAITING_CUSTOM_BLESSING, WAITING_BUBBLE_TEXT = range(1, 11)

# 步骤顺序，用于返回上一步
STEP_ORDER = ['type', 'receive', 'carrot', 'number', 'blessing', 'password', 'media']

def get_media_cache_entry(uploaded_files, file_id):
    """兼容旧的 url 字符串缓存和新的结构化缓存。"""
    cached = uploaded_files.get(file_id)
    if isinstance(cached, dict):
        return cached
    if cached:
        return {"url": cached}
    return None

def set_media_cache_entry(uploaded_files, file_id, url, file_type, api_file_id=None):
    uploaded_files[file_id] = {
        "url": url,
        "file_type": file_type,
        "api_file_id": api_file_id
    }

def update_media_cache_file_id(context, telegram_file_id, api_file_id):
    if not telegram_file_id or not api_file_id:
        return
    uploaded_files = context.user_data.get('uploaded_files', {})
    cached = get_media_cache_entry(uploaded_files, telegram_file_id)
    if cached:
        cached['api_file_id'] = api_file_id
        uploaded_files[telegram_file_id] = cached

def build_bubble_svg(text):
    lines = []
    for paragraph in text.splitlines() or [text]:
        wrapped = textwrap.wrap(paragraph, width=14) or ['']
        lines.extend(wrapped)
    lines = lines[:6]
    width = 760
    line_height = 48
    bubble_height = max(220, 120 + len(lines) * line_height)
    height = bubble_height + 100
    text_y = 92 + max(0, (bubble_height - 120 - len(lines) * line_height) // 2)
    tspans = []
    for index, line in enumerate(lines):
        escaped = html.escape(line)
        tspans.append(f'<tspan x="380" y="{text_y + index * line_height}">{escaped}</tspan>')
    joined_tspans = ''.join(tspans)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">
  <defs>
    <filter id="shadow" x="-20%" y="-20%" width="140%" height="140%">
      <feDropShadow dx="0" dy="8" stdDeviation="12" flood-color="#000000" flood-opacity="0.18"/>
    </filter>
  </defs>
  <rect width="100%" height="100%" rx="38" fill="#f7f3eb"/>
  <path d="M86 56 H674 Q714 56 714 96 V{bubble_height - 4} Q714 {bubble_height + 36} 674 {bubble_height + 36} H236 L160 {bubble_height + 84} L184 {bubble_height + 36} H86 Q46 {bubble_height + 36} 46 {bubble_height - 4} V96 Q46 56 86 56 Z" fill="#ffffff" filter="url(#shadow)"/>
  <path d="M86 56 H674 Q714 56 714 96 V{bubble_height - 4} Q714 {bubble_height + 36} 674 {bubble_height + 36} H236 L160 {bubble_height + 84} L184 {bubble_height + 36} H86 Q46 {bubble_height + 36} 46 {bubble_height - 4} V96 Q46 56 86 56 Z" fill="none" stroke="#efcf79" stroke-width="4"/>
  <text font-family="Microsoft YaHei, PingFang SC, Noto Sans CJK SC, Arial, sans-serif" font-size="34" font-weight="700" fill="#3d3122" text-anchor="middle">{joined_tspans}</text>
  <text x="380" y="{height - 32}" font-family="Arial, sans-serif" font-size="20" fill="#b08b3f" text-anchor="middle">EMOS RED PACKET</text>
</svg>'''

async def create_bubble_cover(update, context, text):
    user_id = update.effective_user.id
    image_data = build_bubble_png(text)
    file_name = f"redpacket_bubble_{user_id}_{datetime.now(beijing_tz).strftime('%Y%m%d%H%M%S')}.png"
    return await upload_r2_async(image_data, file_name, "redpacket")

async def upload_r2_async(file_data, file_name, folder):
    return await asyncio.wait_for(
        asyncio.to_thread(r2_client.upload_file, file_data, file_name, folder),
        timeout=30
    )

def get_bubble_font(size):
    from PIL import ImageFont
    font_paths = [
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for font_path in font_paths:
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            continue
    return ImageFont.load_default()

def build_bubble_png(text):
    from PIL import Image, ImageDraw

    lines = []
    for paragraph in text.splitlines() or [text]:
        wrapped = textwrap.wrap(paragraph, width=14) or ['']
        lines.extend(wrapped)
    lines = lines[:6]

    width = 760
    line_height = 58
    height = max(360, 150 + len(lines) * line_height)
    image = Image.new("RGB", (width, height), (255, 255, 255))
    draw = ImageDraw.Draw(image)

    font = get_bubble_font(42)
    total_text_height = len(lines) * line_height
    y = max(48, (height - total_text_height) // 2)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        draw.text(((width - text_width) // 2, y), line, font=font, fill=(0, 0, 0))
        y += line_height

    output = BytesIO()
    image.save(output, format="PNG", optimize=True)
    return output.getvalue()

async def delete_current_prompt_message(update, context):
    prompt_message = context.user_data.pop('current_prompt_message', None)
    if not prompt_message:
        return
    message_id = getattr(prompt_message, 'message_id', prompt_message)
    try:
        await context.bot.delete_message(
            chat_id=update.effective_chat.id,
            message_id=message_id
        )
    except Exception as e:
        logger.error(f"删除提示消息失败: {e}")

def get_redpacket_type_keyboard():
    keyboard = [
        [
            InlineKeyboardButton("🧧 普通", callback_data="type_random"),
            InlineKeyboardButton("🔐 口令", callback_data="type_password")
        ],
        [
            InlineKeyboardButton("🖼️ 图片", callback_data="type_image"),
            InlineKeyboardButton("🎵 语音", callback_data="type_audio")
        ],
        [
            InlineKeyboardButton("💬 气泡", callback_data="type_bubble"),
            InlineKeyboardButton("💝 私包", callback_data="type_private")
        ],
        [
            InlineKeyboardButton("🔙 返回红包菜单", callback_data="menu_redpacket_main")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

async def show_receive_choice(query, title="请选择领取方式："):
    keyboard = [
        [
            InlineKeyboardButton("⚖️ 均分", callback_data="receive_average"),
            InlineKeyboardButton("🎲 随机", callback_data="receive_random")
        ],
        [InlineKeyboardButton("⬅️ 返回类型", callback_data="back_type")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(title, reply_markup=reply_markup)
    return WAITING_RECEIVE

async def show_exclusive_choice(query, media_name):
    keyboard = [
        [
            InlineKeyboardButton("✅ 独占", callback_data="exclusive_yes"),
            InlineKeyboardButton("🚫 普通", callback_data="exclusive_no")
        ],
        [InlineKeyboardButton("⬅️ 返回类型", callback_data="back_type")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"{media_name}红包\n\n请选择展示方式：\n"
        "独占模式开启后，bot 只展示文件内容。",
        reply_markup=reply_markup
    )
    return WAITING_TYPE

async def show_attachment_choice(query, title):
    keyboard = [
        [InlineKeyboardButton("🚫 不加文件", callback_data="attach_none")],
        [
            InlineKeyboardButton("🖼️ 独占图片", callback_data="attach_image_exclusive"),
            InlineKeyboardButton("🎵 独占语音", callback_data="attach_audio_exclusive")
        ],
        [InlineKeyboardButton("⬅️ 返回类型", callback_data="back_type")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(
        f"{title}\n\n请选择展示内容：\n独占模式会让 bot 只显示你上传的文件内容。",
        reply_markup=reply_markup
    )
    return WAITING_TYPE

async def continue_after_attachment_choice(query, context):
    redpacket_data = context.user_data['redpacket']
    if redpacket_data.get('private'):
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("💝 私包\n\n💰 请输入红包金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    if redpacket_data.get('type') == 'password':
        return await show_receive_choice(query, "🔐 口令红包\n\n请选择领取方式：")
    return await show_receive_choice(query, "🧧 普通红包\n\n请选择领取方式：")

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
    
    reply_markup = get_redpacket_type_keyboard()
    
    message_text = "🧧 创建红包\n\n请选择类型："
    
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
        redpacket_data['has_password'] = False
        redpacket_data['current_step'] = 'attachment_choice'
        return await show_attachment_choice(query, "🧧 普通红包")
    elif data == 'type_password':
        redpacket_data['type'] = 'password'
        redpacket_data['has_password'] = True
        redpacket_data['current_step'] = 'attachment_choice'
        return await show_attachment_choice(query, "🔐 口令红包")
    elif data == 'type_image':
        redpacket_data['type'] = 'image'
        redpacket_data['current_step'] = 'password_choice'
        # 显示口令选择菜单
        keyboard = [
            [
                InlineKeyboardButton("🚫 无口令", callback_data="image_no_password"),
                InlineKeyboardButton("🔐 有口令", callback_data="image_with_password")
            ],
            [InlineKeyboardButton("⬅️ 返回类型", callback_data="back_type")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🖼️ 图片红包\n\n请选择是否需要口令：", reply_markup=reply_markup)
        return WAITING_TYPE
    elif data == 'type_audio':
        redpacket_data['type'] = 'audio'
        redpacket_data['current_step'] = 'password_choice'
        # 显示口令选择菜单
        keyboard = [
            [
                InlineKeyboardButton("🚫 无口令", callback_data="audio_no_password"),
                InlineKeyboardButton("🔐 有口令", callback_data="audio_with_password")
            ],
            [InlineKeyboardButton("⬅️ 返回类型", callback_data="back_type")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎵 语音红包\n\n请选择是否需要口令：", reply_markup=reply_markup)
        return WAITING_TYPE
    elif data == 'type_bubble':
        redpacket_data['type'] = 'image'
        redpacket_data['file_type'] = 'image'
        redpacket_data['bubble_mode'] = True
        redpacket_data['is_exclusive'] = True
        redpacket_data['current_step'] = 'password_choice'
        keyboard = [
            [
                InlineKeyboardButton("🚫 无口令", callback_data="bubble_no_password"),
                InlineKeyboardButton("🔐 有口令", callback_data="bubble_with_password")
            ],
            [InlineKeyboardButton("⬅️ 返回类型", callback_data="back_type")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("💬 气泡红包\n\n请选择是否需要口令：", reply_markup=reply_markup)
        return WAITING_TYPE
    elif data == 'type_private':
        redpacket_data['type'] = 'password'
        redpacket_data['has_password'] = True
        redpacket_data['private'] = True
        redpacket_data['current_step'] = 'attachment_choice'
        return await show_attachment_choice(query, "💝 私包")
    elif data == 'attach_none':
        redpacket_data['attachment_required'] = False
        redpacket_data.pop('expected_file_type', None)
        redpacket_data.pop('is_exclusive', None)
        return await continue_after_attachment_choice(query, context)
    elif data in ('attach_image_exclusive', 'attach_audio_exclusive'):
        expected_file_type = 'image' if data == 'attach_image_exclusive' else 'audio'
        redpacket_data['attachment_required'] = True
        redpacket_data['expected_file_type'] = expected_file_type
        redpacket_data['file_type'] = expected_file_type
        redpacket_data['is_exclusive'] = True
        return await continue_after_attachment_choice(query, context)
    elif data == 'image_no_password':
        redpacket_data['has_password'] = False
        redpacket_data['current_step'] = 'exclusive'
        return await show_exclusive_choice(query, "🖼️ 图片")
    elif data == 'image_with_password':
        redpacket_data['has_password'] = True
        redpacket_data['current_step'] = 'exclusive'
        return await show_exclusive_choice(query, "🖼️ 图片")
    elif data == 'audio_no_password':
        redpacket_data['has_password'] = False
        redpacket_data['current_step'] = 'exclusive'
        return await show_exclusive_choice(query, "🎵 语音")
    elif data == 'audio_with_password':
        redpacket_data['has_password'] = True
        redpacket_data['current_step'] = 'exclusive'
        return await show_exclusive_choice(query, "🎵 语音")
    elif data == 'bubble_no_password':
        redpacket_data['has_password'] = False
        redpacket_data['is_exclusive'] = True
        redpacket_data['current_step'] = 'receive'
        return await show_receive_choice(query, "💬 气泡红包 - 无口令\n\n请选择领取方式：")
    elif data == 'bubble_with_password':
        redpacket_data['has_password'] = True
        redpacket_data['is_exclusive'] = True
        redpacket_data['current_step'] = 'receive'
        return await show_receive_choice(query, "💬 气泡红包 - 有口令\n\n请选择领取方式：")
    elif data in ('exclusive_yes', 'exclusive_no'):
        redpacket_data['is_exclusive'] = data == 'exclusive_yes'
        redpacket_data['current_step'] = 'receive'
        media_name = "图片" if redpacket_data.get('type') == 'image' else "语音"
        mode_name = "独占模式" if redpacket_data['is_exclusive'] else "普通展示"
        return await show_receive_choice(query, f"{media_name}红包 - {mode_name}\n\n请选择领取方式：")
    elif data == 'receive_average':
        redpacket_data['receive'] = 'average'
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CARROT
    elif data == 'receive_random':
        redpacket_data['receive'] = 'random'
        redpacket_data['current_step'] = 'carrot'
        message = await query.edit_message_text("💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）", reply_markup=get_step_keyboard('carrot'))
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
                InlineKeyboardButton("🧧 创建红包", callback_data="menu_redpocket")
            ],
            [
                InlineKeyboardButton("📋 我发的红包", callback_data="my_redpackets"),
                InlineKeyboardButton("🔎 ID 查询", callback_data="input_id")
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
        await query.edit_message_text("🧧 创建红包\n\n请选择类型：", reply_markup=get_redpacket_type_keyboard())
        return WAITING_TYPE
    elif prev_step == 'receive':
        redpacket_data['current_step'] = 'receive'
        return await show_receive_choice(query)
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
        
        await delete_current_prompt_message(update, context)
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
        if redpacket_data['type'] in ['image', 'audio'] and not redpacket_data.get('bubble_mode'):
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
        
        await delete_current_prompt_message(update, context)
        redpacket_data['number'] = number
        redpacket_data['current_step'] = 'blessing'
        
        # 图片/语音红包提示可以上传媒体
        if redpacket_data['type'] in ['image', 'audio'] and not redpacket_data.get('bubble_mode'):
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
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    if len(text) > 50:
        message = await update.message.reply_text("⚠️ 祝福语不能超过50字，请重新输入：", reply_markup=get_step_keyboard('blessing'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BLESSING
    
    await delete_current_prompt_message(update, context)
    redpacket_data['blessing'] = text
    if redpacket_data.get('bubble_mode'):
        redpacket_data['current_step'] = 'password' if redpacket_data.get('has_password') else 'bubble_text'
    else:
        redpacket_data['current_step'] = 'password' if redpacket_data.get('has_password') or redpacket_data['type'] == 'password' else 'media' if redpacket_data['type'] in ['image', 'audio'] else 'complete'
    
    if redpacket_data.get('bubble_mode') and not redpacket_data.get('has_password'):
        message = await update.message.reply_text("💬 请输入要生成气泡图片的文字（最多80字）：", reply_markup=get_step_keyboard('media'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BUBBLE_TEXT
    elif redpacket_data['type'] == 'password':
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
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    await delete_current_prompt_message(update, context)
    redpacket_data['password'] = text
    redpacket_data['current_step'] = 'bubble_text' if redpacket_data.get('bubble_mode') else 'media' if redpacket_data['type'] in ['image', 'audio'] else 'complete'
    
    if redpacket_data.get('bubble_mode'):
        message = await update.message.reply_text("💬 请输入要生成气泡图片的文字（最多80字）：", reply_markup=get_step_keyboard('media'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BUBBLE_TEXT
    elif redpacket_data['type'] in ['image', 'audio']:
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
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    expected_file_type = redpacket_data.get('expected_file_type')
    
    # 检查文件类型
    if update.message.photo:
        if expected_file_type == 'audio':
            await update.message.reply_text("❌ 当前选择的是独占语音，请发送语音或音频文件")
            return WAITING_MEDIA
        # 处理图片
        photo = update.message.photo[-1]
        file_id = photo.file_id
        
        cached_file = get_media_cache_entry(context.user_data['uploaded_files'], file_id)
        if cached_file:
            cover_url = cached_file.get('url')
            redpacket_data['file_id'] = cached_file.get('api_file_id')
            await update.message.reply_text("✅ 使用已上传的图片！")
        else:
            loading = await update.message.reply_text("🔄 正在上传图片到云端...")
            try:
                file = await context.bot.get_file(file_id)
                file_data = await file.download_as_bytearray()
                file_name = f"redpacket_{user_id}_{file_id}.jpg"
                
                logger.info(f"开始上传图片: {file_name}, 大小: {len(file_data)} bytes")
                cover_url = await upload_r2_async(bytes(file_data), file_name, "redpacket")
                logger.info(f"图片上传成功: {cover_url}")
                
                set_media_cache_entry(context.user_data['uploaded_files'], file_id, cover_url, 'image')
                await loading.edit_text("✅ 图片上传成功！")
            except Exception as e:
                logger.error(f"上传图片失败: {e}")
                await loading.edit_text("❌ 图片上传失败，请稍后重试")
                return WAITING_MEDIA
        
        redpacket_data['cover_url'] = cover_url
        redpacket_data['file_type'] = 'image'
        redpacket_data['telegram_file_id'] = file_id
        redpacket_data['current_step'] = 'complete'
        await delete_current_prompt_message(update, context)
        
        # 根据当前步骤继续
        return await continue_after_media(update, context)
    
    elif update.message.voice or update.message.audio or update.message.document:
        if expected_file_type == 'image':
            await update.message.reply_text("❌ 当前选择的是独占图片，请发送图片")
            return WAITING_MEDIA
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
        
        cached_file = get_media_cache_entry(context.user_data['uploaded_files'], file_id)
        if cached_file:
            audio_url = cached_file.get('url')
            redpacket_data['file_id'] = cached_file.get('api_file_id')
            await update.message.reply_text("✅ 使用已上传的音频！")
        else:
            loading = await update.message.reply_text("🔄 正在上传音频到云端...")
            try:
                file = await context.bot.get_file(file_id)
                file_data = await file.download_as_bytearray()
                file_name = f"redpacket_{user_id}_{file_id}.{file_extension}"
                
                logger.info(f"开始上传音频: {file_name}, 大小: {len(file_data)} bytes")
                audio_url = await upload_r2_async(bytes(file_data), file_name, "redpacket")
                logger.info(f"音频上传成功: {audio_url}")
                
                set_media_cache_entry(context.user_data['uploaded_files'], file_id, audio_url, 'audio')
                await loading.edit_text("✅ 音频上传成功！")
            except Exception as e:
                logger.error(f"上传音频失败: {e}")
                await loading.edit_text("❌ 音频上传失败，请稍后重试")
                return WAITING_MEDIA
        
        redpacket_data['cover_url'] = audio_url
        redpacket_data['file_type'] = 'audio'
        redpacket_data['telegram_file_id'] = file_id
        redpacket_data['current_step'] = 'complete'
        await delete_current_prompt_message(update, context)
        
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

async def handle_bubble_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理气泡红包文字并生成图片封面"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    logger.info(f"用户 {user_id} 输入气泡文字")
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    if not text:
        message = await update.message.reply_text("⚠️ 气泡文字不能为空，请重新输入：", reply_markup=get_step_keyboard('media'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BUBBLE_TEXT
    if len(text) > 80:
        message = await update.message.reply_text("⚠️ 气泡文字不能超过80字，请重新输入：", reply_markup=get_step_keyboard('media'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BUBBLE_TEXT
    
    await delete_current_prompt_message(update, context)
    loading = await update.message.reply_text("🔄 正在生成气泡图片...")
    try:
        cover_url = await create_bubble_cover(update, context, text)
        redpacket_data['bubble_text'] = text
        redpacket_data['cover_url'] = cover_url
        redpacket_data['file_type'] = 'image'
        redpacket_data['is_exclusive'] = True
        redpacket_data['current_step'] = 'complete'
        await loading.edit_text("✅ 气泡图片生成成功！")
        return await create_redpacket(update, context)
    except Exception as e:
        logger.error(f"生成气泡图片失败: {e}")
        await loading.edit_text("❌ 气泡图片生成失败，请稍后重试")
        message = await update.message.reply_text("💬 请重新输入气泡文字：", reply_markup=get_step_keyboard('media'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_BUBBLE_TEXT

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

    if data.get('attachment_required') and not (data.get('cover_url') or data.get('file_id')):
        data['current_step'] = 'media'
        media_type = "图片" if data.get('expected_file_type') == 'image' else "语音"
        prompt_text = f"👁️ 独占模式已开启\n\n请发送{media_type}内容："
        if update.message:
            message = await update.message.reply_text(prompt_text, reply_markup=get_step_keyboard('media'))
        else:
            message = await update.callback_query.message.reply_text(prompt_text, reply_markup=get_step_keyboard('media'))
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_MEDIA
    
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
        
        if data.get('type') == 'password' or data.get('has_password') or data.get('private'):
            redpacket_type = "password"
            redpacket_text = data.get('password', None)
        else:
            redpacket_type = "default"
            redpacket_text = None
        
        receive_type = data.get('receive', 'average') if not data.get('private') else 'average'
        
        payload = {
            "type": redpacket_type,
            "receive": receive_type,
            "carrot": data['carrot'],
            "number": data['number'],
            "blessing": data['blessing'],
            "text": redpacket_text
        }

        if data.get('file_id'):
            payload["file_id"] = data['file_id']
            payload["file_type"] = data.get('file_type')
        elif data.get('cover_url'):
            payload["file_url"] = data['cover_url']
            payload["file_type"] = data.get('file_type')

        if data.get('cover_url') or data.get('file_id'):
            payload["is_exclusive"] = bool(data.get('is_exclusive', False))
        
        logger.info(
            f"创建红包: type={redpacket_type}, receive={receive_type}, "
            f"file_type={data.get('file_type')}, exclusive={data.get('is_exclusive', False)}, "
            f"carrot={data['carrot']}, number={data['number']}"
        )
        
        response = requests.post(
            Config.REDPACKET_CREATE_URL,
            json=payload,
            headers=headers,
            timeout=10,
            # proxies=proxies 已删除
        )
        
        if response.status_code == 200:
            result = response.json()
            logger.info(f"API返回结果: {result}")
            
            file_info = result.get('file')
            api_file_id = result.get('file_id') or result.get('fileId')
            if not api_file_id and isinstance(file_info, dict):
                api_file_id = file_info.get('id') or file_info.get('file_id')
            update_media_cache_file_id(context, data.get('telegram_file_id'), api_file_id)

            red_packet_id = result.get('red_packet_id')
            if red_packet_id:
                try:
                    from app.database import add_redpacket_record
                    add_redpacket_record(
                        telegram_id=user_id,
                        user_id=(user_info or {}).get('user_id') if isinstance(user_info, dict) else None,
                        username=(user_info or {}).get('username') if isinstance(user_info, dict) else None,
                        red_packet_id=red_packet_id,
                        redpacket_type='bubble' if data.get('bubble_mode') else redpacket_type,
                        receive_type=receive_type,
                        carrot=data.get('carrot', 0),
                        number=data.get('number', 0),
                        blessing=data.get('blessing'),
                        password_text=redpacket_text,
                        file_type=data.get('file_type'),
                        is_exclusive=bool(data.get('is_exclusive', False)),
                    )
                except Exception as e:
                    logger.error(f"保存红包记录失败: {e}")
            
            if data.get('bubble_mode'):
                redpacket_type_display = "💬 气泡红包"
            elif data.get('file_type') == 'image':
                redpacket_type_display = "🖼️ 图片红包"
            elif data.get('file_type') == 'audio':
                redpacket_type_display = "🎵 语音红包"
            elif redpacket_type == "password":
                redpacket_type_display = "🔐 口令红包"
            else:
                redpacket_type_display = "🎲 普通红包"
            
            # 获取用户余额 - 使用user接口获取
            balance = 0
            try:
                user_response = requests.get(
                    Config.API_USER_ENDPOINT,
                    headers=headers,
                    timeout=5,
                    # proxies=proxies 已删除
                )
                if user_response.status_code == 200:
                    user_data = user_response.json()
                    balance = user_data.get('carrot', 0)
            except Exception as e:
                logger.error(f"获取用户余额失败: {e}")
            
            receive_display = "⚖️ 均分模式" if receive_type == 'average' else "🎲 随机模式"
            
            message = (
                f"#红包凭证\n\n"
                f"✅ 红包创建成功！\n\n"
                f"{redpacket_type_display}\n"
                f"{receive_display}\n"
                f"💰 金额: {data['carrot']} 萝卜\n"
                f"👥 人数: {data['number']}\n"
                f"💬 祝福语: `{data['blessing']}`\n"
                f"💎 当前余额: {balance} 萝卜\n"
            )
            if redpacket_text:
                message += f"🔑 口令: `{redpacket_text}`\n"
            if data.get('cover_url') or data.get('file_id'):
                if data.get('file_type') == 'image':
                    message += f"🖼️ 封面: 已上传 ✓\n"
                elif data.get('file_type') == 'audio':
                    message += f"🎵 语音: 已上传 ✓\n"
                if data.get('bubble_mode'):
                    message += f"💬 气泡: 已生成 ✓\n"
                if data.get('is_exclusive'):
                    message += f"👁️ 展示: 独占模式\n"
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
            
            action_text = "请选择后续操作："
            
            # 凭证和操作按钮分开发，返回/再创建不会把凭证一起改没。
            try:
                await loading.edit_text(message, parse_mode="Markdown")
                await loading.reply_text(action_text, reply_markup=reply_markup)
            except Exception as edit_error:
                logger.error(f"编辑消息失败: {edit_error}")
                # 尝试发送新消息
                if update.message:
                    await update.message.reply_text(message, parse_mode="Markdown")
                    await update.message.reply_text(action_text, reply_markup=reply_markup)
                else:
                    await update.callback_query.message.reply_text(message, parse_mode="Markdown")
                    await update.callback_query.message.reply_text(action_text, reply_markup=reply_markup)
        else:
            # 尝试编辑消息显示失败信息
            error_message = f"❌ 创建失败，状态码：{response.status_code}"
            # 尝试解析 API 返回的错误信息
            if response.text:
                try:
                    error_data = response.json()
                    if 'error' in error_data:
                        # 翻译常见的错误信息
                        error_msg = error_data['error']
                        if error_msg == '红包口令重复':
                            error_message = "❌ 创建失败：红包口令重复，请使用其他口令"
                        elif error_msg == '余额不足':
                            error_message = "❌ 创建失败：余额不足，请先充值"
                        elif error_msg == '参数错误':
                            error_message = "❌ 创建失败：参数错误，请检查输入"
                        elif error_msg == '红包金额超出限制':
                            error_message = "❌ 创建失败：红包金额超出限制"
                        elif error_msg == '红包人数超出限制':
                            error_message = "❌ 创建失败：红包人数超出限制"
                        else:
                            error_message = f"❌ 创建失败：{error_msg}"
                except Exception:
                    # 如果解析失败，使用原始状态码
                    pass
                logger.error(f"API返回: {response.text}")
            
            try:
                await loading.edit_text(error_message)
            except Exception as edit_error:
                logger.error(f"编辑消息失败: {edit_error}")
                # 尝试发送新消息
                if update.message:
                    await update.message.reply_text(error_message)
                else:
                    await update.callback_query.message.reply_text(error_message)
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
        year = today.year
        month = today.month
        day = today.day
        
        logger.info(f"节日红包检查 - 当前日期: {today}, 年份: {year}, 月份: {month}, 日期: {day}")
        
        # 根据日期判断节日
        festival_blessings = []
        
        # 尝试联网获取节日信息
        festival_name = None
        try:
            # 使用第三方API获取节日信息
            import httpx
            url = f"https://api.vvhan.com/api/holiday?type=1&date={year}-{month:02d}-{day:02d}"
            response = httpx.get(url, timeout=5)
            if response.status_code == 200:
                data = response.json()
                if data.get('code') == 1:
                    festival_name = data.get('data', {}).get('name')
                    logger.info(f"联网获取节日信息成功: {festival_name}")
        except Exception as e:
            logger.error(f"联网获取节日信息失败: {e}")
        
        # 如果联网获取失败，使用本地判断
        if not festival_name:
            # 情人节 (2月14日)
            if month == 2 and day == 14:
                festival_name = "情人节"
            # 清明节 (4月4日-6日)
            elif month == 4 and 4 <= day <= 6:
                festival_name = "清明节"
            # 劳动节 (5月1日)
            elif month == 5 and day == 1:
                festival_name = "劳动节"
            # 国庆节 (10月1日)
            elif month == 10 and day == 1:
                festival_name = "国庆节"
            # 圣诞节 (12月25日)
            elif month == 12 and day == 25:
                festival_name = "圣诞节"
        
        logger.info(f"最终确定的节日: {festival_name}")
        
        # 根据节日名称生成祝福语
        if festival_name == "春节":
            festival_blessings = [
                "🧧 新年快乐！祝你在新的一年里万事如意！",
                "🎊 春节快乐！愿你阖家幸福，财源广进！",
                "🎉 新年大吉！愿你在新的一年里心想事成！",
                "✨ 新春快乐！愿你在新的一年里事业有成！",
                "🎈 过年好！愿你在新的一年里身体健康！"
            ]
        elif festival_name == "元宵节":
            festival_blessings = [
                "🏮 元宵节快乐！愿你团团圆圆，幸福美满！",
                "🎊 元宵佳节，愿你阖家欢乐，万事顺意！",
                "🎉 元宵节快乐！愿你在新的一年里事事如意！",
                "✨ 元宵快乐！愿你在新的一年里心想事成！",
                "🎈 元宵节到，愿你平安吉祥，幸福安康！"
            ]
        elif festival_name == "情人节":
            festival_blessings = [
                "💖 情人节快乐！愿你和爱人甜甜蜜蜜！",
                "💕 情人节快乐！愿你爱情美满，幸福长久！",
                "💝 情人节快乐！愿你和心爱的人永远在一起！",
                "🌹 情人节快乐！愿你的爱情如玫瑰般美丽！",
                "💌 情人节快乐！愿你收到心仪的人的表白！"
            ]
        elif festival_name == "清明节":
            festival_blessings = [
                "🌿 清明节安康！愿逝者安息，生者珍惜！",
                "🌸 清明时节，愿你缅怀先人，珍惜当下！",
                "🌱 清明节到，愿你心怀感恩，珍惜生活！",
                "🍃 清明安康！愿你在春天里收获希望！",
                "🌾 清明节快乐！愿你珍惜眼前人，过好每一天！"
            ]
        elif festival_name == "劳动节":
            festival_blessings = [
                "🏃 劳动节快乐！愿你工作顺利，生活愉快！",
                "💪 劳动节快乐！愿你在工作中收获成长！",
                "🎉 劳动节快乐！愿你在假期里好好休息！",
                "✨ 劳动节到，愿你劳逸结合，事半功倍！",
                "🎊 劳动节快乐！愿你在劳动中创造价值！"
            ]
        elif festival_name == "端午节":
            festival_blessings = [
                "🌿 端午节快乐！愿你端午安康，百病不侵！",
                "🐲 端午节快乐！愿你如龙般矫健，如粽般香甜！",
                "🏮 端午节到，愿你平安吉祥，幸福安康！",
                "🎉 端午节快乐！愿你在节日里收获快乐！",
                "✨ 端午安康！愿你在夏天里一切顺利！"
            ]
        elif festival_name == "中秋节":
            festival_blessings = [
                "🌙 中秋节快乐！愿你月圆人圆，事事圆满！",
                "🥮 中秋节快乐！愿你和家人团团圆圆！",
                "🎑 中秋节到，愿你阖家欢乐，幸福美满！",
                "✨ 中秋快乐！愿你在节日里收获团圆和快乐！",
                "🎊 中秋节快乐！愿你心想事成，万事如意！"
            ]
        elif festival_name == "国庆节":
            festival_blessings = [
                "🇨🇳 国庆节快乐！愿祖国繁荣昌盛！",
                "🎉 国庆节快乐！愿你在假期里玩得开心！",
                "✨ 国庆佳节，愿你和家人共度美好时光！",
                "🎊 国庆节到，愿你在假期里收获快乐！",
                "🏮 国庆节快乐！愿你生活美满，万事如意！"
            ]
        elif festival_name == "圣诞节":
            festival_blessings = [
                "🎅 圣诞节快乐！愿你收到心仪的礼物！",
                "🎄 圣诞节快乐！愿你在节日里收获快乐！",
                "🌟 圣诞节到，愿你和家人共度美好时光！",
                "✨ 圣诞快乐！愿你在新的一年里心想事成！",
                "🎊 圣诞节快乐！愿你生活美满，万事如意！"
            ]
        
        logger.info(f"节日红包检查 - 节日祝福列表: {festival_blessings}")
        
        if festival_blessings:
            # 当天是节日，使用节日祝福语
            redpacket_data['blessing'] = random.choice(festival_blessings)
            # 直接创建红包
            return await create_redpacket(update, context)
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
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("⚠️ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    # 检查祝福语长度
    if len(text) > 50:
        message = await update.message.reply_text("⚠️ 祝福语不能超过50字，请重新输入：")
        context.user_data['current_prompt_message'] = message.message_id
        return WAITING_CUSTOM_BLESSING
    
    await delete_current_prompt_message(update, context)
    # 存储祝福语
    redpacket_data['blessing'] = text
    
    # 直接创建红包
    return await create_redpacket(update, context)
