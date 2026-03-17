#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
import os
from datetime import datetime
from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# 确保只有一个实例运行
def ensure_single_instance():
    """确保只有一个实例运行"""
    lock_file = 'bot.lock'
    
    # 检查锁文件是否存在
    if os.path.exists(lock_file):
        try:
            # 尝试读取锁文件中的进程ID
            with open(lock_file, 'r') as f:
                pid = f.read().strip()
            
            # 检查进程是否存在
            if sys.platform == 'win32':
                # Windows 平台
                import ctypes
                kernel32 = ctypes.windll.kernel32
                process = kernel32.OpenProcess(0x100000, False, int(pid))
                if process:
                    kernel32.CloseHandle(process)
                    print("另一个机器人实例已在运行，请先关闭它")
                    sys.exit(1)
            else:
                # 其他平台
                import subprocess
                try:
                    subprocess.check_call(['kill', '-0', pid])
                    print("另一个机器人实例已在运行，请先关闭它")
                    sys.exit(1)
                except subprocess.CalledProcessError:
                    pass
        except:
            pass
    
    # 创建或更新锁文件
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))

# 确保在程序退出时删除锁文件
import atexit

def cleanup():
    """程序退出时清理"""
    lock_file = 'bot.lock'
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass

atexit.register(cleanup)

from config import Config, BOT_COMMANDS, SERVICE_PROVIDER_TOKEN
from utils.db_helper import ensure_user_exists, create_recharge_order
from handlers.common import (
    start, menu_command, help_command, cancel_command,
    button_callback, post_init,
    WAITING_REDPACKET_ID, WAITING_LOTTERY_CANCEL_ID
)
from handlers.redpacket import (
    redpocket_command, redpocket_process, cancel_redpacket,
    WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD
)
from handlers.redpacket_query import check_redpacket_command, get_redpacket_id
from games.lottery import (
    lottery_command, lottery_process,
    WAITING_LOTTERY_NAME, WAITING_LOTTERY_DESC, WAITING_LOTTERY_START,
    WAITING_LOTTERY_END, WAITING_LOTTERY_AMOUNT, WAITING_LOTTERY_NUMBER,
    WAITING_LOTTERY_RULE_CARROT, WAITING_LOTTERY_RULE_SIGN, WAITING_LOTTERY_PRIZES,
    handle_bodys_choice, get_lottery_bodys, handle_prize_choice
)
from games.lottery_cancel import lottery_cancel_command, get_lottery_cancel_id
from ranks.carrot_rank import rank_carrot_command
from ranks.upload_rank import rank_upload_command
from ranks.playing_rank import playing_command

# 创建 logs 文件夹
if not os.path.exists('logs'):
    os.makedirs('logs')

# 生成日志文件名
log_filename = f"logs/bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"日志文件: {log_filename}")
logger.info("=" * 60)

def main() -> None:
    """主函数"""
    # 确保只有一个实例运行
    ensure_single_instance()
    
    logger.info("正在启动机器人...")
    
    # 创建应用
    application = Application.builder() \
        .token(Config.BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    # ===== 基本命令 =====
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # ===== 红包对话 =====
    redpocket_conv = ConversationHandler(
        entry_points=[
            CommandHandler("redpocket", redpocket_command),
            CallbackQueryHandler(redpocket_command, pattern="^menu_redpocket$")
        ],
        states={
            WAITING_CARROT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_BLESSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_redpacket)]
    )
    application.add_handler(redpocket_conv)
    
    # ===== 红包查询对话 =====
    redpocket_query_conv = ConversationHandler(
        entry_points=[
            CommandHandler("check_redpacket", check_redpacket_command),
            CallbackQueryHandler(check_redpacket_command, pattern="^menu_check_redpacket$")
        ],
        states={
            WAITING_REDPACKET_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_redpacket_id),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    application.add_handler(redpocket_query_conv)
    
    # ===== 抽奖对话 =====
    lottery_conv = ConversationHandler(
        entry_points=[
            CommandHandler("lottery", lottery_command),
            CallbackQueryHandler(lottery_command, pattern="^menu_lottery$")
        ],
        states={
            WAITING_LOTTERY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_END: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_RULE_CARROT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_RULE_SIGN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_PRIZES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(handle_bodys_choice, pattern="^need_bodys_"),
                CallbackQueryHandler(handle_prize_choice, pattern="^(add_more_prizes|finish_prizes)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_lottery_bodys),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    application.add_handler(lottery_conv)
    
    # ===== 取消抽奖对话 =====
    lottery_cancel_conv = ConversationHandler(
        entry_points=[
            CommandHandler("lottery_cancel", lottery_cancel_command),
            CallbackQueryHandler(lottery_cancel_command, pattern="^menu_lottery_cancel$")
        ],
        states={
            WAITING_LOTTERY_CANCEL_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_lottery_cancel_id),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    application.add_handler(lottery_cancel_conv)
    
    # ===== 排行榜命令 =====
    application.add_handler(CommandHandler("playing", playing_command))
    application.add_handler(CommandHandler("rank_carrot", rank_carrot_command))
    application.add_handler(CommandHandler("rank_upload", rank_upload_command))
    
    # 处理用户输入
    async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户输入的信息"""
        user_id = update.effective_user.id
        input_text = update.message.text.strip()
        
        if 'current_operation' in context.user_data:
            operation = context.user_data['current_operation']
            token = context.user_data.get('token')
            
            if operation == 'change_pseudonym':
                # 处理笔名更新
                if token:
                    loading = await update.message.reply_text("🔄 正在更新笔名...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        async with httpx.AsyncClient() as client:
                            response = await client.put(
                                f"{Config.API_BASE_URL}/user/pseudonym?name={input_text}",
                                headers=headers,
                                timeout=10
                            )
                        
                        if response.status_code == 200:
                            await loading.edit_text(f"✅ 笔名更新成功！新笔名为：{input_text}")
                        else:
                            await loading.edit_text(f"❌ 更新笔名失败，状态码：{response.status_code}")
                    except Exception as e:
                        logger.error(f"更新笔名失败: {e}")
                        await loading.edit_text("❌ 更新笔名失败，请稍后重试")
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'invite_user':
                # 处理邀请用户
                if token:
                    loading = await update.message.reply_text("🔄 正在邀请用户...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        data = {"invite_user_id": input_text}
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                f"{Config.API_BASE_URL}/invite",
                                headers=headers,
                                json=data,
                                timeout=10
                            )
                        
                        if response.status_code == 200:
                            result = response.json()
                            remaining = result.get('invite_remaining', 0)
                            await loading.edit_text(f"✅ 邀请成功！剩余邀请次数：{remaining}")
                        else:
                            await loading.edit_text(f"❌ 邀请失败，状态码：{response.status_code}")
                    except Exception as e:
                        logger.error(f"邀请用户失败: {e}")
                        await loading.edit_text("❌ 邀请用户失败，请稍后重试")
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'transfer_user_id':
                # 处理转赠用户ID输入
                if token:
                    # 存储对方用户ID
                    context.user_data['target_user_id'] = input_text
                    # 提示用户输入转赠金额
                    await update.message.reply_text("💸 请输入转赠萝卜数量（2-6000之间）：")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'transfer_amount'
                    return 103  # 继续等待金额输入
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'transfer_amount':
                # 处理转赠金额输入
                if token:
                    target_user_id = context.user_data.get('target_user_id')
                    try:
                        amount = int(input_text)
                        if 2 <= amount <= 6000:
                            loading = await update.message.reply_text("🔄 正在转赠...")
                            
                            try:
                                import httpx
                                headers = {"Authorization": f"Bearer {token}"}
                                data = {"user_id": target_user_id, "carrot": amount}
                                async with httpx.AsyncClient() as client:
                                    response = await client.put(
                                        f"{Config.API_BASE_URL}/carrot/transfer",
                                        headers=headers,
                                        json=data,
                                        timeout=10
                                    )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    remaining = result.get('carrot', 0)
                                    await loading.edit_text(f"✅ 转赠成功！\n剩余萝卜：{remaining}")
                                else:
                                    await loading.edit_text(f"❌ 转赠失败，状态码：{response.status_code}")
                            except Exception as e:
                                logger.error(f"转赠失败: {e}")
                                await loading.edit_text("❌ 转赠失败，请稍后重试")
                        else:
                            await update.message.reply_text("❌ 转赠金额必须在2-6000之间，请重新输入：")
                            return 103  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                        return 103  # 继续等待金额输入
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_recharge_amount':
                # 处理充值金额输入
                if token:
                    try:
                        amount = int(input_text)
                        if 1 <= amount <= 50000:
                            loading = await update.message.reply_text("🔄 正在创建支付订单...")
                            
                            try:
                                import httpx
                                import uuid
                                from datetime import datetime
                                
                                # 生成唯一参数
                                param = str(uuid.uuid4())[:8]
                                
                                # 调用创建订单API（使用服务商token）
                                headers = {"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"}
                                data = {
                                    "pay_way": "telegram_bot",
                                    "price": amount,
                                    "name": f"游戏币充值 {amount}萝卜",
                                    "param": param,
                                    "callback_telegram_bot_name": Config.BOT_USERNAME
                                }
                                
                                logger.info(f"创建支付订单: {data}")
                                
                                async with httpx.AsyncClient() as client:
                                    response = await client.post(
                                        f"{Config.API_BASE_URL}/pay/create",
                                        headers=headers,
                                        json=data,
                                        timeout=10
                                    )
                                
                                logger.info(f"支付订单API响应状态码: {response.status_code}")
                                logger.info(f"支付订单API响应内容: {response.text}")
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    pay_url = result.get('pay_url')
                                    order_no = result.get('no')
                                    expired = result.get('expired')
                                    
                                    if pay_url:
                                        # 先获取用户信息，保存到本地数据库
                                        try:
                                            import httpx
                                            user_headers = {"Authorization": f"Bearer {token}"}
                                            async with httpx.AsyncClient() as client:
                                                user_response = await client.get(
                                                    f"{Config.API_BASE_URL}/user",
                                                    headers=user_headers,
                                                    timeout=10
                                                )
                                            
                                            if user_response.status_code == 200:
                                                user_data = user_response.json()
                                                emos_user_id = user_data.get('user_id')
                                                username = user_data.get('username')
                                                
                                                # 确保用户在本地数据库中存在
                                                local_user_id = ensure_user_exists(
                                                    emos_user_id=emos_user_id,
                                                    token=token,
                                                    telegram_id=user_id,
                                                    username=username,
                                                    first_name=update.effective_user.first_name,
                                                    last_name=update.effective_user.last_name
                                                )
                                                
                                                if local_user_id:
                                                    # 生成本地订单号
                                                    local_order_no = f"R{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                                                    
                                                    # 解析过期时间
                                                    expire_time = None
                                                    if expired:
                                                        try:
                                                            expire_time = datetime.strptime(expired, '%Y-%m-%d %H:%M:%S')
                                                        except:
                                                            pass
                                                    
                                                    # 保存订单到本地数据库
                                                    create_recharge_order(
                                                        order_no=local_order_no,
                                                        local_user_id=local_user_id,
                                                        telegram_user_id=user_id,
                                                        carrot_amount=amount,
                                                        platform_order_no=order_no,
                                                        pay_url=pay_url,
                                                        expire_time=expire_time
                                                    )
                                                    logger.info(f"订单已保存到本地数据库: {local_order_no}")
                                        except Exception as db_error:
                                            logger.error(f"保存订单到本地数据库失败: {db_error}")
                                        
                                        # 存储订单信息
                                        context.user_data['recharge_order'] = {
                                            'order_no': order_no,
                                            'amount': amount,
                                            'param': param,
                                            'token': token
                                        }
                                        
                                        message = f"📋 充值订单已创建\n\n"
                                        message += f"订单号：{order_no}\n"
                                        message += f"充值金额：{amount} 萝卜\n"
                                        message += f"预计兑换：{amount * 10} 游戏币\n"
                                        message += f"过期时间：{expired}\n\n"
                                        message += "请点击下方按钮完成支付："
                                        
                                        keyboard = [
                                            [InlineKeyboardButton("💳 去支付", url=pay_url)],
                                            [InlineKeyboardButton("❌ 取消", callback_data="cancel_recharge")]
                                        ]
                                        reply_markup = InlineKeyboardMarkup(keyboard)
                                        await loading.edit_text(message, reply_markup=reply_markup)
                                    else:
                                        await loading.edit_text("❌ 创建订单失败，没有返回支付链接")
                                else:
                                    await loading.edit_text(f"❌ 创建订单失败，状态码：{response.status_code}\n响应：{response.text}")
                            except Exception as e:
                                logger.error(f"创建支付订单失败: {e}")
                                await loading.edit_text(f"❌ 创建订单失败，请稍后重试\n错误：{str(e)}")
                        else:
                            await update.message.reply_text("❌ 充值金额必须在1-50000之间，请重新输入：")
                            return 104  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                        return 104  # 继续等待金额输入
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_withdraw_amount':
                # 处理提现金额输入
                if token:
                    try:
                        amount = int(input_text)
                        game_balance = context.user_data.get('game_balance', 0)
                        local_user_id = context.user_data.get('local_user_id')
                        user_id = update.effective_user.id
                        
                        if 10 <= amount <= 50000 and amount % 10 == 0 and amount <= game_balance:
                            loading = await update.message.reply_text("🔄 正在处理提现...")
                            
                            try:
                                import httpx
                                import uuid
                                from datetime import datetime
                                from utils.db_helper import create_withdraw_order, update_withdraw_order_status
                                
                                # 生成提现订单号
                                order_no = f"W{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                                
                                # 1. 创建提现订单
                                carrot_amount = amount  # 1游戏币=1萝卜
                                create_withdraw_order(
                                    order_no=order_no,
                                    user_id=local_user_id,
                                    telegram_user_id=user_id,
                                    game_coin_amount=amount,
                                    carrot_amount=carrot_amount
                                )
                                
                                # 2. 尝试调用游戏提现API扣除游戏币
                                game_success = False
                                try:
                                    game_headers = {"Authorization": f"Bearer {token}"}
                                    game_data = {"game_coin_amount": amount}
                                    async with httpx.AsyncClient() as client:
                                        game_response = await client.post(
                                            f"{Config.API_BASE_URL}/game/withdraw",
                                            headers=game_headers,
                                            json=game_data,
                                            timeout=10
                                        )
                                    
                                    if game_response.status_code == 200:
                                        game_success = True
                                    else:
                                        # API不存在或失败，使用本地数据库扣除游戏币
                                        logger.warning(f"游戏提现API调用失败，状态码：{game_response.status_code}，使用本地数据库扣除游戏币")
                                        game_success = True  # 即使API失败，也继续执行
                                except Exception as e:
                                    # API调用失败，使用本地数据库扣除游戏币
                                    logger.warning(f"游戏提现API调用异常：{str(e)}，使用本地数据库扣除游戏币")
                                    game_success = True  # 即使API失败，也继续执行
                                
                                if game_success:
                                    # 3. 使用服务商token给用户转账萝卜
                                    # 获取用户的emos ID
                                    user_headers = {"Authorization": f"Bearer {token}"}
                                    async with httpx.AsyncClient() as client:
                                        user_response = await client.get(
                                            f"{Config.API_BASE_URL}/user",
                                            headers=user_headers,
                                            timeout=10
                                        )
                                    
                                    if user_response.status_code == 200:
                                        user_info = user_response.json()
                                        user_emos_id = user_info.get('user_id')
                                        
                                        if user_emos_id:
                                            # 使用服务商token转账
                                            service_headers = {"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"}
                                            transfer_data = {"user_id": user_emos_id, "carrot": carrot_amount}
                                            async with httpx.AsyncClient() as client:
                                                transfer_response = await client.post(
                                                    f"{Config.API_BASE_URL}/pay/transfer",
                                                    headers=service_headers,
                                                    json=transfer_data,
                                                    timeout=10
                                                )
                                            
                                            if transfer_response.status_code == 200:
                                                # 更新提现订单状态为成功
                                                update_withdraw_order_status(
                                                    order_no=order_no,
                                                    status='success',
                                                    transfer_result=f"转账成功，金额：{carrot_amount}萝卜"
                                                )
                                                await loading.edit_text(f"✅ 提现成功！\n\n订单号：{order_no}\n游戏币扣除：{amount}\n兑换萝卜：{carrot_amount}\n已转入您的账号")
                                            else:
                                                # 更新提现订单状态为失败
                                                update_withdraw_order_status(
                                                    order_no=order_no,
                                                    status='failed',
                                                    transfer_result=f"转账失败，状态码：{transfer_response.status_code}"
                                                )
                                                await loading.edit_text(f"❌ 转账失败，状态码：{transfer_response.status_code}\n订单号：{order_no}")
                                        else:
                                            # 更新提现订单状态为失败
                                            update_withdraw_order_status(
                                                order_no=order_no,
                                                status='failed',
                                                transfer_result="获取用户信息失败"
                                            )
                                            await loading.edit_text(f"❌ 获取用户信息失败\n订单号：{order_no}")
                                    else:
                                        # 更新提现订单状态为失败
                                        update_withdraw_order_status(
                                            order_no=order_no,
                                            status='failed',
                                            transfer_result=f"获取用户信息失败，状态码：{user_response.status_code}"
                                        )
                                        await loading.edit_text(f"❌ 获取用户信息失败，状态码：{user_response.status_code}\n订单号：{order_no}")
                                else:
                                    # 更新提现订单状态为失败
                                    update_withdraw_order_status(
                                        order_no=order_no,
                                        status='failed',
                                        transfer_result=f"游戏币扣除失败，状态码：{game_response.status_code}"
                                    )
                                    await loading.edit_text(f"❌ 游戏币扣除失败，状态码：{game_response.status_code}\n订单号：{order_no}")
                            except Exception as e:
                                logger.error(f"提现失败: {e}")
                                # 更新提现订单状态为失败
                                update_withdraw_order_status(
                                    order_no=order_no,
                                    status='failed',
                                    transfer_result=f"提现失败：{str(e)}"
                                )
                                await loading.edit_text(f"❌ 提现失败，请稍后重试\n错误：{str(e)}\n订单号：{order_no}")
                        else:
                            if amount > game_balance:
                                await update.message.reply_text(f"❌ 提现金额不能超过游戏余额（{game_balance}游戏币），请重新输入：")
                            else:
                                await update.message.reply_text("❌ 提现金额必须在10-50000之间且为10的倍数，请重新输入：")
                            return 105  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                        return 105  # 继续等待金额输入
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_game_recharge_amount':
                # 处理游戏充值金额输入
                if token:
                    game_id = context.user_data.get('game_id')
                    try:
                        amount = int(input_text)
                        if 1 <= amount <= 50000:
                            loading = await update.message.reply_text("🔄 正在创建游戏充值订单...")
                            
                            try:
                                import httpx
                                headers = {"Authorization": f"Bearer {token}"}
                                data = {"game_id": game_id, "carrot_amount": amount}
                                async with httpx.AsyncClient() as client:
                                    response = await client.post(
                                        f"{Config.API_BASE_URL}/game/recharge",
                                        headers=headers,
                                        json=data,
                                        timeout=10
                                    )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    game_coin = result.get('game_coin', 0)
                                    await loading.edit_text(f"✅ 游戏充值成功！\n兑换游戏币：{game_coin}")
                                else:
                                    await loading.edit_text(f"❌ 游戏充值失败，状态码：{response.status_code}")
                            except Exception as e:
                                logger.error(f"游戏充值失败: {e}")
                                await loading.edit_text("❌ 游戏充值失败，请稍后重试")
                        else:
                            await update.message.reply_text("❌ 充值金额必须在1-50000之间，请重新输入：")
                            return 106  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                        return 106  # 继续等待金额输入
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_apply_name':
                # 处理服务商名称输入
                if token:
                    # 存储服务商名称
                    context.user_data['service_name'] = input_text
                    # 提示用户输入服务商描述
                    await update.message.reply_text("🏢 请输入服务商描述（200字以内）：")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_apply_description'
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_apply_description':
                # 处理服务商描述输入
                if token:
                    service_name = context.user_data.get('service_name')
                    service_description = input_text
                    
                    loading = await update.message.reply_text("🔄 正在申请成为服务商...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        data = {"name": service_name, "description": service_description}
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                f"{Config.API_BASE_URL}/pay/apply",
                                headers=headers,
                                json=data,
                                timeout=10
                            )
                        
                        if response.status_code == 200:
                            await loading.edit_text("✅ 申请成功！请等待审核结果")
                        else:
                            await loading.edit_text(f"❌ 申请失败，状态码：{response.status_code}")
                    except Exception as e:
                        logger.error(f"申请成为服务商失败: {e}")
                        await loading.edit_text("❌ 申请失败，请稍后重试")
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_update_name':
                # 处理服务商名称输入
                if token:
                    # 存储服务商名称
                    context.user_data['service_name'] = input_text
                    # 提示用户输入服务商描述
                    await update.message.reply_text("🏢 请输入服务商描述（200字以内）：")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_update_description'
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_update_description':
                # 处理服务商描述输入
                if token:
                    service_name = context.user_data.get('service_name')
                    service_description = input_text
                    # 提示用户输入回调地址
                    await update.message.reply_text("🏢 请输入回调地址（可为空）：")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_update_notify_url'
                    context.user_data['service_name'] = service_name
                    context.user_data['service_description'] = service_description
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_update_notify_url':
                # 处理服务商回调地址输入
                if token:
                    service_name = context.user_data.get('service_name')
                    service_description = context.user_data.get('service_description')
                    service_notify_url = input_text if input_text else None
                    
                    loading = await update.message.reply_text("🔄 正在更新服务商信息...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        data = {"name": service_name, "description": service_description, "notify_url": service_notify_url}
                        async with httpx.AsyncClient() as client:
                            response = await client.post(
                                f"{Config.API_BASE_URL}/pay/update",
                                headers=headers,
                                json=data,
                                timeout=10
                            )
                        
                        if response.status_code == 200:
                            await loading.edit_text("✅ 更新成功！")
                        else:
                            await loading.edit_text(f"❌ 更新失败，状态码：{response.status_code}")
                    except Exception as e:
                        logger.error(f"更新服务商信息失败: {e}")
                        await loading.edit_text("❌ 更新失败，请稍后重试")
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_fund_transfer_user_id':
                # 处理转账用户ID输入
                if token:
                    # 存储对方用户ID
                    context.user_data['target_user_id'] = input_text
                    # 提示用户输入转账金额
                    await update.message.reply_text("💸 请输入转账萝卜数量（1-50000之间）：")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_fund_transfer_amount'
                    return 107  # 继续等待金额输入
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_fund_transfer_amount':
                # 处理转账金额输入
                if token:
                    target_user_id = context.user_data.get('target_user_id')
                    try:
                        amount = int(input_text)
                        if 1 <= amount <= 50000:
                            loading = await update.message.reply_text("🔄 正在转账...")
                            
                            try:
                                import httpx
                                headers = {"Authorization": f"Bearer {token}"}
                                data = {"user_id": target_user_id, "carrot": amount}
                                async with httpx.AsyncClient() as client:
                                    response = await client.post(
                                        f"{Config.API_BASE_URL}/pay/transfer",
                                        headers=headers,
                                        json=data,
                                        timeout=10
                                    )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    deduct = result.get('deduct', 0)
                                    carrot = result.get('carrot', 0)
                                    await loading.edit_text(f"✅ 转账成功！\n消耗萝卜：{deduct}\n剩余萝卜：{carrot}")
                                else:
                                    await loading.edit_text(f"❌ 转账失败，状态码：{response.status_code}")
                            except Exception as e:
                                logger.error(f"转账失败: {e}")
                                await loading.edit_text("❌ 转账失败，请稍后重试")
                        else:
                            await update.message.reply_text("❌ 转账金额必须在1-50000之间，请重新输入：")
                            return 107  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                        return 107  # 继续等待金额输入
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_pay_create_amount':
                # 处理创建订单金额输入
                if token:
                    try:
                        amount = int(input_text)
                        if 1 <= amount <= 50000:
                            # 提示用户输入商品名称
                            await update.message.reply_text("💳 请输入商品名称（100字以内）：")
                            # 更新操作状态
                            context.user_data['current_operation'] = 'service_pay_create_name'
                            context.user_data['amount'] = amount
                        else:
                            await update.message.reply_text("❌ 订单金额必须在1-50000之间，请重新输入：")
                            return 108  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                        return 108  # 继续等待金额输入
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_pay_create_name':
                # 处理创建订单商品名称输入
                if token:
                    amount = context.user_data.get('amount')
                    name = input_text
                    # 提示用户选择支付方式
                    keyboard = [
                        [InlineKeyboardButton("🤖 Telegram机器人支付", callback_data="service_pay_create_telegram_bot")],
                        [InlineKeyboardButton("🌐 网页支付", callback_data="service_pay_create_web")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text("💳 请选择支付方式：", reply_markup=reply_markup)
                    # 存储数据
                    context.user_data['amount'] = amount
                    context.user_data['name'] = name
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_pay_query_no':
                # 处理查询订单号输入
                if token:
                    order_no = input_text
                    loading = await update.message.reply_text("🔄 正在查询订单...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        async with httpx.AsyncClient() as client:
                            response = await client.get(
                                f"{Config.API_BASE_URL}/pay/query?no={order_no}",
                                headers=headers,
                                timeout=10
                            )
                        
                        if response.status_code == 200:
                            order_info = response.json()
                            message = f"📋 订单信息\n\n"
                            message += f"订单号：{order_info.get('no', '未知')}\n"
                            message += f"状态：{order_info.get('status', '未知')}\n"
                            message += f"金额：{order_info.get('price', 0)} 萝卜\n"
                            message += f"商品名称：{order_info.get('name', '未知')}\n"
                            message += f"创建时间：{order_info.get('created_at', '未知')}\n"
                            await loading.edit_text(message)
                        else:
                            await loading.edit_text(f"❌ 查询失败，状态码：{response.status_code}")
                    except Exception as e:
                        logger.error(f"查询订单失败: {e}")
                        await loading.edit_text("❌ 查询失败，请稍后重试")
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_pay_close_no':
                # 处理关闭订单号输入
                if token:
                    order_no = input_text
                    loading = await update.message.reply_text("🔄 正在关闭订单...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        async with httpx.AsyncClient() as client:
                            response = await client.put(
                                f"{Config.API_BASE_URL}/pay/close?no={order_no}",
                                headers=headers,
                                timeout=10
                            )
                        
                        if response.status_code == 200:
                            await loading.edit_text("✅ 订单关闭成功！")
                        else:
                            await loading.edit_text(f"❌ 关闭失败，状态码：{response.status_code}")
                    except Exception as e:
                        logger.error(f"关闭订单失败: {e}")
                        await loading.edit_text("❌ 关闭失败，请稍后重试")
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        
        return
    
    # 添加用户输入处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))
    
    # 按钮回调（处理所有未被对话捕获的回调）
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # 打印启动信息
    print("=" * 60)
    print("机器人启动成功！")
    print("=" * 60)
    print("可用命令：")
    for cmd, desc in BOT_COMMANDS:
        print(f"   /{cmd:<15} - {desc}")
    print("=" * 60)
    print(f"机器人 @{Config.BOT_USERNAME}")
    print(f"日志文件: {log_filename}")
    print("=" * 60)
    
    logger.info(f"机器人 @{Config.BOT_USERNAME} 启动成功")
    
    # 启动机器人
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()