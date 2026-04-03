#!/usr/bin/env python3
"""
消息工具函数
"""

import asyncio
from telegram import Update
from telegram.ext import ContextTypes
from utils.http_client import http_client

async def auto_delete_message(update: Update, context: ContextTypes.DEFAULT_TYPE, message, delay: int = 5):
    """
    自动删除消息
    
    Args:
        update: Update对象
        context: Context对象
        message: 要删除的消息对象
        delay: 延迟时间（秒），默认5秒
    """
    await asyncio.sleep(delay)
    try:
        if message:
            # 对于普通消息，使用delete_message删除
            await context.bot.delete_message(
                chat_id=message.chat_id,
                message_id=message.message_id
            )
        elif update.callback_query:
            # 对于回调查询，删除回调消息
            await context.bot.delete_message(
                chat_id=update.callback_query.message.chat_id,
                message_id=update.callback_query.message.message_id
            )
        elif update.message:
            # 对于普通消息，删除消息
            await context.bot.delete_message(
                chat_id=update.message.chat_id,
                message_id=update.message.message_id
            )
    except Exception as e:
        # 忽略删除失败的错误
        pass

async def auto_replace_message(update: Update, context: ContextTypes.DEFAULT_TYPE, new_text: str, delay: int = 5):
    """
    自动替换消息内容
    
    Args:
        update: Update对象
        context: Context对象
        new_text: 新的消息内容
        delay: 延迟时间（秒），默认5秒
    """
    await asyncio.sleep(delay)
    try:
        if update.callback_query:
            await update.callback_query.edit_message_text(new_text)
    except Exception as e:
        # 忽略替换失败的错误
        pass
