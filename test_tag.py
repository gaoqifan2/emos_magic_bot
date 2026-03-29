#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试群标签赋予功能（使用 Telegram Bot API 9.5）
"""

import httpx
from config import Config, DEFAULT_GROUP_CHAT_ID

# 获取 BOT_TOKEN
BOT_TOKEN = Config.BOT_TOKEN

# 测试用户的 Telegram ID（用户提供的）
TEST_USER_ID = 8230046662  # 用户提供的 Telegram ID

def test_set_chat_member_tag():
    """测试设置群成员标签"""
    print("开始测试群标签赋予功能...")
    print(f"BOT_TOKEN: {BOT_TOKEN[:10]}...")  # 只显示前10个字符，保护隐私
    print(f"DEFAULT_GROUP_CHAT_ID: {DEFAULT_GROUP_CHAT_ID}")
    print(f"测试用户ID: {TEST_USER_ID}")
    
    # 使用 Telegram Bot API 9.5 设置标签
    api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMemberTag"
    payload = {
        "chat_id": DEFAULT_GROUP_CHAT_ID,
        "user_id": TEST_USER_ID,
        "tag": "新手村"  # 使用正确的参数名 tag，而不是 tag_name
    }
    
    try:
        response = httpx.post(api_url, json=payload, timeout=10)
        print(f"\nAPI响应状态码: {response.status_code}")
        print(f"API响应内容: {response.text}")
        
        if response.status_code == 200:
            print("\n✅ 标签设置成功！")
        else:
            print("\n❌ 标签设置失败！")
            print("可能的原因：")
            print("1. 机器人不是群管理员")
            print("2. 机器人没有 can_manage_tags 权限")
            print("3. 群聊 ID 不正确")
            print("4. 用户不在群聊中")
    except Exception as e:
        print(f"\n❌ 测试失败: {e}")

if __name__ == "__main__":
    test_set_chat_member_tag()
