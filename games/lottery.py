# games/lottery.py
import logging
import requests
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler

from config import user_tokens, Config
from handlers.common import add_cancel_button

logger = logging.getLogger(__name__)

# 抽奖对话状态
WAITING_LOTTERY_NAME = 10
WAITING_LOTTERY_DESC = 11
WAITING_LOTTERY_START = 12
WAITING_LOTTERY_END = 13
WAITING_LOTTERY_AMOUNT = 14
WAITING_LOTTERY_NUMBER = 15
WAITING_LOTTERY_RULE_CARROT = 16
WAITING_LOTTERY_RULE_SIGN = 17
WAITING_LOTTERY_PRIZES = 18

# 存储临时数据
lottery_data = {}

async def lottery_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始创建抽奖"""
    user_id = update.effective_user.id
    
    # 添加取消按钮
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if user_id not in user_tokens:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录", reply_markup=reply_markup)
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录", reply_markup=reply_markup)
        return ConversationHandler.END
    
    # 初始化抽奖数据
    lottery_data[user_id] = {}
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🎲 创建抽奖\n\n"
            "请输入抽奖名称（30字内）：",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🎲 创建抽奖\n\n"
            "请输入抽奖名称（30字内）：",
            reply_markup=reply_markup
        )
    
    return WAITING_LOTTERY_NAME

async def lottery_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理抽奖创建流程"""
    user_id = update.effective_user.id
    text = update.message.text
    state = context.user_data.get('lottery_state', WAITING_LOTTERY_NAME)
    
    # 添加取消按钮
    keyboard = add_cancel_button([[]])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if user_id not in lottery_data:
        lottery_data[user_id] = {}
    
    if state == WAITING_LOTTERY_NAME:
        if len(text) > 30:
            await update.message.reply_text("❌ 名称不能超过30字，请重新输入：", reply_markup=reply_markup)
            return WAITING_LOTTERY_NAME
        
        lottery_data[user_id]['name'] = text
        context.user_data['lottery_state'] = WAITING_LOTTERY_DESC
        await update.message.reply_text("请输入抽奖简介（200字内）：", reply_markup=reply_markup)
        return WAITING_LOTTERY_DESC
    
    elif state == WAITING_LOTTERY_DESC:
        if len(text) > 200:
            await update.message.reply_text("❌ 简介不能超过200字，请重新输入：", reply_markup=reply_markup)
            return WAITING_LOTTERY_DESC
        
        lottery_data[user_id]['description'] = text
        context.user_data['lottery_state'] = WAITING_LOTTERY_START
        await update.message.reply_text(
            "请输入开始时间（格式：YYYY-MM-DD HH:MM:SS）\n"
            "例如：2024-01-01 12:00:00",
            reply_markup=reply_markup
        )
        return WAITING_LOTTERY_START
    
    elif state == WAITING_LOTTERY_START:
        try:
            datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
            lottery_data[user_id]['time_start'] = text
            context.user_data['lottery_state'] = WAITING_LOTTERY_END
            await update.message.reply_text("请输入结束时间（格式：YYYY-MM-DD HH:MM:SS）：", reply_markup=reply_markup)
            return WAITING_LOTTERY_END
        except ValueError:
            await update.message.reply_text("❌ 时间格式错误，请重新输入：", reply_markup=reply_markup)
            return WAITING_LOTTERY_START
    
    elif state == WAITING_LOTTERY_END:
        try:
            datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
            start = datetime.strptime(lottery_data[user_id]['time_start'], '%Y-%m-%d %H:%M:%S')
            end = datetime.strptime(text, '%Y-%m-%d %H:%M:%S')
            if end <= start:
                await update.message.reply_text("❌ 结束时间必须晚于开始时间，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_END
            
            lottery_data[user_id]['time_end'] = text
            context.user_data['lottery_state'] = WAITING_LOTTERY_AMOUNT
            await update.message.reply_text("请输入每人参与所需萝卜数量：", reply_markup=reply_markup)
            return WAITING_LOTTERY_AMOUNT
        except ValueError:
            await update.message.reply_text("❌ 时间格式错误，请重新输入：", reply_markup=reply_markup)
            return WAITING_LOTTERY_END
    
    elif state == WAITING_LOTTERY_AMOUNT:
        try:
            amount = int(text)
            if amount <= 0 or amount > 50000:
                await update.message.reply_text("❌ 金额必须在1-50000之间，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_AMOUNT
            lottery_data[user_id]['amount'] = amount
            context.user_data['lottery_state'] = WAITING_LOTTERY_NUMBER
            await update.message.reply_text("请输入中奖人数：", reply_markup=reply_markup)
            return WAITING_LOTTERY_NUMBER
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_AMOUNT
    
    elif state == WAITING_LOTTERY_NUMBER:
        try:
            number = int(text)
            if number <= 0 or number > 1000:
                await update.message.reply_text("❌ 人数必须在1-1000之间，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_NUMBER
            lottery_data[user_id]['number'] = number
            context.user_data['lottery_state'] = WAITING_LOTTERY_RULE_CARROT
            await update.message.reply_text(
                "请输入参与条件（萝卜数量要求，没有则输0）：",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_RULE_CARROT
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_NUMBER
    
    elif state == WAITING_LOTTERY_RULE_CARROT:
        try:
            carrot_rule = int(text)
            if carrot_rule < 0:
                await update.message.reply_text("❌ 请输入非负数：", reply_markup=reply_markup)
                return WAITING_LOTTERY_RULE_CARROT
            lottery_data[user_id]['rule_carrot'] = carrot_rule
            context.user_data['lottery_state'] = WAITING_LOTTERY_RULE_SIGN
            await update.message.reply_text(
                "请输入参与条件（签到天数要求，没有则输0）：",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_RULE_SIGN
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_RULE_CARROT
    
    elif state == WAITING_LOTTERY_RULE_SIGN:
        try:
            sign_rule = int(text)
            if sign_rule < 0:
                await update.message.reply_text("❌ 请输入非负数：", reply_markup=reply_markup)
                return WAITING_LOTTERY_RULE_SIGN
            lottery_data[user_id]['rule_sign'] = sign_rule
            context.user_data['lottery_state'] = WAITING_LOTTERY_PRIZES
            await update.message.reply_text(
                "请输入奖品（支持多行，每行格式：奖品名称|数量|图片URL，图片URL可选）\n"
                "例如：\n"
                "iPhone 15|1|https://xxx.com/phone.jpg\n"
                "优惠券|10\n"
                "直接发送 /skip 跳过",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_PRIZES
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_RULE_SIGN
    
    elif state == WAITING_LOTTERY_PRIZES:
        token = user_tokens.get(user_id)
        if not token:
            await update.message.reply_text("❌ 登录已过期", reply_markup=reply_markup)
            return ConversationHandler.END
        
        prizes = []
        if text != '/skip':
            for line in text.split('\n'):
                line = line.strip()
                if not line:
                    continue
                parts = line.split('|')
                if len(parts) >= 2:
                    prize = {
                        'name': parts[0].strip(),
                        'number': int(parts[1].strip())
                    }
                    if len(parts) >= 3 and parts[2].strip():
                        prize['image'] = parts[2].strip()
                    prizes.append(prize)
        
        data = lottery_data[user_id]
        loading = await update.message.reply_text("🔄 正在创建抽奖...")
        
        try:
            headers = {"Authorization": f"Bearer {token}"}
            payload = {
                "name": data['name'],
                "description": data['description'],
                "time_start": data['time_start'],
                "time_end": data['time_end'],
                "amount": data['amount'],
                "number": data['number'],
                "rule": {
                    "carrot": data['rule_carrot'],
                    "sign": data['rule_sign']
                }
            }
            if prizes:
                payload['prizes'] = prizes
            
            response = requests.post(
                Config.LOTTERY_CREATE_URL,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                result = response.json()
                await loading.edit_text(
                    f"✅ 抽奖创建成功！\n\n"
                    f"抽奖ID: {result.get('lottery_id', '未知')}\n"
                    f"名称: {data['name']}\n"
                    f"时间: {data['time_start']} 至 {data['time_end']}\n"
                    f"参与: {data['amount']} 萝卜/人\n"
                    f"中奖: {data['number']} 人"
                )
            elif response.status_code == 401:
                if user_id in user_tokens:
                    del user_tokens[user_id]
                await loading.edit_text("❌ 登录已过期，请重新发送 /start 登录")
            else:
                await loading.edit_text(f"❌ 创建失败，状态码：{response.status_code}")
                
        except Exception as e:
            logger.error(f"用户 {user_id} 创建抽奖失败: {e}")
            await loading.edit_text("❌ 创建失败，请稍后重试")
        
        # 清理数据
        if user_id in lottery_data:
            del lottery_data[user_id]
        context.user_data.clear()
        
        # 操作完成后显示返回菜单按钮
        keyboard = add_cancel_button([[]])
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("🏠 返回菜单", reply_markup=reply_markup)
        return ConversationHandler.END