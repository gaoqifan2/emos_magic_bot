"""
游戏规则模块
显示所有游戏的规则说明
"""

from telegram import Update
from telegram.ext import ContextTypes


async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示游戏规则"""
    
    rules_text = """
🎮 *游戏规则说明*
━━━━━━━━━━━━━━━━━━

🎲 *猜大小游戏* /guess
• 私聊：/guess <金额> <大/小>
• 群聊：回复消息 + /guess <金额> <大/小>
• 规则：4-6为大，1-3为小
• 赔率：1:1（扣除10%服务费）

🎰 *老虎机游戏* /slot
• 私聊：/slot <金额>
• 规则：3个相同图案即中奖
• 赔率：根据图案不同

🃏 *21点游戏* /blackjack
• 私聊：/blackjack <金额>
• 规则：点数接近21点，超过21点爆牌
• 赔率：1:1（黑杰克1.5:1）

✊ *猜拳游戏* /gameshoot
• 私聊：/gameshoot <金额>
• 群聊：回复消息 + /gameshoot <金额>
• 规则：石头剪刀布，平局返还
• 赔率：1:1

🎭 *打劫游戏* /rob
• 群聊：回复消息 + /rob <金额>
• 规则：成功率50%
• 成功：抢到金额（扣除10%税）
• 失败：损失输入金额
• 限制：每天最多3次，金额10-10000

👥 *群聊庄家模式* /createguess
• 创建：/createguess <金额> <大/小>
• 下注：/guess_bet <金额> <大/小>
• 规则：多人下注，庄家开奖
• 赔率：动态计算

━━━━━━━━━━━━━━━━━━
💡 使用 /balance 查看余额
💡 使用 /help 查看所有命令
"""
    
    await update.message.reply_text(rules_text, parse_mode='Markdown')
