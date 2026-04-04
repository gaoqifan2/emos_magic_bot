"""
打劫游戏模块
规则：
1. 回复群成员消息并发送 /rob <金额> 命令
2. 成功率：动态概率（基于等级和其他因素）
3. 成功：抢到输入的金额，扣除10%税后实际获得90%
4. 失败：损失输入的金额给对方
5. 冷却：每人每天最多 3 次（数据库存储，重启不丢失）
6. 高等级打劫需要额外交税
"""

import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import ContextTypes
from utils.http_client import http_client
from utils.http_client import http_client

# 每日最大打劫次数
MAX_ROBBERY_PER_DAY = 3
# 基础成功率
BASE_SUCCESS_RATE = 0.5
# 基础税收比例
TAX_RATE = 0.10
# 等级税收比例（高等级打劫额外税收）
LEVEL_TAX_RATE = 0.05

# 等级权重映射
LEVEL_WEIGHT = {
    "青铜": 0,
    "白银": 1,
    "黄金": 2,
    "钻石": 3,
    "宗师": 4,
    "大师": 5,
    "王者": 6
}


def calculate_robbery_success_rate(robber_level, victim_level, robber_balance, victim_balance, robbery_count):
    """
    计算打劫成功率
    - 基础概率：50%
    - 等级优势：打劫者等级高于被打劫者时，每高1级+5%
    - 余额优势：打劫者余额少于被打劫者时，+5%
    - 首次打劫：当天第一次打劫+5%
    - 次数惩罚：当天打劫次数越多，每次-3%
    - 概率范围：30% - 70%
    """
    # 计算等级权重
    robber_weight = LEVEL_WEIGHT.get(robber_level, 0)
    victim_weight = LEVEL_WEIGHT.get(victim_level, 0)
    
    # 计算基础概率
    success_rate = BASE_SUCCESS_RATE
    
    # 等级优势
    level_diff = robber_weight - victim_weight
    if level_diff > 0:
        success_rate += level_diff * 0.05  # 每高1级+5%
    
    # 余额优势
    if robber_balance < victim_balance:
        success_rate += 0.05  # 余额少+5%
    
    # 首次打劫奖励
    if robbery_count == 0:
        success_rate += 0.05  # 第一次+5%
    
    # 次数惩罚
    if robbery_count > 0:
        success_rate -= min(0.15, robbery_count * 0.03)  # 最多-15%
    
    # 限制概率范围
    success_rate = max(0.3, min(0.7, success_rate))
    
    return success_rate


def get_robbery_record(emos_user_id):
    """从数据库获取用户今日打劫记录（使用emos_user_id）"""
    from app.database import get_db_connection
    connection = get_db_connection()
    if not connection:
        return {'count': 0, 'date': datetime.now().date()}
    
    try:
        with connection.cursor() as cursor:
            today = datetime.now().date()
            cursor.execute('''
                SELECT robbery_count, robbery_date 
                FROM robbery_records 
                WHERE user_id = %s
            ''', (str(emos_user_id),))
            
            result = cursor.fetchone()
            if result:
                record_date = result['robbery_date']
                # 如果是新的一天，重置次数
                if record_date != today:
                    cursor.execute('''
                        UPDATE robbery_records 
                        SET robbery_count = 0, robbery_date = %s 
                        WHERE user_id = %s
                    ''', (today, str(emos_user_id)))
                    connection.commit()
                    return {'count': 0, 'date': today}
                return {'count': result['robbery_count'], 'date': record_date}
            else:
                return None  # 没有记录，需要初始化
    except Exception as e:
        print(f"获取打劫记录失败: {e}")
        return {'count': 0, 'date': datetime.now().date()}
    finally:
        connection.close()


def init_robbery_record(emos_user_id, username):
    """初始化用户打劫记录"""
    from app.database import get_db_connection
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            today = datetime.now().date()
            cursor.execute('''
                INSERT INTO robbery_records (user_id, username, robbery_count, robbery_date)
                VALUES (%s, %s, 0, %s)
            ''', (str(emos_user_id), username, today))
            connection.commit()
            return True
    except Exception as e:
        print(f"初始化打劫记录失败: {e}")
        return False
    finally:
        connection.close()


def update_robbery_count(emos_user_id, username, count):
    """更新用户今日打劫次数"""
    from app.database import get_db_connection
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            today = datetime.now().date()
            cursor.execute('''
                INSERT INTO robbery_records (user_id, username, robbery_count, robbery_date)
                VALUES (%s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE 
                    robbery_count = %s, 
                    robbery_date = %s,
                    username = %s
            ''', (str(emos_user_id), username, count, today, count, today, username))
            connection.commit()
            return True
    except Exception as e:
        print(f"更新打劫记录失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()


async def robbery_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理打劫命令"""
    # 只能在群聊中使用
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ 打劫只能在群聊中使用！")
        return
    
    # 必须回复消息
    if not update.message.reply_to_message:
        await update.message.reply_text(
            "❌ 请回复要打劫的群成员消息！\n\n"
            "使用方法：回复目标成员的消息，然后发送 /rob <金额>\n"
            "例如：`/rob 100`\n\n"
            "直接复制：`/rob 100`",
            parse_mode='Markdown'
        )
        return
    
    # 获取输入的金额
    args = context.args
    if not args or len(args) != 1:
        await update.message.reply_text(
            "❌ 请输入打劫金额！\n\n"
            "使用方法：回复目标成员的消息，然后发送 /rob <金额>\n"
            "例如：`/rob 100`\n\n"
            "直接复制：`/rob 100`",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = int(args[0])
        if amount < 10:
            await update.message.reply_text("❌ 打劫金额至少为 10 🪙！")
            return
        if amount > 10000:
            await update.message.reply_text("❌ 单次打劫金额不能超过 10000 🪙！")
            return
    except ValueError:
        await update.message.reply_text("❌ 请输入有效的数字金额！")
        return
    
    robber = update.effective_user
    victim = update.message.reply_to_message.from_user
    
    # 不能打劫自己
    if robber.id == victim.id:
        await update.message.reply_text("❌ 不能打劫自己！")
        return
    
    # 不能打劫机器人
    if victim.is_bot:
        await update.message.reply_text("❌ 不能打劫机器人！")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if robber.id not in user_tokens:
        await update.message.reply_text("❌ 请先使用 /start 命令登录！")
        return
    
    # 获取打劫者信息（emos）
    robber_info = user_tokens[robber.id]
    robber_emos_id = robber_info.get('user_id', str(robber.id))
    robber_username = robber_info.get('username', robber.first_name)
    
    # 获取被打劫者信息（emos）
    if victim.id not in user_tokens:
        await update.message.reply_text("❌ 对方还未登录游戏！")
        return
    
    victim_info = user_tokens[victim.id]
    victim_emos_id = victim_info.get('user_id', str(victim.id))
    victim_username = victim_info.get('username', victim.first_name)
    
    # 检查打劫者累计充值，限制最大打劫金额
    from app.database import get_user_total_recharge
    robber_total_recharge = get_user_total_recharge(robber_emos_id)
    max_rob_amount = min(10000, max(100, int(robber_total_recharge * 10)))
    if amount > max_rob_amount:
        await update.message.reply_text(
            f"❌ 您的打劫金额超出限制！\n"
            f"您的累计充值：{robber_total_recharge} 🥕\n"
            f"最大打劫金额：{max_rob_amount} 🪙\n"
            f"（充值越多，可打劫金额越高）"
        )
        return
    
    # ========== 每日3次限制计算（数据库存储，使用emos_user_id）==========
    record = get_robbery_record(robber_emos_id)
    
    # 如果没有记录，初始化
    if record is None:
        init_robbery_record(robber_emos_id, robber_username)
        record = {'count': 0, 'date': datetime.now().date()}
    
    # 检查是否超过次数
    if record['count'] >= MAX_ROBBERY_PER_DAY:
        await update.message.reply_text(
            f"❌ 您今天的打劫次数已用完！\n"
            f"每人每天最多打劫 {MAX_ROBBERY_PER_DAY} 次\n"
            f"请明天再来..."
        )
        return
    
    # 获取双方余额
    from app.database import get_balance, update_balance
    from app.database.user_score import get_user_score, get_user_level
    
    robber_balance = get_balance(robber_emos_id)
    victim_balance = get_balance(victim_emos_id)
    
    # 获取双方等级
    robber_score = get_user_score(str(robber.id))  # 使用telegram_id
    victim_score = get_user_score(str(victim.id))  # 使用telegram_id
    robber_level_info = get_user_level(robber_score)
    victim_level_info = get_user_level(victim_score)
    robber_level = robber_level_info[0]
    victim_level = victim_level_info[0]
    
    # 检查余额
    if robber_balance < amount:
        await update.message.reply_text(
            f"❌ 您的游戏币不足！\n"
            f"需要：{amount} 🪙\n"
            f"当前余额：{robber_balance} 🪙"
        )
        return
    
    if victim_balance < amount:
        await update.message.reply_text(
            f"❌ 对方的游戏币不足！\n"
            f"需要：{amount} 🪙\n"
            f"对方余额：{victim_balance} 🪙"
        )
        return
    
    # 执行打劫
    new_count = record['count'] + 1
    update_robbery_count(robber_emos_id, robber_username, new_count)
    print(f"[DEBUG] 用户 {robber_username}({robber_emos_id}) 今日打劫次数：{new_count}/{MAX_ROBBERY_PER_DAY}")
    
    # 计算动态成功率
    success_rate = calculate_robbery_success_rate(
        robber_level, victim_level, robber_balance, victim_balance, record['count']
    )
    print(f"[DEBUG] 打劫成功率：{success_rate:.2f}")
    
    # 发送打劫中提示
    loading_message = await update.message.reply_text(
        f"🎭 *打劫中...*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"🦹 打劫者：{robber_username}（{robber_level}）\n"
        f"🎯 目标：{victim_username}（{victim_level}）\n"
        f"💰 打劫金额：{amount} 🪙\n"
        f"🎲 成功率：{int(success_rate * 100)}%\n\n"
        f"⏳ 正在进行打劫，请稍后...\n"
        f"━━━━━━━━━━━━━━━━━━",
        parse_mode='Markdown'
    )
    
    # 延迟2秒
    import asyncio
    await asyncio.sleep(2)
    
    # 随机决定是否成功
    is_success = random.random() < success_rate
    
    if is_success:
        # ========== 打劫成功 ==========
        # 计算基础税收（10%）
        tax_amount = int(amount * TAX_RATE)
        
        # 计算等级额外税收（高等级打劫额外5%）
        level_tax = 0
        robber_level_weight = LEVEL_WEIGHT.get(robber_level, 0)
        if robber_level_weight >= 2:  # 黄金及以上等级
            level_tax = int(amount * LEVEL_TAX_RATE)
        
        total_tax = tax_amount + level_tax
        net_amount = amount - total_tax
        
        # 转账：从受害者扣除
        update_balance(victim_emos_id, -amount)
        # 转账：打劫者获得（扣除税后）
        update_balance(robber_emos_id, net_amount)
        
        # 记录游戏结果
        from app.database import add_game_record
        add_game_record(robber_emos_id, 'robbery', amount, 'win', net_amount, robber_username)
        add_game_record(victim_emos_id, 'robbery', amount, 'lose', -amount, victim_username)
        
        # 获取新余额
        new_robber_balance = get_balance(robber_emos_id)
        new_victim_balance = get_balance(victim_emos_id)
        
        result_message = (
            f"🎭 *打劫结果*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🦹 打劫者：{robber_username}（{robber_level}）\n"
            f"🎯 目标：{victim_username}（{victim_level}）\n"
            f"💰 打劫金额：{amount} 🪙\n"
            f"🎲 成功率：{int(success_rate * 100)}%\n\n"
            f"✅ *打劫成功！*\n"
            f"💸 基础税收：{tax_amount} 🪙（10%）\n"
        )
        
        if level_tax > 0:
            result_message += f"💎 等级税收：{level_tax} 🪙（5%）\n"
        
        result_message += (
            f"📊 总税收：{total_tax} 🪙\n"
            f"💵 实际获得：{net_amount} 🪙\n\n"
            f"📊 余额变动：\n"
            f"🦹 {robber_username}：{robber_balance} → {new_robber_balance} 🪙\n"
            f"🎯 {victim_username}：{victim_balance} → {new_victim_balance} 🪙\n\n"
            f"📋 *概率计算*\n"
            f"  • 基础概率：50%\n"
        )
        
        # 计算等级优势
        level_diff = LEVEL_WEIGHT.get(robber_level, 0) - LEVEL_WEIGHT.get(victim_level, 0)
        if level_diff > 0:
            result_message += f"  • 等级优势：+{level_diff * 5}%（高{level_diff}级）\n"
        
        # 计算余额优势
        if robber_balance < victim_balance:
            result_message += f"  • 余额优势：+5%（余额较少）\n"
        
        # 计算首次打劫奖励
        if record['count'] == 0:
            result_message += f"  • 首次打劫：+5%\n"
        
        # 计算次数惩罚
        if record['count'] > 0:
            penalty = min(15, record['count'] * 3)
            result_message += f"  • 次数惩罚：-{penalty}%（已打劫{record['count']}次）\n"
        
        result_message += (
            f"⏰ 今日剩余次数：{MAX_ROBBERY_PER_DAY - new_count}/{MAX_ROBBERY_PER_DAY}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
    else:
        # ========== 打劫失败 ==========
        # 计算税收（10%）
        tax_amount = int(amount * TAX_RATE)
        total_loss = amount + tax_amount
        
        # 转账：打劫者损失（包括税收）
        update_balance(robber_emos_id, -total_loss)
        # 转账：受害者获得（不含税收）
        update_balance(victim_emos_id, amount)
        
        # 记录游戏结果
        from app.database import add_game_record
        add_game_record(robber_emos_id, 'robbery', amount, 'lose', -total_loss, robber_username)
        add_game_record(victim_emos_id, 'robbery', amount, 'win', amount, victim_username)
        
        # 获取新余额
        new_robber_balance = get_balance(robber_emos_id)
        new_victim_balance = get_balance(victim_emos_id)
        
        result_message = (
            f"🎭 *打劫结果*\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🦹 打劫者：{robber_username}（{robber_level}）\n"
            f"🎯 目标：{victim_username}（{victim_level}）\n"
            f"💰 打劫金额：{amount} 🪙\n"
            f"🎲 成功率：{int(success_rate * 100)}%\n\n"
            f"❌ *打劫失败！*\n"
            f"💸 损失：{amount} 🪙\n"
            f"💸 税收：{tax_amount} 🪙（10%）\n"
            f"📊 总损失：{total_loss} 🪙\n\n"
            f"📊 余额变动：\n"
            f"🦹 {robber_username}：{robber_balance} → {new_robber_balance} 🪙\n"
            f"🎯 {victim_username}：{victim_balance} → {new_victim_balance} 🪙\n\n"
            f"📋 *概率计算*\n"
            f"  • 基础概率：50%\n"
        )
        
        # 计算等级优势
        level_diff = LEVEL_WEIGHT.get(robber_level, 0) - LEVEL_WEIGHT.get(victim_level, 0)
        if level_diff > 0:
            result_message += f"  • 等级优势：+{level_diff * 5}%（高{level_diff}级）\n"
        
        # 计算余额优势
        if robber_balance < victim_balance:
            result_message += f"  • 余额优势：+5%（余额较少）\n"
        
        # 计算首次打劫奖励
        if record['count'] == 0:
            result_message += f"  • 首次打劫：+5%\n"
        
        # 计算次数惩罚
        if record['count'] > 0:
            penalty = min(15, record['count'] * 3)
            result_message += f"  • 次数惩罚：-{penalty}%（已打劫{record['count']}次）\n"
        
        result_message += (
            f"⏰ 今日剩余次数：{MAX_ROBBERY_PER_DAY - new_count}/{MAX_ROBBERY_PER_DAY}\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
    
    # 删除打劫中提示
    try:
        await loading_message.delete()
    except Exception as e:
        print(f"删除打劫中提示失败: {e}")
    
    await update.message.reply_text(result_message, parse_mode='Markdown')


async def robbery_status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询打劫状态"""
    user = update.effective_user
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user.id not in user_tokens:
        await update.message.reply_text("❌ 请先使用 /start 命令登录！")
        return
    
    # 获取用户信息（emos）
    user_info = user_tokens[user.id]
    emos_user_id = user_info.get('user_id', str(user.id))
    username = user_info.get('username', user.first_name)
    
    # 获取用户等级
    from app.database.user_score import get_user_score, get_user_level
    user_score = get_user_score(str(user.id))
    user_level_info = get_user_level(user_score)
    user_level = user_level_info[0]
    
    # ========== 查询今日次数（数据库存储，使用emos_user_id）==========
    record = get_robbery_record(emos_user_id)
    
    # 如果没有记录，初始化
    if record is None:
        init_robbery_record(emos_user_id, username)
        record = {'count': 0, 'date': datetime.now().date()}
    
    remaining = MAX_ROBBERY_PER_DAY - record['count']
    
    # 发送状态消息并获取消息对象
    status_message = await update.message.reply_text(
        f"🎭 *打劫状态*\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👤 用户：{username}\n"
        f"🏆 等级：{user_level}\n"
        f"📅 今日已使用：{record['count']} 次\n"
        f"⏰ 今日剩余：{remaining} 次\n"
        f"📊 总次数限制：{MAX_ROBBERY_PER_DAY} 次/天\n"
        f"🎲 成功率：动态概率（30%-70%）\n"
        f"💸 成功税收：10% + 高等级额外5%\n"
        f"💸 失败税收：10%\n"
        f"📈 金额限制：10 - 10000 🪙\n\n"
        f"📋 *动态概率规则*\n"
        f"  • 基础概率：50%\n"
        f"  • 等级优势：每高1级+5%\n"
        f"  • 余额优势：余额少于对方+5%\n"
        f"  • 首次打劫：+5%\n"
        f"  • 次数惩罚：每次-3%\n\n"
        f"💡 使用方法：回复目标消息 + `/rob <金额>`\n"
        f"例如：`/rob 100`\n\n"
        f"直接复制：`/rob 100`\n"
        f"━━━━━━━━━━━━━━━━━━",
        parse_mode='Markdown'
    )
    
    # 1分钟后自动删除消息
    import asyncio
    await asyncio.sleep(60)
    try:
        await status_message.delete()
    except Exception as e:
        print(f"删除打劫状态消息失败: {e}")
