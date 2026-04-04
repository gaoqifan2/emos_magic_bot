#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
import os
import httpx
import asyncio
import time
from datetime import datetime, timedelta, timezone

# 强制设置异步库，解决 sniffio 无法检测到异步库的问题
import sniffio
sniffio.current_async_library = lambda: "asyncio"

# 兼容 Python 3.12+, 替换已被移除的 imghdr 模块
sys.modules['imghdr'] = __import__('utils.imghdr_compat')

# 设置环境变量
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LANG'] = 'zh_CN.UTF-8'
os.environ['LC_ALL'] = 'zh_CN.UTF-8'
os.environ['LC_CTYPE'] = 'zh_CN.UTF-8'

# Windows平台特殊处理
if sys.platform == 'win32':
    # 尝试设置Windows控制台编码
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleOutputCP(65001)
        kernel32.SetConsoleCP(65001)
    except:
        pass

# Fix for Python 3.13+ event loop issue
if sys.version_info >= (3, 13):
    try:
        import signal
        # Python 3.13+ 需要使用 get_running_loop 或 new_event_loop
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        # 禁用信号处理
        loop.add_signal_handler = lambda sig, handler: None
    except:
        pass

# 北京时间 UTC+8
beijing_tz = timezone(timedelta(hours=8))

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

# 导入HTTP客户端
from utils.http_client import http_client

# 每日从AI游戏净赢取上限
DAILY_NET_WIN_LIMIT = 10000

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
                    print("另一个机器人实例已在运行, 请先关闭它")
                    sys.exit(1)
            else:
                # 其他平台
                import subprocess
                try:
                    subprocess.check_call(['kill', '-0', pid])
                    print("另一个机器人实例已在运行, 请先关闭它")
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

def clear_operation_data(context):
    """清理操作相关的用户数据, 保留登录信息"""
    # 保留的关键字段
    preserved_keys = ['token', 'user_id', 'local_user_id', 'emos_user_id', 'username']
    
    # 获取需要保留的值
    preserved_data = {}
    for key in preserved_keys:
        if key in context.user_data:
            preserved_data[key] = context.user_data[key]
    
    # 清理所有数据
    context.user_data.clear()
    
    # 恢复保留的数据
    for key, value in preserved_data.items():
        context.user_data[key] = value

from config import Config, BOT_COMMANDS, SERVICE_PROVIDER_TOKEN, user_tokens, GROUP_ALLOWED_COMMANDS
from utils.db_helper import ensure_user_exists, create_recharge_order
from handlers.common import (
    start, menu_command, help_command, cancel_command,
    button_callback, post_init,
    WAITING_REDPACKET_ID, WAITING_LOTTERY_CANCEL_ID
)
from handlers.rules import rules_handler

# 群聊命令过滤装饰器
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

def group_command_filter(func):
    """群聊命令过滤装饰器"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 检查是否是群聊
        if update.message and update.message.chat.type in ['group', 'supergroup']:
            # 获取命令名称, 处理带@机器人用户名的情况
            command_part = update.message.text.split(' ')[0].lstrip('/')
            # 移除@机器人用户名部分
            command = command_part.split('@')[0]
            # 检查命令是否在允许列表中
            if command not in GROUP_ALLOWED_COMMANDS:
                # 群聊中不允许的命令, 不执行
                logger.info(f"群聊中拒绝执行命令 /{command_part}")
                return
        # 执行原函数
        return await func(update, context)
    return wrapper

from handlers.redpacket import (
    redpocket_command, handle_type, handle_carrot, handle_number, handle_blessing, 
    handle_password, handle_media, create_redpacket, cancel_redpacket, handle_scene, handle_custom_blessing,
    WAITING_TYPE, WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD, WAITING_MEDIA, WAITING_SCENE, WAITING_CUSTOM_BLESSING
)
from app.handlers.command_handlers import (
    start_handler, balance_handler, slot_handler, daily_handler, help_handler, 
    blackjack_handler, hit_handler, stand_handler, message_handler, withdraw_handler
)
from handlers.robbery import robbery_handler, robbery_status_handler
from handlers.card_games import cardduel_handler, join_cardduel_handler
from handlers.redpacket_query import WAITING_QUERY_TYPE
from handlers.redpacket_query import check_redpacket_command, get_redpacket_id, handle_query_type
from games.lottery import (
    lottery_command, lottery_process,
    WAITING_LOTTERY_NAME, WAITING_LOTTERY_DESC, WAITING_LOTTERY_START,
    WAITING_LOTTERY_END, WAITING_LOTTERY_AMOUNT, WAITING_LOTTERY_NUMBER,
    WAITING_LOTTERY_RULE_CARROT, WAITING_LOTTERY_RULE_SIGN, WAITING_LOTTERY_PRIZES,
    handle_bodys_choice, get_lottery_bodys, handle_prize_choice, handle_end_time_choice
)
from games.lottery_cancel import lottery_cancel_command, get_lottery_cancel_id
from ranks.carrot_rank import rank_carrot_command
from ranks.upload_rank import rank_upload_command
from ranks.playing_rank import playing_command
from utils.http_client import http_client

# 创建 logs 文件
if not os.path.exists('logs'):
    os.makedirs('logs')

# 设置环境变量确保UTF-8编码
os.environ['PYTHONIOENCODING'] = 'utf-8'
os.environ['LANG'] = 'zh_CN.UTF-8'

# 生成日志文件
log_filename = f"logs/bot_{datetime.now(beijing_tz).strftime('%Y%m%d_%H%M%S')}.log"

# 确保日志目录存在
if not os.path.exists('logs'):
    os.makedirs('logs')

# 设置标准输出和标准错误的编码
try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

# Windows平台编码处理
if sys.platform == 'win32':
    # 尝试多种方法设置Windows控制台编码
    try:
        # 方法1: 使用win32console
        import win32console
        win32console.SetConsoleOutputCP(65001)  # 设置控制台输出为UTF-8
        win32console.SetConsoleCP(65001)  # 设置控制台输入为UTF-8
    except ImportError:
        try:
            # 方法2: 使用ctypes
            import ctypes
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleOutputCP(65001)
            kernel32.SetConsoleCP(65001)
        except:
            # 方法3: 使用系统命令
            os.system('chcp 65001 >nul 2>&1')

# 配置日志处理器
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler = logging.FileHandler(log_filename, encoding='utf-8')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

# 配置根日志
logging.basicConfig(
    level=logging.INFO,
    handlers=[console_handler, file_handler],
    force=True
)

# 设置第三方库的日志级别为WARNING, 减少不必要的日志输出
logging.getLogger('telegram').setLevel(logging.WARNING)
logging.getLogger('httpx').setLevel(logging.WARNING)
logging.getLogger('httpcore').setLevel(logging.WARNING)

# 获取logger实例
logger = logging.getLogger(__name__)

logger.info(f"日志文件: {log_filename}")
logger.info("=" * 60)

# 猜拳游戏全局变量
shoot_games = {}

# 猜大小游戏全局变量
guess_games = {}  # 存储每个群的猜大小游戏
private_guess_games = {}  # 存储等待中的猜大小游戏(用于群聊)

# post_init 包装函数
async def post_init_wrapper(application):
    """包装post_init函数, 在设置命令菜单后启动游戏检查任务"""
    # 先调用原始的post_init函数
    await post_init(application)
    
    # 启动猜大小游戏检查任务
    logger.info("启动猜大小游戏检查任务..")
    asyncio.create_task(check_guess_games(application))
    logger.info("猜大小游戏检查任务已启动")
    
    # 启动猜拳游戏检查任务
    logger.info("启动猜拳游戏检查任务..")
    asyncio.create_task(check_shoot_games_task(application))
    logger.info("猜拳游戏检查任务已启动")
    
    # 启动游戏状态清理任务
    logger.info("启动游戏状态清理任务..")
    asyncio.create_task(cleanup_game_states_task())
    logger.info("游戏状态清理任务已启动")


# 游戏状态清理任务
async def cleanup_game_states_task():
    """定期清理过期的游戏状态"""
    while True:
        try:
            cleanup_expired_game_states()
        except Exception as e:
            logger.error(f"清理游戏状态失败 {e}")
        await asyncio.sleep(60)  # 每分钟检查一次


# 猜大小游戏检查任务函数
async def check_guess_games(application):
    """检查并处理过期的猜大小游戏"""
    while True:
        current_time = datetime.now()
        expired_games = []
        
        for chat_id, game in guess_games.items():
            if game['status'] == 'waiting' and current_time >= game['end_time']:
                expired_games.append(chat_id)
        
        for chat_id in expired_games:
            await end_guess_game(chat_id, application)
        
        await asyncio.sleep(10)  # 每10秒检查一次

async def end_guess_game(chat_id, application):
    if chat_id not in guess_games:
        return
    
    game = guess_games[chat_id]
    if game['status'] != 'waiting':
        return
    
    # 更新游戏状态
    game['status'] = 'playing'
    
    # 发送骰子
    bot = application.bot
    try:
        # 生成三个骰子的点数
        import random
        dice1 = random.randint(1, 6)
        dice2 = random.randint(1, 6)
        dice3 = random.randint(1, 6)
        total_value = dice1 + dice2 + dice3
        
        # 判断大小(三个骰子规则:4-10为小11-17为大
        if 4 <= total_value <= 10:
            actual_result = "小"
        else:
            actual_result = "大"

        # 奖池分配模式结算
        TAX_RATE = 0.1  # 系统抽水比例 10%
        winners = []  # 赢家列表
        losers = []  # 输家列表
        total_service_fee = 0

        # 计算胜方和输方总金额
        if actual_result == '小':
            winning_total = game['big_total']
            losing_total = game['small_total']
        else:
            winning_total = game['small_total']
            losing_total = game['big_total']
        
        # 处理单边投注情况
        if winning_total == 0:
            # 所有人都押输了, 退还本金
            # 处理庄家
            banker_user_info = user_tokens.get(game['banker'])
            if banker_user_info:
                banker_user_id = banker_user_info.get('user_id', game['banker'])
                banker_amount = game['banker_amount']
                from app.database import update_balance
                new_balance = update_balance(banker_user_id, banker_amount)
                
                winners.append({
                    'user_name': f"庄家 {game['banker_name']}",
                    'guess': game['banker_guess'],
                    'amount': banker_amount,
                    'win_amount': 0,
                    'net_profit': 0,
                    'new_balance': new_balance
                })
            
            # 处理闲家
            for user_id, bet in game['bets'].items():
                user_info = user_tokens.get(user_id)
                if not user_info:
                    continue
                
                user_id_str = user_info.get('user_id', user_id)
                bet_amount = bet['amount']
                user_name = bet['user_name']
                
                # 退还本金
                from app.database import update_balance
                new_balance = update_balance(user_id_str, bet_amount)
                
                winners.append({
                    'user_name': user_name,
                    'guess': bet['guess'],
                    'amount': bet_amount,
                    'win_amount': 0,
                    'net_profit': 0,
                    'new_balance': new_balance
                })
        elif losing_total == 0:
            # 所有人都押赢了, 退还本金
            # 处理庄家
            banker_user_info = user_tokens.get(game['banker'])
            if banker_user_info:
                banker_user_id = banker_user_info.get('user_id', game['banker'])
                banker_amount = game['banker_amount']
                from app.database import update_balance
                new_balance = update_balance(banker_user_id, banker_amount)
                
                winners.append({
                    'user_name': f"庄家 {game['banker_name']}",
                    'guess': game['banker_guess'],
                    'amount': banker_amount,
                    'win_amount': 0,
                    'net_profit': 0,
                    'new_balance': new_balance
                })
            
            # 处理闲家
            for user_id, bet in game['bets'].items():
                user_info = user_tokens.get(user_id)
                if not user_info:
                    continue
                
                user_id_str = user_info.get('user_id', user_id)
                bet_amount = bet['amount']
                user_name = bet['user_name']
                
                # 退还本金
                from app.database import update_balance
                new_balance = update_balance(user_id_str, bet_amount)
                
                winners.append({
                    'user_name': user_name,
                    'guess': bet['guess'],
                    'amount': bet_amount,
                    'win_amount': 0,
                    'net_profit': 0,
                    'new_balance': new_balance
                })
        else:
            # 正常情况:计算奖金并分配
            # 按照新规则分配：输家3%给庄，7%给平台，剩下90%按赢家下注比例分配
            banker_fee = int(losing_total * 0.03)  # 庄家获得3%
            platform_fee = int(losing_total * 0.07)  # 平台获得7%
            total_service_fee = banker_fee + platform_fee
            # 剩余部分作为奖池
            prize_pool = losing_total - total_service_fee
            
            # 处理庄家
            banker_user_info = user_tokens.get(game['banker'])
            if banker_user_info:
                banker_user_id = banker_user_info.get('user_id', game['banker'])
                banker_amount = game['banker_amount']
                banker_guess = game['banker_guess']
                
                if banker_guess == actual_result:
                    # 庄家赢了
                    # 计算庄家的奖金比例
                    banker_ratio = banker_amount / winning_total
                    # 计算庄家的奖（向下取整）
                    banker_prize = int(prize_pool * banker_ratio)
                    # 加上3%的服务费
                    total_banker_prize = banker_prize + banker_fee
                    banker_win_amount = banker_amount + total_banker_prize
                    banker_net_profit = total_banker_prize
                    
                    # 更新庄家余额
                    from app.database import update_balance
                    new_balance = update_balance(banker_user_id, total_banker_prize)
                    
                    winners.append({
                        'user_name': f"庄家 {game['banker_name']}",
                        'guess': banker_guess,
                        'amount': banker_amount,
                        'win_amount': banker_win_amount,
                        'net_profit': banker_net_profit,
                        'new_balance': new_balance
                    })
                else:
                    # 庄家输了
                    # 庄家已经在创建游戏时被扣除了下注金额
                    from app.database import get_balance
                    new_balance = get_balance(banker_user_id)
                    
                    losers.append({
                        'user_name': f"庄家 {game['banker_name']}",
                        'guess': banker_guess,
                        'amount': banker_amount,
                        'loss_amount': banker_amount,
                        'net_profit': -banker_amount,
                        'new_balance': new_balance
                    })
            
            # 处理闲家
            for user_id, bet in game['bets'].items():
                user_info = user_tokens.get(user_id)
                if not user_info:
                    continue
                
                user_id_str = user_info.get('user_id', user_id)
                bet_amount = bet['amount']
                guess = bet['guess']
                user_name = bet['user_name']
                
                if guess == actual_result:
                    # 闲家赢了
                    # 计算闲家的奖金比例
                    user_ratio = bet_amount / winning_total
                    # 计算闲家的奖（向下取整）
                    user_prize = int(prize_pool * user_ratio)
                    user_win_amount = bet_amount + user_prize
                    user_net_profit = user_prize
                    
                    # 更新闲家余额
                    from app.database import update_balance
                    new_balance = update_balance(user_id_str, user_prize)
                    
                    winners.append({
                        'user_name': user_name,
                        'guess': guess,
                        'amount': bet_amount,
                        'win_amount': user_win_amount,
                        'net_profit': user_net_profit,
                        'new_balance': new_balance
                    })
                else:
                    # 闲家输了
                    # 闲家已经在下注时被扣除了下注金额
                    from app.database import get_balance
                    new_balance = get_balance(user_id_str)
                    
                    losers.append({
                        'user_name': user_name,
                        'guess': guess,
                        'amount': bet_amount,
                        'loss_amount': bet_amount,
                        'net_profit': -bet_amount,
                        'new_balance': new_balance
                    })
        
        # 检查是否为空盘(没有玩家参与)
        is_empty_game = len(game['bets']) == 0
        empty_game_fee = 0
        
        if is_empty_game:
            # 计算空盘费(庄家下注金额*1%)
            empty_game_fee = int(game['banker_amount'] * 0.01)
            # 从庄家账户扣除空盘费
            banker_user_info = user_tokens.get(game['banker'])
            if banker_user_info:
                banker_user_id = banker_user_info.get('user_id', game['banker'])
                from app.database import update_balance
                update_balance(banker_user_id, -empty_game_fee)
                
                # 退还庄家的下注金额
                update_balance(banker_user_id, game['banker_amount'])
                
                # 更新庄家信息
                from app.database import get_balance
                new_balance = get_balance(banker_user_id)
                
                # 构建空盘结果
                result_message = f"NO.{game['game_no']}\n"
                result_message += f"🎲 开奖结果:{actual_result}(点数:{dice1}, {dice2}, {dice3}, 总和:{total_value})\n"
                result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                result_message += f"📊 本局结算明细:\n"
                result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                result_message += f"[空盘]\n"
                result_message += f"庄家 {game['banker_name']}:押{game['banker_guess']} {game['banker_amount']}, 退还本金, 扣除空盘{empty_game_fee}, 净收益 {-empty_game_fee:+}\n"
                result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
                result_message += f"💰 平台空盘费:{empty_game_fee}(庄家下注的1%)\n"
                result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        else:
            # 正常游戏结果
            result_message = f"NO.{game['game_no']}\n"
            result_message += f"🎲 开奖结果:{actual_result}(点数:{dice1}, {dice2}, {dice3}, 总和:{total_value})\n"
            result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            result_message += f"📊 本局结算明细:\n"
            result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            
            # 显示赢家
            if winners:
                result_message += f"[赢家]\n"
                for winner in winners:
                    result_message += f"{winner['user_name']}:押{winner['guess']} {winner['amount']}, 赢得{winner['win_amount']}, 净收益 {winner['net_profit']:+}, 余额:{winner['new_balance']} 🪙\n"
                result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            
            # 显示输家
            if losers:
                result_message += f"[输家]\n"
                for loser in losers:
                    result_message += f"{loser['user_name']}:押{loser['guess']} {loser['amount']}, 损失{loser['loss_amount']}, 净收益 {loser['net_profit']:+}, 余额:{loser['new_balance']} 🪙\n"
                result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
            
            # 显示平台服务费和庄家奖励
            if total_service_fee > 0:
                result_message += f"💰 平台服务费:{platform_fee}(输方总额7%)\n"
                result_message += f"🎁 庄家服务费奖励:{banker_fee}(输方总额3%)\n"
                result_message += f"━━━━━━━━━━━━━━━━━━━━━━\n"
        
        # 发送结束
        await bot.send_message(
            chat_id=game['chat_id'],
            text=result_message,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"结束猜大小游戏失败 {e}")
        await bot.send_message(
            chat_id=game['chat_id'],
            text=f"游戏结束失败, 请联系管理员"
        )
    
    # 标记游戏为结束
    game['status'] = 'ended'
    # 删除游戏
    del guess_games[chat_id]

# 猜大小游戏命令处理器
async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    # 检查是否是群聊
    if update.message.chat.type in ['group', 'supergroup']:
        # 检查是否有正在进行的庄家游戏
        if chat_id in guess_games:
            # 有正在进行的庄家游戏 - 参与庄家游戏
            if len(args) != 2:
                await update.message.reply_text("请输入猜测的大小和金额, 例如:`/guess 大 10`\n\n直接复制:`/guess 大 10`", parse_mode='Markdown')
                return
            
            # 尝试两种参数顺序
            if args[0] in ['大', '小']:
                guess = args[0]
                try:
                    amount = int(args[1])
                except ValueError:
                    await update.message.reply_text("请输入有效的数字")
                    return
            elif args[1] in ['大', '小']:
                guess = args[1]
                try:
                    amount = int(args[0])
                except ValueError:
                    await update.message.reply_text("请输入有效的数字")
                    return
            else:
                await update.message.reply_text("猜测必须是[大]或[小]")
                return
            
            if amount <= 0:
                await update.message.reply_text("下注金额必须大于0")
                return
        
            game = guess_games[chat_id]
            if game['status'] != 'waiting':
                await update.message.reply_text("游戏已经开始或已结束")
                return
            
            # 检查用户是否已登录
            from app.config import user_tokens
            if user_id not in user_tokens:
                await update.message.reply_text("请先使用 /start 命令登录")
                return
            
            # 检查是否是庄家自己
            if game['banker'] == user_id:
                await update.message.reply_text("庄家不能参与自己的游戏!")
                return
            
            # 检查用户是否已经下注过
            if user_id in game['bets']:
                await update.message.reply_text("您已经下注过了!")
                return
            
            # 获取用户emos_id
            user_info = user_tokens[user_id]
            emos_user_id = user_info.get('user_id', str(user_id))
            
            # 检查用户余额
            from app.database import get_balance
            balance = get_balance(emos_user_id)
            if balance < amount:
                await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
                return
            
            # 添加用户下注
            game['bets'][user_id] = {
                'amount': amount,
                'guess': guess,
                'user_name': update.effective_user.first_name
            }
            
            # 更新总金额
            if guess == '大':
                game['big_total'] += amount
            else:
                game['small_total'] += amount
            
            # 计算实时赔率
            total_bets = game['big_total'] + game['small_total']
            if total_bets > 0:
                big_odds = total_bets / game['big_total'] if game['big_total'] > 0 else 1.0
                small_odds = total_bets / game['small_total'] if game['small_total'] > 0 else 1.0
            else:
                big_odds = 1.0
                small_odds = 1.0
            
            player_count = len(game['bets'])
            
            # 计算剩余时间
            remaining_time = game['end_time'] - datetime.now()
            remaining_seconds = int(remaining_time.total_seconds())
            if remaining_seconds < 0:
                remaining_text = "即将开奖"
            else:
                remaining_minutes = remaining_seconds // 60
                remaining_secs = remaining_seconds % 60
                remaining_text = f"{remaining_minutes}分{remaining_secs}秒"
            
            # 回复用户
            await update.message.reply_text(
                f"✅ 下注成功!\n\n"
                f"🎮 猜大小游戏\n"
                f"庄家:{game['banker_name']}\n"
                f"您的猜测:{guess}\n"
                f"下注金额:{amount} 🪙\n\n"
                f"📊 当前赔率:\n"
                f"猜大:{big_odds:.1f}倍\n"
                f"猜小:{small_odds:.1f}倍\n\n"
                f"👥 参与人数:{player_count} 人\n"
                f"⏳ 距离开奖:{remaining_text}"
            )
            
            # 更新群聊中的游戏信息
            try:
                from __main__ import application
                text = (
                    f"🎮 猜大小游戏(庄家模式)\n\n"
                    f"庄家:{game['banker_name']}\n"
                    f"下注金额:{game['amount']} 🪙\n\n"
                    f"📊 当前赔率:\n"
                    f"猜大:{big_odds:.1f}倍\n"
                    f"猜小:{small_odds:.1f}倍\n\n"
                    f"💰 当前下注:\n"
                    f"猜大:{game['big_total']} 🪙\n"
                    f"猜小:{game['small_total']} 🪙\n\n"
                    f"👥 参与人数:{player_count} 人\n\n"
                    f"⏳ 5分钟后自动开奖\n\n"
                    f"💡 发送 `/guess <金额> <大/小>` 参与下注"
                )
                
                await application.bot.edit_message_text(
                    chat_id=game['chat_id'],
                    message_id=game['message_id'],
                    text=text,
                    parse_mode="Markdown"
                )
            except Exception as e:
                logger.error(f"更新群聊消息失败: {e}")
        else:
            # 没有正在进行的庄家游戏- 自己玩(像私聊一样, 使用官方骰子)
            if len(args) != 2:
                await update.message.reply_text("请输入下注金额和猜测的大小, 例如:`/guess 10 大`\n\n直接复制:`/guess 10 大`", parse_mode='Markdown')
                return
            
            try:
                amount = int(args[0])
                if amount <= 0:
                    await update.message.reply_text("下注金额必须大于0")
                    return
            except ValueError:
                await update.message.reply_text("请输入有效的数字")
                return
            
            guess = args[1]
            if guess not in ['大', '小']:
                await update.message.reply_text("猜测必须是[大]或[小]")
                return
            
            # 检查用户是否已登录
            from app.config import user_tokens
            if user_id not in user_tokens:
                await update.message.reply_text("请先使用 /start 命令登录")
                return
            
            # 获取用户emos_id
            user_info = user_tokens[user_id]
            emos_user_id = user_info.get('user_id', str(user_id))
            
            # 检查用户余额
            from app.database import get_balance, update_balance
            balance = get_balance(emos_user_id)
            if balance < amount:
                await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
                return
            
            # 扣除下注金额
            update_balance(emos_user_id, -amount)
            
            # 保存下注信息到全局字典(用于群聊中机器人发送骰子后的结算)
            chat_id = update.effective_chat.id
            if chat_id not in private_guess_games:
                private_guess_games[chat_id] = {}
            private_guess_games[chat_id][user_id] = {
                'amount': amount,
                'guess': guess,
                'emos_user_id': emos_user_id
            }
            
            # 调试信息
            print(f"保存游戏状态- chat_id={chat_id}, user_id={user_id}, amount={amount}, guess={guess}")
            
            # 发送Telegram官方骰子(使用reply_to回复用户消息)
            dice_message = await update.message.reply_dice(emoji='🎲', reply_to_message_id=update.message.message_id)
            
            # 等待骰子动画完成(约3-4秒)
            await asyncio.sleep(4)
            
            # 获取骰子结果
            dice_value = dice_message.dice.value
            
            # 直接处理结果
            await process_guess_result(update, dice_value, amount, guess, emos_user_id, user_id, chat_id, context)
            
            # 清除游戏数据
            if chat_id in private_guess_games and user_id in private_guess_games[chat_id]:
                del private_guess_games[chat_id][user_id]
                if not private_guess_games[chat_id]:
                    del private_guess_games[chat_id]
            
            return
    else:
        # 私聊模式 - 与机器人猜大小
        if len(args) != 2:
            await update.message.reply_text("请输入下注金额和猜测的大小, 例如:`/guess 10 大`\n\n直接复制:`/guess 10 大`", parse_mode='Markdown')
            return
        
        try:
            amount = int(args[0])
            if amount <= 0:
                await update.message.reply_text("下注金额必须大于0")
                return
        except ValueError:
            await update.message.reply_text("请输入有效的数字")
            return
        
        guess = args[1]
        if guess not in ['大', '小']:
            await update.message.reply_text("猜测必须是[大]或[小]")
            return
        
        # 检查用户是否已登录
        from app.config import user_tokens
        if user_id not in user_tokens:
            await update.message.reply_text("请先使用 /start 命令登录")
            return
        
        # 获取用户emos_id
        user_info = user_tokens[user_id]
        emos_user_id = user_info.get('user_id', str(user_id))
        
        # 检查用户余额
        from app.database import get_balance, update_balance
        balance = get_balance(emos_user_id)
        if balance < amount:
            await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
            return
        
        # 扣除下注金额
        update_balance(emos_user_id, -amount)
        
        # 保存下注信息到全局字典(用于私聊中机器人发送骰子后的结算)
        chat_id = update.effective_chat.id
        if chat_id not in private_guess_games:
            private_guess_games[chat_id] = {}
        private_guess_games[chat_id][user_id] = {
            'amount': amount,
            'guess': guess,
            'emos_user_id': emos_user_id
        }
        
        # 发送Telegram官方骰子(使用reply_to回复用户消息)
        dice_message = await update.message.reply_dice(emoji='🎲', reply_to_message_id=update.message.message_id)
        
        # 等待骰子动画完成(约3-4秒)
        await asyncio.sleep(4)
        
        # 获取骰子结果
        dice_value = dice_message.dice.value
        
        # 直接处理结果
        await process_guess_result(update, dice_value, amount, guess, emos_user_id, user_id, chat_id, context)
        
        # 清除游戏数据
        if chat_id in private_guess_games and user_id in private_guess_games[chat_id]:
            del private_guess_games[chat_id][user_id]
            if not private_guess_games[chat_id]:
                del private_guess_games[chat_id]
        
        return

# 全局字典存储分步输入状态(用于群聊和私聊)
# 格式: {user_id: {'game': str, 'data': dict, 'timestamp': float}}
# game: 'guess', 'slot', 'blackjack', 'shoot'
step_input_states = {}

# 全局字典存储21点游戏状态(用于群聊和私聊)
# 格式: {user_id: {'player_cards': list, 'dealer_cards': list, 'amount': int, 'user_id': str, 'username': str, 'timestamp': float}}
blackjack_games = {}

# 游戏状态过期时间(秒)
GAME_STATE_TIMEOUT = 600  # 10分钟

def cleanup_expired_game_states():
    import time
    current_time = time.time()
    
    # 清理分步输入状态
    expired_users = []
    for user_id, state in step_input_states.items():
        if current_time - state.get('timestamp', 0) > GAME_STATE_TIMEOUT:
            expired_users.append(user_id)
    for user_id in expired_users:
        del step_input_states[user_id]
    
    # 清理21点游戏状态
    expired_users = []
    for user_id, game in blackjack_games.items():
        if current_time - game.get('timestamp', 0) > GAME_STATE_TIMEOUT:
            expired_users.append(user_id)
    for user_id in expired_users:
        del blackjack_games[user_id]
    
    if expired_users:
        logger.info(f"清理{len(expired_users)} 个过期游戏状态")

async def handle_dice_result(update: Update, context: ContextTypes.DEFAULT_TYPE):
    print("\n" + "="*50)
    print("🔄 开始处理骰子结束")
    print("="*50)

    try:
        chat_id = update.effective_chat.id
        dice_message = update.effective_message
        
        # 调试信息
        print(f"1. handle_dice_result 被调用- chat_id={chat_id}")
        print(f"2. 消息类型: {type(dice_message)}")
        print(f"3. dice_message 属 {dir(dice_message)}")
        print(f"4. dice_message.reply_to_message 存在: {bool(dice_message.reply_to_message)}")
        
        # 检查是否有 dice 属
        if not hasattr(dice_message, 'dice') or dice_message.dice is None:
            print("[ERROR] 消息没有 dice 属性")
            return
        
        # 获取骰子点数
        dice_value = dice_message.dice.value
        print(f"5. 骰子点数: {dice_value}")
        print(f"6. 骰子emoji: {dice_message.dice.emoji}")
        
        # 只处理普通骰子(emoji为🎲)
        if dice_message.dice.emoji != '🎲':
            print("6. 不是普通骰子, 跳过处理")
            return
        
        # 获取原始用户ID - 从reply_to_message中获取
        original_user_id = None
        if dice_message.reply_to_message:
            original_user = dice_message.reply_to_message.from_user
            original_user_id = original_user.id
            print(f"6. 从reply_to_message获取原始用户ID: {original_user_id}")
            print(f"7. 原始用户名称: {original_user.first_name}")
        
        # 从全局字典中查找该聊天中的游戏
        print(f"8. 查找游戏 - chat_id={chat_id}")
        print(f"9. private_guess_games 状态 {private_guess_games}")
        
        if chat_id in private_guess_games:
            print(f"10. chat_id in private_guess_games")
            chat_games = private_guess_games[chat_id]
            print(f"11. 该chat_id下的游戏: {chat_games}")
            
            # 如果有reply_to_message, 优先使用其中的用户ID
            if original_user_id and original_user_id in chat_games:
                print(f"12. 找到匹配的游戏数- user_id={original_user_id}")
                game_data = chat_games[original_user_id]
                amount = game_data['amount']
                guess = game_data['guess']
                emos_user_id = game_data['emos_user_id']
                
                print(f"13. 游戏数据 - amount={amount}, guess={guess}, emos_user_id={emos_user_id}")
                
                # 处理结果
                print("14. 开始处理游戏结束")
                await process_guess_result(update, dice_value, amount, guess, emos_user_id, original_user_id, chat_id, context)
                
                # 清除游戏数据
                print("15. 清除游戏数据")
                del private_guess_games[chat_id][original_user_id]
                if not private_guess_games[chat_id]:
                    del private_guess_games[chat_id]
                    print("16. 清除空的chat_id条目")
                print("17. 游戏数据已清理")
                return
            else:
                # 如果没有reply_to_message或找不到对应用户, 尝试获取该聊天中的第一个游戏
                if chat_games:
                    # 获取第一个等待中的游戏
                    first_user_id = list(chat_games.keys())[0]
                    game_data = chat_games[first_user_id]
                    amount = game_data['amount']
                    guess = game_data['guess']
                    emos_user_id = game_data['emos_user_id']
                    
                    print(f"12. 使用第一个可用的游戏数据 - user_id={first_user_id}")
                    print(f"13. 游戏数据 - amount={amount}, guess={guess}, emos_user_id={emos_user_id}")
                    
                    # 处理结果
                    print("14. 开始处理游戏结束")
                    await process_guess_result(update, dice_value, amount, guess, emos_user_id, first_user_id, chat_id, context)
                    
                    # 清除游戏数据
                    print("15. 清除游戏数据")
                    del private_guess_games[chat_id][first_user_id]
                    if not private_guess_games[chat_id]:
                        del private_guess_games[chat_id]
                        print("16. 清除空的chat_id条目")
                    print("17. 游戏数据已清理")
                    return
                else:
                    print(f"12. 该chat_id下没有游戏数据")
        else:
            print(f"10. chat_id 不在 private_guess_games 中")
        
        print("18. 没有找到游戏数据")
    except Exception as e:
        print(f"handle_dice_result 出错: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("="*50)
        print("🔄 骰子结果处理结束")
        print("="*50 + "\n")

async def process_guess_result(update: Update, dice_value: int, amount: int, guess: str, 
                               emos_user_id: str, user_id: int, chat_id: int, context=None):
    # 调试信息
    print(f"process_guess_result 被调用- amount={amount}, guess={guess}, emos_user_id={emos_user_id}")
    print(f"dice_value={dice_value}, user_id={user_id}, chat_id={chat_id}")
    
    # 判断大小(一个骰子规则:4-6为大,1-3为小)
    if dice_value in [4, 5, 6]:
        actual_result = "大"
    else:
        actual_result = "小"
    
    print(f"实际结果: {actual_result}, 猜测: {guess}")
    
    # 处理结果
    
    # 获取连胜记录和余额
    streak_info = {'streak': 0, 'total_games': 0, 'total_wins': 0, 'total_losses': 0}
    current_balance = 0
    try:
        from app.database import get_user_streak, get_balance
        streak_info = get_user_streak(emos_user_id, 'guess')
        current_balance = get_balance(emos_user_id)
    except Exception as e:
        print(f"获取连胜记录失败: {e}")
    
    # 判断输赢
    is_win = (guess == actual_result)
    
    # 构建连胜/连败显示
    streak_text = ""
    if is_win:
        if streak_info['streak'] > 0:
            streak_text = f"🔥 连胜 {streak_info['streak'] + 1} 场!"
        else:
            streak_text = f"🎉 开启连胜!"
    else:
        if streak_info['streak'] < 0:
            streak_text = f"💔 连败 {abs(streak_info['streak']) + 1} 场..."
        else:
            streak_text = f"😢 运气不佳..."
    
    # 构建结果消息
    if is_win:
        # 赢了, 获得相同金额
        win_amount = amount
        service_fee = int(win_amount * 0.1)
        net_win = win_amount - service_fee
        
        # 检查每日净赢取上限
        from app.database import get_daily_win, init_daily_win_record, update_daily_win
        daily_win_record = get_daily_win(emos_user_id)
        if daily_win_record is None:
            init_daily_win_record(emos_user_id, '')
            daily_win_record = {'amount': 0}
        
        current_daily_net_win = daily_win_record['amount']
        remaining_limit = DAILY_NET_WIN_LIMIT - current_daily_net_win
        
        if remaining_limit <= 0:
            result_text = (
                f"🎲 猜大小游戏结束\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 您的选择:`{guess}`\n"
                f"🎲 骰子点数:`{dice_value}`({actual_result})\n\n"
                f"🎉 您赢了!\n"
                f"⚠️ 今日净赢已达上限!\n"
                f"每日上限:{DAILY_NET_WIN_LIMIT} 🪙\n"
                f"今日净赢:{current_daily_net_win} 🪙\n"
                f"无法获得更多奖励\n\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
        else:
            actual_win = min(net_win, remaining_limit)
            update_daily_win(emos_user_id, '', actual_win)
            new_daily_net_win = current_daily_net_win + actual_win
            
            result_text = (
                f"🎲 猜大小游戏结束\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"🎯 您的选择:`{guess}`\n"
                f"🎲 骰子点数:`{dice_value}`({actual_result})\n\n"
                f"🎉 您赢了!\n"
                f"💰 获得:`{win_amount}` 🪙\n"
                f"💸 服务费:`{service_fee}` 🪙\n"
                f"💵 实际到账:`{actual_win}` 🪙\n\n"
                f"{streak_text}\n"
                f"📊 战绩:{streak_info['total_wins']}胜{streak_info['total_losses']}败\n"
                f"💎 当前余额:`{current_balance + actual_win}` 🪙\n"
                f"📊 今日净赢:{new_daily_net_win}/{DAILY_NET_WIN_LIMIT} 🪙\n\n"
                f"━━━━━━━━━━━━━━━━━━"
            )
    else:
        # 输了, 失去下注金额
        from app.database import update_daily_win
        update_daily_win(emos_user_id, '', -amount)
        
        # 获取最新的净赢记录
        from app.database import get_daily_win
        daily_win_record = get_daily_win(emos_user_id)
        current_daily_net_win = daily_win_record['amount'] if daily_win_record else 0
        
        result_text = (
            f"🎲 猜大小游戏结束\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"🎯 您的选择:`{guess}`\n"
            f"🎲 骰子点数:`{dice_value}`({actual_result})\n\n"
            f"😢 您输了!\n"
            f"💸 扣除:`{amount}` 🪙\n\n"
            f"{streak_text}\n"
            f"📊 战绩:{streak_info['total_wins']}胜{streak_info['total_losses']}败\n"
            f"💎 当前余额:`{current_balance - amount}` 🪙\n"
            f"📊 今日净赢:{current_daily_net_win}/{DAILY_NET_WIN_LIMIT} 🪙\n\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
    
    # 尝试更新数据库(异步, 不阻塞主流程)
    async def update_database():
        try:
            from app.database import update_balance, add_game_record, get_daily_win, update_daily_win, init_daily_win_record
            from app.config import user_tokens
            
            # 获取用户信息
            user_info = user_tokens.get(user_id, {})
            username = user_info.get('username', '')
            
            if is_win:
                # 赢了
                win_amount = amount
                service_fee = int(win_amount * 0.1)
                net_win = win_amount - service_fee
                
                # 检查每日净赢取上限
                daily_win_record = get_daily_win(emos_user_id)
                if daily_win_record is None:
                    init_daily_win_record(emos_user_id, username)
                    daily_win_record = {'amount': 0}
                
                current_daily_net_win = daily_win_record['amount']
                remaining_limit = DAILY_NET_WIN_LIMIT - current_daily_net_win
                
                if remaining_limit > 0:
                    actual_win = min(net_win, remaining_limit)
                    # 更新余额
                    update_balance(emos_user_id, actual_win)
                    # 更新每日净赢记录
                    update_daily_win(emos_user_id, username, actual_win)
                # 记录游戏结果 - 使用实际到账金额
                add_game_record(emos_user_id, "guess", amount, "win", actual_win, username)
            else:
                # 输了
                # 更新余额
                update_balance(emos_user_id, -amount)
                # 更新每日净赢记录
                update_daily_win(emos_user_id, username, -amount)
                # 记录游戏结果
                add_game_record(emos_user_id, "guess", amount, "lose", 0, username)
            
            print("数据库更新成功")
        except Exception as e:
            print(f"数据库更新失败 {e}")
    
    # 启动异步任务更新数据
    import asyncio
    asyncio.create_task(update_database())
    
    # 发送结束
    try:
        # 使用context.bot.send_message发送消息, 确保消息能够正确发送
        if context:
            await context.bot.send_message(chat_id=chat_id, text=result_text, parse_mode='Markdown')
        else:
            # 如果没有context, 使用update.effective_message.reply_text
            await update.effective_message.reply_text(result_text, parse_mode='Markdown')
    except Exception as e:
        print(f"发送结果消息失败 {e}")
        import traceback
        traceback.print_exc()
    
    # 清除context中的数据(如果是私聊模式
    if context:
        keys_to_clear = ['guess_amount', 'guess_choice', 'guess_emos_user_id', 
                         'guess_user_id']
        for key in keys_to_clear:
            if key in context.user_data:
                del context.user_data[key]

# 群聊下注命令处理器
async def guess_bet_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    # 检查是否是群聊
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("下注命令只能在群聊中使用")
        return
    
    # 检查参与
    if len(args) != 2:
        await update.message.reply_text("请输入猜测的大小和金额, 例如:`/guess_bet 大 100`\n\n直接复制:`/guess_bet 大 100`", parse_mode='Markdown')
        return
    
    guess = args[0]
    if guess not in ['大', '小']:
        await update.message.reply_text("猜测必须是[大]或[小]")
        return
    
    try:
        amount = int(args[1])
        if amount < 100:
            await update.message.reply_text("群聊猜大小游戏最低下注金额为100游戏币")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字")
        return
    
    # 检查是否有正在进行的游戏
    if chat_id not in guess_games:
        await update.message.reply_text("当前没有正在进行的猜大小游戏, 请先使用`/createguess 大/小 金额` 命令创建游戏")
        return
    
    game = guess_games[chat_id]
    if game['status'] != 'waiting':
        await update.message.reply_text("游戏已经开始或已结束")
        return
    
    # 检查是否已过截止下注时间
    current_time = datetime.now()
    if current_time >= game.get('bet_end_time', game['end_time']):
        await update.message.reply_text("下注时间已截止, 无法再下注")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user_id not in user_tokens:
        await update.message.reply_text("请先使用 /start 命令登录")
        return
    
    # 检查是否是庄家自己
    if game['banker'] == user_id:
        await update.message.reply_text("庄家已经下注, 不能重复下注!")
        return
    
    # 检查用户是否已经下注过
    if user_id in game['bets']:
        await update.message.reply_text("您已经下注过了!")
        return
    
    # 获取用户emos_id
    user_info = user_tokens[user_id]
    emos_user_id = user_info.get('user_id', str(user_id))
    
    # 检查用户余额
    from app.database import get_balance
    balance = get_balance(emos_user_id)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
        return
    
    # 扣除用户下注金额
    from app.database import update_balance
    update_balance(emos_user_id, -amount)
    
    # 添加用户下注
    game['bets'][user_id] = {
        'amount': amount,
        'guess': guess,
        'user_name': update.effective_user.first_name
    }
    
    # 更新总金额
    if guess == '大':
        game['big_total'] += amount
    else:
        game['small_total'] += amount
    
    player_count = len(game['bets'])
    
    # 计算剩余时间
    remaining_time = game['end_time'] - datetime.now()
    remaining_seconds = int(remaining_time.total_seconds())
    if remaining_seconds < 0:
        remaining_text = "即将开奖"
    else:
        remaining_minutes = remaining_seconds // 60
        remaining_secs = remaining_seconds % 60
        remaining_text = f"{remaining_minutes}分{remaining_secs}秒"
    
    # 回复用户
    await update.message.reply_text(
        f"✅ 下注成功!\n\n"
        f"🎮 猜大小游戏(庄家参与版)\n"
        f"庄家:{game['banker_name']}(押{game['banker_guess']} {game['banker_amount']})\n"
        f"您的猜测:{guess}\n"
        f"下注金额:{amount} 🪙\n\n"
        f"📊 当前奖池状态\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🎲 大池:{game['big_total']} 游戏币\n"
        f"🎲 小池:{game['small_total']} 游戏币\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👥 参与人数:{player_count} 人\n"
        f"⏳ 距离开奖:{remaining_text}"
    )
    
    # 更新群聊中的游戏信息
    try:
        from __main__ import application
        text = (
            f"🎮 猜大小游戏(庄家参与版)\n\n"
            f"庄家:{game['banker_name']}\n"
            f"庄家下注:{game['banker_guess']} {game['banker_amount']} 🪙\n\n"
            f"📊 当前奖池状态\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"🎲 大池:{game['big_total']} 游戏币\n"
            f"🎲 小池:{game['small_total']} 游戏币\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👥 参与人数:{player_count} 人\n\n"
            f"⏳ 5分钟后自动开奖\n\n"
            f"💡 发送 `/guess_bet <大/小> <金额>` 参与下注"
        )
        
        await application.bot.edit_message_text(
            chat_id=game['chat_id'],
            message_id=game['message_id'],
            text=text,
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"更新群聊消息失败: {e}")

# 群聊庄家模式猜大小游戏命令处理器
async def createguess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    # 只在群聊中使用
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("庄家模式只能在群聊中使用")
        return
    
    # 检查参与
    if len(args) != 2:
        await update.message.reply_text("请输入猜测的大小和金额, 例如:`/createguess 大 100`\n\n直接复制:`/createguess 大 100`", parse_mode='Markdown')
        return
    
    guess = args[0]
    if guess not in ['大', '小']:
        await update.message.reply_text("猜测必须是[大]或[小]")
        return
    
    try:
        amount = int(args[1])
        if amount < 100:
            await update.message.reply_text("群聊猜大小游戏最低下注金额为100游戏币")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user_id not in user_tokens:
        await update.message.reply_text("请先使用 /start 命令登录")
        return
    
    # 获取用户emos_id
    user_info = user_tokens[user_id]
    emos_user_id = user_info.get('user_id', str(user_id))
    
    # 检查用户余额
    from app.database import get_balance
    balance = get_balance(emos_user_id)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
        return
    
    # 检查是否已经有游戏在进行中
    if chat_id in guess_games:
        game = guess_games[chat_id]
        # 只要有游戏存在(不管状态如何), 就不允许创建新游戏
        await update.message.reply_text("群里已经有游戏在进行中, 请等待当前游戏结束")
        return
    
    # 创建群聊猜大小游戏
    await create_guess_game(update, context, user_id, guess, amount)

async def create_guess_game(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, guess: str, amount: int):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # 再次检查是否已经有游戏在进行中
    if chat_id in guess_games:
        await update.message.reply_text("群里已经有游戏在进行中, 请等待当前游戏结束")
        return
    
    # 获取游戏编号
    game_no = f"{increment_game_counter()}"
    
    # 计算结束时间(5分钟后)
    end_time = datetime.now() + timedelta(minutes=5)
    # 计算截止下注时间(结束前30秒)
    bet_end_time = end_time - timedelta(seconds=30)
    
    # 初始化游戏数
    big_total = amount if guess == '大' else 0
    small_total = amount if guess == '小' else 0
    
    guess_games[chat_id] = {
        'game_no': game_no,
        'banker': user_id,
        'banker_name': user.first_name,
        'banker_guess': guess,  # 庄家的猜测
        'banker_amount': amount,  # 庄家的下注金额
        'bets': {},  # 闲家下注记录
        'big_total': big_total,  # 猜大的总金额
        'small_total': small_total,  # 猜小的总金额
        'created_at': datetime.now(),
        'end_time': end_time,
        'bet_end_time': bet_end_time,  # 截止下注时间
        'chat_id': chat_id,
        'message_id': None,
        'status': 'waiting'
    }
    
    # 扣除庄家的下注金额
    from app.config import user_tokens
    user_info = user_tokens[user_id]
    emos_user_id = user_info.get('user_id', str(user_id))
    from app.database import update_balance
    update_balance(emos_user_id, -amount)
    
    # 在群聊中发布游戏信息
    text = (
        f"NO.{game_no}\n"
        f"🎮 猜大小游戏(庄家参与版)\n\n"
        f"庄家:{user.first_name}\n"
        f"庄家下注:{guess} {amount} 🪙\n\n"
        f"⏳ 5分钟后自动开奖\n\n"
        f"🎯 游戏规则:\n"
        f"1. 发送 `/guess_bet <大/小> <金额>` 参与下注\n"
        f"2. 三个骰子规则:4-10为小,11-17为大\n"
        f"3. 猜对的一方按各自下注比例瓜分输方的全部下注(扣除10%服务费)\n"
        f"4. 庄家与玩家同场竞技, 按下注比例分配奖金\n\n"
        f"💡 示例:`/guess_bet 大 10` 下注10游戏币猜大"
    )
    
    message = await update.message.reply_text(text, parse_mode="Markdown")
    guess_games[chat_id]['message_id'] = message.message_id

# 猜大小游戏回调处理器
async def guess_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    data = query.data
    
    # 处理猜大
    if data.startswith("guess_bet_big_"):
        game_id = data.replace("guess_bet_big_", "")
        await handle_guess_bet(update, context, game_id, user_id, "大")
    # 处理猜小
    elif data.startswith("guess_bet_small_"):
        game_id = data.replace("guess_bet_small_", "")
        await handle_guess_bet(update, context, game_id, user_id, "小")

async def handle_guess_bet(update: Update, context: ContextTypes.DEFAULT_TYPE, game_id: str, user_id: int, guess: str):
    query = update.callback_query
    
    if game_id not in guess_games:
        await query.answer("游戏不存在或已结束!")
        return
    
    game = guess_games[game_id]
    
    if game['status'] != 'waiting':
        await query.answer("游戏已经开始!")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user_id not in user_tokens:
        await query.answer("请先使用 /start 命令登录")
        return
    
    # 检查用户余额
    user_info = user_tokens[user_id]
    emos_user_id = user_info.get('user_id', str(user_id))
    from app.database import get_balance
    balance = get_balance(emos_user_id)
    
    if balance < game['amount']:
        await query.answer(f"游戏币不足!当前余额:{balance}")
        return
    
    # 检查用户是否已经下注过
    if user_id in game['bets']:
        await query.answer("您已经下注过了!")
        return
    
    # 添加用户下注
    game['bets'][user_id] = {
        'amount': game['amount'],
        'guess': guess,
        'user_name': update.effective_user.first_name
    }
    
    # 更新总金额
    if guess == '大':
        game['big_total'] += game['amount']
    else:
        game['small_total'] += game['amount']
    
    await query.answer(f"你选择了猜{guess}!下注{game['amount']} 🪙")
    
    # 计算实时赔率(奖池平分模式)
    TAX_RATE = 0.1  # 系统抽水比例 10%
    big_total = game['big_total']
    small_total = game['small_total']
    
    # 实时赔率计算:Odds = 1 + (输方总下注× (1 - T)) / 胜方总下注
    if big_total > 0:
        # 猜大开奖时的赔率
        big_odds = 1 + (small_total * (1 - TAX_RATE)) / big_total if small_total > 0 else 1.0
    else:
        big_odds = 1.0
    
    if small_total > 0:
        # 猜小开奖时的赔率
        small_odds = 1 + (big_total * (1 - TAX_RATE)) / small_total if big_total > 0 else 1.0
    else:
        small_odds = 1.0
    
    # 更新消息
    player_count = len(game['bets'])
    text = (
        f"🎮 猜大小游戏(庄家模式)\n\n"
        f"庄家:{game['banker_name']}\n"
        f"下注金额:{game['amount']} 🪙\n\n"
        f"📊 当前赔率:\n"
        f"猜大:{big_odds:.1f}倍\n"
        f"猜小:{small_odds:.1f}倍\n\n"
        f"💰 当前下注:\n"
        f"猜大:{game['big_total']} 🪙\n"
        f"猜小:{game['small_total']} 🪙\n\n"
        f"👥 参与人数:{player_count} 人\n\n"
        f"⏳ 1分钟后自动开奖"
    )
    
    keyboard = [
        [InlineKeyboardButton("🎲 猜大", callback_data=f"guess_bet_big_{game_id}"),
         InlineKeyboardButton("🎲 猜小", callback_data=f"guess_bet_small_{game_id}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(text, reply_markup=reply_markup)

# 猜拳游戏命令处理器
async def gameshoot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    args = context.args
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user_id not in user_tokens:
        await update.message.reply_text("请先使用 /start 命令登录")
        return
    
    if not args:
        # 没有参数, 提示完整指令
        await update.message.reply_text(
            "✊ 猜拳游戏\n\n"
            "请输入完整命令, 例如:\n"
            "普通单挑: `/gameshoot 10`\n"
            "庄家模式: `/gameshoot 10 3` (10是金额, 3是PK人数)\n\n"
            "直接复制:`/gameshoot 10` 或 `/gameshoot 10 3`",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = int(args[0])
        if amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
        
        # 检查是否是庄家模式
        if len(args) >= 2:
            pk_count = int(args[1])
            if pk_count <= 0 or pk_count > 100:
                await update.message.reply_text("PK人数必须在1-100之间")
                return
            
            # 检查是否是群聊
            if update.message.chat.type not in ['group', 'supergroup']:
                await update.message.reply_text("庄家模式只能在群聊中使用")
                return
            
            # 开始庄家模式
            await create_shoot_banker_game(update, context, user_id, amount, pk_count)
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字")
        return
    
    # 获取用户emos_id
    user_info = user_tokens[user_id]
    emos_user_id = user_info.get('user_id', str(user_id))
    
    # 检查用户余额
    from app.database import get_balance
    balance = get_balance(emos_user_id)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
        return
    
    # 检查是否是群聊
    if update.message.chat.type in ['group', 'supergroup']:
        # 群聊模式
        # 检查是否是回复别人
        if update.message.reply_to_message:
            # 单挑模式
            target_user_id = update.message.reply_to_message.from_user.id
            target_user = update.message.reply_to_message.from_user
            
            if target_user_id == user_id:
                await update.message.reply_text("不能和自己对战")
                return
            
            # 检查目标用户是否已登录
            if target_user_id not in user_tokens:
                await update.message.reply_text("对方未登录游戏系统!")
                return
            
            target_info = user_tokens[target_user_id]
            target_emos_id = target_info.get('user_id', str(target_user_id))
            
            # 检查目标用户余额
            target_balance = get_balance(target_emos_id)
            if target_balance < amount:
                await update.message.reply_text(f"对方游戏币不足!对方余额:{target_balance}")
                return
            
            # 开始单挑
            await start_shoot_duel(update, context, user_id, target_user_id, amount)
        else:
            # 直接创建一个新的群聊游戏, 显示选择按钮
            await create_shoot_game_with_buttons(update, context, user_id, amount)
    else:
        # 私聊模式, 与AI对战
        await start_shoot_ai(update, context, user_id, amount)

async def start_shoot_ai(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int):
    import random
    choices = ['石头', '剪刀', '布']
    ai_choice = random.choice(choices)
    
    # 创建内联键盘
    keyboard = [
        [
            InlineKeyboardButton("✊ 石头", callback_data=f"shoot_ai_rock_{amount}"),
            InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_ai_scissors_{amount}"),
            InlineKeyboardButton("🖐 布", callback_data=f"shoot_ai_paper_{amount}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"🎮 猜拳游戏 - 挑战天道\n\n"
        f"您下注了 {amount} 🪙\n\n"
        f"请选择你的出拳：",
        reply_markup=reply_markup
    )

async def start_shoot_duel(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, target_user_id: int, amount: int):
    user = update.effective_user
    target_user = update.message.reply_to_message.from_user
    chat_id = update.effective_chat.id
    
    # 获取emos用户信息
    user_info = user_tokens[user_id]
    target_info = user_tokens[target_user_id]
    user_emos_name = user_info.get('username', user.first_name)
    target_emos_name = target_info.get('username', target_user.first_name)
    
    # 存储游戏信息
    game_id = f"duel_{chat_id}_{int(datetime.now().timestamp())}"
    
    # 创建内联键盘
    keyboard = [
        [
            InlineKeyboardButton("✊ 石头", callback_data=f"shoot_duel_rock_{game_id}"),
            InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_duel_scissors_{game_id}"),
            InlineKeyboardButton("🖐 布", callback_data=f"shoot_duel_paper_{game_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    shoot_games[game_id] = {
        'type': 'duel',
        'players': {
            user_id: {'name': user_emos_name, 'choice': None, 'emos_id': user_info.get('user_id', str(user_id))},
            target_user_id: {'name': target_emos_name, 'choice': None, 'emos_id': target_info.get('user_id', str(target_user_id))}
        },
        'amount': amount,
        'created_at': datetime.now(),
        'chat_id': chat_id,
        'message_id': None,
        'status': 'playing'
    }
    
    message = await update.message.reply_text(
        f"🎮 猜拳单挑\n\n"
        f"{user_emos_name} ⚔️ {target_emos_name}\n"
        f"下注金额:{amount} 🪙\n\n"
        f"请双方选择出拳：",
        reply_markup=reply_markup
    )
    shoot_games[game_id]['message_id'] = message.message_id

async def create_shoot_game_with_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # 获取emos用户信息
    user_info = user_tokens[user_id]
    emos_username = user_info.get('username', user.first_name)
    
    # 清理之前的游戏
    if chat_id in shoot_games:
        del shoot_games[chat_id]
    
    shoot_games[chat_id] = {
        'type': 'group',
        'creator': user_id,
        'creator_name': emos_username,
        'amount': amount,
        'players': {
            user_id: {'name': emos_username, 'emos_id': user_info.get('user_id', str(user_id)), 'choice': None}
        },
        'created_at': datetime.now(),
        'end_time': datetime.now() + timedelta(minutes=1),
        'chat_id': chat_id,
        'message_id': None,
        'status': 'playing'  # 直接设为playing, 因为按钮是给所有人点击?
    }
    
    # 创建选择按钮
    keyboard = [
        [
            InlineKeyboardButton("✊ 石头", callback_data=f"shoot_group_rock_{chat_id}"),
            InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_group_scissors_{chat_id}"),
            InlineKeyboardButton("🖐 布", callback_data=f"shoot_group_paper_{chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 发布游戏信息
    text = (
        f"#游戏石头剪刀布 {emos_username} 邀请大家玩 {amount} 🪙 的石头剪刀布\n\n"
        f"⏱️ 1分钟后自动结算\n\n"
        f"请选择你的出拳："
    )
    
    message = await update.message.reply_text(text, reply_markup=reply_markup)
    shoot_games[chat_id]['message_id'] = message.message_id

async def create_shoot_banker_game(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int, pk_count: int):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # 获取用户信息
    user_info = user_tokens[user_id]
    emos_username = user_info.get('username', user.first_name)
    emos_user_id = user_info.get('user_id', str(user_id))
    
    # 检查用户余额（庄家押注金额）
    from app.database import get_balance
    balance = get_balance(emos_user_id)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
        return
    
    # 生成游戏编号（自增数字，从数据库获取）
    from app.database.db import increment_game_counter
    game_no = f"{increment_game_counter()}"
    
    # 清理之前的游戏
    if chat_id in shoot_games:
        del shoot_games[chat_id]
    
    # 创建庄家模式游戏数据
    shoot_games[chat_id] = {
        'type': 'banker',
        'game_no': game_no,
        'banker': {
            'user_id': user_id,
            'name': emos_username,
            'emos_id': emos_user_id,
            'choice': None,
            'amount': amount
        },
        'pk_count': pk_count,
        'players': {},
        'created_at': datetime.now(),
        'end_time': datetime.now() + timedelta(minutes=1),
        'chat_id': chat_id,
        'message_id': None,
        'status': 'waiting',
        'banker_choice_collected': False
    }
    
    # 创建按钮（庄家出拳 + 玩家加入）
    keyboard = [
        [
            InlineKeyboardButton("✊ 石头", callback_data=f"shoot_banker_play_rock_{chat_id}"),
            InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_banker_play_scissors_{chat_id}"),
            InlineKeyboardButton("🖐 布", callback_data=f"shoot_banker_play_paper_{chat_id}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 发布游戏信息
    text = (
        f"NO.{game_no}\n"
        f"🎮 猜拳庄家模式\n\n"
        f"庄家: {emos_username}\n"
        f"下注金额: {amount} 🪙\n"
        f"PK人数: 0/{pk_count} 人\n\n"
        f"⏱️ 1分钟后自动结算\n\n"
        f"选择你的出拳"
    )
    
    message = await update.message.reply_text(text, reply_markup=reply_markup)
    shoot_games[chat_id]['message_id'] = message.message_id

async def update_shoot_banker_game_message(chat_id: int, bot):
    if chat_id not in shoot_games:
        return
    
    game = shoot_games[chat_id]
    if game['type'] != 'banker':
        return
    
    try:
        if game['status'] == 'waiting':
            # 等待参与状态
            text = (
                f"NO.{game['game_no']}\n"
                f"🎮 猜拳庄家模式\n\n"
                f"庄家: {game['banker']['name']} "
            )
            
            # 庄家状态
            if game['banker']['choice']:
                text += "✅ 已出拳\n"
            else:
                text += "⏳ 等待出拳...\n"
            
            text += (
                f"下注金额: {game['banker']['amount']} 🪙\n"
                f"PK人数: {len(game['players'])}/{game['pk_count']} 人\n\n"
            )
            
            # 玩家列表
            if game['players']:
                text += "已参与玩家：\n"
                for player_id, player_data in game['players'].items():
                    text += f"  ✅ {player_data['name']} 已出拳\n"
                text += "\n"
            
            text += (
                f"⏱️ 1分钟后自动结算\n\n"
                f"选择你的出拳"
            )
            
            # 创建参与按钮（三个出拳选项）
            keyboard = [
                [
                    InlineKeyboardButton("✊ 石头", callback_data=f"shoot_banker_play_rock_{chat_id}"),
                    InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_banker_play_scissors_{chat_id}"),
                    InlineKeyboardButton("🖐 布", callback_data=f"shoot_banker_play_paper_{chat_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=game['message_id'],
                text=text,
                reply_markup=reply_markup
            )
    
    except Exception as e:
        logger.error(f"更新庄家模式游戏消息失败: {e}")

async def start_shoot_banker_game(chat_id: int, bot):
    if chat_id not in shoot_games:
        return
    
    game = shoot_games[chat_id]
    if game['type'] != 'banker':
        return
    
    game['status'] = 'playing'
    await update_shoot_banker_game_message(chat_id, bot)

async def settle_shoot_banker_game(chat_id: int, bot):
    if chat_id not in shoot_games:
        return
    
    game = shoot_games[chat_id]
    if game['type'] != 'banker':
        return
    
    game['status'] = 'settling'
    
    # 如果庄家没出拳，随机选择一个
    if game['banker']['choice'] is None:
        import random
        choices = ['石头', '剪刀', '布']
        game['banker']['choice'] = random.choice(choices)
    
    # 获取结果
    banker_choice = game['banker']['choice']
    amount = game['banker']['amount']
    
    # 构建结果文本
    result_text = (
        f"NO.{game['game_no']}\n"
        f"🎮 猜拳庄家模式结果\n\n"
        f"庄家: {game['banker']['name']}\n"
        f"庄家选择: {get_choice_emoji(banker_choice)}\n\n"
        f"PK人数: {len(game['players'])} 人\n\n"
    )
    
    # 初始化结果统计
    total_tax = 0
    banker_net = 0
    player_results = []
    
    # 导入数据库函数
    from app.database import get_balance, update_balance, add_game_record
    
    # 遍历所有玩家进行结算
    for player_id, player_data in game['players'].items():
        player_choice = player_data['choice']
        player_name = player_data['name']
        player_emos_id = player_data['emos_id']
        banker_emos_id = game['banker']['emos_id']
        
        # 判定胜负
        result = determine_shoot_result(player_choice, banker_choice)
        
        # 计算10%税
        tax = int(amount * 0.1)
        total_tax += tax
        
        player_text = f"{player_name}: {get_choice_emoji(player_choice)} - "
        
        if result == 'win':
            # 玩家赢
            win_amount = amount
            net_win = win_amount - tax
            
            # 更新余额
            update_balance(player_emos_id, net_win)
            update_balance(banker_emos_id, -amount)
            
            # 获取新余额
            new_player_balance = get_balance(player_emos_id)
            new_banker_balance = get_balance(banker_emos_id)
            
            player_text += f"🎉 赢了! 赢得 {net_win} 🪙 (税-{tax}), 余额:{new_player_balance} 🪙"
            
            # 添加游戏记录
            add_game_record(player_emos_id, '猜拳庄家模式', amount, 'win', net_win, player_choice)
            add_game_record(banker_emos_id, '猜拳庄家模式', amount, 'lose', 0, banker_choice)
            
            banker_net -= amount
        
        elif result == 'lose':
            # 玩家输
            
            # 更新余额
            update_balance(player_emos_id, -amount)
            update_balance(banker_emos_id, amount - tax)
            
            # 获取新余额
            new_player_balance = get_balance(player_emos_id)
            new_banker_balance = get_balance(banker_emos_id)
            
            player_text += f"😢 输了! 损失 {amount} 🪙 (税-{tax}), 余额:{new_player_balance} 🪙"
            
            # 添加游戏记录
            add_game_record(player_emos_id, '猜拳庄家模式', amount, 'lose', 0, player_choice)
            add_game_record(banker_emos_id, '猜拳庄家模式', amount, 'win', amount - tax, banker_choice)
            
            banker_net += (amount - tax)
        
        else:
            # 平局
            
            # 更新余额 - 每人扣税
            update_balance(player_emos_id, -tax)
            update_balance(banker_emos_id, -tax)
            total_tax += tax * 2
            
            # 获取新余额
            new_player_balance = get_balance(player_emos_id)
            new_banker_balance = get_balance(banker_emos_id)
            
            player_text += f"🤝 平局! (税-{tax}), 余额:{new_player_balance} 🪙"
            
            # 添加游戏记录 - 记录税后变化
            add_game_record(player_emos_id, '猜拳庄家模式', amount, 'draw', -tax, player_choice)
            add_game_record(banker_emos_id, '猜拳庄家模式', amount, 'draw', -tax, banker_choice)
        
        player_results.append(player_text)
    
    # 添加玩家结果
    result_text += "\n".join(player_results)
    result_text += f"\n\n💰 总税收: {total_tax} 🪙"
    
    # 添加庄家净收益和余额
    banker_emos_id = game['banker']['emos_id']
    banker_balance = get_balance(banker_emos_id)
    result_text += f"\n💼 庄家净收益: {banker_net} 🪙, 余额:{banker_balance} 🪙"
    
    # 更新消息
    try:
        await bot.edit_message_text(
            chat_id=chat_id,
            message_id=game['message_id'],
            text=result_text
        )
    except Exception as e:
        logger.error(f"更新庄家模式结果消息失败: {e}")
        # 发送新消息
        await bot.send_message(chat_id=chat_id, text=result_text)
    
    # 清理游戏
    del shoot_games[chat_id]

async def create_shoot_game(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int, player_count: int = None):
    chat_id = update.effective_chat.id
    user = update.effective_user
    
    # 获取emos用户信息
    user_info = user_tokens[user_id]
    emos_username = user_info.get('username', user.first_name)
    
    shoot_games[chat_id] = {
        'type': 'group',
        'creator': user_id,
        'creator_name': emos_username,
        'amount': amount,
        'player_count': player_count,
        'players': {
            user_id: {'name': emos_username, 'emos_id': user_info.get('user_id', str(user_id)), 'choice': None}
        },
        'created_at': datetime.now(),
        'chat_id': chat_id,
        'message_id': None,
        'status': 'waiting'
    }
    
    # 在群聊中发布游戏信息
    player_count_text = f"目标人数:{player_count} 人\n当前参与/{player_count} 人\n\n" if player_count else "当前参与 人\n\n"
    
    text = (
        f"🎮 猜拳游戏创建成功!\n\n"
        f"创建者:{emos_username}\n"
        f"下注金额:{amount} 🪙\n"
        f"{player_count_text}"
        f"?1分钟后自动开始\n\n"
        f"💡 发?`/gameshoot {amount}` 参与游戏"  # 直接在群里发送命令参与
    )
    
    message = await update.message.reply_text(text)
    shoot_games[chat_id]['message_id'] = message.message_id

async def join_shoot_game(update: Update, context: ContextTypes.DEFAULT_TYPE, user_id: int, amount: int):
    chat_id = update.effective_chat.id
    game = shoot_games[chat_id]
    
    # 检查游戏状态
    if game['status'] != 'waiting':
        await update.message.reply_text("游戏已经开始或已结束")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user_id not in user_tokens:
        await update.message.reply_text("请先使用 /start 命令登录")
        return
    
    # 检查用户是否已经参与
    if user_id in game['players']:
        await update.message.reply_text("您已经参与了这个游戏")
        return
    
    # 检查用户余额
    user_info = user_tokens[user_id]
    emos_user_id = user_info.get('user_id', str(user_id))
    from app.database import get_balance
    balance = get_balance(emos_user_id)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足!当前余额:{balance}")
        return
    
    # 获取emos用户?
    emos_username = user_info.get('username', update.effective_user.first_name)
    
    # 添加用户到游戏
    game['players'][user_id] = {
        'name': emos_username,
        'emos_id': emos_user_id,
        'choice': None
    }
    
    # 回复用户
    player_count = len(game['players'])
    player_count_text = f"{player_count}/{game['player_count']}" if game['player_count'] else f"{player_count}"
    
    # 计算赔率(简化版, 实际可以根据参与人数和下注金额计算?
    odds = 1.0
    if player_count > 1:
        odds = round(player_count * 0.9, 1)  # 简单的赔率计算
    
    await update.message.reply_text(
        f"?下注成功!\n\n"
        f"🎮 猜拳游戏\n"
        f"创建者:{game['creator_name']}\n"
        f"下注金额:{amount} 🪙\n"
        f"当前参与:{player_count_text} 人\n\n"
        f"📊 赔率:{odds}倍\n\n"
        f"?等待游戏开奖.."
    )
    
    # 更新群聊中的游戏信息
    try:
        text = (
            f"🎮 猜拳游戏\n\n"
            f"创建者:{game['creator_name']}\n"
            f"下注金额:{amount} 🪙\n"
            f"当前参与:{player_count_text} 人\n\n"
            f"📊 赔率:{odds}倍\n\n"
            f"?1分钟后自动开始\n\n"
            f"💡 发?`/gameshoot {amount}` 参与游戏"
        )
        
        await context.bot.edit_message_text(
            chat_id=game['chat_id'],
            message_id=game['message_id'],
            text=text
        )
    except Exception as e:
        logger.error(f"更新群聊消息失败: {e}")

# 处理用户输入
async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    input_text = update.message.text.strip()
    
    # 首先检查是否有游戏状态需要处?
    # 检查是否在等待猜大小游戏的输入(使用全局字典?
    user_id = update.effective_user.id
    if user_id in step_input_states and step_input_states[user_id].get('game') == 'guess':
        from app.handlers.command_handlers import process_guess
        parts = input_text.split()
        state_data = step_input_states[user_id]['data']
        
        if len(parts) == 2:
            # 输入了金额和猜测, 例如:10 ?
            amount, guess = parts
            await process_guess(update, context, amount, guess)
            # 清除状态
            del step_input_states[user_id]
        elif len(parts) == 1:
            # 只输入了一个?
            if 'amount' in state_data:
                # 已经有金额, 这个值应该是猜测
                amount = state_data['amount']
                guess = parts[0]
                if guess in ['大', '小']:
                    await process_guess(update, context, amount, guess)
                    # 清除状态
                    del step_input_states[user_id]
                else:
                    await update.message.reply_text("猜测必须是[大]或[小], 请重新输入")
                    # 不清除状态, 让用户重新输出
            else:
                # 没有金额, 这个值应该是金额
                try:
                    amount = int(parts[0])
                    if amount <= 0:
                        await update.message.reply_text("下注金额必须大于0, 请重新输入")
                        # 不清除状态, 让用户重新输出
                    else:
                        # 存储金额, 等待用户输入猜?
                        import time
                        step_input_states[user_id]['data']['amount'] = str(amount)
                        step_input_states[user_id]['timestamp'] = time.time()
                        await update.message.reply_text(f"已收到下注金额:{amount} 🪙\n\n请输入猜测的大小:`大` 或 `小`", parse_mode='Markdown')
                        # 不清除状态, 继续等待猜测
                except ValueError:
                    await update.message.reply_text("请输入有效的数字作为金额, 请重新输入")
                    # 不清除状态, 让用户重新输出
        else:
            await update.message.reply_text("请输入正确的格式, 例如:`10 大` 或只输入 `10`")
            # 不清除状态, 让用户重新输出
        return
    
    # 检查是否在等待老虎机游戏的输入
    if 'awaiting_slot' in context.user_data and context.user_data['awaiting_slot']:
        # 验证输入是否为有效数
        try:
            amount = int(input_text.strip())
            if amount <= 0:
                await update.message.reply_text("下注金额必须大于0, 请重新输入")
                return
        except ValueError:
            await update.message.reply_text("请输入有效的数字作为金额, 请重新输入")
            return
        
        from app.handlers.command_handlers import process_slot
        await process_slot(update, context, input_text)
        context.user_data['awaiting_slot'] = False
        return
    
    # 检查是否在等待21点游戏的输入
    if 'awaiting_blackjack' in context.user_data and context.user_data['awaiting_blackjack']:
        # 验证输入是否为有效数
        try:
            amount = int(input_text.strip())
            if amount <= 0:
                await update.message.reply_text("下注金额必须大于0, 请重新输入")
                return
        except ValueError:
            await update.message.reply_text("请输入有效的数字作为金额, 请重新输入")
            return
        
        from app.handlers.command_handlers import process_blackjack
        await process_blackjack(update, context, input_text)
        context.user_data['awaiting_blackjack'] = False
        return
    
    # 检查是否在等待猜拳游戏的输出
    if 'awaiting_shoot' in context.user_data and context.user_data['awaiting_shoot']:
        # 验证输入是否为有效数
        try:
            amount = int(input_text.strip())
            if amount <= 0:
                await update.message.reply_text("下注金额必须大于0, 请重新输入")
                return
        except ValueError:
            await update.message.reply_text("请输入有效的数字作为金额, 请重新输入")
            return
        
        # 设置参数并调用gameshoot_handler
        context.args = [input_text.strip()]
        await gameshoot_handler(update, context)
        context.user_data['awaiting_shoot'] = False
        return
    
    # 检查是否有游戏厅相关的文本输入需要处理(充值、提现、转账等?
    if 'current_operation' in context.user_data and context.user_data['current_operation'] in ['recharge_amount', 'withdraw_amount', 'service_fund_transfer_user_id', 'service_fund_transfer_amount']:
        from app.handlers.command_handlers import message_handler as game_message_handler
        # 调用游戏厅的消息处理器处理充值、提现或转账
        await game_message_handler(update, context)
        return

    if 'current_operation' in context.user_data:
        operation = context.user_data['current_operation']
        user_id = update.effective_user.id
        token = None
        from config import user_tokens
        print(f"DEBUG: user_id={user_id}")
        print(f"DEBUG: user_tokens type={type(user_tokens)}")
        print(f"DEBUG: user_tokens keys={list(user_tokens.keys())}")
        try:
            # 优先从context.user_data中获取token
            if 'token' in context.user_data:
                token = context.user_data.get('token')
                print(f"DEBUG: token from context={token[:20]}..." if token else "DEBUG: token is None from context")
            # 如果context中没有token, 从user_tokens中获?
            elif user_id in user_tokens:
                user_info = user_tokens[user_id]
                print(f"DEBUG: user_info type={type(user_info)}")
                if isinstance(user_info, dict):
                    token = user_info.get('token')
                    print(f"DEBUG: token from dict={token[:20]}..." if token else "DEBUG: token is None from dict")
                else:
                    token = user_info
                    print(f"DEBUG: token from string={token[:20]}..." if token else "DEBUG: token is None from string")
            print(f"DEBUG: final token={token[:20]}..." if token else "DEBUG: final token is None")
        except Exception as e:
            print(f"DEBUG: Token获取异常: {type(e).__name__}: {e}")
            token = None
        
        if operation == 'change_pseudonym':
            # 处理笔名更新
            if token:
                loading = await update.message.reply_text("🔄 正在更新笔名...")
                
                try:
                    headers = {"Authorization": f"Bearer {token}"}
                    response = await http_client.put(
                        f"{Config.API_BASE_URL}/user/pseudonym?name={input_text}",
                        headers=headers
                    )
                    
                    if response.status_code == 200:
                        await loading.edit_text(f"✅ 笔名更新成功!新笔名为:{input_text}")
                    else:
                        error_text = response.text[:200] if response.text else "无响应内容"
                        logger.error(f"更新笔名API错误: 状态码={response.status_code}, 内容={error_text}")
                        await loading.edit_text(f"⚠️ 更新笔名失败, 状态码:{response.status_code}\n{error_text}")
                except Exception as e:
                    # 记录详细的错误信息
                    logger.error(f"更新笔名失败: {type(e).__name__}: {str(e)}")
                    await loading.edit_text(f"⚠️ 更新笔名失败, 请稍后重试\n错误: {type(e).__name__}")
                
                # 显示返回菜单
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = [[InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("操作完成", reply_markup=reply_markup)
                
                # 清理用户数据
                clear_operation_data(context)
            else:
                await update.message.reply_text("请先登录!发送 /start 登录")
        
        elif operation == 'invite_user':
            # 处理邀请用户
            if token:
                loading = await update.message.reply_text("🔄 正在邀请用?..")
                
                try:
                    import httpx  # 确保httpx在局部作用域中可?
                    headers = {"Authorization": f"Bearer {token}"}
                    data = {"invite_user_id": input_text}
                    response = await http_client.post(
                        f"{Config.API_BASE_URL}/invite",
                        headers=headers,
                        json=data
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        remaining = result.get('invite_remaining', 0)
                        await loading.edit_text(f"?邀请成功!剩余邀请次数:{remaining}")
                    else:
                        error_text = response.text[:200] if response.text else "无响应内容"
                        logger.error(f"邀请用户API错误: 状态码={response.status_code}, 内容={error_text}")
                        await loading.edit_text(f"?邀请失败, 状态码:{response.status_code}\n{error_text}")
                except Exception as e:
                    # 记录详细的错误信息
                    logger.error(f"邀请用户失败 {type(e).__name__}: {str(e)}")
                    await loading.edit_text(f"?邀请用户失败, 请稍后重试\n错误: {type(e).__name__}")
                
                # 显示返回菜单
                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                keyboard = [[InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text("操作完成", reply_markup=reply_markup)
                
                # 清理用户数据
                clear_operation_data(context)
            else:
                await update.message.reply_text("请先登录!发送 /start 登录")
        
        elif operation == 'transfer_user_id':
            # 处理转赠用户ID输入
            if token:
                # 检查是否返回上一步
                if input_text == '返回':
                    # 返回到转账菜单
                    from handlers.common import show_transfer_menu
                    await show_transfer_menu(update, context)
                    # 清理用户数据
                    clear_operation_data(context)
                    return
                
                # 存储对方用户ID
                context.user_data['target_user_id'] = input_text
                # 获取余额
                balance = context.user_data.get('balance', '未知')
                # 提示用户输入转赠金额
                await update.message.reply_text(f"💸 请输入转赠萝卜数量(2-6000之间):\n\n当前余额: {balance} 🥕\n\n输入'返回'可返回上一步")
                # 更新操作状态
                context.user_data['current_operation'] = 'transfer_amount'
                return 103  # 继续等待金额输入
            else:
                await update.message.reply_text("请先登录!发送 /start 登录")
        
        elif operation == 'transfer_amount':
            # 处理转赠金额输入
            if token:
                # 检查是否返回上一步
                if input_text == '返回':
                    # 返回到输入用户ID的步骤
                    await update.message.reply_text("💸 请输入对方用户ID（10位字符串，以e开头s结尾）：\n\n输入'返回'可返回上一步")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'transfer_user_id'
                    return 102  # 继续等待用户ID输入
                
                target_user_id = context.user_data.get('target_user_id')
                try:
                    amount = int(input_text)
                    if 2 <= amount <= 6000:
                        loading = await update.message.reply_text("🔄 正在转赠...")
                        
                        try:
                            import httpx
                            headers = {"Authorization": f"Bearer {token}"}
                            data = {"user_id": target_user_id, "carrot": amount}
                            response = await http_client.put(
                                f"{Config.API_BASE_URL}/carrot/transfer",
                                headers=headers,
                                json=data
                            )
                            
                            if response.status_code == 200:
                                result = response.json()
                                remaining = result.get('carrot', 0)
                                await loading.edit_text(f"🎉 转赠成功!\n\n💰 剩余萝卜: {remaining} 🥕")
                            else:
                                error_msg = response.text[:200] if response.text else "未知错误"
                                logger.error(f"转赠失败: 状态码={response.status_code}, 错误={error_msg}")
                                await loading.edit_text(f"?转赠失败\n状态码:{response.status_code}\n错误:{error_msg}")
                        except Exception as e:
                            logger.error(f"转赠异常: {str(e)}")
                            await loading.edit_text(f"?转赠失败:{str(e)}")
                        
                        # 显示返回菜单
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = [[InlineKeyboardButton("🔙 返回转账菜单", callback_data="menu_transfer_main")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text("操作完成", reply_markup=reply_markup)
                    else:
                        await update.message.reply_text("转赠金额必须在1-6000之间, 请重新输入")
                        return 103  # 继续等待金额输入
                except ValueError:
                    await update.message.reply_text("请输入有效的数字, 请重新输入")
                    return 103  # 继续等待金额输入
                
                # 清理用户数据
                clear_operation_data(context)
            else:
                await update.message.reply_text("请先登录!发送 /start 登录")
        
        elif operation == 'service_recharge_amount':
            # 处理充值金额输出
            if token:
                try:
                    amount = int(input_text)
                    if 1 <= amount <= 50000:
                        # 检查累计充值限?
                        total_recharge = context.user_data.get('total_recharge', 0)
                        remaining_recharge = context.user_data.get('remaining_recharge', 100)
                        
                        if total_recharge + amount > 1500:
                            remaining = 1500 - total_recharge
                            await update.message.reply_text(f"充值限额为1500萝卜, 您已累计充值{total_recharge}萝卜, 还可充值{remaining}萝卜")
                            # 清理用户操作数据
                            clear_operation_data(context)
                            return
                        
                        # 从context中获取用户信?
                        local_user_id = context.user_data.get('local_user_id')
                        emos_user_id = context.user_data.get('emos_user_id')
                        telegram_id = user_id
                        
                        loading = await update.message.reply_text("🔄 正在创建支付订单...")
                        
                        try:
                            import uuid
                            import json
                            from datetime import datetime
                            
                            # 生成唯一参数
                            param = str(uuid.uuid4())[:8]
                            
                            # 调用创建订单API(使用服务商token?
                            headers = {
                                "Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}",
                                "Content-Type": "application/json; charset=utf-8"
                            }
                            data = {
                                "pay_way": "telegram_bot",
                                "price": amount,
                                "name": f"游戏币充?{amount}萝卜",
                                "param": param,
                                "callback_telegram_bot_name": Config.BOT_USERNAME
                            }
                            
                            logger.info(f"创建支付订单: {data}")
                            
                            json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                            
                            response = await http_client.post(
                                f"{Config.API_BASE_URL}/pay/create",
                                headers=headers,
                                content=json_data
                            )
                            
                            logger.info(f"支付订单API响应状态码: {response.status_code}")
                            logger.info(f"支付订单API响应内容: {response.text}")
                            
                            if response.status_code == 200:
                                result = response.json()
                                pay_url = result.get('pay_url')
                                order_no = result.get('no')
                                expired = result.get('expired')
                                
                                if pay_url:
                                    # 先获取用户信息, 保存到本地数据库
                                    try:
                                        user_headers = {"Authorization": f"Bearer {token}"}
                                        user_response = await http_client.get(
                                            f"{Config.API_BASE_URL}/user",
                                            headers=user_headers
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
                                                # 生成本地订单?
                                                local_order_no = f"R{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                                                
                                                # 解析过期时间
                                                expire_time = None
                                                if expired:
                                                    try:
                                                        expire_time = datetime.strptime(expired, '%Y-%m-%d %H:%M:%S')
                                                    except Exception as e:
                                                        logger.error(f"解析过期时间失败: {e}")
                                                
                                                # 保存订单到本地数据库
                                                logger.info(f"开始创建充值订? local_order_no={local_order_no}, platform_order_no={order_no}, emos_user_id={emos_user_id}, username={username}")
                                                
                                                # 清理用户操作数据
                                                clear_operation_data(context)
                                                success = create_recharge_order(
                                                    order_no=local_order_no,
                                                    emos_user_id=emos_user_id,
                                                    username=username,
                                                    telegram_user_id=user_id,
                                                    carrot_amount=amount,
                                                    platform_order_no=order_no,
                                                    pay_url=pay_url,
                                                    expire_time=expire_time
                                                )
                                                if success:
                                                    logger.info(f"订单已保存到本地数据 {local_order_no}")
                                                else:
                                                    logger.error(f"订单保存到本地数据库失败: {local_order_no}")
                                                
                                                # 存储订单信息
                                                context.user_data['recharge_order'] = {
                                                    'order_no': order_no,
                                                    'amount': amount,
                                                    'param': param,
                                                    'token': token
                                                }
                                                
                                                message = f"{update.effective_user.first_name} 充值订单创建成功!\n\n"
                                                message += f"订单号:{order_no}\n"
                                                message += f"平台订单号:{order_no}\n"
                                                message += f"充值萝卜:{amount} 萝卜\n"
                                                message += f"获得游戏币:{amount * 10} 游戏币\n\n"
                                                message += "请点击下方按钮前往支付"
                                                
                                                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                                keyboard = [
                                                    [InlineKeyboardButton("💳 前往支付", url=pay_url)],
                                                    [InlineKeyboardButton("🔙 返回", callback_data='back')]
                                                ]
                                                reply_markup = InlineKeyboardMarkup(keyboard)
                                                await loading.edit_text(message, reply_markup=reply_markup)
                                            else:
                                                await loading.edit_text("⚠️ 创建订单失败, 用户信息获取失败")
                                        else:
                                            await loading.edit_text(f"⚠️ 获取用户信息失败, 状态码:{user_response.status_code}")
                                    except Exception as db_error:
                                        logger.error(f"保存订单到本地数据库失败: {db_error}")
                                        await loading.edit_text("⚠️ 订单创建失败, 请稍后重试")
                                else:
                                    await loading.edit_text("⚠️ 创建订单失败, 没有返回支付链接")
                            else:
                                await loading.edit_text(f"⚠️ 创建订单失败, 状态码:{response.status_code}\n响应:{response.text}")
                        except Exception as e:
                            # 记录详细的错误信息
                            logger.error(f"创建支付订单失败: {type(e).__name__}: {e}")
                            import traceback
                            logger.error(f"错误堆栈: {traceback.format_exc()}")
                            await loading.edit_text(f"?创建订单失败: {type(e).__name__}: {e}")
                    else:
                        await update.message.reply_text("充值金额必须在1-50000之间, 请重新输入")
                        return 104  # 继续等待金额输入
                except ValueError:
                    await update.message.reply_text("请输入有效的数字, 请重新输入")
                    return 104  # 继续等待金额输入
            else:
                await update.message.reply_text("请先登录!发送 /start 登录")
                # 清理用户操作数据
                clear_operation_data(context)
            
            # 注意:这里不应该有代码, 因为前面?if-elif 链已经结束
            # 提现处理应该在单独的 elif 分支?
            
        elif operation == 'service_withdraw_amount':
            # 处理提现萝卜数量输入
            if token:
                try:
                    carrot_amount = int(input_text)
                    game_balance = context.user_data.get('game_balance', 0)
                    local_user_id = context.user_data.get('local_user_id')
                    emos_user_id = context.user_data.get('emos_user_id')
                    user_id = update.effective_user.id
                    
                    # 计算需要的游戏币数量(10游戏1萝卜?游戏萝卜手续费)
                    base_game_coin = carrot_amount * 10
                    fee_game_coin = carrot_amount * 1  # 1游戏萝卜手续?
                    amount = base_game_coin + fee_game_coin
                    # 计算税后萝卜数量?%税率?
                    tax_rate = 0.01
                    tax_carrot = int(carrot_amount * tax_rate)
                    after_tax_carrot = carrot_amount - tax_carrot
                    
                    # 检查提现限?
                    from utils.db_helper import check_withdraw_limits
                    limit_check = check_withdraw_limits(emos_user_id, carrot_amount)
                    if not limit_check['success']:
                        await update.message.reply_text(f"⚠️ {limit_check['error']}")
                        return
                    
                    if 1 <= carrot_amount <= 5000 and amount <= game_balance:
                        loading = await update.message.reply_text("🔄 正在处理提现...")
                        
                        try:
                            import httpx
                            import uuid
                            from datetime import datetime
                            from utils.db_helper import create_withdraw_order, update_withdraw_order_status
                            
                            # 生成提现订单?
                            order_no = f"W{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                            
                            # 1. 创建提现订单
                            # 手续费已从游戏币中扣除, 萝卜数量保持不变
                            # 获取用户信息, 包括username
                            from app.config import user_tokens
                            user_info = user_tokens.get(user_id, {})
                            username = user_info.get('username', '') if isinstance(user_info, dict) else ''
                            
                            create_withdraw_order(
                                order_no=order_no,
                                emos_user_id=emos_user_id,
                                telegram_user_id=user_id,
                                game_coin_amount=amount,
                                carrot_amount=carrot_amount,
                                username=username
                            )
                            
                            # 直接使用本地数据库扣除游戏币(使用emos_user_id?
                            from app.database import update_balance
                            game_success = update_balance(emos_user_id, -amount)
                            if game_success:
                                logger.info(f"使用本地数据库扣除游戏币:{amount}")
                            else:
                                logger.error(f"扣除游戏币失败:{amount}")
                            
                            if game_success:
                                # 3. 使用服务商token给用户转账萝?
                                # 获取用户的emos ID
                                user_headers = {"Authorization": f"Bearer {token}"}
                                user_response = await http_client.get(
                                    f"{Config.API_BASE_URL}/user",
                                    headers=user_headers
                                )
                                
                                if user_response.status_code == 200:
                                    user_info = user_response.json()
                                    user_emos_id = user_info.get('user_id')
                                    
                                    if user_emos_id:
                                        # 使用服务商token转账(税后金额)
                                        service_headers = {"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"}
                                        transfer_data = {"user_id": user_emos_id, "carrot": after_tax_carrot}
                                        transfer_response = await http_client.post(
                                            f"{Config.API_BASE_URL}/pay/transfer",
                                            headers=service_headers,
                                            json=transfer_data
                                        )
                                        
                                        if transfer_response.status_code == 200:
                                            # 更新提现订单状态为成功
                                            update_withdraw_order_status(
                                                order_no=order_no,
                                                status='success',
                                                transfer_result=f"转账成功, 金额:{after_tax_carrot}萝卜(税前{carrot_amount}萝卜, 税费{tax_carrot}萝卜), 手续费:{fee_game_coin}游戏币"
                                            )
                                            # 计算剩余游戏币余额
                                            remaining_balance = game_balance - amount
                                            
                                            # 计算剩余可提现额
                                            from app.database import get_user_total_recharge, get_user_total_withdraw
                                            total_recharge = get_user_total_recharge(local_user_id)
                                            total_withdraw_after = get_user_total_withdraw(local_user_id)
                                            max_withdraw_limit = int(total_recharge * 3)
                                            remaining_withdraw_limit = max_withdraw_limit - total_withdraw_after
                                            
                                            # 按照游戏厅格式显?
                                            await loading.edit_text(
                                                f"?提现申请成功!\n\n"
                                                f"📋 订单号:`{order_no}`\n"
                                                f"🥕 提现萝卜:{carrot_amount}\n"
                                                f"💼 税费:{tax_carrot} 萝卜?%)\n"
                                                f"🎁 实际到账:{after_tax_carrot} 萝卜\n"
                                                f"🪙 基础游戏币:{base_game_coin}\n"
                                                f"💸 手续费:{fee_game_coin}\n"
                                                f"💰 扣除游戏币:{amount}\n"
                                                f"🪙 剩余游戏币:{remaining_balance}\n\n"
                                                f"📊 剩余可提现额度:{remaining_withdraw_limit} 🥕\n"
                                                f"(累计充值{total_recharge} 🥕3倍, 已提现{total_withdraw_after} 🥕)",
                                                parse_mode="Markdown"
                                            )
                                        
                                        # 显示返回菜单
                                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                        keyboard = [
                                            [InlineKeyboardButton("🎮 前往游戏", callback_data="games"),
                                             InlineKeyboardButton("💎 继续提现", callback_data="service_withdraw")],
                                            [InlineKeyboardButton("🔙 返回", callback_data="back")]
                                        ]
                                        reply_markup = InlineKeyboardMarkup(keyboard)
                                        await update.message.reply_text("操作完成", reply_markup=reply_markup)
                                    else:
                                        # 更新提现订单状态为失败
                                        update_withdraw_order_status(
                                            order_no=order_no,
                                            status='failed',
                                            transfer_result=f"转账失败, 状态码:{transfer_response.status_code}"
                                        )
                                        await loading.edit_text(f"?转账失败, 状态码:{transfer_response.status_code}\n订单号:\n```\n{order_no}\n```\n", parse_mode="Markdown")
                                else:
                                    # 更新提现订单状态为失败
                                    update_withdraw_order_status(
                                        order_no=order_no,
                                        status='failed',
                                        transfer_result=f"获取用户信息失败"
                                    )
                                    await loading.edit_text(f"?获取用户信息失败\n订单号:\n```\n{order_no}\n```\n", parse_mode="Markdown")
                            else:
                                # 更新提现订单状态为失败
                                update_withdraw_order_status(
                                    order_no=order_no,
                                    status='failed',
                                    transfer_result=f"获取用户信息失败, 状态码:{user_response.status_code}"
                                )
                                await loading.edit_text(f"?获取用户信息失败, 状态码:{user_response.status_code}\n订单号:\n```\n{order_no}\n```\n", parse_mode="Markdown")
                        except Exception as e:
                            # 直接记录固定的错误信息, 避免尝试编码包含emoji的异常信?
                            logger.error("提现失败")
                            # 更新提现订单状态为失败
                            update_withdraw_order_status(
                                order_no=order_no,
                                status='failed',
                                transfer_result="提现失败, 请稍后重试"
                            )
                            await loading.edit_text(f"?提现失败, 请稍后重试\n订单号:\n```\n{order_no}\n```\n", parse_mode="Markdown")
                except ValueError:
                    await update.message.reply_text("请输入有效的数字, 请重新输入")
                    return 105  # 继续等待金额输入
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_game_recharge_amount':
                # 处理游戏充值金额输出
                if token:
                    game_id = context.user_data.get('game_id')
                    try:
                        amount = int(input_text)
                        if 1 <= amount <= 50000:
                            loading = await update.message.reply_text("🔄 正在创建游戏充值订?..")
                            
                            try:
                                import httpx
                                headers = {"Authorization": f"Bearer {token}"}
                                data = {"game_id": game_id, "carrot_amount": amount}
                                response = await http_client.post(
                                    f"{Config.API_BASE_URL}/game/recharge",
                                    headers=headers,
                                    json=data
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    game_coin = result.get('game_coin', 0)
                                    await loading.edit_text(f"?游戏充值成功!\n兑换游戏币:{game_coin}")
                                else:
                                    await loading.edit_text(f"?游戏充值失败, 状态码:{response.status_code}")
                            except Exception as e:
                                # 直接记录固定的错误信息, 避免尝试编码包含emoji的异常信?
                                logger.error("游戏充值失败")
                                await loading.edit_text("?游戏充值失败, 请稍后重试")
                            
                            # 显示返回菜单
                            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                            keyboard = [[InlineKeyboardButton("🔙 返回游戏", callback_data="games")]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await update.message.reply_text("操作完成", reply_markup=reply_markup)
                        else:
                            await update.message.reply_text("充值金额必须在1-50000之间, 请重新输入")
                            return 106  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("请输入有效的数字, 请重新输入")
                        return 106  # 继续等待金额输入
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_apply_name':
                # 处理服务商名称输出
                if token:
                    # 存储服务商名?
                    context.user_data['service_name'] = input_text
                    # 提示用户输入服务商描?
                    await update.message.reply_text("🏢 请输入服务商描述(100字以内)")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_apply_description'
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_apply_description':
                # 处理服务商描述输出
                if token:
                    service_name = context.user_data.get('service_name')
                    service_description = input_text
                    
                    loading = await update.message.reply_text("🔄 正在申请成为服务..")
                    
                    try:
                        import httpx
                        import json
                        print(f"DEBUG: Creating headers with token length={len(token) if token else 0}")
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json; charset=utf-8"
                        }
                        data = {"name": service_name, "description": service_description}
                        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                        
                        print(f"DEBUG: Request data: {data}")
                        
                        response = await http_client.post(
                            f"{Config.API_BASE_URL}/pay/apply",
                            headers=headers,
                            content=json_data
                        )
                        
                        print(f"DEBUG: Response status code: {response.status_code}")
                        print(f"DEBUG: Response content: {response.text}")
                        
                        if response.status_code == 200:
                            await loading.edit_text("?申请成功, 等待审核")
                        else:
                            try:
                                error_data = response.json()
                                safe_error = error_data.get('msg', '未知错误')
                                logger.error(f"申请服务商API返回错误: 状态码={response.status_code}, 错误信息={safe_error}")
                                await loading.edit_text(f"?申请失败, 状态码:{response.status_code}\n{safe_error}")
                            except Exception as e:
                                print(f"DEBUG: Error processing error text: {type(e).__name__}: {e}")
                                logger.error(f"申请服务商API返回错误: 状态码={response.status_code} [无法处理的响应]")
                                await loading.edit_text(f"?申请失败, 状态码:{response.status_code}\n[响应内容无法显示]")
                    except httpx.HTTPStatusError as e:
                        print(f"DEBUG: HTTPStatusError: {e}")
                        logger.error(f"申请服务商HTTP错误: {e.response.status_code}")
                        await loading.edit_text(f"?申请失败, HTTP错误:{e.response.status_code}")
                    except httpx.RequestError as e:
                        print(f"DEBUG: RequestError: {e}")
                        logger.error(f"申请服务商请求错误:{type(e).__name__}")
                        await loading.edit_text("?申请失败, 网络请求错误, 请检查网络连接")
                    except UnicodeEncodeError as e:
                        print(f"DEBUG: UnicodeEncodeError: {e}")
                        print(f"DEBUG: Error details: {e.encode}")
                        # 记录异常类型但不记录可能包含emoji的消?
                        logger.error(f"申请服务商发生异?UnicodeEncodeError")
                        await loading.edit_text("?申请失败, 请稍后重试")
                    except Exception as e:
                        print(f"DEBUG: Other exception: {type(e).__name__}: {e}")
                        # 记录异常类型但不记录可能包含emoji的消?
                        logger.error(f"申请服务商发生异?{type(e).__name__}")
                        await loading.edit_text("?申请失败, 请稍后重试")
                    
                    # 显示返回菜单
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    keyboard = [[InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text("操作完成", reply_markup=reply_markup)
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_update_name':
                # 处理服务商名称输出
                if token:
                    # 存储服务商名?
                    context.user_data['service_name'] = input_text
                    # 提示用户输入服务商描?
                    await update.message.reply_text("🏢 请输入服务商描述(100字以内)")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_update_description'
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_update_description':
                # 处理服务商描述输出
                if token:
                    service_name = context.user_data.get('service_name')
                    service_description = input_text
                    # 提示用户输入回调地址
                    await update.message.reply_text("🏢 请输入回调地址(可为空):")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_update_notify_url'
                    context.user_data['service_name'] = service_name
                    context.user_data['service_description'] = service_description
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_update_notify_url':
                # 处理服务商回调地址输入
                if token:
                    service_name = context.user_data.get('service_name')
                    service_description = context.user_data.get('service_description')
                    service_notify_url = input_text if input_text else None
                    
                    loading = await update.message.reply_text("🔄 正在更新服务商信?..")
                    
                    try:
                        import httpx
                        import json
                        headers = {
                            "Authorization": f"Bearer {token}",
                            "Content-Type": "application/json; charset=utf-8"
                        }
                        data = {"name": service_name, "description": service_description, "notify_url": service_notify_url}
                        json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                        response = await http_client.post(
                            f"{Config.API_BASE_URL}/pay/update",
                            headers=headers,
                            content=json_data
                        )
                        
                        if response.status_code == 200:
                            await loading.edit_text("?更新成功!")
                        else:
                            await loading.edit_text(f"?更新失败, 状态码:{response.status_code}")
                    except Exception as e:
                        logger.error(f"更新服务商信息失败{e}")
                        await loading.edit_text("?更新失败, 请稍后重试")
                    
                    # 显示返回菜单
                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                    keyboard = [[InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    await update.message.reply_text("操作完成", reply_markup=reply_markup)
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_fund_transfer_user_id':
                # 处理转账用户ID输入
                if token:
                    # 检查是否返回上一步
                    if input_text == '返回':
                        # 返回到转账菜单
                        from handlers.common import show_transfer_menu
                        await show_transfer_menu(update, context)
                        # 清理用户数据
                        clear_operation_data(context)
                        return
                    
                    # 检查是否是服务
                    is_service = False
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        response = await http_client.get(
                            f"{Config.API_BASE_URL}/pay/base",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            is_service = result.get('status') == 'pass'
                        else:
                            logger.error("检查服务商状态失败")
                            is_service = False
                    except Exception as e:
                        logger.error("检查服务商状态失败")
                        is_service = False
                    
                    if not is_service:
                        # 优化提示消息
                        message = await update.message.reply_text("🔒 只有服务商才能使用此功能！")
                        # 30秒后自动消失
                        import asyncio
                        from utils.message_utils import auto_delete_message
                        asyncio.create_task(auto_delete_message(update, context, message, 30))
                        # 清理用户数据
                        clear_operation_data(context)
                        return
                    
                    # 存储目标用户ID
                    context.user_data['target_user_id'] = input_text
                    # 获取余额
                    balance = context.user_data.get('balance', '未知')
                    # 提示用户输入转账金额
                    await update.message.reply_text(f"💸 请输入转账萝卜数量(1-50000之间):\n\n当前余额: {balance} 🥕\n\n输入'返回'可返回上一步")
                    # 更新操作状态
                    context.user_data['current_operation'] = 'service_fund_transfer_amount'
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_fund_transfer_amount':
                # 处理转账金额输入
                if token:
                    # 检查是否返回上一步
                    if input_text == '返回':
                        # 返回到输入用户ID的步骤
                        await update.message.reply_text("🏢 请输入对方用户ID（10位字符串，以e开头s结尾）：\n\n输入'返回'可返回上一步")
                        # 更新操作状态
                        context.user_data['current_operation'] = 'service_fund_transfer_user_id'
                        return 107  # 继续等待用户ID输入
                    
                    target_user_id = context.user_data.get('target_user_id')
                    try:
                        amount = int(input_text)
                        if 1 <= amount <= 50000:
                            # 检查是否是服务
                            is_service = False
                            try:
                                headers = {"Authorization": f"Bearer {token}"}
                                response = await http_client.get(
                                    f"{Config.API_BASE_URL}/pay/base",
                                    headers=headers
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    is_service = result.get('status') == 'pass'
                                else:
                                    logger.error("检查服务商状态失败")
                                    is_service = False
                            except Exception as e:
                                logger.error(f"检查服务商状态失败 {e}")
                                is_service = False
                            
                            if not is_service:
                                # 优化提示消息
                                message = await update.message.reply_text("🔒 只有服务商才能使用此功能！")
                                # 30秒后自动消失
                                import asyncio
                                from utils.message_utils import auto_delete_message
                                asyncio.create_task(auto_delete_message(update, context, message, 30))
                                # 清理用户数据
                                clear_operation_data(context)
                                return
                            
                            # 先发送加载消息, 确保loading变量在try块之前定?
                            loading = await update.message.reply_text("🔄 正在转账...")
                            
                            try:
                                # 使用服务商token进行转账
                                headers = {"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"}
                                data = {"user_id": target_user_id, "carrot": amount}
                                response = await http_client.post(
                                    f"{Config.API_BASE_URL}/pay/transfer",
                                    headers=headers,
                                    json=data
                                )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    logger.info(f"转账API响应: {result}")
                                    if 'deduct' in result:
                                        deduct = result.get('deduct', 0)
                                        carrot = result.get('carrot', 0)
                                        await loading.edit_text(
                                            f"🎉 转账成功!\n\n"
                                            f"💰 转账金额: {amount} 🥕\n"
                                            f"🎁 转账用户: {target_user_id}\n"
                                            f"📊 扣除萝卜: {deduct} 🥕\n"
                                            f"💎 剩余萝卜: {carrot} 🥕"
                                        )
                                    else:
                                        msg = result.get('msg', '未知错误')
                                        logger.error(f"转账失败: {msg}, 完整响应: {result}")
                                        await loading.edit_text(f"?转账失败:{msg}")
                                else:
                                    await loading.edit_text(f"?转账失败, 状态码:{response.status_code}")
                            except Exception as e:
                                logger.error(f"转账失败: {e}")
                                import traceback
                                logger.error(f"转账异常堆栈: {traceback.format_exc()}")
                                await loading.edit_text(f"?转账失败:{str(e)}")
                            
                            # 显示返回菜单
                            keyboard = [[InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]]
                            reply_markup = InlineKeyboardMarkup(keyboard)
                            await update.message.reply_text("操作完成", reply_markup=reply_markup)
                        else:
                            await update.message.reply_text("转账金额必须在1-50000之间, 请重新输入")
                            return 107  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("请输入有效的数字, 请重新输入")
                        return 107  # 继续等待金额输入
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_pay_create_amount':
                # 处理创建订单金额输入
                if token:
                    try:
                        amount = int(input_text)
                        if 1 <= amount <= 50000:
                            # 提示用户输入商品名称
                            await update.message.reply_text("💳 请输入商品名称(100字以内)")
                            # 更新操作状态
                            context.user_data['current_operation'] = 'service_pay_create_name'
                            context.user_data['amount'] = amount
                        else:
                            await update.message.reply_text("订单金额必须在1-50000之间, 请重新输入")
                            return 108  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("请输入有效的数字, 请重新输入")
                        return 108  # 继续等待金额输入
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
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
                    await update.message.reply_text("💳 请选择支付方式", reply_markup=reply_markup)
                    # 存储数据
                    context.user_data['amount'] = amount
                    context.user_data['name'] = name
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_pay_query_no':
                # 处理查询订单号输出
                if token:
                    order_no = input_text
                    loading = await update.message.reply_text("🔄 正在查询订单...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        response = await http_client.get(
                            f"{Config.API_BASE_URL}/pay/query?no={order_no}",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            message = f"📋 订单信息\n\n"
                            message += f"订单号:`{result.get('no', '未知')}`\n"
                            message += f"支付方式:{result.get('pay_way', '未知')}\n"
                            message += f"订单状态:{result.get('pay_status', '未知')}\n"
                            message += f"订单金额:{result.get('price_order', '未知')} 萝卜\n"
                            message += f"结算金额:{result.get('price_settle', '未知')} 萝卜\n"
                            message += f"商品名称:{result.get('order_name', '未知')}\n"
                            message += f"支付时间:{result.get('time_payed', '未知')}\n"
                            message += f"回调状态:{result.get('notify_status', '未知')}"
                            await loading.edit_text(message, parse_mode="Markdown")
                        else:
                            await loading.edit_text(f"?查询失败, 状态码:{response.status_code}")
                    except Exception as e:
                        logger.error(f"查询订单失败: {e}")
                        await loading.edit_text("?查询失败, 请稍后重试")
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_pay_close_no':
                # 处理关闭订单号输出
                if token:
                    order_no = input_text
                    loading = await update.message.reply_text("🔄 正在关闭订单...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        response = await http_client.put(
                            f"{Config.API_BASE_URL}/pay/close?no={order_no}",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            await loading.edit_text("?订单关闭成功!")
                        else:
                            await loading.edit_text(f"?关闭失败, 状态码:{response.status_code}")
                    except Exception as e:
                        logger.error(f"关闭订单失败: {e}")
                        await loading.edit_text("?关闭失败, 请稍后重试")
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'service_lottery_win_id':
                # 处理查询中奖列表
                if token:
                    lottery_id = input_text
                    loading = await update.message.reply_text("🔄 正在查询中奖列表...")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        response = await http_client.get(
                            f"{Config.API_BASE_URL}/lottery/win?lottery_id={lottery_id}",
                            headers=headers
                        )
                        
                        if response.status_code == 200:
                            win_data = response.json()
                            message = "🏆 中奖列表\n\n"
                            message += f"抽奖ID:`#{lottery_id}`\n"
                            message += f"结束时间:{win_data.get('time_end', '未知')}\n"
                            message += f"抽奖价格:{win_data.get('amount', 0)}\n"
                            
                            users = win_data.get('users', [])
                            winning_count = len(users)
                            message += f"中奖个数:{winning_count}\n\n"
                            
                            if users:
                                message += "中奖名单:\n"
                                for i, user in enumerate(users, 1):
                                    username = user.get('user_username', user.get('username', '未知'))
                                    user_id = user.get('user_id', '未知')
                                    join_index = user.get('join_index', '未知')
                                    message += f"{i}. `{username}` (id:`{user_id}`) 中奖号码:`{join_index}`\n"
                            else:
                                message += "暂无中奖用户\n"
                            
                            await loading.edit_text(message, parse_mode="Markdown")
                        else:
                            await loading.edit_text(f"?查询失败, 状态码:{response.status_code}", parse_mode="Markdown")
                    except Exception as e:
                        logger.error(f"查询中奖列表失败: {e}")
                        await loading.edit_text("?查询失败, 请稍后重试", parse_mode="Markdown")
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")
            
            elif operation == 'revoke_invite':
                # 处理撤销邀?
                if token:
                    target_user_id = input_text
                    loading = await update.message.reply_text("🔄 正在撤销邀?..")
                    
                    try:
                        import httpx
                        headers = {"Authorization": f"Bearer {token}"}
                        data = {"user_id": target_user_id}
                        response = await http_client.post(
                            f"{Config.API_BASE_URL}/invite/revoke",
                            headers=headers,
                            json=data
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            remaining = result.get('invite_remaining', 0)
                            await loading.edit_text(f"?撤销成功!剩余邀请次数:{remaining}")
                        else:
                            await loading.edit_text(f"?撤销失败, 状态码:{response.status_code}")
                    except Exception as e:
                        logger.error(f"撤销邀请失败 {e}")
                        await loading.edit_text("?撤销失败, 请稍后重试")
                    
                    # 清理用户数据
                    clear_operation_data(context)
                else:
                    await update.message.reply_text("请先登录!发送 /start 登录")

    return

# 猜拳游戏回调处理器
async def shoot_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    
    user_id = update.effective_user.id
    data = query.data
    
    # 庄家模式 - 出拳（庄家和玩家都用这个）
    if data.startswith("shoot_banker_play_rock_") or data.startswith("shoot_banker_play_scissors_") or data.startswith("shoot_banker_play_paper_"):
        parts = data.split("_")
        choice_type = parts[3]
        chat_id = int(parts[4])
        
        # 映射选择类型到出拳
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        user_choice = choice_map.get(choice_type, '石头')
        
        if chat_id not in shoot_games:
            await query.answer("游戏不存在或已结束!", show_alert=True)
            return
        
        game = shoot_games[chat_id]
        if game['type'] != 'banker':
            await query.answer("这不是庄家模式游戏!", show_alert=True)
            return
        
        if game['status'] != 'waiting':
            await query.answer("游戏已结束!", show_alert=True)
            return
        
        # 检查是否是庄家
        if user_id == game['banker']['user_id']:
            # 庄家出拳
            if game['banker']['choice'] is not None:
                await query.answer("您已经出拳了!", show_alert=True)
                return
            game['banker']['choice'] = user_choice
            await query.answer(f"您选择了{user_choice}!")
        else:
            # 玩家出拳
            if user_id in game['players']:
                await query.answer("您已经出拳了!", show_alert=True)
                return
            
            # 检查用户是否已登录
            from app.config import user_tokens
            if user_id not in user_tokens:
                await query.answer("请先使用 /start 命令登录")
                return
            
            # 检查用户余额
            user_info = user_tokens[user_id]
            emos_user_id = user_info.get('user_id', str(user_id))
            from app.database import get_balance
            balance = get_balance(emos_user_id)
            if balance < game['banker']['amount']:
                await query.answer(f"游戏币不足!当前余额:{balance}")
                return
            
            emos_username = user_info.get('username', update.effective_user.first_name)
            
            # 添加用户到游戏并记录选择
            game['players'][user_id] = {
                'name': emos_username,
                'emos_id': emos_user_id,
                'choice': user_choice
            }
            await query.answer(f"加入成功!您选择了{user_choice}!")
        
        # 更新游戏消息
        await update_shoot_banker_game_message(chat_id, context.bot)
        
        # 检查是否达到PK人数，够了就直接结算
        if len(game['players']) >= game['pk_count']:
            await settle_shoot_banker_game(chat_id, context.bot)
        
        return
    
    # 庄家模式 - 创建游戏时选择出拳（旧版，为了兼容性）
    if data.startswith("shoot_banker_create_rock_") or data.startswith("shoot_banker_create_scissors_") or data.startswith("shoot_banker_create_paper_"):
        parts = data.split("_")
        choice_type = parts[3]
        creator_user_id = int(parts[4])
        amount = int(parts[5])
        pk_count = int(parts[6])
        
        # 验证是否是创建者本人
        if user_id != creator_user_id:
            await query.answer("这不是您的游戏!", show_alert=True)
            return
        
        # 映射选择类型到出拳
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        banker_choice = choice_map.get(choice_type, '石头')
        
        # 创建游戏
        chat_id = update.effective_chat.id
        user = update.effective_user
        
        # 获取用户信息
        user_info = user_tokens[user_id]
        emos_username = user_info.get('username', user.first_name)
        emos_user_id = user_info.get('user_id', str(user_id))
        
        # 生成游戏编号（自增数字，从数据库获取）
        from app.database.db import increment_game_counter
        game_no = f"{increment_game_counter()}"
        
        # 清理之前的游戏
        if chat_id in shoot_games:
            del shoot_games[chat_id]
        
        # 创建庄家模式游戏数据 - 庄家已经选择了出拳
        shoot_games[chat_id] = {
            'type': 'banker',
            'game_no': game_no,
            'banker': {
                'user_id': user_id,
                'name': emos_username,
                'emos_id': emos_user_id,
                'choice': banker_choice,  # 庄家已选择出拳
                'amount': amount
            },
            'pk_count': pk_count,
            'players': {},  # 挑战者
            'created_at': datetime.now(),
            'end_time': datetime.now() + timedelta(minutes=1),
            'chat_id': chat_id,
            'message_id': None,
            'status': 'waiting',  # 直接等待玩家参与
            'banker_choice_collected': True
        }
        
        # 创建参与按钮（三个出拳选项）
        keyboard = [
            [
                InlineKeyboardButton("✊ 石头", callback_data=f"shoot_banker_join_rock_{chat_id}"),
                InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_banker_join_scissors_{chat_id}"),
                InlineKeyboardButton("🖐 布", callback_data=f"shoot_banker_join_paper_{chat_id}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 发布游戏信息
        text = (
            f"NO.{game_no}\n"
            f"🎮 猜拳庄家模式\n\n"
            f"庄家: {emos_username}\n"
            f"庄家已选择出拳 ✓\n"
            f"下注金额: {amount} 🪙\n"
            f"PK人数: {pk_count} 人\n\n"
            f"⏱️ 1分钟后自动结算\n\n"
            f"选择你的出拳加入游戏"
        )
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        shoot_games[chat_id]['message_id'] = query.message.message_id
        
        return
    
    # 庄家模式 - 加入游戏
    if data.startswith("shoot_banker_join_rock_") or data.startswith("shoot_banker_join_scissors_") or data.startswith("shoot_banker_join_paper_"):
        parts = data.split("_")
        choice_type = parts[3]
        chat_id = int(parts[4])
        
        # 映射选择类型到出拳
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        user_choice = choice_map.get(choice_type, '石头')
        


        if chat_id not in shoot_games:
            await query.answer("游戏不存在或已结束!", show_alert=True)
            return
        
        game = shoot_games[chat_id]
        if game['type'] != 'banker':
            await query.answer("这不是庄家模式游戏!", show_alert=True)
            return
        
        if game['status'] != 'waiting':
            await query.answer("游戏已开始或已结束!", show_alert=True)
            return
        
        if user_id == game['banker']['user_id']:
            await query.answer("庄家不能参与自己的游戏!", show_alert=True)
            return
        
        if user_id in game['players']:
            await query.answer("您已经加入了这个游戏!", show_alert=True)
            return
        
        # 检查用户是否已登录
        from app.config import user_tokens
        if user_id not in user_tokens:
            await query.answer("请先使用 /start 命令登录")
            return
        
        # 检查用户余额
        user_info = user_tokens[user_id]
        emos_user_id = user_info.get('user_id', str(user_id))
        from app.database import get_balance
        balance = get_balance(emos_user_id)
        if balance < game['banker']['amount']:
            await query.answer(f"游戏币不足!当前余额:{balance}")
            return
        
        emos_username = user_info.get('username', update.effective_user.first_name)
        
        # 添加用户到游戏并记录选择
        game['players'][user_id] = {
            'name': emos_username,
            'emos_id': emos_user_id,
            'choice': user_choice
        }
        
        await query.answer(f"加入成功!")
        
        # 更新游戏消息
        await update_shoot_banker_game_message(chat_id, context.bot)
        
        # 检查是否达到PK人数
        if len(game['players']) >= game['pk_count']:
            await settle_shoot_banker_game(chat_id, context.bot)
        
        return
    
    # 庄家模式 - 出拳
    if data.startswith("shoot_banker_choice_"):
        parts = data.split("_")
        chat_id = int(parts[3])
        choice_type = parts[4]
        
        if chat_id not in shoot_games:
            await query.answer("游戏不存在或已结束!", show_alert=True)
            return
        
        game = shoot_games[chat_id]
        if game['type'] != 'banker':
            await query.answer("这不是庄家模式游戏!", show_alert=True)
            return
        
        if game['status'] != 'playing':
            await query.answer("游戏不在出拳阶段!", show_alert=True)
            return
        
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        user_choice = choice_map.get(choice_type, '石头')
        
        # 检查是否是庄家
        if user_id == game['banker']['user_id']:
            if game['banker']['choice'] is not None:
                await query.answer("您已经出拳了!", show_alert=True)
                return
            game['banker']['choice'] = user_choice
            await query.answer(f"庄家选择了{user_choice}!")
        elif user_id in game['players']:
            if game['players'][user_id]['choice'] is not None:
                await query.answer("您已经出拳了!", show_alert=True)
                return
            game['players'][user_id]['choice'] = user_choice
            await query.answer(f"您选择了{user_choice}!")
        else:
            await query.answer("您没有参与这个游戏!", show_alert=True)
            return
        
        # 更新游戏消息
        await update_shoot_banker_game_message(chat_id, context.bot)
        
        # 检查是否所有人都出拳了
        all_choices = True
        if game['banker']['choice'] is None:
            all_choices = False
        for player_id, player_data in game['players'].items():
            if player_data['choice'] is None:
                all_choices = False
                break
        
        if all_choices:
            await settle_shoot_banker_game(chat_id, context.bot)
        
        return
    
    # AI对战模式
    if data.startswith("shoot_ai_"):
        # 格式: shoot_ai_rock_10
        parts = data.split("_")
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        user_choice = choice_map.get(parts[2], '石头')
        amount = int(parts[3])
        
        # 生成AI选择
        import random
        choices = ['石头', '剪刀', '布']
        ai_choice = random.choice(choices)
        
        # 判定胜负
        result = determine_shoot_result(user_choice, ai_choice)
        
        # 获取用户emos_id
        from app.config import user_tokens
        user_info = user_tokens.get(user_id, {})
        emos_user_id = user_info.get('user_id', str(user_id))
        
        # 获取emos用户?
        emos_username = user_info.get('username', update.effective_user.first_name)
        
        # 处理结果
        from app.database import get_balance, update_balance, add_game_record, get_daily_win, update_daily_win, init_daily_win_record
        if result == 'win':
            win_amount = amount
            service_fee = int(win_amount * 0.1)
            net_win = win_amount - service_fee
            
            # 检查每日净赢取上限
            daily_win_record = get_daily_win(emos_user_id)
            if daily_win_record is None:
                init_daily_win_record(emos_user_id, emos_username)
                daily_win_record = {'amount': 0}
            
            current_daily_net_win = daily_win_record['amount']
            remaining_limit = DAILY_NET_WIN_LIMIT - current_daily_net_win
            
            if remaining_limit <= 0:
                result_text = (
                    f"🎮 猜拳结果 - 挑战天道\n\n"
                    f"您选择:{user_choice} {get_choice_emoji(user_choice)} 🎉\n"
                    f"天道选择:{ai_choice} {get_choice_emoji(ai_choice)} 😢\n\n"
                    f"🎉 您赢了!\n"
                    f"⚠️ 今日净赢已达上限!\n"
                    f"每日上限:{DAILY_NET_WIN_LIMIT} 🪙\n"
                    f"今日净赢:{current_daily_net_win} 🪙\n"
                    f"无法获得更多奖励"
                )
            else:
                actual_win = min(net_win, remaining_limit)
                update_balance(emos_user_id, actual_win)
                update_daily_win(emos_user_id, emos_username, actual_win)
                new_balance = get_balance(emos_user_id)
                new_daily_net_win = current_daily_net_win + actual_win
                
                result_text = (
                    f"🎮 猜拳结果 - 挑战天道\n\n"
                    f"您选择:{user_choice} {get_choice_emoji(user_choice)} 🎉\n"
                    f"天道选择:{ai_choice} {get_choice_emoji(ai_choice)} 😢\n\n"
                    f"🎉 您赢了!\n"
                    f"获得:{win_amount} 🪙\n"
                    f"服务费:{service_fee} 🪙\n"
                    f"实际到账:{actual_win} 🪙\n"
                    f"当前余额:{new_balance} 🪙\n\n"
                    f"📊 今日净赢:{new_daily_net_win}/{DAILY_NET_WIN_LIMIT} 🪙"
                )
            # 添加游戏记录
            add_game_record(emos_user_id, 'shoot', amount, 'win', net_win, emos_username)
        elif result == 'lose':
            update_balance(emos_user_id, -amount)
            # 输了，减少净赢记录
            update_daily_win(emos_user_id, emos_username, -amount)
            new_balance = get_balance(emos_user_id)
            
            # 获取最新的净赢记录
            daily_win_record = get_daily_win(emos_user_id)
            current_daily_net_win = daily_win_record['amount'] if daily_win_record else 0
            
            result_text = (
                f"🎮 猜拳结果 - 挑战天道\n\n"
                f"您选择:{user_choice} {get_choice_emoji(user_choice)} 😢\n"
                f"天道选择:{ai_choice} {get_choice_emoji(ai_choice)} 🎉\n\n"
                f"😢 您输了!\n"
                f"扣除:{amount} 🪙\n"
                f"当前余额:{new_balance} 🪙\n\n"
                f"📊 今日净赢:{current_daily_net_win}/{DAILY_NET_WIN_LIMIT} 🪙"
            )
            # 添加游戏记录
            add_game_record(emos_user_id, 'shoot', amount, 'lose', -amount, emos_username)
        else:
            # 平局，双方各收5%的税
            tax = int(amount * 0.05)
            update_balance(emos_user_id, -tax)
            new_balance = get_balance(emos_user_id)
            result_text = (
                f"🎮 猜拳结果 - 挑战天道\n\n"
                f"您选择:{user_choice} {get_choice_emoji(user_choice)} 🤝\n"
                f"天道选择:{ai_choice} {get_choice_emoji(ai_choice)} 🤝\n\n"
                f"🤝 平局!\n"
                f"扣除服务费:{tax} 🪙\n"
                f"当前余额:{new_balance} 🪙"
            )
            # 添加游戏记录
            add_game_record(emos_user_id, 'shoot', amount, 'draw', -tax, emos_username)
        
        # 添加再次挑战按钮
        keyboard = [[InlineKeyboardButton("🔄 再次挑战", callback_data=f"shoot_ai_retry_{amount}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(result_text, reply_markup=reply_markup)
        return
    
    # AI对战重试
    if data.startswith("shoot_ai_retry_"):
        amount = int(data.split("_")[3])
        
        # 检查余额
        from app.config import user_tokens
        user_info = user_tokens.get(user_id, {})
        emos_user_id = user_info.get('user_id', str(user_id))
        from app.database import get_balance
        balance = get_balance(emos_user_id)
        
        if balance < amount:
            await query.edit_message_text(f"游戏币不足!当前余额:{balance}")
            return
        
        # 提示用户
        await query.answer("✅ 开始新的挑战!")
        
        # 重新创建游戏
        keyboard = [
            [
                InlineKeyboardButton("✊ 石头", callback_data=f"shoot_ai_rock_{amount}"),
                InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_ai_scissors_{amount}"),
                InlineKeyboardButton("🖐 布", callback_data=f"shoot_ai_paper_{amount}")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(
            f"🎮 猜拳游戏 - 挑战天道\n\n"
            f"您下注了 {amount} 🪙\n\n"
            f"请选择你的出拳：",
            reply_markup=reply_markup
        )
        return
    
    # 群聊模式
    if data.startswith("shoot_group_"):
        # 格式: shoot_group_rock_chat_id
        parts = data.split("_")
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        user_choice = choice_map.get(parts[2], '石头')
        chat_id = int(parts[3])
        
        if chat_id not in shoot_games:
            await query.answer("游戏不存在或已结束")
            return
        
        game = shoot_games[chat_id]
        
        if user_id not in game['players']:
            # 如果用户还没参与, 添加到游戏
            from app.config import user_tokens
            if user_id not in user_tokens:
                await query.answer("请先使用 /start 命令登录")
                return
            
            user_info = user_tokens[user_id]
            emos_user_id = user_info.get('user_id', str(user_id))
            
            # 检查余额
            from app.database import get_balance
            balance = get_balance(emos_user_id)
            if balance < game['amount']:
                await query.answer(f"游戏币不足!当前余额:{balance}")
                return
            
            # 获取emos用户?
            emos_username = user_info.get('username', update.effective_user.first_name)
            
            # 添加用户到游戏
            game['players'][user_id] = {
                'name': emos_username,
                'emos_id': emos_user_id,
                'choice': user_choice
            }
            
            await query.answer(f"✅ 您选择了{user_choice}!已参与游戏")
        else:
            # 用户已经在游戏中, 更新选择
            if game['players'][user_id]['choice'] is not None:
                await query.answer(f"✅ 您已出拳")
            else:
                game['players'][user_id]['choice'] = user_choice
                await query.answer(f"✅ 您选择了{user_choice}")
        
        return
    
    # 单挑模式
    if data.startswith("shoot_duel_"):
        # 格式: shoot_duel_rock_gameid
        parts = data.split("_")
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        user_choice = choice_map.get(parts[2], '石头')
        game_id = "_".join(parts[3:])
        
        if game_id not in shoot_games:
            await query.edit_message_text("游戏不存在或已结束")
            return
        
        game = shoot_games[game_id]
        
        if user_id not in game['players']:
            await query.answer("您不是这个游戏的参与者!")
            return
        
        # 记录用户选择
        game['players'][user_id]['choice'] = user_choice
        
        # 检查是否双方都出拳?
        players = list(game['players'].keys())
        player1_id = players[0]
        player2_id = players[1]
        
        player1_choice = game['players'][player1_id]['choice']
        player2_choice = game['players'][player2_id]['choice']
        
        if player1_choice and player2_choice:
            # 双方都出拳了, 判定结束
            await process_duel_result(game_id, context)
        else:
            # 等待对方出拳
            await query.answer(f"✅ 您选择了{user_choice}, 等待对方出拳...")
            # 更新消息显示已出拳状态, 但保留按钮
            player1_name = game['players'][player1_id]['name']
            player2_name = game['players'][player2_id]['name']
            
            status_text = f"🎮 猜拳单挑\n\n{player1_name} ⚔️ {player2_name}\n下注金额:{game['amount']} 🪙\n\n"
            if player1_choice:
                status_text += f"✅ {player1_name} 已出拳\n"
            else:
                status_text += f"⏳ {player1_name} 等待中...\n"
            
            if player2_choice:
                status_text += f"✅ {player2_name} 已出拳\n"
            else:
                status_text += f"⏳ {player2_name} 等待中...\n"
            
            # 保留按钮, 让另一方可以继续选择
            keyboard = [
                [
                    InlineKeyboardButton("✊ 石头", callback_data=f"shoot_duel_rock_{game_id}"),
                    InlineKeyboardButton("✌️ 剪刀", callback_data=f"shoot_duel_scissors_{game_id}"),
                    InlineKeyboardButton("🖐 布", callback_data=f"shoot_duel_paper_{game_id}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(status_text, reply_markup=reply_markup)
        return
    
    # 加入群聊游戏并选择出拳
    if data.startswith("shoot_join_rock_") or data.startswith("shoot_join_scissors_") or data.startswith("shoot_join_paper_"):
        # 格式: shoot_join_rock_gameid
        parts = data.split("_")
        choice_map = {'rock': '石头', 'scissors': '剪刀', 'paper': '布'}
        user_choice = choice_map.get(parts[2], '石头')
        game_id = "_".join(parts[3:])
        
        if game_id not in shoot_games:
            await query.answer("游戏不存在或已结束!")
            return
        
        game = shoot_games[game_id]
        
        if user_id in game['players']:
            await query.answer("您已经加入了这个游戏")
            return
        
        if game['status'] != 'waiting':
            await query.answer("游戏已经开始!")
            return
        
        # 检查用户是否已登录
        from app.config import user_tokens
        if user_id not in user_tokens:
            await query.answer("请先使用 /start 命令登录")
            return
        
        # 检查用户余额
        user_info = user_tokens[user_id]
        emos_user_id = user_info.get('user_id', str(user_id))
        from app.database import get_balance
        balance = get_balance(emos_user_id)
        
        if balance < game['amount']:
            await query.answer(f"游戏币不足!当前余额:{balance}")
            return
        
        # 获取emos用户?
        emos_username = user_info.get('username', update.effective_user.first_name)
        
        # 添加用户到游戏并记录选择
        game['players'][user_id] = {
            'name': emos_username,
            'emos_id': emos_user_id,
            'choice': user_choice
        }
        
        await query.answer(f"加入成功!您选择了{user_choice}")
        
        # 回复用户确认选择
        await context.bot.send_message(
            chat_id=user_id,
            text=f"🎮 猜拳游戏\n\n" 
            f"您已成功加入游戏并选择了:{user_choice} {get_choice_emoji(user_choice)}\n" 
            f"下注金额:{game['amount']} 🪙\n\n" 
            f"等待游戏开奖.."
        )
        
        # 检查是否达到目标人?
        player_count = len(game['players'])
        if game['player_count'] and player_count >= game['player_count']:
            await start_shoot_group_game(game_id, context)
        return
    
    # 加入群聊游戏(旧方式, 保留兼容)
    if data.startswith("shoot_join_"):
        game_id = data.replace("shoot_join_", "")
        
        if game_id not in shoot_games:
            await query.answer("游戏不存在或已结束!")
            return
        
        game = shoot_games[game_id]
        
        if user_id in game['players']:
            await query.answer("您已经加入了这个游戏")
            return
        
        if game['status'] != 'waiting':
            await query.answer("游戏已经开始!")
            return
        
        # 检查用户是否已登录
        from app.config import user_tokens
        if user_id not in user_tokens:
            await query.answer("请先使用 /start 命令登录")
            return
        
        # 检查用户余额
        user_info = user_tokens[user_id]
        emos_user_id = user_info.get('user_id', str(user_id))
        from app.database import get_balance
        balance = get_balance(emos_user_id)
        
        if balance < game['amount']:
            await query.answer(f"游戏币不足!当前余额:{balance}")
            return
        
        # 获取emos用户?
        emos_username = user_info.get('username', update.effective_user.first_name)
        
        # 添加用户到游戏
        game['players'][user_id] = {
            'name': emos_username,
            'emos_id': emos_user_id,
            'choice': None
        }
        
        await query.answer("加入成功")
        
        # 更新消息
        player_count = len(game['players'])
        if game['player_count']:
            progress = f"{player_count}/{game['player_count']}"
        else:
            progress = f"{player_count}"
        
        text = (
            f"🎮 猜拳游戏创建成功"
        )
        if game['player_count']:
            text += "(坐庄模式)\n\n"
            text += f"庄家:{game['creator_name']}\n"
        else:
            text += "\n\n"
            text += f"创建者:{game['creator_name']}\n"
        
        text += f"下注金额:{game['amount']} 🪙\n"
        text += f"当前参与:{progress} 人\n\n"
        text += "🎲 1分钟后自动开奖"
        
        keyboard = [[InlineKeyboardButton("🎮 点击参与", callback_data=f"shoot_join_{game_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await query.edit_message_text(text, reply_markup=reply_markup)
        
        # 检查是否达到目标人?
        if game['player_count'] and player_count >= game['player_count']:
            await start_shoot_group_game(game_id, context)
        return

async def process_duel_result(game_id: str, context: ContextTypes.DEFAULT_TYPE):
    game = shoot_games[game_id]
    players = list(game['players'].keys())
    player1_id = players[0]
    player2_id = players[1]
    
    player1 = game['players'][player1_id]
    player2 = game['players'][player2_id]
    
    player1_choice = player1['choice']
    player2_choice = player2['choice']
    
    # 判定胜负
    result = determine_shoot_result(player1_choice, player2_choice)
    
    from app.database import get_balance, update_balance, add_game_record
    amount = game['amount']
    TAX_RATE = 0.1  # 系统抽水比例 10%
    
    if result == 'win':
        # player1赢
        # 计算服务费(从利润中抽取)
        service_fee = int(amount * TAX_RATE)
        net_win = amount - service_fee
        # 赢家获得:下注金额+ 输家的下注- 服务费
        # 输家失去:下注金额
        update_balance(player1['emos_id'], net_win)
        update_balance(player2['emos_id'], -amount)
        
        new_balance1 = get_balance(player1['emos_id'])
        new_balance2 = get_balance(player2['emos_id'])
        
        result_text = (
            f"🎮 猜拳单挑结果\n\n"
            f"{player1['name']} ⚔️ {player2['name']}\n\n"
            f"{player1['name']} 选择:{player1_choice} {get_choice_emoji(player1_choice)} 🎉\n"
            f"{player2['name']} 选择:{player2_choice} {get_choice_emoji(player2_choice)} 😢\n\n"
            f"🎉 {player1['name']} 赢了!\n"
            f"赢取:{amount} 🪙\n"
            f"服务费:{service_fee} 🪙\n"
            f"实际到账:{net_win} 🪙\n\n"
            f"{player1['name']} 余额:{new_balance1} 🪙\n"
            f"{player2['name']} 余额:{new_balance2} 🪙"
        )
        # 添加游戏记录
        add_game_record(player1['emos_id'], 'shoot', amount, 'win', net_win, player1['name'])
        add_game_record(player2['emos_id'], 'shoot', amount, 'lose', -amount, player2['name'])
    elif result == 'lose':
        # player2赢
        # 计算服务费(从利润中抽取)
        service_fee = int(amount * TAX_RATE)
        net_win = amount - service_fee
        # 赢家获得:下注金额+ 输家的下注- 服务费
        # 输家失去:下注金额
        update_balance(player2['emos_id'], net_win)
        update_balance(player1['emos_id'], -amount)
        
        new_balance1 = get_balance(player1['emos_id'])
        new_balance2 = get_balance(player2['emos_id'])
        
        result_text = (
            f"🎮 猜拳单挑结果\n\n"
            f"{player1['name']} ⚔️ {player2['name']}\n\n"
            f"{player1['name']} 选择:{player1_choice} {get_choice_emoji(player1_choice)} 😢\n"
            f"{player2['name']} 选择:{player2_choice} {get_choice_emoji(player2_choice)} 🎉\n\n"
            f"🎉 {player2['name']} 赢了!\n"
            f"赢取:{amount} 🪙\n"
            f"服务费:{service_fee} 🪙\n"
            f"实际到账:{net_win} 🪙\n\n"
            f"{player1['name']} 余额:{new_balance1} 🪙\n"
            f"{player2['name']} 余额:{new_balance2} 🪙"
        )
        # 添加游戏记录
        add_game_record(player2['emos_id'], 'shoot', amount, 'win', net_win, player2['name'])
        add_game_record(player1['emos_id'], 'shoot', amount, 'lose', -amount, player1['name'])
    else:
        # 平局
        new_balance1 = get_balance(player1['emos_id'])
        new_balance2 = get_balance(player2['emos_id'])
        
        result_text = (
            f"🎮 猜拳单挑结果\n\n"
            f"{player1['name']} ⚔️ {player2['name']}\n\n"
            f"{player1['name']} 选择:{player1_choice} {get_choice_emoji(player1_choice)} 🤝\n"
            f"{player2['name']} 选择:{player2_choice} {get_choice_emoji(player2_choice)} 🤝\n\n"
            f"🤝 平局!\n"
            f"不扣除游戏币\n\n"
            f"{player1['name']} 余额:{new_balance1} 🪙\n"
            f"{player2['name']} 余额:{new_balance2} 🪙"
        )
        # 添加游戏记录
        add_game_record(player1['emos_id'], 'shoot', amount, 'draw', 0, player1['name'])
        add_game_record(player2['emos_id'], 'shoot', amount, 'draw', 0, player2['name'])
    
    # 删除之前的游戏消息
    if game['message_id']:
        try:
            await context.bot.delete_message(
                chat_id=game['chat_id'],
                message_id=game['message_id']
            )
        except Exception as e:
            logger.error(f"删除游戏消息失败: {e}")
    
    # 发送结果并设置3分钟后自动删除
    message = await context.bot.send_message(
        chat_id=game['chat_id'],
        text=result_text
    )
    # 3分钟后删除消息(180秒)
    asyncio.create_task(delete_message_after_delay(context, game['chat_id'], message.message_id, 180))
    
    # 删除游戏
    del shoot_games[game_id]

def determine_shoot_result(user_choice: str, ai_choice: str) -> str:
    if user_choice == ai_choice:
        return 'draw'
    elif (user_choice == '石头' and ai_choice == '剪刀') or \
         (user_choice == '剪刀' and ai_choice == '布') or \
         (user_choice == '布' and ai_choice == '石头'):
        return 'win'
    else:
        return 'lose'

def get_choice_emoji(choice: str) -> str:
    emoji_map = {
        '石头': '✊',
        '剪刀': '✌️',
        '布': '🖐️'
    }
    return emoji_map.get(choice, '')

# 加入猜拳游戏命令处理器(保留用于兼容性)
async def join_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("请使用游戏消息中的[点击参与]按钮加入游戏!")

async def start_shoot_group_game(chat_id: str, context: ContextTypes.DEFAULT_TYPE):
    if chat_id not in shoot_games:
        return
    
    game = shoot_games[chat_id]
    game['status'] = 'playing'
    
    players = list(game['players'].keys())
    player_count = len(players)
    
    # 通知游戏开奖
    await context.bot.send_message(
        chat_id=game['chat_id'],
        text=f"🎮 猜拳游戏开始!\n\n参与人数:{player_count} 人\n正在分组对战..."
    )
    
    # 两两分组
    groups = []
    for i in range(0, player_count, 2):
        if i + 1 < player_count:
            groups.append((players[i], players[i+1]))
        else:
            # 单数, 最后一名和AI(天道)对战
            await process_ai_match(game, players[i], context)
    
    # 处理每组对战
    for group in groups:
        await process_player_match(game, group[0], group[1], context)
    
    # 删除游戏
    del shoot_games[chat_id]

async def process_ai_match(game: dict, user_id: int, context: ContextTypes.DEFAULT_TYPE):
    import random
    
    player = game['players'][user_id]
    amount = game['amount']
    
    # AI随机选择
    choices = ['石头', '剪刀', '布']
    ai_choice = random.choice(choices)
    user_choice = player['choice'] or random.choice(choices)
    
    # 判定胜负
    result = determine_shoot_result(user_choice, ai_choice)
    
    from app.database import get_balance, update_balance, add_game_record
    TAX_RATE = 0.1  # 系统抽水比例 10%
    
    if result == 'win':
        # 玩庄家
        service_fee = int(amount * TAX_RATE)
        net_win = amount - service_fee
        update_balance(player['emos_id'], net_win)
        new_balance = get_balance(player['emos_id'])
        
        result_text = (
            f"🎮 猜拳游戏结果 - 挑战天道\n\n"
            f"{player['name']} ⚔️ 天道\n\n"
            f"{player['name']} 选择:{user_choice} {get_choice_emoji(user_choice)} 🎉\n"
            f"天道选择:{ai_choice} {get_choice_emoji(ai_choice)} 😢\n\n"
            f"🎉 {player['name']} 赢了!\n"
            f"赢取:{amount} 🪙\n"
            f"服务费:{service_fee} 🪙\n"
            f"实际到账:{net_win} 🪙\n"
            f"当前余额:{new_balance} 🪙"
        )
        # 添加游戏记录
        add_game_record(player['emos_id'], 'shoot', amount, 'win', net_win, player['name'])
    elif result == 'lose':
        # AI?
        update_balance(player['emos_id'], -amount)
        new_balance = get_balance(player['emos_id'])
        
        result_text = (
            f"🎮 猜拳游戏结果 - 挑战天道\n\n"
            f"{player['name']} ⚔️ 天道\n\n"
            f"{player['name']} 选择:{user_choice} {get_choice_emoji(user_choice)} 😢\n"
            f"天道选择:{ai_choice} {get_choice_emoji(ai_choice)} 🎉\n\n"
            f"😢 {player['name']} 输了!\n"
            f"扣除:{amount} 🪙\n"
            f"当前余额:{new_balance} 🪙"
        )
        # 添加游戏记录
        add_game_record(player['emos_id'], 'shoot', amount, 'lose', -amount, player['name'])
    else:
        # 平局
        new_balance = get_balance(player['emos_id'])
        
        result_text = (
            f"🎮 猜拳游戏结果 - 挑战天道\n\n"
            f"{player['name']} ⚔️ 天道\n\n"
            f"{player['name']} 选择:{user_choice} {get_choice_emoji(user_choice)} 🤝\n"
            f"天道选择:{ai_choice} {get_choice_emoji(ai_choice)} 🤝\n\n"
            f"🤝 平局!\n"
            f"不扣除游戏币\n"
            f"当前余额:{new_balance} 🪙"
        )
        # 添加游戏记录
        add_game_record(player['emos_id'], 'shoot', amount, 'draw', 0, player['name'])
    
    # 发送消息并设置3分钟后自动删?
    message = await context.bot.send_message(chat_id=game['chat_id'], text=result_text)
    # 3分钟后删除消息(180秒)
    asyncio.create_task(delete_message_after_delay(context, game['chat_id'], message.message_id, 180))

async def delete_message_after_delay(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int, delay: int):
    await asyncio.sleep(delay)
    try:
        await context.bot.delete_message(chat_id=chat_id, message_id=message_id)
    except Exception as e:
        print(f"删除消息失败: {e}")

async def process_player_match(game: dict, user1_id: int, user2_id: int, context: ContextTypes.DEFAULT_TYPE):
    import random
    choices = ['石头', '剪刀', '布']
    
    player1 = game['players'][user1_id]
    player2 = game['players'][user2_id]
    
    user1_choice = player1['choice'] or random.choice(choices)
    user2_choice = player2['choice'] or random.choice(choices)
    
    result = determine_shoot_result(user1_choice, user2_choice)
    
    from app.database import get_balance, update_balance, add_game_record
    amount = game['amount']
    TAX_RATE = 0.1  # 系统抽水比例 10%
    
    if result == 'win':
        # player1?
        # 计算服务费(从利润中抽取?
        service_fee = int(amount * TAX_RATE)
        net_win = amount - service_fee
        # 赢家获得:下注金额+ 输家的下注- 服务
        # 输家失去:下注金额
        update_balance(player1['emos_id'], net_win)
        update_balance(player2['emos_id'], -amount)
        
        new_balance1 = get_balance(player1['emos_id'])
        new_balance2 = get_balance(player2['emos_id'])
        
        result_text = (
            f"🎮 猜拳对战结果\n\n"
            f"{player1['name']} VS {player2['name']}\n"
            f"{player1['name']} 选择:{user1_choice} {get_choice_emoji(user1_choice)} 🎉\n"
            f"{player2['name']} 选择:{user2_choice} {get_choice_emoji(user2_choice)} 😢\n\n"
            f"🎉 {player1['name']} 赢了!\n"
            f"赢取:{amount} 🪙\n"
            f"服务费:{service_fee} 🪙\n"
            f"实际到账:{net_win} 🪙\n\n"
            f"{player1['name']} 余额:{new_balance1} 🪙\n"
            f"{player2['name']} 余额:{new_balance2} 🪙"
        )
        # 添加游戏记录
        add_game_record(player1['emos_id'], 'shoot', amount, 'win', net_win, player1['name'])
        add_game_record(player2['emos_id'], 'shoot', amount, 'lose', -amount, player2['name'])
    elif result == 'lose':
        # player2?
        # 计算服务费(从利润中抽取?
        service_fee = int(amount * TAX_RATE)
        net_win = amount - service_fee
        # 赢家获得:下注金额+ 输家的下注- 服务
        # 输家失去:下注金额
        update_balance(player2['emos_id'], net_win)
        update_balance(player1['emos_id'], -amount)
        
        new_balance1 = get_balance(player1['emos_id'])
        new_balance2 = get_balance(player2['emos_id'])
        
        result_text = (
            f"🎮 猜拳对战结果\n\n"
            f"{player1['name']} VS {player2['name']}\n"
            f"{player1['name']} 选择:{user1_choice} {get_choice_emoji(user1_choice)} 😢\n"
            f"{player2['name']} 选择:{user2_choice} {get_choice_emoji(user2_choice)} 🎉\n\n"
            f"🎉 {player2['name']} 赢了!\n"
            f"赢取:{amount} 🪙\n"
            f"服务费:{service_fee} 🪙\n"
            f"实际到账:{net_win} 🪙\n\n"
            f"{player1['name']} 余额:{new_balance1} 🪙\n"
            f"{player2['name']} 余额:{new_balance2} 🪙"
        )
        # 添加游戏记录
        add_game_record(player2['emos_id'], 'shoot', amount, 'win', net_win, player2['name'])
        add_game_record(player1['emos_id'], 'shoot', amount, 'lose', -amount, player1['name'])
    else:
        # 平局
        new_balance1 = get_balance(player1['emos_id'])
        new_balance2 = get_balance(player2['emos_id'])
        
        result_text = (
            f"🎮 猜拳对战结果\n\n"
            f"{player1['name']} VS {player2['name']}\n"
            f"{player1['name']} 选择:{user1_choice} {get_choice_emoji(user1_choice)} 🤝\n"
            f"{player2['name']} 选择:{user2_choice} {get_choice_emoji(user2_choice)} 🤝\n\n"
            f"🤝 平局!\n"
            f"不扣除游戏币\n\n"
            f"{player1['name']} 余额:{new_balance1} 🪙\n"
            f"{player2['name']} 余额:{new_balance2} 🪙"
        )
        # 添加游戏记录
        add_game_record(player1['emos_id'], 'shoot', amount, 'draw', 0, player1['name'])
        add_game_record(player2['emos_id'], 'shoot', amount, 'draw', 0, player2['name'])
    
    # 发送消息并设置3分钟后自动删?
    message = await context.bot.send_message(chat_id=game['chat_id'], text=result_text)
    # 3分钟后删除消息(180秒)
    asyncio.create_task(delete_message_after_delay(context, game['chat_id'], message.message_id, 180))

# 检查猜拳游戏超?
async def check_shoot_games_task(application):
    import asyncio
    while True:
        await asyncio.sleep(10)  # 每10秒检查一次
        
        current_time = datetime.now()
        expired_games = []
        
        for chat_id, game in list(shoot_games.items()):
            # 检查是否超时
            if game.get('type') == 'banker':
                # 庄家模式
                if current_time >= game.get('end_time', game['created_at'] + timedelta(minutes=1)):
                    expired_games.append(chat_id)
            else:
                # 普通模式
                if (current_time - game['created_at']).total_seconds() > 60:
                    expired_games.append(chat_id)
        
        for chat_id in expired_games:
            await end_shoot_game(chat_id, application)

async def end_shoot_game(chat_id: str, application):
    if chat_id not in shoot_games:
        return
    
    game = shoot_games[chat_id]
    
    # 检查是否是庄家模式
    if game.get('type') == 'banker':
        await end_shoot_banker_game(chat_id, application)
        return
    
    # 如果是等待中的游戏, 且人数不?
    if game['status'] == 'waiting':
        player_count = len(game['players'])
        
        if player_count < 2:
            await application.bot.send_message(
                chat_id=game['chat_id'],
                text=f"🎮 猜拳游戏结束\n\n?分钟内无人参与, 游戏自动结束"
            )
        else:
            # 有人参与但时间到了, 开始游戏
            await application.bot.send_message(
                chat_id=game['chat_id'],
                text=f"🎮 猜拳游戏时间到!\n\n参与人数:{player_count} 人\n游戏开始!"
            )
            await start_shoot_group_game(chat_id, application)
            return
    elif game['status'] == 'playing':
        # 带按钮的游戏, 时间到了直接开始结束
        player_count = len(game['players'])
        # 检查是否有玩家选择了出拳(至少有创建者)
        players_with_choice = sum(1 for p in game['players'].values() if p['choice'] is not None)
        
        if players_with_choice == 0:
            # 没有人选择, 结束游戏
            await application.bot.send_message(
                chat_id=game['chat_id'],
                text=f"🎮 猜拳游戏结束\n\n无人参与, 游戏自动结束"
            )
        else:
            # 有人选择了, 开始结束
            await application.bot.send_message(
                chat_id=game['chat_id'],
                text=f"🎮 猜拳游戏时间到!\n\n参与人数:{players_with_choice} 人\n游戏开始!"
            )
            await start_shoot_group_game(chat_id, application)
            return
    
    del shoot_games[chat_id]

async def end_shoot_banker_game(chat_id: int, application):
    if chat_id not in shoot_games:
        return
    
    game = shoot_games[chat_id]
    if game.get('type') != 'banker':
        return
    
    bot = application.bot
    
    # 获取游戏状态
    game_no = game['game_no']
    status = game['status']
    banker = game['banker']
    players = game['players']
    amount = banker['amount']
    
    if status == 'waiting':
        # 等待参与阶段超时
        if len(players) == 0:
            # 无人参与，直接结束，不扣税
            await bot.send_message(
                chat_id=chat_id,
                text=f"🎮 猜拳庄家模式结束 - NO.{game_no}\n\n"
                     f"庄家: {banker['name']}\n"
                     f"⏱️ 1分钟内无人参与, 游戏自动结束\n"
                     f"💰 无人参与，不扣税"
            )
        else:
            # 有人参与，直接结算
            await settle_shoot_banker_game(chat_id, bot)
            return
    
    elif status == 'playing':
        # 出拳阶段超时，开始结算
        # 随机选择未出拳的人的出拳
        import random
        choices = ['石头', '剪刀', '布']
        
        # 庄家未出拳，随机选择
        if banker['choice'] is None:
            banker['choice'] = random.choice(choices)
        
        # 玩家未出拳，随机选择
        for player_id, player_data in players.items():
            if player_data['choice'] is None:
                player_data['choice'] = random.choice(choices)
        
        # 开始结算
        await settle_shoot_banker_game(chat_id, bot)
        return
    
    # 清理游戏
    if chat_id in shoot_games:
        del shoot_games[chat_id]
    

async def init_http_client():
    """初始化HTTP客户端"""
    try:
        await http_client.init_client()
        logger.info("HTTP客户端初始化成功")
    except Exception as e:
        logger.error(f"HTTP客户端初始化失败: {e}")

async def shutdown_http_client():
    """关闭HTTP客户端"""
    try:
        await http_client.close()
        logger.info("HTTP客户端关闭成功")
    except Exception as e:
        logger.error(f"HTTP客户端关闭失败: {e}")

def main() -> None:
    print("=== [DEBUG] ENTERING main() ===")
    import sys

    # 确保只有一个实例运行
    ensure_single_instance()
    
    logger.info("正在启动机器..")
    
    # 初始化HTTP客户端将在run_bot函数中执行
    
    # 初始化游戏数据库
    logger.info("初始化游戏数据库...")
    from app.database import init_db
    init_db()
    
    # 加载游戏用户token
    logger.info("加载游戏用户token...")
    try:
        logger.info("开始加载用户token...")
        from app.config import load_tokens_from_db
        logger.info("成功导入load_tokens_from_db函数")
        load_tokens_from_db()
        logger.info("成功加载用户token")
    except Exception as e:
        logger.error(f"加载用户token时出错: {e}")
        import traceback
        logger.error(f"加载用户token时出错堆栈: {traceback.format_exc()}")
    
    # 创建应用
    
    # 配置并发参数以支持多玩家
    # 使用更高的worker数量来处理并发请?
    from telegram.ext import Defaults
    import os
    
    # 从环境变量读取并发配置, 默认使用较高值以充分利用VPS资源
    concurrent_workers = int(os.getenv('BOT_CONCURRENT_WORKERS', '32'))
    connection_pool_size = int(os.getenv('BOT_CONNECTION_POOL_SIZE', '16'))
    
    print(f"[DEBUG] 并发配置: workers={concurrent_workers}, pool_size={connection_pool_size}")
    
    application = Application.builder() \
        .token(Config.BOT_TOKEN) \
        .post_init(post_init_wrapper) \
        .concurrent_updates(True) \
        .build()
    print("[DEBUG] Application创建完成")
    
    try:
        # 确保导入 rules_handler
        from handlers.rules import rules_handler
        
        # ===== 基本命令 =====
        print("[DEBUG] 添加start handler...")
        application.add_handler(CommandHandler("start", group_command_filter(start)))
        print("[DEBUG] 添加menu handler...")
        application.add_handler(CommandHandler("menu", group_command_filter(menu_command)))
        print("[DEBUG] 添加help handler...")
        application.add_handler(CommandHandler("help", group_command_filter(help_command)))
        print("[DEBUG] 添加cancel handler...")
        application.add_handler(CommandHandler("cancel", group_command_filter(cancel_command)))
        
        # ===== 游戏命令 =====
        print("[DEBUG] 添加游戏命令 handlers...")
        application.add_handler(CommandHandler("game", group_command_filter(start_handler)))
        application.add_handler(CommandHandler("balance", group_command_filter(balance_handler)))
        application.add_handler(CommandHandler("rules", group_command_filter(rules_handler)))
        application.add_handler(CommandHandler("guess", group_command_filter(guess_handler)))
        application.add_handler(CommandHandler("guess_bet", group_command_filter(guess_bet_handler)))
        application.add_handler(CommandHandler("slot", group_command_filter(slot_handler)))
        application.add_handler(CommandHandler("blackjack", group_command_filter(blackjack_handler)))
        application.add_handler(CommandHandler("hit", group_command_filter(hit_handler)))
        application.add_handler(CommandHandler("stand", group_command_filter(stand_handler)))
        application.add_handler(CommandHandler("daily", group_command_filter(daily_handler)))
        application.add_handler(CommandHandler("withdraw", group_command_filter(withdraw_handler)))
        print("[DEBUG] 游戏命令 handlers 添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    # ===== 红包对话 =====
    print("[DEBUG] 创建红包对话...")
    try:
        redpocket_conv = ConversationHandler(
        entry_points=[
            CommandHandler("redpocket", group_command_filter(redpocket_command)),
            CallbackQueryHandler(redpocket_command, pattern="^menu_redpocket$")
        ],
        states={
            WAITING_TYPE: [
                CallbackQueryHandler(handle_type, pattern="^(type_|image_no_password|image_with_password|audio_no_password|audio_with_password|back_)"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_CARROT: [
                MessageHandler(filters.TEXT, handle_carrot),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_NUMBER: [
                MessageHandler(filters.TEXT, handle_number),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_BLESSING: [
                MessageHandler(filters.TEXT, handle_blessing),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_PASSWORD: [
                MessageHandler(filters.TEXT, handle_password),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_SCENE: [
                CallbackQueryHandler(handle_scene, pattern="^scene_"),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_CUSTOM_BLESSING: [
                MessageHandler(filters.TEXT, handle_custom_blessing),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_MEDIA: [
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ]
        },
        fallbacks=[CommandHandler("cancel", cancel_redpacket)]
        )
        application.add_handler(redpocket_conv)
        print("[DEBUG] 红包对话handler添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    # ===== 红包查询对话 =====
    print("[DEBUG] 创建红包查询对话...")
    try:
        redpocket_query_conv = ConversationHandler(
            entry_points=[
                CommandHandler("check_redpacket", group_command_filter(check_redpacket_command)),
                CallbackQueryHandler(check_redpacket_command, pattern="^menu_check_redpacket$")
            ],
            states={
                WAITING_QUERY_TYPE: [
                    CallbackQueryHandler(handle_query_type, pattern="^(my_redpackets|input_id)$"),
                    CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
                ],
                WAITING_REDPACKET_ID: [
                    MessageHandler(filters.TEXT & ~filters.COMMAND, get_redpacket_id),
                    CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
                ],
            },
            fallbacks=[CommandHandler("cancel", cancel_command)]
        )
        application.add_handler(redpocket_query_conv)
        print("[DEBUG] 红包查询对话handler添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    # ===== 抽奖对话 =====
    print("[DEBUG] 创建抽奖对话...")
    try:
        lottery_conv = ConversationHandler(
        entry_points=[
            CommandHandler("lottery", group_command_filter(lottery_command)),
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
                CallbackQueryHandler(handle_end_time_choice, pattern="^end_time_"),
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
        print("[DEBUG] 抽奖对话handler添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    # ===== 取消抽奖对话 =====
    print("[DEBUG] 创建取消抽奖对话...")
    try:
        lottery_cancel_conv = ConversationHandler(
            entry_points=[
                CommandHandler("lottery_cancel", group_command_filter(lottery_cancel_command)),
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
        print("[DEBUG] 取消抽奖对话handler添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    # ===== 排行榜命令=====
    print("[DEBUG] 添加排行榜命令..")
    try:
        application.add_handler(CommandHandler("playing", group_command_filter(playing_command)))
        application.add_handler(CommandHandler("rank_carrot", group_command_filter(rank_carrot_command)))
        application.add_handler(CommandHandler("rank_upload", group_command_filter(rank_upload_command)))
        print("[DEBUG] 排行榜命令添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    # ===== 猜拳游戏命令 =====
    print("[DEBUG] 添加猜拳游戏命令...")
    try:
        application.add_handler(CommandHandler("gameshoot", group_command_filter(gameshoot_handler)))
        application.add_handler(CommandHandler("shoot", gameshoot_handler))
        application.add_handler(CallbackQueryHandler(shoot_callback_handler, pattern="^shoot_"))
        print("[DEBUG] 猜拳游戏命令添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return

    # ===== 打劫游戏命令 =====
    print("[DEBUG] 添加打劫游戏命令...")
    try:
        application.add_handler(CommandHandler("rob", group_command_filter(robbery_handler)))
        application.add_handler(CommandHandler("robstatus", robbery_status_handler))
        print("[DEBUG] 打劫游戏命令添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return
    
    # ===== 扑克牌游戏命令 =====
    print("[DEBUG] 添加扑克牌游戏命令...")
    try:
        from handlers.card_games import cardduel_callback_handler
        application.add_handler(CommandHandler("cardduel", group_command_filter(cardduel_handler)))
        application.add_handler(CommandHandler("join", group_command_filter(join_cardduel_handler)))
        application.add_handler(CallbackQueryHandler(cardduel_callback_handler, pattern="^join_card_"))
        print("[DEBUG] 扑克牌游戏命令添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return

    # ===== 牛牛游戏命令 =====
    print("[DEBUG] 添加牛牛游戏命令...")
    try:
        from handlers.card_games import niuniu_handler, join_niuniu_handler, niuniu_callback_handler
        application.add_handler(CommandHandler("niuniu", group_command_filter(niuniu_handler)))
        application.add_handler(CommandHandler("join", group_command_filter(join_niuniu_handler)))
        application.add_handler(CallbackQueryHandler(niuniu_callback_handler, pattern="^join_niuniu_"))
        print("[DEBUG] 牛牛游戏命令添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return

    # ===== 游戏规则命令 =====
    print("[DEBUG] 添加游戏规则命令...")
    try:
        from handlers.rules import rules_handler, menu_handler, rules_callback
        application.add_handler(CommandHandler("rules", group_command_filter(rules_handler)))
        application.add_handler(CommandHandler("menu", group_command_filter(menu_handler)))
        application.add_handler(CallbackQueryHandler(rules_callback, pattern="^rules_"))
        application.add_handler(CallbackQueryHandler(rules_callback, pattern="^game_"))
        print("[DEBUG] 游戏规则和菜单命令添加完成")
    except Exception as e:
        import traceback
        traceback.print_exc()
        return

    # 注意:游戏检查任务在post_init回调中启?

    # 添加猜大小游戏命令处理器
    application.add_handler(CommandHandler("guess", group_command_filter(guess_handler)))
    application.add_handler(CommandHandler("createguess", group_command_filter(createguess_handler)))
    application.add_handler(CallbackQueryHandler(guess_callback_handler, pattern="^guess_"))
    
    # 添加21点游戏按钮回调处理器
    application.add_handler(CallbackQueryHandler(hit_handler, pattern="^hit_"))
    application.add_handler(CallbackQueryHandler(stand_handler, pattern="^stand_"))
    
    # 添加用户输入处理器(包含游戏消息处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))
    
    # 添加骰子结果处理器
    print("[DEBUG] 注册骰子处理器..")
    try:
        # 使用 filters.Dice.ALL 过滤器捕获所有骰子消?
        dice_handler = MessageHandler(filters.Dice.ALL, handle_dice_result)
        application.add_handler(dice_handler, group=1)
        print("[DEBUG] 骰子处理器注册完成")
    except Exception as e:
        print(f"[ERROR] 注册骰子处理器失败 {e}")
        import traceback
        traceback.print_exc()
    
    # 按钮回调(处理所有未被对话捕获的回调用
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # 打印启动信息
    print("=" * 60)
    print("机器人启动成功!")
    print("=" * 60)
    print("可用命令:")
    for cmd, desc in BOT_COMMANDS:
        print(f"   /{cmd:<15} - {desc}")
    print("=" * 60)
    print(f"机器@{Config.BOT_USERNAME}")
    print(f"日志文件: {log_filename}")
    print("=" * 60)
    
    logger.info(f"机器@{Config.BOT_USERNAME} 启动成功")
    
    # 启动机器
    restart_count = 0
    while True:
        try:
            restart_count += 1
            # 直接运行机器人，使用默认行为
            logger.info(f"准备运行机器人... (第 {restart_count} 次启动)")
            # 添加更多的日志信息，以便排查问题
            logger.info("开始运行机器人...")
            # 使用较短的轮询间隔和超时时间，确保机器人保持运行状态
            # drop_pending_updates=True 表示在启动时丢弃所有未处理的更新
            application.run_polling(allowed_updates=Update.ALL_TYPES, poll_interval=0.5, timeout=30, drop_pending_updates=True)
            logger.info("机器人运行结束")
            # 如果机器人正常结束，等待一段时间后重新启动
            logger.info("机器人正常结束，5秒后重新启动...")
            import time
            time.sleep(5)
        except Exception as e:
            logger.error(f"运行机器人出错: {e}")
            import traceback
            logger.error(f"运行机器人出错堆栈: {traceback.format_exc()}")
            # 如果机器人出错，等待一段时间后重新启动
            logger.info("机器人出错，5秒后重新启动...")
            import time
            time.sleep(5)
        except BaseException as e:
            # 捕获所有异常，包括系统级别的异常
            logger.error(f"运行机器人出现严重错误: {e}")
            import traceback
            logger.error(f"运行机器人出现严重错误堆栈: {traceback.format_exc()}")
            # 如果机器人出现严重错误，等待一段时间后重新启动
            logger.info("机器人出现严重错误，5秒后重新启动...")
            import time
            time.sleep(5)

if __name__ == "__main__":
    main()

