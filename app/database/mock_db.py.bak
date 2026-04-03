# 模拟数据库
# 用户数据库，存储用户信息
users_db = {
    123456789: {
        'id': 123456789,
        'username': 'user1',
        'first_name': 'User',
        'last_name': 'One'
    },
    987654321: {
        'id': 987654321,
        'username': 'user2',
        'first_name': 'User',
        'last_name': 'Two'
    },
    111222333: {
        'id': 111222333,
        'username': 'user3',
        'first_name': 'User',
        'last_name': 'Three'
    }
}

# 余额数据库，存储用户游戏币余额
balances_db = {
    123456789: 100,
    987654321: 200,
    111222333: 50
}

# 签到记录，存储用户上次签到时间
daily_checkins = {}


def get_user(user_id):
    """获取用户信息"""
    return users_db.get(user_id, None)


def add_user(user_id, user_data):
    """添加用户"""
    users_db[user_id] = user_data


def get_balance(user_id):
    """获取用户余额"""
    return balances_db.get(user_id, 0)


def update_balance(user_id, amount):
    """更新用户余额"""
    current_balance = balances_db.get(user_id, 0)
    new_balance = current_balance + amount
    balances_db[user_id] = new_balance
    return new_balance


def get_last_checkin(user_id):
    """获取用户上次签到时间"""
    return daily_checkins.get(user_id, None)


def update_checkin_time(user_id, timestamp):
    """更新用户签到时间"""
    daily_checkins[user_id] = timestamp
