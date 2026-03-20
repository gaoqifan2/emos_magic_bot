#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试语音红包功能
"""

import logging
import asyncio
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ConversationHandler, filters, ContextTypes

# 北京时间 UTC+8
beijing_tz = timezone(timedelta(hours=8))

# 导入必要的模块
from config import Config, user_tokens
from utils.r2_client import r2_client
from utils.message_utils import auto_delete_message

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 对话状态
WAITING_REDPACKET_TYPE, WAITING_CARROT = range(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始命令"""
    await update.message.reply_text("欢迎测试语音红包功能！")

async def redpocket_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始创建红包"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 开始创建红包")
    
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
        [InlineKeyboardButton("🎵 语音红包", callback_data="redpacket_type_audio")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = "🧧 创建红包\n\n请选择红包类型："
    
    message = await update.message.reply_text(message_text, reply_markup=reply_markup)
    return WAITING_REDPACKET_TYPE

async def redpocket_process(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理红包创建流程"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 触发 redpocket_process")
    
    if 'redpacket' not in context.user_data:
        logger.warning(f"用户 {user_id} 的红包数据不存在")
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    redpacket_data = context.user_data['redpacket']
    
    # 检查是否有回调数据（处理红包类型选择）
    if update.callback_query:
        callback_data = update.callback_query.data
        await update.callback_query.answer()
        
        if callback_data.startswith('redpacket_type_'):
            # 处理红包类型选择
            redpacket_type = callback_data.split('redpacket_type_')[1]
            logger.info(f"用户 {user_id} 选择了红包类型: {redpacket_type}")
            
            redpacket_data['type'] = redpacket_type
            
            # 语音红包：要求用户上传语音
            if redpacket_type == 'audio':
                message = await update.callback_query.edit_message_text(
                    "🎵 请发送语音作为红包内容：\n\n💡 使用 /cancel 可以随时取消"
                )
                return WAITING_CARROT
    
    # 处理语音上传
    if update.message.voice:
        logger.info(f"用户 {user_id} 发送了语音")
        return await handle_audio_upload(update, context)
    
    return WAITING_CARROT

async def handle_audio_upload(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理语音上传"""
    user_id = update.effective_user.id
    
    if 'redpacket' not in context.user_data:
        await update.message.reply_text("❌ 请先开始创建红包")
        return WAITING_CARROT
    
    loading = await update.message.reply_text("🔄 正在上传语音到云端...")
    
    try:
        voice = update.message.voice
        file_id = voice.file_id
        
        if file_id in context.user_data['uploaded_files']:
            audio_url = context.user_data['uploaded_files'][file_id]
            await loading.edit_text("✅ 使用已上传的语音！")
        else:
            # 检查R2客户端状态
            if not r2_client:
                logger.error("R2客户端未初始化")
                await loading.edit_text("❌ 语音上传服务未初始化，请稍后重试")
                return WAITING_CARROT
            
            # 检查R2客户端内部状态
            if not hasattr(r2_client, 'client') or not r2_client.client:
                logger.error("R2客户端内部client未初始化")
                await loading.edit_text("❌ 语音上传服务未就绪，请稍后重试")
                return WAITING_CARROT
            
            file = await context.bot.get_file(file_id)
            file_data = await file.download_as_bytearray()
            file_name = f"redpacket_{user_id}_{file_id}.ogg"
            
            logger.info(f"开始上传语音: {file_name}, 大小: {len(file_data)} bytes")
            audio_url = r2_client.upload_file(bytes(file_data), file_name, "redpacket")
            logger.info(f"语音上传成功: {audio_url}")
            
            context.user_data['uploaded_files'][file_id] = audio_url
            await loading.edit_text("✅ 语音上传成功！")
        
        context.user_data['redpacket']['cover_url'] = audio_url
        context.user_data['redpacket']['file_type'] = 'audio'
        
        # 语音上传后直接进入金额输入
        redpacket_data = context.user_data['redpacket']
        redpacket_data['step'] = 'carrot'
        
        message = await update.message.reply_text(
            "💰 请输入红包总金额（萝卜）：\n（1 - 60000 之间）\n\n💡 使用 /cancel 可以随时取消"
        )
        
    except Exception as e:
        logger.error(f"上传语音失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        await loading.edit_text("❌ 语音上传失败，请稍后重试")
    
    return WAITING_CARROT

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消操作"""
    if 'redpacket' in context.user_data:
        del context.user_data['redpacket']
    await update.message.reply_text("❌ 操作已取消")
    return ConversationHandler.END

def main() -> None:
    """主函数"""
    logger.info("正在启动测试机器人...")
    
    # 创建应用
    application = Application.builder() \
        .token(Config.BOT_TOKEN) \
        .build()
    
    # ===== 基本命令 =====
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # ===== 红包对话 =====
    redpocket_conv = ConversationHandler(
        entry_points=[
            CommandHandler("redpocket", redpocket_command)
        ],
        states={
            WAITING_REDPACKET_TYPE: [
                CallbackQueryHandler(redpocket_process, pattern="^redpacket_type_")
            ],
            WAITING_CARROT: [
                MessageHandler(filters.VOICE, redpocket_process),
                CommandHandler("cancel", cancel_command)
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    application.add_handler(redpocket_conv)
    
    # 打印启动信息
    print("=" * 60)
    print("测试机器人启动成功！")
    print("=" * 60)
    print("可用命令：")
    print("   /start       - 开始")
    print("   /redpocket   - 创建红包")
    print("   /cancel      - 取消操作")
    print("=" * 60)
    print(f"机器人 @{Config.BOT_USERNAME}")
    print("=" * 60)
    
    logger.info(f"测试机器人 @{Config.BOT_USERNAME} 启动成功")
    
    # 启动机器人
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
