from datetime import datetime, timedelta
import random
from app.database import get_balance, update_balance, get_last_checkin, update_checkin_time
from utils.http_client import http_client


def check_balance(user_id, amount):
    """
    检查用户余额是否充足
    :param user_id: 用户ID
    :param amount: 需要的金额
    :return: (是否充足, 当前余额)
    """
    current_balance = get_balance(user_id)
    if current_balance >= amount:
        return True, current_balance
    return False, current_balance


def process_daily_checkin(user_id):
    """
    处理每日签到
    :param user_id: 用户ID
    :return: (是否成功, 消息)
    """
    last_checkin = get_last_checkin(user_id)
    now = datetime.now()
    
    # 检查是否已经签到
    if last_checkin:
        # 计算上次签到时间到现在是否超过24小时
        time_diff = now - last_checkin
        if time_diff < timedelta(hours=24):
            return False, "您今天已经签到过了，明天再来吧！"
    
    # 发放1-5游戏币随机奖励
    reward = random.randint(1, 5)
    update_balance(user_id, reward)
    # 更新签到时间
    update_checkin_time(user_id, now)
    
    return True, f"签到成功！获得{reward}游戏币奖励。"
