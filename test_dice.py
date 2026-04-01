#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试骰子结果处理器
"""

from telegram import Update, Message, Dice, User, Chat
from telegram.ext import ContextTypes
from main import handle_dice_result, private_guess_games

async def test_handle_dice_result():
    """测试 handle_dice_result 函数"""
    print("=== 测试 handle_dice_result 函数 ===")
    
    # 模拟更新对象
    user = User(id=12345, first_name="Test User", is_bot=False)
    chat = Chat(id=67890, type="group")
    
    # 模拟回复消息
    reply_message = Message(
        message_id=100,
        date=None,
        chat=chat,
        from_user=user
    )
    
    # 模拟骰子消息
    dice = Dice(value=5, emoji="🎲")
    dice_message = Message(
        message_id=101,
        date=None,
        chat=chat,
        from_user=user,
        reply_to_message=reply_message,
        dice=dice
    )
    
    # 模拟更新
    update = Update(
        update_id=123,
        message=dice_message
    )
    
    # 模拟上下文
    class MockContext:
        def __init__(self):
            self.user_data = {}
    
    context = MockContext()
    
    # 保存游戏状态
    private_guess_games[chat.id] = {
        user.id: {
            'amount': 10,
            'guess': '大',
            'emos_user_id': '12345'
        }
    }
    
    print(f"private_guess_games 状态: {private_guess_games}")
    
    # 调用处理函数
    try:
        await handle_dice_result(update, context)
        print("✅ 测试成功！")
    except Exception as e:
        print(f"❌ 测试失败: {e}")
        import traceback
        traceback.print_exc()
    
    print(f"private_guess_games 状态: {private_guess_games}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_handle_dice_result())
