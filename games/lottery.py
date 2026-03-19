# games/lottery.py
import logging
import requests
from datetime import datetime, timedelta, timezone
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
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

async def lottery_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """开始创建抽奖"""
    user_id = update.effective_user.id
    
    if user_id not in user_tokens:
        if update.message:
            await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        else:
            await update.callback_query.edit_message_text("❌ 请先登录！发送 /start 登录")
        return ConversationHandler.END
    
    # 初始化抽奖数据
    context.user_data['lottery'] = {
        'user_id': user_id,
        'step': 'name',
        'prizes': []
    }
    
    keyboard = add_cancel_button([[]], show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if update.callback_query:
        await update.callback_query.edit_message_text(
            "🎲 创建抽奖\n\n请输入抽奖名称（30字内）：",
            reply_markup=reply_markup
        )
    else:
        await update.message.reply_text(
            "🎲 创建抽奖\n\n请输入抽奖名称（30字内）：",
            reply_markup=reply_markup
        )
    
    return WAITING_LOTTERY_NAME

async def lottery_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理抽奖创建流程"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if 'lottery' not in context.user_data:
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    lottery_data = context.user_data['lottery']
    current_step = lottery_data.get('step', 'name')
    
    keyboard = add_cancel_button([[]], show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if current_step == 'name':
        if len(text) > 50:
            await update.message.reply_text("❌ 名称不能超过50字，请重新输入：", reply_markup=reply_markup)
            return WAITING_LOTTERY_NAME
        
        lottery_data['name'] = text
        lottery_data['description'] = ""  # 默认空描述
        
        # 自动设置开始时间为当前北京时间
        # 北京时间 UTC+8
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)
        lottery_data['time_start'] = now.strftime("%Y-%m-%d %H:%M:%S")
        
        lottery_data['step'] = 'end'
        context.user_data['lottery'] = lottery_data
        
        # 计算不同时长的结束时间（北京时间）
        end_1h = (now + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        end_1d = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        end_7d = (now + timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        
        # 显示结束时间选择按钮
        keyboard = [
            [InlineKeyboardButton("⏱️ 1小时速抽", callback_data=f"end_time_1h_{end_1h}")],
            [InlineKeyboardButton("📅 1天期限", callback_data=f"end_time_1d_{end_1d}")],
            [InlineKeyboardButton("📆 1周开奖", callback_data=f"end_time_7d_{end_7d}")],
            [InlineKeyboardButton("✏️ 自定义时间", callback_data="end_time_custom")]
        ]
        keyboard = add_cancel_button(keyboard, show_back=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "⏰ 请选择开奖时间\n\n"  
            f"开始时间：`{lottery_data['time_start']}`",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return WAITING_LOTTERY_END
    
    elif current_step == 'end':
        try:
            end_time = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            start_time = datetime.strptime(lottery_data['time_start'], "%Y-%m-%d %H:%M:%S")
            
            if end_time <= start_time:
                await update.message.reply_text("❌ 结束时间必须晚于开始时间，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_END
            
            days_diff = (end_time - start_time).days
            if days_diff > 7:
                await update.message.reply_text("❌ 结束时间必须在开始时间的一周内，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_END
            
            lottery_data['time_end'] = text
            lottery_data['step'] = 'amount'
            context.user_data['lottery'] = lottery_data
            await update.message.reply_text(
                "💰 请输入每人参与所需萝卜数量（1-50000）：",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_AMOUNT
        except ValueError:
            await update.message.reply_text("❌ 时间格式错误，请重新输入：", reply_markup=reply_markup)
            return WAITING_LOTTERY_END
    
    elif current_step == 'amount':
        try:
            amount = int(text)
            if amount <= 0 or amount > 50000:
                await update.message.reply_text("❌ 金额必须在1-50000之间，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_AMOUNT
            lottery_data['amount'] = amount
            lottery_data['step'] = 'number'
            context.user_data['lottery'] = lottery_data
            
            # 简化说明
            help_text = (
                "👥 请输入开奖人数（0-5000）\n\n"
                "• 输入 **0**：时间开奖模式，到结束时间自动开奖\n"
                "• 输入 **数字**：人数开奖模式，达到指定人数或到结束时间开奖\n"
            )
            
            await update.message.reply_text(
                help_text,
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_NUMBER
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_AMOUNT
    
    elif current_step == 'number':
        try:
            number = int(text)
            if number < 0 or number > 5000:
                await update.message.reply_text("❌ 人数必须在0-5000之间，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_NUMBER
            
            lottery_data['number'] = number
            
            # 简化模式设置
            if number == 0:
                lottery_data['mode'] = 'time'
                lottery_data['mode_display'] = '⏰ 时间开奖模式'
            else:
                lottery_data['mode'] = 'people'
                lottery_data['mode_display'] = '👥 人数开奖模式'
            
            lottery_data['step'] = 'rule_carrot'
            context.user_data['lottery'] = lottery_data
            await update.message.reply_text(
                "🥕 请输入参与条件（萝卜数量要求，没有则输0）：",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_RULE_CARROT
                
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_NUMBER
    
    elif current_step == 'rule_carrot':
        try:
            rule_carrot = int(text)
            if rule_carrot < 0:
                await update.message.reply_text("❌ 请输入非负数：", reply_markup=reply_markup)
                return WAITING_LOTTERY_RULE_CARROT
            lottery_data['rule_carrot'] = rule_carrot
            lottery_data['step'] = 'rule_sign'
            context.user_data['lottery'] = lottery_data
            await update.message.reply_text(
                "📅 请输入参与条件（签到天数要求，没有则输0）：",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_RULE_SIGN
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_RULE_CARROT
    
    elif current_step == 'rule_sign':
        try:
            rule_sign = int(text)
            if rule_sign < 0:
                await update.message.reply_text("❌ 请输入非负数：", reply_markup=reply_markup)
                return WAITING_LOTTERY_RULE_SIGN
            lottery_data['rule_sign'] = rule_sign
            lottery_data['step'] = 'prizes'
            lottery_data['prizes'] = []
            lottery_data['current_prize'] = {}
            lottery_data['prize_step'] = 'name'
            context.user_data['lottery'] = lottery_data
            await update.message.reply_text(
                "🎁 请输入第1个奖品的名称（50字内）：",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_PRIZES
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_RULE_SIGN
    
    elif current_step == 'prizes':
        return await handle_prize_input(update, context)
    
    return ConversationHandler.END

async def handle_prize_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理奖品输入"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    lottery_data = context.user_data['lottery']
    prize_step = lottery_data.get('prize_step', 'name')
    current_prize = lottery_data.get('current_prize', {})
    prize_index = len(lottery_data['prizes']) + 1
    
    keyboard = add_cancel_button([[]], show_back=True)
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if prize_step == 'name':
        if len(text) > 50:
            await update.message.reply_text("❌ 奖品名称不能超过50字，请重新输入：", reply_markup=reply_markup)
            return WAITING_LOTTERY_PRIZES
        
        current_prize['name'] = text
        current_prize['description'] = None  # 默认空描述
        lottery_data['current_prize'] = current_prize
        lottery_data['prize_step'] = 'number'
        context.user_data['lottery'] = lottery_data
        
        await update.message.reply_text(
            f"请输入第{prize_index}个奖品的数量（1-100）：",
            reply_markup=reply_markup
        )
        return WAITING_LOTTERY_PRIZES
    
    elif prize_step == 'number':
        try:
            number = int(text)
            if number <= 0 or number > 100:
                await update.message.reply_text("❌ 数量必须在1-100之间，请重新输入：", reply_markup=reply_markup)
                return WAITING_LOTTERY_PRIZES
            
            current_prize['number'] = number
            lottery_data['current_prize'] = current_prize
            lottery_data['prize_step'] = 'need_bodys'
            context.user_data['lottery'] = lottery_data
            
            keyboard = [
                [InlineKeyboardButton("✅ 需要自动发奖", callback_data="need_bodys_yes"),
                 InlineKeyboardButton("❌ 不需要", callback_data="need_bodys_no")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await update.message.reply_text(
                f"是否需要为第{prize_index}个奖品设置自动发奖内容？",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_PRIZES
        except ValueError:
            await update.message.reply_text("❌ 请输入有效的数字：", reply_markup=reply_markup)
            return WAITING_LOTTERY_PRIZES
    
    elif prize_step == 'bodys':
        # 处理自动发奖内容输入
        return await get_lottery_bodys(update, context)
    
    return WAITING_LOTTERY_PRIZES

async def handle_end_time_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理结束时间选择"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    logger.info(f"用户 {user_id} 选择结束时间: {data}")
    
    if 'lottery' not in context.user_data:
        await query.edit_message_text("❌ 会话已过期，请重新发送 /lottery 开始")
        return ConversationHandler.END
    
    lottery_data = context.user_data['lottery']
    
    if data == "end_time_custom":
        # 自定义时间，显示输入框
        keyboard = add_cancel_button([[]], show_back=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 北京时间 UTC+8
        beijing_tz = timezone(timedelta(hours=8))
        now = datetime.now(beijing_tz)
        default_end = (now + timedelta(days=1)).strftime("%Y-%m-%d %H:%M:%S")
        await query.edit_message_text(
            "⏰ 请输入结束时间\n"
            "格式：`YYYY-MM-DD HH:MM:SS`\n"
            f"例如：`{default_end}`\n\n"
            f"开始时间：`{lottery_data['time_start']}`\n\n"
            "💡 请输入北京时间",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return WAITING_LOTTERY_END
    elif data.startswith("end_time_"):
        # 快捷时间选择
        # 解析时间：end_time_1h_2023-12-01 12:00:00
        end_time = data.split('_', 2)[2]
        lottery_data['time_end'] = end_time
        lottery_data['step'] = 'amount'
        context.user_data['lottery'] = lottery_data
        
        keyboard = add_cancel_button([[]], show_back=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"✅ 结束时间已设置：`{end_time}`\n\n"  
            f"💰 请输入每人参与所需萝卜数量（1-50000）：",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return WAITING_LOTTERY_AMOUNT
    
    return WAITING_LOTTERY_END

async def handle_bodys_choice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """处理是否需要自动发奖的选择"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    logger.info(f"用户 {user_id} 点击按钮: {data}")
    logger.info(f"按钮完整数据: {query}")
    
    
    if 'lottery' not in context.user_data:
        await query.edit_message_text("❌ 会话已过期，请重新发送 /lottery 开始")
        return ConversationHandler.END
    
    lottery_data = context.user_data['lottery']
    current_prize = lottery_data.get('current_prize', {})
    prize_index = len(lottery_data['prizes']) + 1
    
    if data == "need_bodys_yes":
        lottery_data['prize_step'] = 'bodys'
        context.user_data['lottery'] = lottery_data
        prize_count = current_prize.get('number', 1)
        
        await query.edit_message_text(
            f"请输入第{prize_index}个奖品的自动发奖内容（每行一个，共{prize_count}个）："
        )
        return WAITING_LOTTERY_PRIZES
        
    elif data == "need_bodys_no":
        lottery_data['prizes'].append(current_prize.copy())
        lottery_data.pop('current_prize', None)
        lottery_data['prize_step'] = 'name'
        context.user_data['lottery'] = lottery_data
        
        if len(lottery_data['prizes']) >= 20:
            return await finish_prizes(update, context)
        else:
            keyboard = [
                [InlineKeyboardButton("✅ 继续添加", callback_data="add_more_prizes"),
                 InlineKeyboardButton("🎯 完成添加", callback_data="finish_prizes")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(
                f"✅ 已添加第{prize_index}个奖品\n当前共添加 {len(lottery_data['prizes'])} 个奖品\n\n是否继续？",
                reply_markup=reply_markup
            )
            return WAITING_LOTTERY_PRIZES
    
    return WAITING_LOTTERY_PRIZES

async def get_lottery_bodys(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """接收自动发奖内容"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if 'lottery' not in context.user_data:
        await update.message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    lottery_data = context.user_data['lottery']
    current_prize = lottery_data.get('current_prize', {})
    prize_count = current_prize.get('number', 1)
    prize_index = len(lottery_data['prizes']) + 1
    
    # 按行分割内容，过滤空行
    bodys = [line.strip() for line in text.split('\n') if line.strip()]
    
    logger.info(f"用户 {user_id} 输入了 {len(bodys)} 行自动发奖内容，需要 {prize_count} 个")
    
    # 检查数量是否匹配
    if len(bodys) != prize_count:
        await update.message.reply_text(
            f"❌ 需要输入 **{prize_count}** 个奖品内容\n"
            f"当前只收到了 **{len(bodys)}** 个\n\n"
            f"请重新输入，每行一个，共 {prize_count} 个：",
            parse_mode="Markdown"
        )
        return WAITING_LOTTERY_PRIZES
    
    # 保存自动发奖内容
    current_prize['bodys'] = bodys
    lottery_data['prizes'].append(current_prize.copy())
    lottery_data.pop('current_prize', None)
    lottery_data['prize_step'] = 'name'
    context.user_data['lottery'] = lottery_data
    
    # 显示成功消息并询问是否继续添加
    total_prizes = len(lottery_data['prizes'])
    
    if len(lottery_data['prizes']) >= 20:
        # 达到最大奖品数量，直接创建抽奖
        await update.message.reply_text(f"✅ 已添加第{prize_index}个奖品，达到最大数量（20个），正在创建抽奖...")
        return await finish_prizes(update, context)
    else:
        # 询问是否继续添加
        keyboard = [
            [InlineKeyboardButton("✅ 继续添加", callback_data="add_more_prizes"),
             InlineKeyboardButton("🎯 完成添加", callback_data="finish_prizes")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"✅ 第{prize_index}个奖品已添加成功！\n"
            f"当前共添加 **{total_prizes}** 个奖品\n\n"
            f"是否继续添加奖品？",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        return WAITING_LOTTERY_PRIZES

async def handle_prize_choice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理奖品添加完成或继续的选择"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"处理奖品选择: {data}")
    
    if 'lottery' not in context.user_data:
        await query.edit_message_text("❌ 会话已过期，请重新发送 /lottery 开始")
        return ConversationHandler.END
    
    lottery_data = context.user_data['lottery']
    
    if data == "finish_prizes":
        # 完成添加，创建抽奖
        await query.edit_message_text("🔄 正在创建抽奖...")
        return await finish_prizes(update, context)
        
    elif data == "add_more_prizes":
        # 继续添加下一个奖品
        prize_index = len(lottery_data['prizes']) + 1
        lottery_data['current_prize'] = {}
        lottery_data['prize_step'] = 'name'
        context.user_data['lottery'] = lottery_data
        
        keyboard = add_cancel_button([[]], show_back=True)
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎁 请输入第{prize_index}个奖品的名称（50字内）：",
            reply_markup=reply_markup
        )
        return WAITING_LOTTERY_PRIZES
    
    return WAITING_LOTTERY_PRIZES

async def finish_prizes(update, context):
    """完成奖品添加，创建抽奖"""
    # 判断是从消息还是回调查询调用
    if isinstance(update, Update):
        if update.callback_query:
            # 来自回调按钮
            query = update.callback_query
            user_id = query.from_user.id
            message = query.message
        else:
            # 来自普通消息
            user_id = update.effective_user.id
            message = update.message
    else:
        # 如果是直接传入的 query 对象
        query = update
        user_id = query.from_user.id
        message = query.message
    
    token = user_tokens.get(user_id)
    
    if not token:
        await message.reply_text("❌ 登录已过期，请重新发送 /start 登录")
        return ConversationHandler.END
    
    lottery_data = context.user_data.get('lottery')
    if not lottery_data:
        await message.reply_text("❌ 会话已过期，请重新开始")
        return ConversationHandler.END
    
    if not lottery_data.get('prizes'):
        await message.reply_text("❌ 至少需要添加一个奖品")
        return WAITING_LOTTERY_PRIZES
    
    # 计算总奖品数量（用于显示）
    total_prizes = sum(prize.get('number', 0) for prize in lottery_data['prizes'])
    
    # 构建API请求参数
    payload = {
        "name": lottery_data['name'],
        "description": lottery_data.get('description', ''),
        "time_start": lottery_data['time_start'],
        "time_end": lottery_data['time_end'],
        "amount": lottery_data['amount'],
        "number": lottery_data['number'],  # 始终包含number字段
        "rule_carrot": lottery_data.get('rule_carrot', 0),
        "rule_sign": lottery_data.get('rule_sign', 0),
        "prizes": lottery_data['prizes']
    }
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # 如果已经有消息正在显示，就编辑它，否则发送新消息
    if isinstance(message, Update) and hasattr(message, 'edit_text'):
        status_msg = await message.edit_text("🔄 正在创建抽奖...")
    else:
        status_msg = await message.reply_text("🔄 正在创建抽奖...")
    
    try:
        logger.info(f"创建抽奖: {payload}")
        
        response = requests.post(
            Config.LOTTERY_CREATE_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        logger.info(f"API响应状态码: {response.status_code}")
        logger.info(f"API响应内容: {response.text}")
        
        if response.status_code == 200:
            result = response.json()
            
            # 根据API返回示例，直接返回 {"lottery_id": "xxx"}
            lottery_id = result.get('lottery_id')
            
            if lottery_id:
                # 构建成功消息
                if lottery_data['number'] == 0:
                    mode_text = "⏰ 时间开奖模式"
                    winners_text = f"由奖品总数决定（共 {total_prizes} 个奖品）"
                else:
                    mode_text = "👥 人数开奖模式"
                    winners_text = f"{lottery_data['number']} 人"
                
                success_msg = (
                    f"✅ **抽奖创建成功！**\n\n"
                    f"🎲 **名称**：{payload['name']}\n"
                    f"⏰ **时间**：`{payload['time_start']}` 至 `{payload['time_end']}`\n"
                    f"💰 **金额**：{payload['amount']} 萝卜\n"
                    f"🎮 **模式**：{mode_text}\n"
                    f"👥 **中奖**：{winners_text}\n"
                    f"🎁 **奖品总数**：{total_prizes} 个\n\n"
                    f"🆔 **抽奖ID**：`{lottery_id}`\n\n"
                    f"💡 点击上方ID即可复制"
                )
                
                await status_msg.edit_text(
                    success_msg,
                    parse_mode="Markdown"
                )
                
                # 显示返回菜单
                from handlers.common import show_menu
                
                # 创建一个合适的update对象
                if isinstance(update, Update):
                    await show_menu(update, "✅ 抽奖创建成功！\n\n返回主菜单：")
                else:
                    # 创建假的update对象用于show_menu
                    class FakeUpdate:
                        def __init__(self, query):
                            self.callback_query = query
                            self.message = None
                            self.effective_user = query.from_user
                    fake_update = FakeUpdate(query)
                    await show_menu(fake_update, "✅ 抽奖创建成功！\n\n返回主菜单：")
                
                # 清理数据并返回 END
                context.user_data.clear()
                return ConversationHandler.END
            else:
                error_msg = result.get('message', '未知错误')
                await status_msg.edit_text(f"❌ 创建失败：{error_msg}")
                return WAITING_LOTTERY_PRIZES
            
        else:
            error_text = response.text if response.text else f"状态码：{response.status_code}"
            await status_msg.edit_text(f"❌ 创建失败，{error_text}")
            return WAITING_LOTTERY_PRIZES
            
    except requests.exceptions.Timeout:
        logger.error("创建抽奖超时")
        await status_msg.edit_text("❌ 创建超时，请稍后重试")
        return WAITING_LOTTERY_PRIZES
    except requests.exceptions.ConnectionError:
        logger.error("创建抽奖连接错误")
        await status_msg.edit_text("❌ 网络连接错误，请稍后重试")
        return WAITING_LOTTERY_PRIZES
    except Exception as e:
        logger.error(f"创建抽奖失败: {e}")
        await status_msg.edit_text("❌ 创建失败，请稍后重试")
        return WAITING_LOTTERY_PRIZES