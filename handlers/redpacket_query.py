# handlers/redpacket_query.py
import asyncio
import logging
from datetime import datetime, timedelta

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes, ConversationHandler

from config import Config, get_user_token, user_tokens
from handlers.common import add_cancel_button
from utils.message_utils import auto_delete_message
from utils.proxy_config import proxies

logger = logging.getLogger(__name__)

WAITING_REDPACKET_ID, WAITING_QUERY_TYPE = range(20, 22)
MY_REDPACKET_PAGE_SIZE = 5


def utc_to_beijing(utc_time_str):
    if not utc_time_str:
        return "未知时间"
    try:
        utc_time = datetime.fromisoformat(str(utc_time_str).replace("Z", "+00:00"))
        beijing_time = utc_time + timedelta(hours=8)
        return beijing_time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(utc_time_str)


def _query_receive_total(headers, red_packet_id):
    try:
        response = requests.get(
            Config.REDPACKET_RECEIVE_URL,
            params={"red_packet_id": red_packet_id},
            headers=headers,
            timeout=10,
            proxies=proxies,
        )
        if response.status_code == 200:
            return int(response.json().get("total", 0))
        logger.info("查询红包领取人数失败: %s %s", response.status_code, response.text[:200])
    except Exception as error:
        logger.error("查询红包领取人数异常: %s", error)
    return 0


async def render_my_redpackets(update, context, page=1):
    query = update.callback_query
    user_id = update.effective_user.id
    token = get_user_token(user_id)

    if not token:
        await query.edit_message_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END

    from app.database import (
        count_redpacket_records_by_telegram_id,
        get_redpacket_records_by_telegram_id,
    )

    total = count_redpacket_records_by_telegram_id(user_id)
    total_pages = max(1, (total + MY_REDPACKET_PAGE_SIZE - 1) // MY_REDPACKET_PAGE_SIZE)
    page = max(1, min(page, total_pages))
    offset = (page - 1) * MY_REDPACKET_PAGE_SIZE
    records = get_redpacket_records_by_telegram_id(
        user_id,
        limit=MY_REDPACKET_PAGE_SIZE,
        offset=offset,
    )

    if not records:
        keyboard = [[InlineKeyboardButton("🔙 返回红包菜单", callback_data="menu_redpacket_main")]]
        await query.edit_message_text(
            "📋 我发的红包\n\n本地还没有记录。新发成功的红包会自动保存到这里。",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return ConversationHandler.END

    headers = {"Authorization": f"Bearer {token}"}
    message = f"📋 我发的红包（{page}/{total_pages}）\n\n"

    for item in records:
        red_packet_id = item.get("red_packet_id") or "未知"
        received = _query_receive_total(headers, red_packet_id)
        receive_mode = "随机" if item.get("receive_type") == "random" else "均分"
        exclusive = " / 独占" if item.get("is_exclusive") else ""
        created_at = item.get("created_at") or "未知时间"

        message += f"🆔 红包ID: `{red_packet_id}`\n"
        message += f"💰 金额: {item.get('carrot', 0)} 萝卜\n"
        message += f"👥 人数: {received}/{item.get('number', 0)}\n"
        message += f"🎲 模式: {receive_mode}{exclusive}\n"
        message += f"🕒 时间: {created_at}\n\n"

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"my_redpackets_page_{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"my_redpackets_page_{page + 1}"))

    keyboard = []
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 返回红包菜单", callback_data="menu_redpacket_main")])

    await query.edit_message_text(
        message,
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )
    return WAITING_QUERY_TYPE


async def check_redpacket_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id

    if user_id not in user_tokens:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return ConversationHandler.END

    keyboard = [
        [
            InlineKeyboardButton("📋 我发的红包", callback_data="my_redpackets"),
            InlineKeyboardButton("🔎 ID 查询", callback_data="input_id"),
        ],
        [InlineKeyboardButton("🔙 返回红包菜单", callback_data="menu_redpacket_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    text = "📊 红包查询\n\n请选择查询方式："

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    return WAITING_QUERY_TYPE


async def handle_query_type(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()

    data = query.data

    if data == "my_redpackets":
        return await render_my_redpackets(update, context, page=1)

    if data.startswith("my_redpackets_page_"):
        try:
            page = int(data.rsplit("_", 1)[1])
        except ValueError:
            page = 1
        return await render_my_redpackets(update, context, page=page)

    if data == "input_id":
        keyboard = add_cancel_button([[]])
        message = await query.edit_message_text(
            "📊 查询红包领取记录\n\n请输入红包ID：",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        context.user_data["current_prompt_message"] = message
        return WAITING_REDPACKET_ID

    return ConversationHandler.END


async def get_redpacket_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    redpacket_id = update.message.text.strip()
    token = get_user_token(user_id)

    if "current_prompt_message" in context.user_data:
        try:
            message = context.user_data["current_prompt_message"]
            await message.delete()
        except Exception as error:
            logger.error("删除提示消息失败: %s", error)
        finally:
            context.user_data.pop("current_prompt_message", None)

    if not token:
        await update.message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END

    loading = await update.message.reply_text("🔄 正在查询红包记录...")

    try:
        headers = {"Authorization": f"Bearer {token}"}
        response = requests.get(
            Config.REDPACKET_RECEIVE_URL,
            params={"red_packet_id": redpacket_id},
            headers=headers,
            timeout=10,
            proxies=proxies,
        )

        if response.status_code == 200:
            data = response.json()
            items = data.get("items", [])

            if not items:
                await loading.edit_text(
                    f"📊 红包查询结果\n\n红包ID: `{redpacket_id}`\n暂无领取记录",
                    parse_mode="Markdown",
                )
                return ConversationHandler.END

            message = "# 红包领取记录\n\n"
            message += f"🆔 红包ID: `{redpacket_id}`\n"
            message += f"📊 总领取: {data.get('total', 0)} 人\n\n"

            for item in items:
                username = item.get("username", "未知用户")
                carrot = item.get("carrot", 0)
                receive_at = utc_to_beijing(item.get("receive_at", "未知时间"))
                message += f"👤 {username}\n"
                message += f"🥕 {carrot} 萝卜\n"
                message += f"⏰ {receive_at}\n\n"

            await loading.edit_text(message, parse_mode="Markdown")
            asyncio.create_task(auto_delete_message(update, context, loading, 100))
        else:
            await loading.edit_text(f"❌ 查询失败，状态码：{response.status_code}", parse_mode="Markdown")
            asyncio.create_task(auto_delete_message(update, context, loading, 5))

    except Exception as error:
        logger.error("查询红包失败: %s", error)
        await loading.edit_text("❌ 查询失败，请稍后重试", parse_mode="Markdown")
        asyncio.create_task(auto_delete_message(update, context, loading, 5))

    return ConversationHandler.END
