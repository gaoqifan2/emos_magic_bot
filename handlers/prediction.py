import asyncio
import hashlib
import json
import logging
import math
import os
import re
import sqlite3
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

import requests
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

from config import Config, DEFAULT_GROUP_CHAT_ID, SERVICE_PROVIDER_TOKEN, user_tokens
from utils.http_client import http_client

logger = logging.getLogger(__name__)

SCHEDULE_URL = os.getenv(
    "WORLD_CUP_SCHEDULE_URL",
    "https://raw.githubusercontent.com/openfootball/worldcup.json/master/2026/worldcup.json",
)
FIFA_MATCHES_URL = os.getenv(
    "FIFA_MATCHES_URL",
    "https://api.fifa.com/api/v3/calendar/matches",
)
FIFA_COMPETITION_ID = os.getenv("FIFA_COMPETITION_ID", "17")
FIFA_SEASON_ID = os.getenv("FIFA_SEASON_ID", "285023")
PREDICTION_SETTLEMENT_INTERVAL_SECONDS = int(os.getenv("PREDICTION_SETTLEMENT_INTERVAL_SECONDS", "30"))
PREDICTION_PAYOUT_TRANSFER_DELAY_SECONDS = max(
    0,
    int(os.getenv("PREDICTION_PAYOUT_TRANSFER_DELAY_SECONDS", "5")),
)
SCHEDULE_TTL_SECONDS = 60 * 60
PREDICTION_DB = Path(os.getenv("PREDICTION_DB", "prediction.db"))
PREDICTION_TICKET_DIR = Path(os.getenv("PREDICTION_TICKET_DIR", "prediction_tickets"))
PREDICTION_TICKET_UPLOAD_DIR = PREDICTION_TICKET_DIR / "uploads"
PREDICTION_TICKET_CARD_MANIFEST = PREDICTION_TICKET_UPLOAD_DIR / "cards.json"
PREDICTION_TICKET_ADMIN_IDS = {
    int(item.strip())
    for item in os.getenv("PREDICTION_TICKET_ADMIN_IDS", "").split(",")
    if item.strip().isdigit()
}
PREDICTION_TICKET_BG_URL = os.getenv(
    "PREDICTION_TICKET_BG_URL",
    "https://commons.wikimedia.org/wiki/Special:FilePath/Hard%20Rock%20Stadium%20Club%20World%20Cup.jpg?width=1600",
)
PREDICTION_TICKET_BG_CACHE = PREDICTION_TICKET_DIR / "worldcup_2026_ticket_bg.jpg"
PREDICTION_TICKET_CARDS = [
    {
        "name": "梅西",
        "code": "GOAT-10",
        "file": "Lionel-Messi-Argentina-2022-FIFA-World-Cup (cropped).jpg",
    },
    {
        "name": "姆巴佩",
        "code": "PARIS-07",
        "file": "2022 FIFA World Cup France 4–1 Australia - (16).jpg",
    },
    {
        "name": "C罗",
        "code": "SIU-07",
        "file": "Cristiano Ronaldo WC2022 - 01 (cropped).jpg",
    },
    {
        "name": "内马尔",
        "code": "SAMBA-10",
        "file": "Brasil vs Serbia WC2022 (Neymar).jpg",
    },
    {
        "name": "三叉戟",
        "code": "TRIO-30",
        "file": "Messi Neymar Mbappé PSG 2022.jpg",
    },
    {
        "name": "凯恩",
        "code": "LION-09",
        "file": "Harry Kane 2022 World Cup (cropped).jpg",
    },
    {
        "name": "孙兴慜",
        "code": "TIGER-07",
        "file": "Son Heung-min - 2022 (52552243725) (cropped).jpg",
    },
    {
        "name": "德布劳内",
        "code": "ENGINE-17",
        "file": "Kevin De Bruyne WC2022.jpg",
    },
    {
        "name": "贝林厄姆",
        "code": "STAR-22",
        "file": "Jude Bellingham WC2022.jpg",
    },
    {
        "name": "维尼修斯",
        "code": "SAMBA-20",
        "file": "Vinicius Junior WC2022.jpg",
    },
    {
        "name": "马内",
        "code": "LION-10",
        "file": "Sadio Mane N*10 du Senegal (cropped).jpg",
    },
    {
        "name": "格列兹曼",
        "code": "ROOSTER-07",
        "file": "2022 FIFA World Cup France 4–1 Australia - (12).jpg",
    },
]
PLATFORM_SUBSIDY = int(os.getenv("PREDICTION_PLATFORM_SUBSIDY", "100"))
POOL_RELEASE_BASE_STAKE = max(1, int(os.getenv("PREDICTION_POOL_RELEASE_BASE_STAKE", "500")))
RESULT_POOL_STAKE_MULTIPLIER = float(os.getenv("PREDICTION_RESULT_POOL_STAKE_MULTIPLIER", "3"))
SCORE_POOL_STAKE_MULTIPLIER = float(os.getenv("PREDICTION_SCORE_POOL_STAKE_MULTIPLIER", "5"))
STAKE_OPTIONS = [10, 50, 100, 500, 1000]
CUSTOM_MATCH_CREATE_FEE = int(os.getenv("PREDICTION_CUSTOM_MATCH_CREATE_FEE", "50"))
CUSTOM_MATCH_FEE_RECEIVER_USER_ID = os.getenv("PREDICTION_FEE_RECEIVER_USER_ID", "")
BEIJING_TZ = timezone(timedelta(hours=8))

_schedule_cache = {"loaded_at": None, "matches": []}


PREDICTION_TABLE_COLUMNS = [
    "id",
    "telegram_user_id",
    "username",
    "match_id",
    "match_label",
    "match_time",
    "result_pick",
    "score_pick",
    "stake",
    "status",
    "created_at",
    "emos_user_id",
    "order_no",
    "platform_order_no",
    "payment_param",
    "pay_url",
    "paid_at",
    "stake_transfer_status",
    "pool_receiver_user_id",
    "settled_result",
    "settled_score",
    "settled_at",
    "payout_amount",
    "payout_status",
    "payout_error",
]


PREDICTION_RULES_TEXT = (
    "⚽ 世界杯预测规则\n\n"
    "玩法采用奖池制，萝卜只用于站内娱乐。\n\n"
    f"1. 单场总奖池 = 用户投入萝卜 + f1bb补贴的 {PLATFORM_SUBSIDY} 萝卜。\n"
    "2. 胜平负池占 40%，比分池占 60%，两个池子独立结算。\n"
    "3. 中奖用户按自己投入占全场已支付投入的比例领取对应池子，剩余留在平台。\n"
    "4. 全场参与越少，实际释放的奖池越少，避免 1 萝卜冷门票拿走整池。\n"
    "5. 比赛开赛前 10 分钟停止预测。\n"
    "6. 比赛取消或延期时，已投入萝卜退回。\n\n"
    f"例：本场用户共下 3000，f1bb补贴 {PLATFORM_SUBSIDY}，总奖池 {3000 + PLATFORM_SUBSIDY}。\n"
    f"胜平负池 {int((3000 + PLATFORM_SUBSIDY) * 0.4)}，比分池 {int((3000 + PLATFORM_SUBSIDY) * 0.6)}。\n"
    "如果某用户下 100 且比分命中，会按 100 / 3000 的全场投入比例领取比分池的一部分。\n"
    "如果无人猜中比分，比分池不发放，留在平台。\n\n"
    f"当前控赔：f1bb每场补贴 {PLATFORM_SUBSIDY} 萝卜，下注金额不设上限。"
)


TEAM_NAMES = {
    "Mexico": "墨西哥",
    "South Africa": "南非",
    "South Korea": "韩国",
    "Czech Republic": "捷克",
    "Canada": "加拿大",
    "Bosnia & Herzegovina": "波黑",
    "Qatar": "卡塔尔",
    "Switzerland": "瑞士",
    "United States": "美国",
    "USA": "美国",
    "Paraguay": "巴拉圭",
    "Morocco": "摩洛哥",
    "Japan": "日本",
    "Germany": "德国",
    "Curaçao": "库拉索",
    "Brazil": "巴西",
    "Haiti": "海地",
    "Belgium": "比利时",
    "Egypt": "埃及",
    "Spain": "西班牙",
    "Cape Verde": "佛得角",
    "France": "法国",
    "Senegal": "塞内加尔",
    "Argentina": "阿根廷",
    "Algeria": "阿尔及利亚",
    "Australia": "澳大利亚",
    "Austria": "奥地利",
    "Ecuador": "厄瓜多尔",
    "New Zealand": "新西兰",
    "Italy": "意大利",
    "Tunisia": "突尼斯",
    "England": "英格兰",
    "Croatia": "克罗地亚",
    "Uruguay": "乌拉圭",
    "Saudi Arabia": "沙特阿拉伯",
    "Colombia": "哥伦比亚",
    "Ghana": "加纳",
    "Portugal": "葡萄牙",
    "Uzbekistan": "乌兹别克斯坦",
    "Netherlands": "荷兰",
    "Iran": "伊朗",
    "Norway": "挪威",
    "Panama": "巴拿马",
    "Scotland": "苏格兰",
    "Ivory Coast": "科特迪瓦",
    "Turkey": "土耳其",
}


def create_worldcup_predictions_table(conn, table_name="worldcup_predictions"):
    conn.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_user_id INTEGER NOT NULL,
            username TEXT,
            match_id TEXT NOT NULL,
            match_label TEXT NOT NULL,
            match_time TEXT NOT NULL,
            result_pick TEXT NOT NULL,
            score_pick TEXT NOT NULL,
            stake INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL,
            emos_user_id TEXT,
            order_no TEXT,
            platform_order_no TEXT,
            payment_param TEXT,
            pay_url TEXT,
            paid_at TEXT,
            stake_transfer_status TEXT DEFAULT 'not_charged',
            pool_receiver_user_id TEXT,
            settled_result TEXT,
            settled_score TEXT,
            settled_at TEXT,
            payout_amount INTEGER DEFAULT 0,
            payout_status TEXT DEFAULT 'not_settled',
            payout_error TEXT
        )
        """
    )


def migrate_prediction_table_remove_unique(conn):
    row = conn.execute(
        """
        SELECT sql
        FROM sqlite_master
        WHERE type = 'table' AND name = 'worldcup_predictions'
        """
    ).fetchone()
    table_sql = row[0] if row and row[0] else ""
    normalized_sql = re.sub(r"\s+", "", table_sql).upper()
    if "UNIQUE(TELEGRAM_USER_ID,MATCH_ID)" not in normalized_sql:
        return

    backup_table = f"worldcup_predictions_unique_backup_{datetime.now(BEIJING_TZ).strftime('%Y%m%d%H%M%S')}"
    conn.execute(f"ALTER TABLE worldcup_predictions RENAME TO {backup_table}")
    create_worldcup_predictions_table(conn)

    old_columns = {
        row[1]
        for row in conn.execute(f"PRAGMA table_info({backup_table})").fetchall()
    }
    copied_columns = [column for column in PREDICTION_TABLE_COLUMNS if column in old_columns]
    column_sql = ", ".join(copied_columns)
    conn.execute(
        f"""
        INSERT INTO worldcup_predictions ({column_sql})
        SELECT {column_sql}
        FROM {backup_table}
        """
    )
    conn.execute(f"DROP TABLE {backup_table}")


def init_prediction_db():
    with sqlite3.connect(PREDICTION_DB) as conn:
        create_worldcup_predictions_table(conn)
        ensure_column(conn, "worldcup_predictions", "emos_user_id", "TEXT")
        ensure_column(conn, "worldcup_predictions", "order_no", "TEXT")
        ensure_column(conn, "worldcup_predictions", "platform_order_no", "TEXT")
        ensure_column(conn, "worldcup_predictions", "payment_param", "TEXT")
        ensure_column(conn, "worldcup_predictions", "pay_url", "TEXT")
        ensure_column(conn, "worldcup_predictions", "paid_at", "TEXT")
        ensure_column(conn, "worldcup_predictions", "stake_transfer_status", "TEXT DEFAULT 'not_charged'")
        ensure_column(conn, "worldcup_predictions", "pool_receiver_user_id", "TEXT")
        ensure_column(conn, "worldcup_predictions", "settled_result", "TEXT")
        ensure_column(conn, "worldcup_predictions", "settled_score", "TEXT")
        ensure_column(conn, "worldcup_predictions", "settled_at", "TEXT")
        ensure_column(conn, "worldcup_predictions", "payout_amount", "INTEGER DEFAULT 0")
        ensure_column(conn, "worldcup_predictions", "payout_status", "TEXT DEFAULT 'not_settled'")
        ensure_column(conn, "worldcup_predictions", "payout_error", "TEXT")
        migrate_prediction_table_remove_unique(conn)
        conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_worldcup_predictions_user_match
            ON worldcup_predictions(telegram_user_id, match_id)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_worldcup_predictions_platform_order
            ON worldcup_predictions(platform_order_no)
            WHERE platform_order_no IS NOT NULL
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS custom_prediction_matches (
                id TEXT PRIMARY KEY,
                creator_telegram_user_id INTEGER NOT NULL,
                creator_username TEXT,
                team1 TEXT NOT NULL,
                team2 TEXT NOT NULL,
                prediction_deadline TEXT NOT NULL,
                platform_subsidy INTEGER NOT NULL,
                create_fee INTEGER NOT NULL,
                fee_status TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_settlement_requests (
                match_id TEXT PRIMARY KEY,
                match_label TEXT,
                fifa_result TEXT,
                fifa_score TEXT,
                status TEXT NOT NULL DEFAULT 'requested',
                notified_at TEXT,
                settled_at TEXT,
                settled_by INTEGER,
                source TEXT,
                note TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_manual_payouts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                reason TEXT NOT NULL,
                prediction_id INTEGER,
                platform_order_no TEXT,
                telegram_user_id INTEGER NOT NULL,
                username TEXT,
                emos_user_id TEXT NOT NULL,
                match_id TEXT,
                match_label TEXT,
                result_pick TEXT,
                score_pick TEXT,
                stake INTEGER,
                payout_amount INTEGER NOT NULL,
                transfer_status TEXT NOT NULL,
                transfer_response TEXT,
                notified INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_public_announcements (
                match_id TEXT PRIMARY KEY,
                chat_id INTEGER,
                message_id INTEGER,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL,
                note TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS prediction_match_subsidies (
                match_id TEXT PRIMARY KEY,
                subsidy INTEGER NOT NULL,
                updated_by INTEGER,
                updated_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def ensure_column(conn, table_name, column_name, column_definition):
    columns = {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})").fetchall()}
    if column_name not in columns:
        conn.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_definition}")


def save_custom_match(user, team1, team2, deadline, fee_status):
    init_prediction_db()
    match_id = f"custom-{datetime.now(BEIJING_TZ).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:6]}"
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            INSERT INTO custom_prediction_matches (
                id, creator_telegram_user_id, creator_username, team1, team2,
                prediction_deadline, platform_subsidy, create_fee, fee_status,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'open', ?)
            """,
            (
                match_id,
                user.id,
                user.username or user.full_name,
                team1,
                team2,
                deadline.isoformat(),
                PLATFORM_SUBSIDY,
                CUSTOM_MATCH_CREATE_FEE,
                fee_status,
                datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return match_id


def save_demo_match(team1, team2, settlement_time, creator_user_id=0):
    init_prediction_db()
    match_id = f"demo-{datetime.now(BEIJING_TZ).strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4]}"
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            INSERT OR REPLACE INTO custom_prediction_matches (
                id, creator_telegram_user_id, creator_username, team1, team2,
                prediction_deadline, platform_subsidy, create_fee, fee_status,
                status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 0, 'demo', 'open', ?)
            """,
            (
                match_id,
                creator_user_id,
                "demo",
                team1,
                team2,
                settlement_time.isoformat(),
                PLATFORM_SUBSIDY,
                datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return match_id


def get_open_custom_matches():
    init_prediction_db()
    now_text = datetime.now(BEIJING_TZ).isoformat()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM custom_prediction_matches
            WHERE status = 'open' AND prediction_deadline > ?
            ORDER BY prediction_deadline ASC
            LIMIT 20
            """,
            (now_text,),
        ).fetchall()

    matches = []
    for row in rows:
        item = dict(row)
        deadline = datetime.fromisoformat(item["prediction_deadline"])
        matches.append({
            "id": item["id"],
            "team1": item["team1"],
            "team2": item["team2"],
            "group": "模拟测试" if item["id"].startswith("demo-") else "自定义预测",
            "ground": f"结算 {deadline.strftime('%H:%M')}" if item["id"].startswith("demo-") else f"截止 {deadline.strftime('%m-%d %H:%M')}",
            "beijing_time": deadline,
            "prediction_deadline": deadline,
            "is_custom": True,
            "is_demo": item["id"].startswith("demo-"),
            "create_fee": item["create_fee"],
            "fee_status": item["fee_status"],
            "platform_subsidy": int(item.get("platform_subsidy") or PLATFORM_SUBSIDY),
        })
    return matches


def get_match_subsidy(match_id, match=None):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT subsidy FROM prediction_match_subsidies WHERE match_id = ?",
            (match_id,),
        ).fetchone()
        if row:
            return int(row["subsidy"] or 0)
        custom = conn.execute(
            "SELECT platform_subsidy FROM custom_prediction_matches WHERE id = ?",
            (match_id,),
        ).fetchone()
        if custom:
            return int(custom["platform_subsidy"] or 0)
    if match and "platform_subsidy" in match:
        return int(match.get("platform_subsidy") or 0)
    return PLATFORM_SUBSIDY


def set_match_subsidy(match_id, subsidy, updated_by):
    init_prediction_db()
    subsidy = max(0, int(subsidy))
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            INSERT INTO prediction_match_subsidies (match_id, subsidy, updated_by, updated_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                subsidy = excluded.subsidy,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (
                match_id,
                subsidy,
                int(updated_by or 0),
                datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
            ),
        )
        conn.commit()
    return subsidy


def clear_match_subsidy(match_id):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute("DELETE FROM prediction_match_subsidies WHERE match_id = ?", (match_id,))
        conn.commit()


def build_prediction_order_no():
    return f"P{datetime.now(BEIJING_TZ).strftime('%Y%m%d%H%M%S')}{uuid.uuid4().hex[:6].upper()}"


def save_prediction(
    user,
    pick,
    status="pending",
    emos_user_id=None,
    transfer_status="paid",
    order_no=None,
    platform_order_no=None,
    payment_param=None,
    pay_url=None,
):
    init_prediction_db()
    order_no = order_no or pick.get("order_no") or build_prediction_order_no()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            INSERT INTO worldcup_predictions (
                telegram_user_id, username, match_id, match_label, match_time,
                result_pick, score_pick, stake, status, created_at,
                emos_user_id, order_no, platform_order_no, payment_param, pay_url,
                stake_transfer_status, pool_receiver_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user.id,
                user.username or user.full_name,
                pick["match"]["id"],
                match_label(pick["match"]),
                pick["match"]["beijing_time"].isoformat(),
                pick["result"],
                pick["score"],
                pick["stake"],
                status,
                datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
                emos_user_id,
                order_no,
                platform_order_no,
                payment_param,
                pay_url,
                transfer_status,
                None,
            ),
        )
        conn.commit()
    return order_no


def update_prediction_payment(platform_order_no, status, transfer_status, paid_at=None):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            UPDATE worldcup_predictions
            SET status = ?, stake_transfer_status = ?, paid_at = ?
            WHERE platform_order_no = ?
            """,
            (status, transfer_status, paid_at, platform_order_no),
        )
        conn.commit()


def get_prediction_by_platform_order(platform_order_no):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM worldcup_predictions WHERE platform_order_no = ?",
            (platform_order_no,),
        ).fetchone()
    return dict(row) if row else None


def get_user_predictions(user_id, limit=8):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT * FROM worldcup_predictions
            WHERE telegram_user_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def get_payout_history_matches(limit=8, offset=0):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT
                match_id,
                match_label,
                MAX(match_time) AS match_time,
                MAX(settled_at) AS settled_at,
                MAX(settled_result) AS settled_result,
                MAX(settled_score) AS settled_score,
                COUNT(*) AS bets,
                SUM(stake) AS total_stake,
                SUM(CASE WHEN payout_status = 'paid' THEN payout_amount ELSE 0 END) AS paid_amount,
                SUM(CASE WHEN payout_status = 'failed' THEN payout_amount ELSE 0 END) AS failed_amount,
                SUM(CASE WHEN payout_amount > 0 THEN 1 ELSE 0 END) AS winner_count
            FROM worldcup_predictions
            WHERE status = 'settled'
            GROUP BY match_id, match_label
            ORDER BY COALESCE(MAX(settled_at), MAX(match_time)) DESC
            LIMIT ? OFFSET ?
            """,
            (limit, offset),
        ).fetchall()
        total = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM (
                SELECT match_id, match_label
                FROM worldcup_predictions
                WHERE status = 'settled'
                GROUP BY match_id, match_label
            )
            """
        ).fetchone()["total"]
    return [dict(row) for row in rows], int(total or 0)


def get_payout_history_for_match(match_id):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        predictions = conn.execute(
            """
            SELECT *
            FROM worldcup_predictions
            WHERE match_id = ? AND status = 'settled'
            ORDER BY payout_amount DESC, stake DESC, id ASC
            """,
            (match_id,),
        ).fetchall()
        manual_rows = conn.execute(
            """
            SELECT *
            FROM prediction_manual_payouts
            WHERE match_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (match_id,),
        ).fetchall()
        request = conn.execute(
            """
            SELECT *
            FROM prediction_settlement_requests
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()
    return {
        "predictions": [dict(row) for row in predictions],
        "manual_payouts": [dict(row) for row in manual_rows],
        "settlement_request": dict(request) if request else None,
    }


def get_match_bet_details(match_id, limit=10, offset=0):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM worldcup_predictions
            WHERE match_id = ?
            ORDER BY
                CASE WHEN stake_transfer_status = 'paid' THEN 0 ELSE 1 END,
                created_at ASC,
                id ASC
            LIMIT ? OFFSET ?
            """,
            (match_id, limit, offset),
        ).fetchall()
        total = conn.execute(
            """
            SELECT COUNT(*) AS total
            FROM worldcup_predictions
            WHERE match_id = ?
            """,
            (match_id,),
        ).fetchone()["total"]
        summary = conn.execute(
            """
            SELECT
                match_label,
                MAX(match_time) AS match_time,
                COUNT(*) AS bets,
                SUM(stake) AS total_stake,
                SUM(CASE WHEN stake_transfer_status = 'paid' THEN 1 ELSE 0 END) AS paid_bets,
                SUM(CASE WHEN stake_transfer_status = 'paid' THEN stake ELSE 0 END) AS paid_stake
            FROM worldcup_predictions
            WHERE match_id = ?
            GROUP BY match_id, match_label
            """,
            (match_id,),
        ).fetchone()
    return {
        "rows": [dict(row) for row in rows],
        "total": int(total or 0),
        "summary": dict(summary) if summary else None,
    }


def get_match_pool_stats(match_id):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT result_pick, score_pick, SUM(stake) AS stake, COUNT(*) AS users
            FROM worldcup_predictions
            WHERE match_id = ? AND status = 'pending'
            GROUP BY result_pick, score_pick
            """,
            (match_id,),
        ).fetchall()

    total_stake = 0
    result_stakes = {"主胜": 0, "平": 0, "客胜": 0}
    result_users = {"主胜": 0, "平": 0, "客胜": 0}
    score_stakes = {}
    score_users = {}

    for row in rows:
        stake = int(row["stake"] or 0)
        users = int(row["users"] or 0)
        result_pick = row["result_pick"]
        score_pick = row["score_pick"]
        total_stake += stake
        result_stakes[result_pick] = result_stakes.get(result_pick, 0) + stake
        result_users[result_pick] = result_users.get(result_pick, 0) + users
        score_stakes[score_pick] = score_stakes.get(score_pick, 0) + stake
        score_users[score_pick] = score_users.get(score_pick, 0) + users

    platform_subsidy = get_match_subsidy(match_id)
    total_pool = total_stake + platform_subsidy
    return {
        "total_stake": total_stake,
        "platform_subsidy": platform_subsidy,
        "total_pool": total_pool,
        "result_pool": int(total_pool * 0.4),
        "score_pool": total_pool - int(total_pool * 0.4),
        "result_stakes": result_stakes,
        "result_users": result_users,
        "score_stakes": score_stakes,
        "score_users": score_users,
    }


def get_settlement_candidate_match_ids():
    init_prediction_db()
    now_text = datetime.now(BEIJING_TZ).isoformat()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT match_id, MIN(match_time) AS match_time, COUNT(*) AS bets
            FROM worldcup_predictions
            WHERE status = 'pending'
              AND stake_transfer_status = 'paid'
              AND (match_id LIKE 'fifa-%' OR match_id LIKE 'demo-%')
              AND match_time <= ?
            GROUP BY match_id
            """,
            (now_text,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_paid_predictions_for_match(match_id):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """
            SELECT *
            FROM worldcup_predictions
            WHERE match_id = ?
              AND status = 'pending'
              AND stake_transfer_status = 'paid'
            ORDER BY id ASC
            """,
            (match_id,),
        ).fetchall()
    return [dict(row) for row in rows]


def get_settlement_request(match_id):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM prediction_settlement_requests WHERE match_id = ?",
            (match_id,),
        ).fetchone()
    return dict(row) if row else None


def save_settlement_request(match_id, match_label_text, fifa_result, fifa_score, status="requested", note=None):
    init_prediction_db()
    now_text = datetime.now(BEIJING_TZ).isoformat(timespec="seconds")
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            INSERT INTO prediction_settlement_requests (
                match_id, match_label, fifa_result, fifa_score, status, notified_at, note
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(match_id) DO UPDATE SET
                match_label = excluded.match_label,
                fifa_result = excluded.fifa_result,
                fifa_score = excluded.fifa_score,
                status = excluded.status,
                notified_at = excluded.notified_at,
                note = excluded.note
            """,
            (match_id, match_label_text, fifa_result, fifa_score, status, now_text, note),
        )
        conn.commit()


def update_settlement_request_done(match_id, admin_id, source, note=None):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            UPDATE prediction_settlement_requests
            SET status = 'settled',
                settled_at = ?,
                settled_by = ?,
                source = ?,
                note = ?
            WHERE match_id = ?
            """,
            (
                datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
                admin_id,
                source,
                note,
                match_id,
            ),
        )
        if match_id.startswith(("custom-", "demo-")):
            conn.execute(
                "UPDATE custom_prediction_matches SET status = 'settled' WHERE id = ?",
                (match_id,),
            )
        conn.commit()


def update_settlement_request_status(match_id, status, note=None):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            UPDATE prediction_settlement_requests
            SET status = ?, note = ?
            WHERE match_id = ?
            """,
            (status, note, match_id),
        )
        conn.commit()


def is_match_settled(match_id):
    request = get_settlement_request(match_id)
    return bool(request and request.get("status") == "settled")


def distribute_pool(pool_amount, winners):
    if pool_amount <= 0 or not winners:
        return {}

    total_stake = sum(int(item["stake"]) for item in winners)
    if total_stake <= 0:
        return {}

    payouts = {}
    remainders = []
    assigned = 0
    for item in winners:
        exact = pool_amount * int(item["stake"]) / total_stake
        base = int(exact)
        payouts[item["id"]] = payouts.get(item["id"], 0) + base
        assigned += base
        remainders.append((exact - base, int(item["stake"]), item["id"]))

    leftover = pool_amount - assigned
    for _, _, prediction_id in sorted(remainders, reverse=True)[:leftover]:
        payouts[prediction_id] = payouts.get(prediction_id, 0) + 1
    return payouts


def distribute_capped_pool(pool_amount, winners, total_stake, stake_multiplier):
    if pool_amount <= 0 or not winners or total_stake <= 0:
        return {}

    total_winner_stake = sum(max(0, int(item["stake"])) for item in winners)
    if total_winner_stake <= 0:
        return {}

    payouts = {}
    assigned = 0
    candidates = []
    for item in winners:
        stake = max(0, int(item["stake"]))
        if stake <= 0:
            continue
        share_by_winners = pool_amount * stake / total_winner_stake
        cap_by_full_pool = pool_amount * stake / total_stake * stake_multiplier
        exact = min(share_by_winners, cap_by_full_pool)
        amount = int(exact)
        if exact > 0 and amount <= 0:
            amount = 1
        if amount <= 0:
            continue
        prediction_id = item["id"]
        payouts[prediction_id] = payouts.get(prediction_id, 0) + amount
        assigned += amount
        candidates.append((exact, amount, prediction_id))

    max_assignable = int(pool_amount)
    if assigned <= max_assignable:
        return payouts

    overflow = assigned - max_assignable
    for _, amount, prediction_id in sorted(candidates):
        if overflow <= 0:
            break
        removable = min(amount, overflow)
        payouts[prediction_id] -= removable
        overflow -= removable
        if payouts[prediction_id] <= 0:
            payouts.pop(prediction_id, None)
    return payouts


def calculate_settlement_payouts(predictions, actual_result, actual_score, platform_subsidy=None):
    total_stake = sum(int(item["stake"]) for item in predictions)
    if platform_subsidy is None and predictions:
        platform_subsidy = get_match_subsidy(predictions[0]["match_id"])
    platform_subsidy = int(platform_subsidy or 0)
    total_pool = total_stake + platform_subsidy if predictions else 0
    result_winners = [item for item in predictions if item["result_pick"] == actual_result]
    score_winners = [item for item in predictions if item["score_pick"] == actual_score]

    result_pool = int(total_pool * 0.4)
    score_pool = total_pool - result_pool
    release_ratio = min(1.0, total_stake / POOL_RELEASE_BASE_STAKE) if total_stake > 0 else 0.0
    result_released_pool = math.ceil(result_pool * release_ratio) if result_winners else 0
    score_released_pool = math.ceil(score_pool * release_ratio) if score_winners else 0

    payouts = {item["id"]: 0 for item in predictions}
    for prediction_id, amount in distribute_capped_pool(
        result_released_pool,
        result_winners,
        total_stake,
        RESULT_POOL_STAKE_MULTIPLIER,
    ).items():
        payouts[prediction_id] = payouts.get(prediction_id, 0) + amount
    for prediction_id, amount in distribute_capped_pool(
        score_released_pool,
        score_winners,
        total_stake,
        SCORE_POOL_STAKE_MULTIPLIER,
    ).items():
        payouts[prediction_id] = payouts.get(prediction_id, 0) + amount
    payout_total = sum(int(value or 0) for value in payouts.values())

    return {
        "total_stake": total_stake,
        "platform_subsidy": platform_subsidy,
        "total_pool": total_pool,
        "result_pool": result_pool,
        "score_pool": score_pool,
        "release_ratio": release_ratio,
        "release_base_stake": POOL_RELEASE_BASE_STAKE,
        "result_released_pool": result_released_pool,
        "score_released_pool": score_released_pool,
        "payout_total": payout_total,
        "platform_retained": max(0, total_pool - payout_total),
        "payouts": payouts,
        "result_winner_count": len(result_winners),
        "score_winner_count": len(score_winners),
    }


def mark_prediction_settled(prediction_id, actual_result, actual_score, payout_amount, payout_status, payout_error=None):
    init_prediction_db()
    with sqlite3.connect(PREDICTION_DB) as conn:
        conn.execute(
            """
            UPDATE worldcup_predictions
            SET status = 'settled',
                settled_result = ?,
                settled_score = ?,
                settled_at = ?,
                payout_amount = ?,
                payout_status = ?,
                payout_error = ?
            WHERE id = ?
            """,
            (
                actual_result,
                actual_score,
                datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
                int(payout_amount),
                payout_status,
                payout_error,
                prediction_id,
            ),
        )
        conn.commit()


async def transfer_prediction_payout(emos_user_id, amount):
    if amount <= 0:
        return {"success": True, "skipped": True}
    if str(emos_user_id or "").startswith("DEMO-"):
        return {"success": True, "skipped": True, "demo": True}
    if not SERVICE_PROVIDER_TOKEN:
        return {"success": False, "error": "服务商 token 未配置"}
    if not emos_user_id:
        return {"success": False, "error": "缺少用户 emos_user_id"}

    try:
        response = await http_client.post(
            f"{Config.API_BASE_URL}/pay/transfer",
            headers={"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"},
            json={"user_id": emos_user_id, "carrot": int(amount)},
            timeout=15,
        )
    except Exception as exc:
        logger.error(f"预测结算转账异常: {exc}")
        return {"success": False, "error": str(exc)}

    if response.status_code != 200:
        error_text = response.text[:160] if response.text else "未知错误"
        return {"success": False, "error": f"状态码 {response.status_code}: {error_text}"}

    try:
        data = response.json() if response.text else {}
    except Exception:
        data = {}
    if "deduct" in data or data.get("status") == "pass" or data.get("success") is True:
        return {"success": True, "data": data}
    msg = data.get("msg") or data.get("message") or data.get("detail") or response.text[:160] or "转账接口未返回成功标记"
    logger.error("预测结算转账失败: user=%s amount=%s response=%s", emos_user_id, amount, data or response.text)
    return {"success": False, "error": str(msg)}


async def notify_prediction_settlement(bot, prediction, actual_result, actual_score, payout_amount, payout_status):
    hit_result = prediction["result_pick"] == actual_result
    hit_score = prediction["score_pick"] == actual_score
    if hit_score:
        hit_text = "🎯 比分全中"
    elif hit_result:
        hit_text = "✅ 命中胜平负"
    else:
        hit_text = "❌ 未命中"

    if payout_status == "paid":
        payout_text = f"✅ 已到账 {payout_amount} 萝卜"
    elif payout_amount > 0:
        payout_text = f"⏳ 应得 {payout_amount} 萝卜，转账待处理"
    else:
        payout_text = "本场没有奖励"

    text = (
        "🏁 世界杯预测结算单\n"
        "━━━━━━━━━━━━━━\n"
        f"⚽ 比赛：{bold_alnum(prediction['match_label'])}\n"
        f"📌 赛果：{actual_result} {bold_alnum(actual_score)}\n\n"
        f"🎫 你的预测：{prediction['result_pick']} {bold_alnum(prediction['score_pick'])}\n"
        f"🥕 投入：{bold_alnum(prediction['stake'])} 萝卜\n"
        f"🏅 命中：{hit_text}\n"
        f"💰 发奖：{bold_alnum(payout_text)}\n"
        "━━━━━━━━━━━━━━"
    )
    try:
        await bot.send_message(chat_id=prediction["telegram_user_id"], text=text)
    except Exception as exc:
        logger.warning(f"发送预测结算通知失败: {exc}")


async def settle_prediction_match(match_id, bot=None):
    predictions = get_paid_predictions_for_match(match_id)
    if not predictions:
        return {"success": True, "settled": False, "reason": "没有待结算下注"}

    result = await asyncio.to_thread(fetch_fifa_match_result_sync, match_id)
    if not result.get("finished"):
        return {"success": True, "settled": False, "reason": result.get("error") or "比赛未完赛"}

    actual_result = result["result"]
    actual_score = result["score"]
    return await settle_prediction_match_with_result(match_id, actual_result, actual_score, bot=bot, source="fifa")


async def settle_prediction_match_with_result(match_id, actual_result, actual_score, bot=None, admin_id=None, source="manual"):
    predictions = get_paid_predictions_for_match(match_id)
    if not predictions:
        return {"success": True, "settled": False, "reason": "没有待结算下注"}

    payout_plan = calculate_settlement_payouts(predictions, actual_result, actual_score)
    payouts = payout_plan["payouts"]
    paid_count = 0
    failed_count = 0
    failed_payouts = []
    attempted_transfer_count = 0

    for prediction in predictions:
        payout_amount = int(payouts.get(prediction["id"], 0))
        payout_status = "none"
        payout_error = None
        if payout_amount > 0:
            if attempted_transfer_count > 0 and PREDICTION_PAYOUT_TRANSFER_DELAY_SECONDS > 0:
                await asyncio.sleep(PREDICTION_PAYOUT_TRANSFER_DELAY_SECONDS)
            attempted_transfer_count += 1
            transfer = await transfer_prediction_payout(prediction.get("emos_user_id"), payout_amount)
            if transfer["success"]:
                payout_status = "paid"
                paid_count += 1
            else:
                payout_status = "failed"
                payout_error = transfer.get("error", "转账失败")
                failed_count += 1
                failed_payouts.append({
                    "prediction_id": prediction.get("id"),
                    "telegram_user_id": prediction.get("telegram_user_id"),
                    "username": prediction.get("username") or str(prediction.get("telegram_user_id")),
                    "emos_user_id": prediction.get("emos_user_id") or "",
                    "match_label": prediction.get("match_label") or match_id,
                    "result_pick": prediction.get("result_pick") or "",
                    "score_pick": prediction.get("score_pick") or "",
                    "stake": int(prediction.get("stake") or 0),
                    "payout_amount": payout_amount,
                    "platform_order_no": prediction.get("platform_order_no") or prediction.get("order_no") or "",
                    "error": payout_error,
                })

        mark_prediction_settled(
            prediction["id"],
            actual_result,
            actual_score,
            payout_amount,
            payout_status,
            payout_error,
        )
        if bot:
            await notify_prediction_settlement(
                bot,
                prediction,
                actual_result,
                actual_score,
                payout_amount,
                payout_status,
            )

    logger.info(
        "预测比赛结算完成: match_id=%s score=%s total_pool=%s paid=%s failed=%s",
        match_id,
        actual_score,
        payout_plan["total_pool"],
        paid_count,
        failed_count,
    )
    result = {
        "success": failed_count == 0,
        "settled": True,
        "match_id": match_id,
        "actual_result": actual_result,
        "actual_score": actual_score,
        "total_pool": payout_plan["total_pool"],
        "payout_total": payout_plan.get("payout_total", 0),
        "platform_retained": payout_plan.get("platform_retained", 0),
        "paid_count": paid_count,
        "failed_count": failed_count,
        "failed_payouts": failed_payouts,
        "result_winner_count": payout_plan["result_winner_count"],
        "score_winner_count": payout_plan["score_winner_count"],
    }
    update_settlement_request_done(
        match_id,
        admin_id or 0,
        source,
        note=f"{actual_result} {actual_score}",
    )
    return result


def build_settlement_preview(match_id, actual_result, actual_score):
    predictions = get_paid_predictions_for_match(match_id)
    payout_plan = calculate_settlement_payouts(predictions, actual_result, actual_score)
    label = predictions[0]["match_label"] if predictions else match_id
    return {
        "match_id": match_id,
        "match_label": label,
        "actual_result": actual_result,
        "actual_score": actual_score,
        "bets": len(predictions),
        **payout_plan,
    }


def format_settlement_preview(preview, title="🏁 请求结算"):
    return (
        f"{title}\n\n"
        f"比赛：{preview['match_label']}\n"
        f"赛果：{preview['actual_result']} {preview['actual_score']}\n"
        f"下注笔数：{preview['bets']}\n"
        f"用户下注：{preview['total_stake']} 萝卜\n"
        f"总奖池：{preview['total_pool']} 萝卜\n"
        f"本场释放：{preview.get('payout_total', 0)} 萝卜\n"
        f"平台留存：{preview.get('platform_retained', 0)} 萝卜\n"
        f"胜平负中奖票：{preview['result_winner_count']} 张\n"
        f"比分中奖票：{preview['score_winner_count']} 张\n\n"
        "确认后会立即按奖池规则给中奖用户转萝卜，并逐个私聊结算结果。"
    )


async def send_settlement_request_to_admins(bot, match_id, fifa_result, fifa_score):
    preview = build_settlement_preview(match_id, fifa_result, fifa_score)
    if preview["bets"] <= 0:
        return False

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 按 FIFA 结算", callback_data=f"prediction_settle_fifa:{match_id}")],
        [InlineKeyboardButton("✍️ 手动结算", callback_data=f"prediction_settle_manual:{match_id}")],
        [InlineKeyboardButton("⏳ 稍后再说", callback_data=f"prediction_settle_later:{match_id}")],
    ])
    text = format_settlement_preview(preview, title="🏁 FIFA 已出赛果，请确认结算")

    sent = False
    for admin_id in PREDICTION_TICKET_ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, reply_markup=keyboard)
            sent = True
        except Exception as exc:
            logger.warning(f"发送预测结算确认给管理员失败: admin={admin_id} err={exc}")
    return sent


async def request_finished_prediction_settlements(bot=None, force=False):
    candidates = get_settlement_candidate_match_ids()
    results = []
    for item in candidates:
        match_id = item["match_id"]
        existing = get_settlement_request(match_id)
        if existing and existing.get("status") in {"requested", "settled", "manual_pending", "later"} and not force:
            results.append({"requested": False, "match_id": match_id, "reason": f"已有请求：{existing.get('status')}"})
            continue

        if match_id.startswith("demo-"):
            fifa = {"finished": True, "result": "主胜", "score": "2:1"}
        else:
            fifa = await asyncio.to_thread(fetch_fifa_match_result_sync, match_id)
            if not fifa.get("finished"):
                results.append({"requested": False, "match_id": match_id, "reason": fifa.get("error") or "比赛未完赛"})
                continue

        preview = build_settlement_preview(match_id, fifa["result"], fifa["score"])
        sent = False
        if bot:
            sent = await send_settlement_request_to_admins(bot, match_id, fifa["result"], fifa["score"])
        save_settlement_request(
            match_id,
            preview["match_label"],
            fifa["result"],
            fifa["score"],
            status="requested",
            note="已发送管理员确认" if sent else "已生成请求，未发送通知",
        )
        results.append({
            "requested": True,
            "match_id": match_id,
            "match_label": preview["match_label"],
            "actual_result": fifa["result"],
            "actual_score": fifa["score"],
            "sent": sent,
        })
    return results


async def prediction_settlement_task(application):
    while True:
        try:
            await request_finished_prediction_settlements(bot=application.bot)
        except Exception as exc:
            logger.error(f"自动请求预测结算失败: {exc}", exc_info=True)
        await asyncio.sleep(PREDICTION_SETTLEMENT_INTERVAL_SECONDS)


def get_logged_in_user_info(telegram_user_id):
    user_info = user_tokens.get(telegram_user_id)
    if not user_info:
        return None, None
    if isinstance(user_info, dict):
        token = user_info.get("token")
        emos_user_id = user_info.get("user_id")
        if not is_valid_emos_user_id(emos_user_id, telegram_user_id):
            logger.warning(
                "Prediction blocked invalid EMOS user id: tg=%s emos_user_id=%s",
                telegram_user_id,
                emos_user_id,
            )
            return token, None
        return token, emos_user_id
    return user_info, None


def is_valid_emos_user_id(emos_user_id, telegram_user_id=None):
    value = str(emos_user_id or "").strip()
    if not value:
        return False
    if telegram_user_id is not None and value == str(telegram_user_id):
        return False
    return not value.isdigit()


def build_payment_param():
    return f"PRED{uuid.uuid4().hex[:12].upper()}"


async def create_prediction_payment_order(user, pick, emos_user_id):
    if not SERVICE_PROVIDER_TOKEN:
        return {"success": False, "error": "服务商 token 未配置，暂时不能创建下注订单。"}

    order_no = pick.get("order_no") or build_prediction_order_no()
    payment_param = build_payment_param()
    data = {
        "no": order_no,
        "pay_way": "telegram_bot",
        "price": pick["stake"],
        "name": f"预测下注{pick['stake']}萝卜",
        "param": payment_param,
        "callback_telegram_bot_name": Config.BOT_USERNAME,
    }

    try:
        response = await http_client.post(
            f"{Config.API_BASE_URL}/pay/create",
            headers={
                "Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=data,
            timeout=10,
        )
    except Exception as exc:
        logger.error(f"创建预测支付订单异常: {exc}")
        return {"success": False, "error": "创建支付订单失败，请稍后重试。"}

    if response.status_code != 200:
        error_text = response.text[:180] if response.text else "未知错误"
        return {"success": False, "error": f"创建支付订单失败，状态码 {response.status_code}：{error_text}"}

    try:
        result = response.json()
    except Exception as exc:
        logger.error("创建预测支付订单返回非 JSON: %s body=%s", exc, response.text[:300])
        return {"success": False, "error": "创建支付订单失败：服务商返回格式异常。"}

    platform_order_no = result.get("no") or result.get("order_no") or order_no
    pay_url = result.get("pay_url")
    if not pay_url:
        logger.error("创建预测支付订单缺少 pay_url: %s", result)
        return {"success": False, "error": "创建支付订单失败：平台未返回支付链接。"}

    try:
        pick["order_no"] = order_no
        save_prediction(
            user,
            pick,
            status="payment_pending",
            emos_user_id=emos_user_id,
            transfer_status="payment_pending",
            order_no=order_no,
            platform_order_no=platform_order_no,
            payment_param=payment_param,
            pay_url=pay_url,
        )
    except Exception as exc:
        logger.exception("保存预测下注订单失败: %s", exc)
        return {"success": False, "error": "支付订单已创建，但本地保存失败，请联系管理员核对订单。"}

    return {
        "success": True,
        "order_no": order_no,
        "platform_order_no": platform_order_no,
        "payment_param": payment_param,
        "pay_url": pay_url,
    }


async def query_platform_payment(platform_order_no):
    if not SERVICE_PROVIDER_TOKEN:
        return {"success": False, "error": "服务商 token 未配置。"}
    try:
        response = await http_client.get(
            f"{Config.API_BASE_URL}/pay/query?no={platform_order_no}",
            headers={"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"},
            timeout=10,
        )
    except Exception as exc:
        logger.error(f"查询预测支付订单异常: {exc}")
        return {"success": False, "error": "查询支付订单失败，请稍后重试。"}

    if response.status_code != 200:
        return {"success": False, "error": f"查询支付订单失败，状态码 {response.status_code}。"}
    return {"success": True, "data": response.json()}


def is_platform_order_paid(order_info):
    status = str(
        order_info.get("pay_status")
        or order_info.get("status")
        or order_info.get("state")
        or ""
    ).lower()
    return status in {"success", "paid", "payed"} or bool(order_info.get("time_payed"))


def find_ticket_font(bold=False):
    candidates = [
        os.getenv("PREDICTION_TICKET_FONT", ""),
        "C:/Windows/Fonts/msyhbd.ttc" if bold else "",
        "C:/Windows/Fonts/msyh.ttc",
        "C:/Windows/Fonts/simhei.ttf",
        "C:/Windows/Fonts/simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
        "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
        "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        "/usr/share/fonts/opentype/source-han-sans/SourceHanSansCN-Regular.otf",
        "/System/Library/Fonts/PingFang.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for path in candidates:
        if path and os.path.exists(path):
            return path
    return None


def load_ticket_font(size, bold=False):
    font_path = find_ticket_font(bold=bold)
    if font_path:
        try:
            return ImageFont.truetype(font_path, size=size)
        except Exception:
            pass
    return ImageFont.load_default()


def draw_centered(draw, xy, text, font, fill):
    x1, y1, x2, y2 = xy
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    draw.text(
        (x1 + (x2 - x1 - text_width) / 2, y1 + (y2 - y1 - text_height) / 2),
        text,
        font=font,
        fill=fill,
    )


def truncate_text(text, max_chars):
    text = str(text or "")
    return text if len(text) <= max_chars else text[: max_chars - 1] + "…"


def bold_alnum(text):
    text = "" if text is None else str(text)
    output = []
    for char in text:
        code = ord(char)
        if 65 <= code <= 90:
            output.append(chr(0x1D5D4 + code - 65))
        elif 97 <= code <= 122:
            output.append(chr(0x1D5EE + code - 97))
        elif 48 <= code <= 57:
            output.append(chr(0x1D7EC + code - 48))
        else:
            output.append(char)
    return "".join(output)


def text_size(draw, text, font):
    bbox = draw.textbbox((0, 0), str(text), font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def fit_font(text, max_width, start_size, min_size=24, bold=False):
    probe = Image.new("RGB", (10, 10))
    probe_draw = ImageDraw.Draw(probe)
    for size in range(start_size, min_size - 1, -2):
        font = load_ticket_font(size, bold=bold)
        if text_size(probe_draw, text, font)[0] <= max_width:
            return font
    return load_ticket_font(min_size, bold=bold)


def draw_text_center(draw, box, text, font, fill):
    x1, y1, x2, y2 = box
    width, height = text_size(draw, text, font)
    draw.text(
        (x1 + (x2 - x1 - width) / 2, y1 + (y2 - y1 - height) / 2),
        str(text),
        font=font,
        fill=fill,
    )


def draw_text_right(draw, x, y, text, font, fill):
    width, _ = text_size(draw, text, font)
    draw.text((x - width, y), str(text), font=font, fill=fill)


def draw_label_value(draw, x, y, label, value, label_font, value_font, max_width):
    draw.text((x, y), str(label), font=label_font, fill="#64748b")
    value_font = fit_font(str(value), max_width, getattr(value_font, "size", 38), 26, bold=True)
    draw.text((x, y + 42), str(value), font=value_font, fill="#0f172a")


def is_ticket_card_admin(user_id):
    return bool(PREDICTION_TICKET_ADMIN_IDS) and int(user_id) in PREDICTION_TICKET_ADMIN_IDS


def load_uploaded_ticket_cards():
    if not PREDICTION_TICKET_CARD_MANIFEST.exists():
        return []

    try:
        cards = json.loads(PREDICTION_TICKET_CARD_MANIFEST.read_text(encoding="utf-8"))
    except Exception as exc:
        logger.warning(f"读取自定义票根背景图库失败: {exc}")
        return []

    valid_cards = []
    for card in cards:
        local_path = Path(card.get("local_path", ""))
        if not local_path.is_absolute():
            local_path = PREDICTION_TICKET_UPLOAD_DIR / local_path
        if local_path.exists():
            item = dict(card)
            item["local_path"] = str(local_path)
            valid_cards.append(item)
    return valid_cards


def save_uploaded_ticket_cards(cards):
    PREDICTION_TICKET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    serializable = []
    for card in cards:
        item = dict(card)
        local_path = Path(item.get("local_path", ""))
        try:
            item["local_path"] = local_path.name
        except Exception:
            pass
        serializable.append(item)
    PREDICTION_TICKET_CARD_MANIFEST.write_text(
        json.dumps(serializable, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_ticket_cards():
    uploaded_cards = load_uploaded_ticket_cards()
    if uploaded_cards:
        return uploaded_cards
    return PREDICTION_TICKET_CARDS


def select_ticket_card(prediction):
    cards = get_ticket_cards()
    seed = (
        prediction.get("platform_order_no")
        or prediction.get("order_no")
        or prediction.get("payment_param")
        or prediction.get("match_id")
        or uuid.uuid4().hex
    )
    index = int(hashlib.sha256(str(seed).encode("utf-8")).hexdigest(), 16) % len(cards)
    card = dict(cards[index])
    card["number"] = f"{index + 1:02d}/{len(cards):02d}"
    return card


def get_ticket_background_cache(card):
    safe_code = re.sub(r"[^A-Za-z0-9_.-]", "_", card["code"])
    return PREDICTION_TICKET_DIR / f"ticket_card_{safe_code}.jpg"


def get_ticket_card_url(card):
    if card.get("local_path"):
        return None
    if card.get("url"):
        return card["url"]
    file_name = card.get("file")
    if not file_name:
        return PREDICTION_TICKET_BG_URL
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quote(file_name)}?width=1400"


def load_ticket_background(width, height, card):
    local_path = card.get("local_path")
    if local_path:
        try:
            with Image.open(local_path) as raw:
                background = raw.convert("RGB")
                resample = getattr(Image, "Resampling", Image).LANCZOS
                return ImageOps.fit(background, (width, height), method=resample)
        except Exception as exc:
            logger.warning(f"读取本地票根背景失败: {exc}")
            return None

    image_url = get_ticket_card_url(card)
    if not image_url:
        return None

    PREDICTION_TICKET_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = get_ticket_background_cache(card)
    try:
        if not cache_path.exists():
            last_error = None
            for _ in range(3):
                try:
                    response = requests.get(
                        image_url,
                        headers={
                            "User-Agent": "emos-magic-bot/1.0 prediction-ticket",
                        },
                        timeout=20,
                    )
                    response.raise_for_status()
                    cache_path.write_bytes(response.content)
                    break
                except Exception as exc:
                    last_error = exc
            else:
                raise last_error

        with Image.open(cache_path) as raw:
            background = raw.convert("RGB")
            resample = getattr(Image, "Resampling", Image).LANCZOS
            return ImageOps.fit(background, (width, height), method=resample)
    except Exception as exc:
        logger.warning(f"加载预测票根背景失败，使用默认背景: {exc}")
        try:
            if cache_path.exists():
                cache_path.unlink()
        except Exception:
            pass
        return None


def create_prediction_ticket_image(prediction):
    PREDICTION_TICKET_DIR.mkdir(parents=True, exist_ok=True)
    width, height = 1080, 1500
    card = select_ticket_card(prediction)
    background = load_ticket_background(width, height, card)
    if background:
        image = background.convert("RGBA")
    else:
        image = Image.new("RGBA", (width, height), "#102a43")

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    overlay_draw = ImageDraw.Draw(overlay)
    for y in range(height):
        if y < 260:
            alpha = int(96 * (1 - y / 260))
        elif y > 650:
            alpha = min(202, int((y - 650) / 850 * 230))
        else:
            alpha = 24
        overlay_draw.line((0, y, width, y), fill=(2, 6, 23, alpha))
    image = Image.alpha_composite(image, overlay)
    draw = ImageDraw.Draw(image)

    title_font = load_ticket_font(52, bold=True)
    sub_font = load_ticket_font(28)
    meta_font = load_ticket_font(25)
    match_font = fit_font(truncate_text(prediction.get("match_label"), 30), 820, 46, 30, bold=True)
    label_font = load_ticket_font(27)
    value_font = load_ticket_font(36, bold=True)
    pick_font = load_ticket_font(50, bold=True)
    tiny_font = load_ticket_font(22)

    paid_at = prediction.get("paid_at") or datetime.now(BEIJING_TZ).isoformat(timespec="seconds")
    try:
        paid_text = datetime.fromisoformat(str(paid_at).replace(" ", "T")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        paid_text = str(paid_at)[:16]

    draw.rounded_rectangle((48, 44, width - 48, height - 44), radius=42, outline=(134, 239, 172, 218), width=3)

    info_top = 700
    draw.rounded_rectangle(
        (66, info_top, width - 66, height - 70),
        radius=34,
        fill=(15, 23, 42, 226),
        outline=(255, 255, 255, 110),
        width=1,
    )
    draw.text((106, info_top + 28), "萝卜预测票根", font=title_font, fill="#ffffff")
    draw.text((110, info_top + 84), "World Cup Prediction", font=sub_font, fill="#dcfce7")
    draw_text_right(draw, width - 106, info_top + 36, paid_text, meta_font, "#f8fafc")
    draw_text_right(draw, width - 106, info_top + 76, f"背景 {card['number']} · {truncate_text(card.get('name', '自定义背景'), 10)}", meta_font, "#bbf7d0")

    draw.text((106, info_top + 128), "本场比赛", font=label_font, fill="#86efac")
    match = truncate_text(prediction.get("match_label"), 30)
    draw_text_center(draw, (104, info_top + 166, width - 104, info_top + 230), match, match_font, "#ffffff")

    result = prediction.get("result_pick", "-")
    score = prediction.get("score_pick", "-")
    stake = prediction.get("stake", 0)

    draw.rounded_rectangle((106, info_top + 254, width - 106, info_top + 408), radius=28, fill=(4, 120, 87, 236))
    draw.text((146, info_top + 284), "你的选择", font=label_font, fill="#bbf7d0")
    draw.text((146, info_top + 326), str(result), font=pick_font, fill="#ffffff")
    draw_text_right(draw, width - 146, info_top + 284, "预测比分", label_font, "#bbf7d0")
    score_font = fit_font(str(score), 300, 72, 42, bold=True)
    draw_text_right(draw, width - 146, info_top + 318, str(score), score_font, "#ffffff")

    cards = [
        ("下注萝卜", f"{stake} 萝卜"),
        ("f1bb补贴", f"{PLATFORM_SUBSIDY} 萝卜"),
        ("平台订单", truncate_text(prediction.get("platform_order_no"), 26)),
        ("本地订单", truncate_text(prediction.get("order_no"), 26)),
    ]
    card_positions = [
        (106, info_top + 408, 520, info_top + 530),
        (560, info_top + 408, width - 106, info_top + 530),
        (106, info_top + 558, 520, info_top + 680),
        (560, info_top + 558, width - 106, info_top + 680),
    ]
    for (label, value), (x1, y1, x2, y2) in zip(cards, card_positions):
        draw.rounded_rectangle((x1, y1, x2, y2), radius=22, fill=(248, 250, 252, 238))
        draw_label_value(draw, x1 + 30, y1 + 22, label, value, label_font, value_font, x2 - x1 - 60)

    draw_text_right(draw, width - 106, height - 98, "EMOS MAGIC BOX", tiny_font, "#94a3b8")

    file_name = f"{prediction.get('platform_order_no') or prediction.get('order_no')}.png"
    path = PREDICTION_TICKET_DIR / re.sub(r"[^A-Za-z0-9_.-]", "_", file_name)
    image.convert("RGB").save(path, "PNG")
    return path


async def send_prediction_ticket(bot, chat_id, prediction):
    try:
        card = select_ticket_card(prediction)
        ticket_path = create_prediction_ticket_image(prediction)
        with open(ticket_path, "rb") as photo:
            await bot.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=f"🎫 预测票根已生成\n背景：{card['number']} {card.get('name', '自定义背景')}",
            )
    except Exception as exc:
        logger.error(f"发送预测票根失败: {exc}")


async def activate_paid_prediction(platform_order_no, param=None, telegram_user_id=None):
    prediction = get_prediction_by_platform_order(platform_order_no)
    if not prediction:
        return {"success": False, "error": "没有找到对应的预测订单。"}

    if telegram_user_id and int(prediction["telegram_user_id"]) != int(telegram_user_id):
        return {"success": False, "error": "这个支付订单不属于当前 Telegram 用户。"}

    stored_param = prediction.get("payment_param")
    if param is not None and stored_param and param != stored_param:
        return {"success": False, "error": "支付参数不匹配，订单校验失败。"}

    if prediction.get("status") == "pending" and prediction.get("stake_transfer_status") == "paid":
        return {"success": True, "already_paid": True, "prediction": prediction}

    payment = await query_platform_payment(platform_order_no)
    if not payment["success"]:
        return payment

    order_info = payment["data"]
    if not is_platform_order_paid(order_info):
        status = order_info.get("pay_status") or order_info.get("status") or "未支付"
        return {"success": False, "error": f"订单还没有支付成功，当前状态：{status}"}

    paid_at = order_info.get("time_payed") or datetime.now(BEIJING_TZ).isoformat(timespec="seconds")
    update_prediction_payment(platform_order_no, "pending", "paid", paid_at)
    prediction = get_prediction_by_platform_order(platform_order_no)
    return {"success": True, "already_paid": False, "prediction": prediction}


async def show_payment_check_result(query, context, platform_order_no):
    loading = await query.edit_message_text("🔄 正在查询支付状态...")
    result = await activate_paid_prediction(platform_order_no, telegram_user_id=query.from_user.id)
    if not result["success"]:
        await loading.edit_text(
            f"❌ 支付未确认\n\n{result['error']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("📋 我的预测", callback_data="prediction_mine")],
                [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
            ]),
        )
        return

    item = result["prediction"]
    await send_prediction_ticket(context.bot, query.message.chat_id, item)
    await loading.edit_text(
        "✅ 支付成功，下注已进入奖池\n\n"
        f"平台订单：{item['platform_order_no']}\n"
        f"本地订单：{item['order_no']}\n"
        f"比赛：{item['match_label']}\n"
        f"选择：{item['result_pick']} {item['score_pick']}\n"
        f"投入：{item['stake']} 萝卜",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 查看奖池", callback_data=f"prediction_pool:{item['match_id']}")],
            [InlineKeyboardButton("📋 我的预测", callback_data="prediction_mine")],
        ]),
    )


async def handle_prediction_payment_start(update, context, platform_order_no, param, tg_id, agreed=True):
    if not agreed:
        update_prediction_payment(platform_order_no, "cancelled", "cancelled")
        await update.message.reply_text(
            f"⚠️ 支付已取消\n平台订单：`{platform_order_no}`",
            parse_mode="Markdown",
        )
        return True

    loading = await update.message.reply_text("🔄 正在核实预测下注订单...")
    result = await activate_paid_prediction(platform_order_no, param=param, telegram_user_id=tg_id)
    if not result["success"]:
        await loading.edit_text(f"❌ 预测下注订单未确认\n\n{result['error']}")
        return True

    item = result["prediction"]
    await send_prediction_ticket(context.bot, update.effective_chat.id, item)
    await loading.edit_text(
        "✅ 预测下注支付成功\n\n"
        f"平台订单：`{platform_order_no}`\n"
        f"本地订单：`{item['order_no']}`\n"
        f"比赛：{item['match_label']}\n"
        f"选择：{item['result_pick']} {item['score_pick']}\n"
        f"投入：{item['stake']} 萝卜\n\n"
        "这笔下注已进入奖池。",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 查看奖池", callback_data=f"prediction_pool:{item['match_id']}")],
            [InlineKeyboardButton("📋 我的预测", callback_data="prediction_mine")],
        ]),
    )
    return True


def parse_match_datetime(match):
    raw_time = match.get("time", "")
    parsed = re.match(r"^(\d{2}):(\d{2}) UTC([+-]\d+)$", raw_time)
    if not parsed:
        return None

    hour, minute, offset = parsed.groups()
    local_tz = timezone(timedelta(hours=int(offset)))
    local_dt = datetime.fromisoformat(match["date"]).replace(
        hour=int(hour),
        minute=int(minute),
        tzinfo=local_tz,
    )
    return local_dt.astimezone(BEIJING_TZ)


def parse_fifa_datetime(match):
    raw_date = match.get("Date") or match.get("LocalDate")
    if not raw_date:
        return None
    try:
        return datetime.fromisoformat(raw_date.replace("Z", "+00:00")).astimezone(BEIJING_TZ)
    except Exception:
        return None


def localized_description(items, fallback=""):
    if not items:
        return fallback
    for item in items:
        if item.get("Locale") in ("zh-CN", "zh", "en-GB", "en"):
            return item.get("Description") or fallback
    return items[0].get("Description") or fallback


def fifa_team_name(team):
    if not team:
        return "待定"
    return (
        localized_description(team.get("TeamName"), "")
        or team.get("ShortClubName")
        or team.get("Abbreviation")
        or "待定"
    )


def team_name(name):
    return TEAM_NAMES.get(name, name)


def match_label(match):
    return f"{team_name(match['team1'])} vs {team_name(match['team2'])}"


def prediction_deadline(match):
    if match.get("is_custom"):
        return match["prediction_deadline"]
    return match["beijing_time"] - timedelta(minutes=10)


def build_match_id(index, match):
    return f"wc2026-{index + 1}"


def build_fifa_matches_url():
    params = (
        f"language=zh&count=200&idCompetition={FIFA_COMPETITION_ID}"
        f"&idSeason={FIFA_SEASON_ID}&from=2026-01-01&to=2026-12-31"
    )
    return f"{FIFA_MATCHES_URL}?{params}"


def normalize_fifa_match(match):
    beijing_time = parse_fifa_datetime(match)
    if not beijing_time:
        return None

    home = match.get("Home") or {}
    away = match.get("Away") or {}
    home_name = fifa_team_name(home)
    away_name = fifa_team_name(away)
    home_score = match.get("HomeTeamScore", home.get("Score"))
    away_score = match.get("AwayTeamScore", away.get("Score"))
    match_status = match.get("MatchStatus")
    is_finished = match_status == 0 and home_score is not None and away_score is not None

    return {
        "id": f"fifa-{match.get('IdMatch')}",
        "fifa_match_id": str(match.get("IdMatch")),
        "team1": home_name,
        "team2": away_name,
        "round": localized_description(match.get("StageName"), ""),
        "group": localized_description(match.get("GroupName"), ""),
        "ground": localized_description(match.get("Stadium", {}).get("Name") if match.get("Stadium") else [], "")
        or match.get("VenueName")
        or "",
        "beijing_time": beijing_time,
        "source": "fifa",
        "match_status": match_status,
        "home_score": home_score,
        "away_score": away_score,
        "is_finished": is_finished,
        "raw": match,
    }


def fetch_fifa_schedule_sync():
    response = requests.get(
        build_fifa_matches_url(),
        headers={"User-Agent": "Mozilla/5.0 emos-magic-bot/1.0"},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    matches = []
    for match in payload.get("Results", []):
        normalized = normalize_fifa_match(match)
        if normalized:
            matches.append(normalized)
    matches.sort(key=lambda item: item["beijing_time"])
    return matches


def fetch_openfootball_schedule_sync():
    with urlopen(SCHEDULE_URL, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))

    matches = []
    for index, match in enumerate(payload.get("matches", [])):
        if not match.get("date") or not match.get("time"):
            continue
        beijing_time = parse_match_datetime(match)
        if not beijing_time:
            continue
        enriched = dict(match)
        enriched["id"] = build_match_id(index, match)
        enriched["beijing_time"] = beijing_time
        enriched["source"] = "openfootball"
        matches.append(enriched)

    matches.sort(key=lambda item: item["beijing_time"])
    return matches


def fetch_schedule_sync():
    try:
        matches = fetch_fifa_schedule_sync()
        if matches:
            return matches
    except Exception as exc:
        logger.warning(f"获取 FIFA 赛程失败，回退 OpenFootball: {exc}")
    return fetch_openfootball_schedule_sync()


def fetch_fifa_match_result_sync(match_id):
    fifa_match_id = str(match_id).replace("fifa-", "")
    matches = fetch_fifa_schedule_sync()
    for match in matches:
        if match.get("fifa_match_id") == fifa_match_id or match.get("id") == match_id:
            if not match.get("is_finished"):
                return {"finished": False, "match": match}
            home_score = int(match["home_score"])
            away_score = int(match["away_score"])
            result = "主胜" if home_score > away_score else "客胜" if away_score > home_score else "平"
            return {
                "finished": True,
                "match": match,
                "home_score": home_score,
                "away_score": away_score,
                "score": f"{home_score}:{away_score}",
                "result": result,
            }
    return {"finished": False, "error": "FIFA 暂时没有找到这场比赛"}


async def get_schedule(force=False):
    now = datetime.now(BEIJING_TZ)
    loaded_at = _schedule_cache["loaded_at"]
    if (
        not force
        and loaded_at
        and (now - loaded_at).total_seconds() < SCHEDULE_TTL_SECONDS
        and _schedule_cache["matches"]
    ):
        return _schedule_cache["matches"]

    matches = await asyncio.to_thread(fetch_schedule_sync)
    _schedule_cache["loaded_at"] = now
    _schedule_cache["matches"] = matches
    return matches


async def get_match(match_id):
    if match_id.startswith(("custom-", "demo-")):
        for match in get_open_custom_matches():
            if match["id"] == match_id:
                return match
        return None

    for match in await get_schedule():
        if match["id"] == match_id:
            return match
    return None


async def get_today_matches():
    now = datetime.now(BEIJING_TZ)
    upcoming = [
        match
        for match in await get_schedule()
        if prediction_deadline(match) > now
    ]
    return sorted(upcoming + get_open_custom_matches(), key=prediction_deadline)[:8]


def build_prediction_keyboard(user_id=None):
    rows = [
        [
            InlineKeyboardButton("📅 可预测比赛", callback_data="prediction_today"),
            InlineKeyboardButton("🥕 我要预测", callback_data="prediction_today"),
        ],
        [
            InlineKeyboardButton("📋 我的预测", callback_data="prediction_mine"),
            InlineKeyboardButton("📖 奖池规则", callback_data="prediction_rules"),
        ],
        [
            InlineKeyboardButton("🏆 发奖历史", callback_data="prediction_payout_history"),
        ],
    ]
    if user_id and is_ticket_card_admin(user_id):
        rows.append([
            InlineKeyboardButton("🖼 上传背景图", callback_data="prediction_upload_bg"),
            InlineKeyboardButton("🖼 图库数量", callback_data="prediction_card_pool"),
        ])
        rows.append([
            InlineKeyboardButton("🏁 检查结算", callback_data="prediction_settle_scan"),
            InlineKeyboardButton("🧪 5分钟模拟结算", callback_data="prediction_demo_settle"),
        ])
    rows.append(
        [
            InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main"),
        ],
    )
    return InlineKeyboardMarkup(rows)


def format_match_line(match, index=None):
    prefix = f"{index}. " if index is not None else ""
    time_text = match["beijing_time"].strftime("%m-%d %H:%M")
    return (
        f"{prefix}{match_label(match)}\n"
        f"   北京时间 {time_text} | {match.get('group', '')} | {match.get('ground', '')}"
    )


async def send_prediction_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = (
        "⚽ 世界杯预测\n\n"
        "先选比赛，再点胜平负、比分和萝卜数，最后确认提交。\n"
        "玩法采用奖池制，f1bb只补贴固定奖池，不承诺固定高倍率赔付。"
    )
    reply_markup = build_prediction_keyboard(update.effective_user.id if update.effective_user else None)

    if update.callback_query:
        await update.callback_query.edit_message_text(message, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message, reply_markup=reply_markup)


async def ask_ticket_background_upload(query, context):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text(
            "这个入口只有管理员能用。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
        )
        return

    context.user_data["prediction_waiting_input"] = "ticket_background"
    await query.edit_message_text(
        "请直接发送一张票根背景图。\n\n"
        "建议用 Telegram 的“文件”方式发送原图，最清晰；普通照片也可以，但会被 Telegram 压缩。\n"
        "配文可选：图片备注\n"
        "例如：世界杯海报、梅西背景、球场夜景",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
    )


async def show_ticket_card_pool(query):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text(
            "这个入口只有管理员能用。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
        )
        return

    uploaded_cards = load_uploaded_ticket_cards()
    if uploaded_cards:
        lines = [
            f"🖼 当前自定义背景图库：{len(uploaded_cards)} 张",
            "",
        ]
        for index, card in enumerate(uploaded_cards[-12:], start=max(1, len(uploaded_cards) - 11)):
            lines.append(f"{index}. {card.get('name')}")
        lines.append("")
        lines.append("有自定义背景时，票根会优先只从这些图片里随机。")
    else:
        lines = [
            "🖼 当前还没有自定义票根背景。",
            "",
            "没有上传图时，会临时使用内置网络背景。",
        ]

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼 上传新背景", callback_data="prediction_upload_bg")],
            [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
        ]),
    )


async def run_settlement_scan(query, context):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text(
            "这个入口只有管理员能用。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
        )
        return

    loading = await query.edit_message_text("🏁 正在从 FIFA 检查已完赛比赛，并请求管理员确认...")
    results = await request_finished_prediction_settlements(bot=context.bot, force=True)
    requested = [item for item in results if item.get("requested")]
    waiting = [item for item in results if not item.get("requested")]

    if not results:
        text = "🏁 当前没有待结算的已支付预测。"
    else:
        lines = [
            "🏁 结算请求检查完成",
            "",
            f"已请求确认：{len(requested)} 场",
            f"未完赛/跳过：{len(waiting)} 场",
        ]
        for item in requested[:6]:
            lines.append(
                f"• {item['match_id']} {item['actual_result']} {item['actual_score']} "
                f"通知管理员：{'成功' if item.get('sent') else '失败'}"
            )
        for item in waiting[:4]:
            lines.append(f"• 跳过：{item.get('reason', '未完赛')}")
        text = "\n".join(lines)

    await loading.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
    )


def result_from_score_text(score_text):
    parsed = parse_score(score_text)
    if not parsed:
        return None
    home, away, normalized = parsed
    if home > away:
        return "主胜", normalized
    if away > home:
        return "客胜", normalized
    return "平", normalized


async def confirm_fifa_settlement(query, context, match_id):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text("这个入口只有管理员能用。")
        return

    request = get_settlement_request(match_id)
    if not request:
        await query.edit_message_text("这场比赛还没有结算请求，请先点“检查结算”。")
        return
    if request.get("status") == "settled":
        await query.edit_message_text("这场比赛已经结算过了。")
        return

    actual_result = request.get("fifa_result")
    actual_score = request.get("fifa_score")
    loading = await query.edit_message_text("🏁 正在按 FIFA 赛果结算并转账...")
    result = await settle_prediction_match_with_result(
        match_id,
        actual_result,
        actual_score,
        bot=context.bot,
        admin_id=query.from_user.id,
        source="fifa_confirm",
    )
    await loading.edit_text(
        format_settlement_result_text(result),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
    )


def format_settlement_result_text(result):
    if not result.get("settled"):
        return f"🏁 没有结算：{result.get('reason', '未知原因')}"
    lines = [
        "🏁 结算完成",
        "",
        f"比赛：{bold_alnum(result['match_id'])}",
        f"赛果：{result['actual_result']} {bold_alnum(result['actual_score'])}",
        f"总奖池：{bold_alnum(result['total_pool'])} 萝卜",
        f"本场应发：{bold_alnum(result.get('payout_total', 0))} 萝卜",
        f"平台留存：{bold_alnum(result.get('platform_retained', 0))} 萝卜",
        f"胜平负中奖票：{bold_alnum(result['result_winner_count'])} 张",
        f"比分中奖票：{bold_alnum(result['score_winner_count'])} 张",
        f"转账成功：{bold_alnum(result['paid_count'])} 笔",
        f"转账失败：{bold_alnum(result['failed_count'])} 笔",
    ]
    failed_payouts = result.get("failed_payouts") or []
    if failed_payouts:
        lines.extend(["", "⚠️ 手动补发清单："])
        for item in failed_payouts[:10]:
            lines.append(
                "------------------\n"
                f"用户：{bold_alnum(item.get('username') or '-')}\n"
                f"EMOS：{bold_alnum(item.get('emos_user_id') or '-')}\n"
                f"应发：{bold_alnum(item.get('payout_amount') or 0)} 萝卜\n"
                f"预测：{item.get('result_pick') or '-'} {bold_alnum(item.get('score_pick') or '-')}\n"
                f"投入：{bold_alnum(item.get('stake') or 0)} 萝卜\n"
                f"订单：{bold_alnum(item.get('platform_order_no') or '-')}\n"
                f"原因：{bold_alnum(str(item.get('error') or '接口异常')[:80])}"
            )
        if len(failed_payouts) > 10:
            lines.append(f"还有 {bold_alnum(len(failed_payouts) - 10)} 条失败记录，请进发奖历史查看。")
    return "\n".join(lines)


async def ask_manual_settlement_score(query, context, match_id):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text("这个入口只有管理员能用。")
        return

    predictions = get_paid_predictions_for_match(match_id)
    match_label_text = predictions[0]["match_label"] if predictions else match_id
    save_settlement_request(
        match_id,
        match_label_text,
        "",
        "",
        status="manual_pending",
        note="等待管理员手动输入比分",
    )
    context.user_data["prediction_waiting_input"] = "settlement_manual"
    context.user_data["prediction_manual_settlement_match_id"] = match_id
    await query.edit_message_text(
        "✍️ 请输入这场比赛的最终比分，例如：2:1\n\n"
        "输入后会先给你预览，点确认才会真正结算转账。",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
    )


async def confirm_manual_settlement(query, context, match_id, score_text):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text("这个入口只有管理员能用。")
        return

    parsed = result_from_score_text(score_text)
    if not parsed:
        await query.edit_message_text("比分格式不对，请重新走手动结算。")
        return
    actual_result, actual_score = parsed
    loading = await query.edit_message_text("🏁 正在按手动比分结算并转账...")
    result = await settle_prediction_match_with_result(
        match_id,
        actual_result,
        actual_score,
        bot=context.bot,
        admin_id=query.from_user.id,
        source="manual_confirm",
    )
    await loading.edit_text(
        format_settlement_result_text(result),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
    )


async def send_demo_settlement_after_delay(bot, admin_id):
    await asyncio.sleep(300)
    text = (
        "🧪 模拟比赛结算确认\n\n"
        "比赛：蓝方 vs 红方\n"
        "FIFA 模拟赛果：主胜 2:1\n"
        "下注笔数：5\n"
        "用户下注：1500 萝卜\n"
        "总奖池：2000 萝卜\n"
        "胜平负中奖票：3 张\n"
        "比分中奖票：2 张\n\n"
        "这是演示流程，点按钮不会真实转账。"
    )
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("✅ 模拟结算", callback_data="prediction_demo_confirm")],
        [InlineKeyboardButton("✍️ 模拟手动结算", callback_data="prediction_demo_manual")],
    ])
    await bot.send_message(chat_id=admin_id, text=text, reply_markup=keyboard)


async def start_demo_settlement(query, context):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text("这个入口只有管理员能用。")
        return

    settlement_time = datetime.now(BEIJING_TZ) + timedelta(minutes=5)
    match_id = save_demo_match("蓝方", "红方", settlement_time, creator_user_id=query.from_user.id)
    await query.edit_message_text(
        "🧪 已创建 5 分钟模拟比赛\n\n"
        f"比赛：蓝方 vs 红方\n"
        f"结算时间：{settlement_time.strftime('%H:%M:%S')}\n"
        f"模拟赛果：主胜 2:1\n\n"
        "现在可以用多个账号进“可预测比赛”下注。到点后会请求管理员确认，不会真实转账。",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📅 去下注", callback_data="prediction_today")],
            [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
        ]),
    )


async def confirm_demo_settlement(query):
    await query.edit_message_text(
        "🧪 模拟结算完成\n\n"
        "赛果：主胜 2:1\n"
        "总奖池：2000 萝卜\n"
        "A：433 萝卜\n"
        "B：266 萝卜\n"
        "C：1300 萝卜\n\n"
        "这是演示结果，没有真实转账。",
    )


async def ask_demo_manual_score(query, context):
    context.user_data["prediction_waiting_input"] = "demo_manual_settlement"
    await query.edit_message_text("🧪 请输入模拟手动比分，例如：3:2。")


def parse_ticket_card_caption(caption, next_index):
    caption = (caption or "").strip()
    if caption:
        parts = [part.strip() for part in re.split(r"[|｜\n]", caption) if part.strip()]
        name = parts[0] if parts else f"背景图{next_index:02d}"
        code = parts[1] if len(parts) > 1 else f"UP-{next_index:02d}"
    else:
        name = f"背景图{next_index:02d}"
        code = f"UP-{next_index:02d}"

    code = re.sub(r"[^A-Za-z0-9_.-]", "-", code.upper())[:24] or f"UP-{next_index:02d}"
    return truncate_text(name, 16), code


async def download_telegram_file_with_retry(bot, file_id, save_path):
    last_error = None
    for attempt in range(3):
        try:
            telegram_file = await bot.get_file(file_id)
            await telegram_file.download_to_drive(custom_path=str(save_path))
            return
        except Exception as exc:
            last_error = exc
            if attempt < 2:
                await asyncio.sleep(1.5 * (attempt + 1))
    raise last_error


async def handle_prediction_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("prediction_waiting_input") != "ticket_background":
        return False

    user = update.effective_user
    if not user or not is_ticket_card_admin(user.id):
        context.user_data.pop("prediction_waiting_input", None)
        await update.message.reply_text("这个入口只有管理员能用。")
        return True

    message = update.message
    document = message.document
    photo = message.photo[-1] if message.photo else None
    if document and not (document.mime_type or "").startswith("image/"):
        await message.reply_text("请发送图片文件，不要发其他类型文件。")
        return True
    if not document and not photo:
        await message.reply_text("请发送图片，或者用文件方式发送原图。")
        return True

    uploaded_cards = load_uploaded_ticket_cards()
    next_index = len(uploaded_cards) + 1
    name, code = parse_ticket_card_caption(message.caption, next_index)
    file_id = document.file_id if document else photo.file_id
    original_name = document.file_name if document and document.file_name else f"{code}.jpg"
    extension = Path(original_name).suffix.lower()
    if extension not in {".jpg", ".jpeg", ".png", ".webp"}:
        extension = ".jpg"

    PREDICTION_TICKET_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_code = re.sub(r"[^A-Za-z0-9_.-]", "_", code)
    save_path = PREDICTION_TICKET_UPLOAD_DIR / f"{datetime.now(BEIJING_TZ).strftime('%Y%m%d%H%M%S')}_{safe_code}{extension}"

    try:
        await download_telegram_file_with_retry(context.bot, file_id, save_path)
        with Image.open(save_path) as image:
            width, height = image.size
            image.verify()
    except Exception as exc:
        logger.error(f"保存票根背景失败: {exc}")
        try:
            if save_path.exists():
                save_path.unlink()
        except Exception:
            pass
        await message.reply_text("图片下载失败，多半是 Telegram 网络抖了。你不用重新点按钮，直接再发一次图就行。")
        return True

    uploaded_cards.append({
        "name": name,
        "code": code,
        "local_path": str(save_path),
        "uploaded_by": user.id,
        "created_at": datetime.now(BEIJING_TZ).isoformat(timespec="seconds"),
        "width": width,
        "height": height,
    })
    save_uploaded_ticket_cards(uploaded_cards)
    context.user_data.pop("prediction_waiting_input", None)

    quality_tip = ""
    if width < 1080 or height < 1400:
        quality_tip = "\n\n提示：这张图尺寸偏小，建议上传 1080x1500 或更大的竖图。"

    await message.reply_text(
        f"✅ 已加入票根背景图库\n\n"
        f"备注：{name}\n"
        f"尺寸：{width}x{height}\n"
        f"当前背景图库：{len(uploaded_cards)} 张\n\n"
        "之后用户下注生成票根时，会随机抽这些自定义图片当背景。"
        f"{quality_tip}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🖼 查看图库", callback_data="prediction_card_pool")],
            [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
        ]),
    )
    return True


async def show_today_matches(query):
    try:
        matches = await get_today_matches()
    except Exception as exc:
        logger.error(f"获取世界杯赛程失败: {exc}")
        keyboard = [[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]
        await query.edit_message_text(
            "📅 今日比赛\n\n赛程暂时拉取失败，请稍后再试。",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    if not matches:
        keyboard = [[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]
        await query.edit_message_text(
            "📅 可预测比赛\n\n暂时没有可预测的世界杯比赛。",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    lines = [format_match_line(match, i + 1) for i, match in enumerate(matches)]
    keyboard = [
        [InlineKeyboardButton(match_label(match), callback_data=f"prediction_match:{match['id']}")]
        for match in matches
    ]
    keyboard.append([InlineKeyboardButton("🔄 刷新赛程", callback_data="prediction_refresh")])
    keyboard.append([InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")])
    await query.edit_message_text(
        "📅 可预测比赛\n\n"
        "已自动跳过开赛前 10 分钟内和已经开赛的比赛。\n\n"
        + "\n\n".join(lines)
        + "\n\n请选择一场比赛：",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_result_options(query, context, match_id):
    if is_match_settled(match_id):
        await query.edit_message_text(
            "🏁 这场比赛已经结算，不能再下注。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回比赛列表", callback_data="prediction_today")]]),
        )
        return

    match = await get_match(match_id)
    if not match:
        await query.edit_message_text(
            "这场比赛暂时找不到了，请刷新赛程。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 刷新赛程", callback_data="prediction_today")]]),
        )
        return

    context.user_data["prediction_pick"] = {"match": match}
    stats = get_match_pool_stats(match_id)
    deadline = prediction_deadline(match).strftime("%m-%d %H:%M")
    detail_text = (
        f"🏟️ {match_label(match)}\n"
        f"开赛/截止：{match['beijing_time'].strftime('%m-%d %H:%M')} / {deadline}\n\n"
        "下注说明：\n"
        "• 单注范围：1 萝卜起，不设上限\n"
        f"• 当前总下注：{stats['total_stake']} 萝卜\n"
        f"• f1bb补贴：{stats['platform_subsidy']} 萝卜\n"
        f"• 当前总奖池：{stats['total_pool']} 萝卜\n"
        "• 胜平负命中分 40%，比分命中分 60%\n\n"
        "请选择你要预测的胜平负："
    )
    keyboard = [
        [
            InlineKeyboardButton("主胜", callback_data="prediction_result:主胜"),
            InlineKeyboardButton("平", callback_data="prediction_result:平"),
            InlineKeyboardButton("客胜", callback_data="prediction_result:客胜"),
        ],
        [InlineKeyboardButton("🔄 刷新实时下注", callback_data=f"prediction_match:{match_id}")],
        [InlineKeyboardButton("📊 奖池比例", callback_data=f"prediction_pool:{match_id}")],
    ]
    if is_ticket_card_admin(query.from_user.id):
        keyboard.append([InlineKeyboardButton("🥕 管理本场补贴", callback_data=f"prediction_subsidy:{match_id}")])
        keyboard.append([InlineKeyboardButton("✍️ 管理员手动结算", callback_data=f"prediction_settle_manual:{match_id}")])
        keyboard.append([InlineKeyboardButton("📒 查看下注详情", callback_data=f"prediction_bets:{match_id}:1")])
    keyboard.append([InlineKeyboardButton("🔙 返回比赛列表", callback_data="prediction_today")])
    await query.edit_message_text(
        detail_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def format_estimated_return(pool, stake):
    if stake <= 0:
        return "暂无下注"
    return f"每 1 萝卜约返 {pool / stake:.2f}"


async def show_pool_stats(query, context, match_id):
    match = await get_match(match_id)
    if not match:
        await query.edit_message_text(
            "这场比赛暂时找不到了，请刷新赛程。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 刷新赛程", callback_data="prediction_today")]]),
        )
        return

    stats = get_match_pool_stats(match_id)
    total_stake = stats["total_stake"]
    total_pool = stats["total_pool"]
    result_pool = stats["result_pool"]
    score_pool = stats["score_pool"]

    lines = [
        f"📊 奖池比例",
        "",
        f"比赛：{match_label(match)}",
        f"用户下注：{total_stake} 萝卜",
        f"f1bb补贴：{stats['platform_subsidy']} 萝卜",
        f"当前总奖池：{total_pool} 萝卜",
        "",
        f"胜平负池：{result_pool} 萝卜",
    ]

    for result in ("主胜", "平", "客胜"):
        stake = stats["result_stakes"].get(result, 0)
        users = stats["result_users"].get(result, 0)
        percent = (stake / total_stake * 100) if total_stake else 0
        lines.append(
            f"• {result}: {stake} 萝卜 / {users} 笔 / {percent:.1f}% / {format_estimated_return(result_pool, stake)}"
        )

    lines.extend(["", f"比分池：{score_pool} 萝卜"])
    score_items = sorted(
        stats["score_stakes"].items(),
        key=lambda item: item[1],
        reverse=True,
    )
    if score_items:
        for score, stake in score_items[:8]:
            users = stats["score_users"].get(score, 0)
            lines.append(
                f"• {score}: {stake} 萝卜 / {users} 笔 / {format_estimated_return(score_pool, stake)}"
            )
    else:
        lines.append("• 暂无比分下注")

    lines.extend([
        "",
        "说明：这是奖池制实时预估，不是固定赔率。后续有人下注后比例会变化。",
    ])

    keyboard = [
        [InlineKeyboardButton("🔄 刷新实时下注", callback_data=f"prediction_pool:{match_id}")],
        [InlineKeyboardButton("🥕 去预测", callback_data=f"prediction_match:{match_id}")],
        [InlineKeyboardButton("🔙 返回比赛列表", callback_data="prediction_today")],
    ]
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_match_subsidy_manager(query, context, match_id):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text("这个入口只有管理员能用。")
        return
    match = await get_match(match_id)
    if not match:
        await query.edit_message_text(
            "这场比赛暂时找不到了，请刷新赛程。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 刷新赛程", callback_data="prediction_today")]]),
        )
        return
    if is_match_settled(match_id):
        await query.edit_message_text(
            "🏁 这场比赛已经结算，不能再修改补贴。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回比赛", callback_data=f"prediction_match:{match_id}")]]),
        )
        return

    current_subsidy = get_match_subsidy(match_id, match)
    context.user_data["prediction_waiting_input"] = "match_subsidy"
    context.user_data["prediction_subsidy_match_id"] = match_id
    await query.edit_message_text(
        f"🥕 管理本场补贴\n\n"
        f"比赛：{match_label(match)}\n"
        f"当前补贴：{bold_alnum(current_subsidy)} 萝卜\n"
        f"默认补贴：{bold_alnum(PLATFORM_SUBSIDY)} 萝卜\n\n"
        "请输入新的本场补贴，0 或正整数都可以。\n"
        "保存后会影响这场之后的实时奖池和结算。",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 返回比赛", callback_data=f"prediction_match:{match_id}")]
        ]),
    )


def score_options_for_result(result):
    if result == "主胜":
        return ["1:0", "2:0", "2:1", "3:0", "3:1", "3:2", "4:0", "4:1", "4:2"]
    if result == "客胜":
        return ["0:1", "0:2", "1:2", "0:3", "1:3", "2:3", "0:4", "1:4", "2:4"]
    return ["0:0", "1:1", "2:2", "3:3", "4:4"]


def parse_score(text):
    normalized = text.strip().replace("：", ":")
    match = re.fullmatch(r"(\d{1,2}):(\d{1,2})", normalized)
    if not match:
        return None
    home_score, away_score = int(match.group(1)), int(match.group(2))
    if home_score > 20 or away_score > 20:
        return None
    return home_score, away_score, f"{home_score}:{away_score}"


def score_matches_result(score, result):
    home_score, away_score, _ = score
    if result == "主胜":
        return home_score > away_score
    if result == "客胜":
        return home_score < away_score
    return home_score == away_score


async def show_score_options(query, context, result):
    pick = context.user_data.get("prediction_pick")
    if not pick or "match" not in pick:
        await show_today_matches(query)
        return

    pick["result"] = result
    options = score_options_for_result(result)
    rows = []
    for idx in range(0, len(options), 3):
        rows.append([
            InlineKeyboardButton(score, callback_data=f"prediction_score:{score}")
            for score in options[idx:idx + 3]
        ])
    rows.append([InlineKeyboardButton("✏️ 其他比分", callback_data="prediction_custom_score")])
    rows.append([InlineKeyboardButton("🔙 重选胜平负", callback_data=f"prediction_match:{pick['match']['id']}")])
    await query.edit_message_text(
        f"🏟️ {match_label(pick['match'])}\n"
        f"选择：{result}\n\n"
        "请选择比分，或者点“其他比分”自己输入：",
        reply_markup=InlineKeyboardMarkup(rows),
    )


async def show_stake_options(query, context, score):
    pick = context.user_data.get("prediction_pick")
    if not pick or "match" not in pick or "result" not in pick:
        await show_today_matches(query)
        return

    pick["score"] = score
    keyboard = []
    for idx in range(0, len(STAKE_OPTIONS), 3):
        keyboard.append([
            InlineKeyboardButton(f"{stake} 萝卜", callback_data=f"prediction_stake:{stake}")
            for stake in STAKE_OPTIONS[idx:idx + 3]
        ])
    keyboard.append([InlineKeyboardButton("✏️ 自定义萝卜", callback_data="prediction_custom_stake")])
    keyboard.append([InlineKeyboardButton("🔙 重选比分", callback_data=f"prediction_result:{pick['result']}")])
    await query.edit_message_text(
        f"🏟️ {match_label(pick['match'])}\n"
        f"选择：{pick['result']} | 比分 {score}\n\n"
        "请选择投入萝卜数，也可以自定义。下注金额不设上限：",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def ask_custom_score(query, context):
    pick = context.user_data.get("prediction_pick")
    if not pick or "match" not in pick or "result" not in pick:
        await show_today_matches(query)
        return

    context.user_data["prediction_waiting_input"] = "score"
    await query.edit_message_text(
        f"🏟️ {match_label(pick['match'])}\n"
        f"选择：{pick['result']}\n\n"
        "请输入自定义比分，例如：5:2\n"
        "注意比分要和胜平负一致，比如主胜就要主队分数更高。",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 返回比分选择", callback_data=f"prediction_result:{pick['result']}")]
        ]),
    )


async def ask_custom_stake(query, context):
    pick = context.user_data.get("prediction_pick")
    if not pick or "match" not in pick or "result" not in pick or "score" not in pick:
        await show_today_matches(query)
        return

    context.user_data["prediction_waiting_input"] = "stake"
    await query.edit_message_text(
        f"🏟️ {match_label(pick['match'])}\n"
        f"选择：{pick['result']} | 比分 {pick['score']}\n\n"
        "请输入自定义萝卜数，1 萝卜起，不设上限：",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 返回萝卜选择", callback_data=f"prediction_score:{pick['score']}")]
        ]),
    )


async def show_confirm(query, context, stake):
    pick = context.user_data.get("prediction_pick")
    if not pick or "match" not in pick or "result" not in pick or "score" not in pick:
        await show_today_matches(query)
        return
    if is_match_settled(pick["match"]["id"]):
        await query.edit_message_text(
            "🏁 这场比赛已经结算，不能再下注。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回比赛列表", callback_data="prediction_today")]]),
        )
        return

    token, emos_user_id = get_logged_in_user_info(query.from_user.id)
    if not token or not emos_user_id:
        await query.edit_message_text(
            "❌ 请先登录后再下注。\n\n发送 /start 完成授权登录后，再回来选择下注数量。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]
            ]),
        )
        return

    pick["stake"] = stake
    loading = await query.edit_message_text("🔄 正在创建下注支付订单...")
    try:
        payment = await create_prediction_payment_order(query.from_user, pick, emos_user_id)
    except Exception as exc:
        logger.exception("创建预测下注订单未捕获异常: %s", exc)
        payment = {"success": False, "error": "创建下注订单异常，请稍后重试。"}
    if not payment["success"]:
        await loading.edit_text(
            f"❌ 创建下注订单失败\n\n{payment['error']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]
            ]),
        )
        return

    context.user_data.pop("prediction_pick", None)
    keyboard = [
        [InlineKeyboardButton("💳 前往支付", url=payment["pay_url"])],
        [
            InlineKeyboardButton("🔎 查询支付状态", callback_data=f"prediction_pay:{payment['platform_order_no']}"),
            InlineKeyboardButton("🔙 重选萝卜", callback_data=f"prediction_score:{pick['score']}"),
        ],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_prediction_main")],
    ]
    await loading.edit_text(
        "✅ 下注订单已创建\n\n"
        f"比赛：{match_label(pick['match'])}\n"
        f"时间：{pick['match']['beijing_time'].strftime('%m-%d %H:%M')}\n"
        f"胜平负：{pick['result']}\n"
        f"比分：{pick['score']}\n"
        f"投入：{stake} 萝卜\n\n"
        f"本地订单：{payment['order_no']}\n"
        f"平台订单：{payment['platform_order_no']}\n"
        f"下注用户：{emos_user_id}\n"
        f"支付参数：{payment['payment_param']}\n\n"
        "请点击下方按钮完成支付。支付成功回到机器人后，订单才会进入奖池。",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def confirm_prediction(query, context):
    await query.edit_message_text(
        "请通过支付订单按钮完成支付，或返回“我的预测”查看订单状态。",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📋 我的预测", callback_data="prediction_mine")],
            [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
        ]),
    )


async def handle_prediction_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    waiting_input = context.user_data.get("prediction_waiting_input")
    if not waiting_input:
        return False

    text = update.message.text.strip()
    if waiting_input == "ticket_background":
        await update.message.reply_text("这里要发图片，最好用“文件”方式发送原图。配文可写：名字|编号")
        return True

    if waiting_input == "settlement_manual":
        parsed = result_from_score_text(text)
        if not parsed:
            await update.message.reply_text("比分格式不对，请重新输入，例如：2:1。")
            return True
        actual_result, actual_score = parsed
        match_id = context.user_data.get("prediction_manual_settlement_match_id")
        context.user_data.pop("prediction_waiting_input", None)
        context.user_data.pop("prediction_manual_settlement_match_id", None)
        preview = build_settlement_preview(match_id, actual_result, actual_score)
        score_param = actual_score.replace(":", "-")
        await update.message.reply_text(
            format_settlement_preview(preview, title="✍️ 手动比分结算预览"),
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ 确认手动结算", callback_data=f"prediction_settle_manual_confirm:{match_id}:{score_param}")],
                [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
            ]),
        )
        return True

    if waiting_input == "demo_manual_settlement":
        parsed = result_from_score_text(text)
        if not parsed:
            await update.message.reply_text("比分格式不对，请重新输入，例如：3:2。")
            return True
        actual_result, actual_score = parsed
        context.user_data.pop("prediction_waiting_input", None)
        await update.message.reply_text(
            "🧪 模拟手动结算完成\n\n"
            f"你录入的赛果：{actual_result} {actual_score}\n"
            "系统会按这个比分重新计算奖池，再等待管理员确认后真实结算。\n\n"
            "这是演示流程，没有真实转账。"
        )
        return True

    if waiting_input == "match_subsidy":
        user = update.effective_user
        if not user or not is_ticket_card_admin(user.id):
            context.user_data.pop("prediction_waiting_input", None)
            context.user_data.pop("prediction_subsidy_match_id", None)
            await update.message.reply_text("这个入口只有管理员能用。")
            return True
        match_id = context.user_data.get("prediction_subsidy_match_id")
        if not match_id:
            context.user_data.pop("prediction_waiting_input", None)
            await update.message.reply_text("补贴设置状态已失效，请重新打开比赛。")
            return True
        if is_match_settled(match_id):
            context.user_data.pop("prediction_waiting_input", None)
            context.user_data.pop("prediction_subsidy_match_id", None)
            await update.message.reply_text("这场比赛已经结算，不能再修改补贴。")
            return True
        try:
            subsidy = int(text)
        except ValueError:
            await update.message.reply_text("请输入 0 或正整数，例如：100。")
            return True
        if subsidy < 0:
            await update.message.reply_text("补贴不能小于 0，请重新输入。")
            return True
        set_match_subsidy(match_id, subsidy, user.id)
        context.user_data.pop("prediction_waiting_input", None)
        context.user_data.pop("prediction_subsidy_match_id", None)
        await update.message.reply_text(
            f"✅ 本场补贴已更新为 {bold_alnum(subsidy)} 萝卜。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回比赛", callback_data=f"prediction_match:{match_id}")],
                [InlineKeyboardButton("📊 查看奖池", callback_data=f"prediction_pool:{match_id}")],
            ]),
        )
        return True

    pick = context.user_data.get("prediction_pick")
    if not pick:
        context.user_data.pop("prediction_waiting_input", None)
        await update.message.reply_text("预测状态已失效，请重新打开 /prediction。")
        return True

    if waiting_input == "score":
        parsed_score = parse_score(text)
        if not parsed_score:
            await update.message.reply_text("比分格式不对，请重新输入，例如：2:1。")
            return True

        if not score_matches_result(parsed_score, pick.get("result")):
            await update.message.reply_text(
                f"这个比分和你选的“{pick.get('result')}”不一致，请重新输入。"
            )
            return True

        context.user_data.pop("prediction_waiting_input", None)
        await show_stake_options_from_message(update, context, parsed_score[2])
        return True

    if waiting_input == "stake":
        try:
            stake = int(text)
        except ValueError:
            await update.message.reply_text("请输入正整数，例如：100。")
            return True

        if stake < 1:
            await update.message.reply_text("下注金额至少 1 萝卜，请重新输入。")
            return True

        context.user_data.pop("prediction_waiting_input", None)
        await show_confirm_from_message(update, context, stake)
        return True

    return False


async def show_stake_options_from_message(update, context, score):
    pick = context.user_data.get("prediction_pick")
    if not pick:
        await update.message.reply_text("预测状态已失效，请重新打开 /prediction。")
        return

    pick["score"] = score
    keyboard = []
    for idx in range(0, len(STAKE_OPTIONS), 3):
        keyboard.append([
            InlineKeyboardButton(f"{stake} 萝卜", callback_data=f"prediction_stake:{stake}")
            for stake in STAKE_OPTIONS[idx:idx + 3]
        ])
    keyboard.append([InlineKeyboardButton("✏️ 自定义萝卜", callback_data="prediction_custom_stake")])
    keyboard.append([InlineKeyboardButton("🔙 重选比分", callback_data=f"prediction_result:{pick['result']}")])

    await update.message.reply_text(
        f"🏟️ {match_label(pick['match'])}\n"
        f"选择：{pick['result']} | 比分 {score}\n\n"
        "请选择投入萝卜数，也可以自定义。下注金额不设上限：",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_confirm_from_message(update, context, stake):
    pick = context.user_data.get("prediction_pick")
    if not pick:
        await update.message.reply_text("预测状态已失效，请重新打开 /prediction。")
        return
    if is_match_settled(pick["match"]["id"]):
        await update.message.reply_text("🏁 这场比赛已经结算，不能再下注。")
        return

    token, emos_user_id = get_logged_in_user_info(update.effective_user.id)
    if not token or not emos_user_id:
        await update.message.reply_text(
            "❌ 请先登录后再下注。\n\n发送 /start 完成授权登录后，再回来选择下注数量。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]
            ]),
        )
        return

    pick["stake"] = stake
    loading = await update.message.reply_text("🔄 正在创建下注支付订单...")
    try:
        payment = await create_prediction_payment_order(update.effective_user, pick, emos_user_id)
    except Exception as exc:
        logger.exception("创建预测下注订单未捕获异常: %s", exc)
        payment = {"success": False, "error": "创建下注订单异常，请稍后重试。"}
    if not payment["success"]:
        await loading.edit_text(
            f"❌ 创建下注订单失败\n\n{payment['error']}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]
            ]),
        )
        return

    context.user_data.pop("prediction_pick", None)
    keyboard = [
        [InlineKeyboardButton("💳 前往支付", url=payment["pay_url"])],
        [
            InlineKeyboardButton("🔎 查询支付状态", callback_data=f"prediction_pay:{payment['platform_order_no']}"),
            InlineKeyboardButton("🔙 重选萝卜", callback_data=f"prediction_score:{pick['score']}"),
        ],
        [InlineKeyboardButton("❌ 取消", callback_data="menu_prediction_main")],
    ]
    await loading.edit_text(
        "✅ 下注订单已创建\n\n"
        f"比赛：{match_label(pick['match'])}\n"
        f"时间：{pick['match']['beijing_time'].strftime('%m-%d %H:%M')}\n"
        f"胜平负：{pick['result']}\n"
        f"比分：{pick['score']}\n"
        f"投入：{stake} 萝卜\n\n"
        f"本地订单：{payment['order_no']}\n"
        f"平台订单：{payment['platform_order_no']}\n"
        f"下注用户：{emos_user_id}\n"
        f"支付参数：{payment['payment_param']}\n\n"
        "请点击下方按钮完成支付。支付成功回到机器人后，订单才会进入奖池。",
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def save_demo_prediction(user, pick, stake):
    pick["stake"] = stake
    order_no = f"DEMO{datetime.now(BEIJING_TZ).strftime('%H%M%S')}{uuid.uuid4().hex[:4].upper()}"
    platform_order_no = f"DEMO-{user.id}-{uuid.uuid4().hex[:6].upper()}"
    save_prediction(
        user,
        pick,
        status="pending",
        emos_user_id=f"DEMO-{user.id}",
        transfer_status="paid",
        order_no=order_no,
        platform_order_no=platform_order_no,
        payment_param="DEMO",
        pay_url="",
    )
    return get_prediction_by_platform_order(platform_order_no)


async def save_demo_prediction_and_reply(query, context, stake):
    pick = context.user_data.get("prediction_pick")
    item = save_demo_prediction(query.from_user, pick, stake)
    context.user_data.pop("prediction_pick", None)
    await query.edit_message_text(
        "🧪 模拟下注成功，已进入模拟奖池\n\n"
        f"比赛：{item['match_label']}\n"
        f"选择：{item['result_pick']} {item['score_pick']}\n"
        f"投入：{item['stake']} 模拟萝卜\n\n"
        "这笔不会扣真实萝卜，也不会真实转账。",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 查看模拟奖池", callback_data=f"prediction_pool:{item['match_id']}")],
            [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
        ]),
    )


async def save_demo_prediction_from_message(update, context, stake):
    pick = context.user_data.get("prediction_pick")
    item = save_demo_prediction(update.effective_user, pick, stake)
    context.user_data.pop("prediction_pick", None)
    await update.message.reply_text(
        "🧪 模拟下注成功，已进入模拟奖池\n\n"
        f"比赛：{item['match_label']}\n"
        f"选择：{item['result_pick']} {item['score_pick']}\n"
        f"投入：{item['stake']} 模拟萝卜\n\n"
        "这笔不会扣真实萝卜，也不会真实转账。",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📊 查看模拟奖池", callback_data=f"prediction_pool:{item['match_id']}")],
            [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")],
        ]),
    )


async def show_my_predictions(query):
    rows = get_user_predictions(query.from_user.id)
    keyboard = [[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]
    if not rows:
        await query.edit_message_text(
            "📋 我的预测\n\n还没有预测记录。",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    lines = []
    for item in rows:
        match_time = datetime.fromisoformat(item["match_time"]).strftime("%m-%d %H:%M")
        order_no = item.get("order_no") or "无订单号"
        transfer_status = item.get("stake_transfer_status") or "unknown"
        lines.append(
            f"{item['match_label']}\n"
            f"   {match_time} | {item['result_pick']} {item['score_pick']} | {item['stake']} 萝卜\n"
            f"   订单：{order_no} | 状态：{item['status']} / {transfer_status}"
        )
    await query.edit_message_text(
        "📋 我的预测\n\n" + "\n\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


def format_history_time(value):
    if not value:
        return "未知时间"
    try:
        return datetime.fromisoformat(str(value)).strftime("%m-%d %H:%M")
    except Exception:
        return str(value)[:16]


def payout_status_text(status):
    return {
        "paid": "已发",
        "failed": "失败",
        "none": "无奖励",
        "not_settled": "未结算",
        "payment_pending": "待支付",
    }.get(str(status or ""), str(status or "未知"))


def payment_status_text(status):
    return {
        "paid": "已支付",
        "payment_pending": "待支付",
        "cancelled": "已取消",
        "not_charged": "未扣款",
    }.get(str(status or ""), str(status or "未知"))


async def show_match_bet_details(query, match_id, page=1):
    if not is_ticket_card_admin(query.from_user.id):
        await query.edit_message_text(
            "这个入口只有管理员能看。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
        )
        return

    page = max(1, int(page or 1))
    page_size = 5
    data = get_match_bet_details(match_id, limit=page_size, offset=(page - 1) * page_size)
    rows = data["rows"]
    total = data["total"]
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
        data = get_match_bet_details(match_id, limit=page_size, offset=(page - 1) * page_size)
        rows = data["rows"]
        total = data["total"]

    summary = data.get("summary") or {}
    keyboard = []
    if not rows:
        await query.edit_message_text(
            "📒 下注详情\n\n这场比赛还没有下注记录。",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]
            ]),
        )
        return

    match_label_text = summary.get("match_label") or rows[0].get("match_label") or match_id
    paid_bets = int(summary.get("paid_bets") or 0)
    paid_stake = int(summary.get("paid_stake") or 0)
    total_stake = int(summary.get("total_stake") or 0)

    lines = [
        "📒 管理员下注详情",
        "━━━━━━━━━━━━━━",
        f"比赛：{bold_alnum(match_label_text)}",
        f"📄 第 {bold_alnum(f'{page}/{total_pages}')} 页    共 {bold_alnum(total)} 笔",
        f"✅ 已支付：{bold_alnum(paid_bets)} 笔 / {bold_alnum(paid_stake)} 萝卜",
        f"🧾 全部订单：{bold_alnum(total_stake)} 萝卜",
    ]

    for index, item in enumerate(rows, start=(page - 1) * page_size + 1):
        username = item.get("username") or str(item.get("telegram_user_id"))
        raw_pay_status = item.get("stake_transfer_status") or item.get("status")
        pay_status = payment_status_text(raw_pay_status)
        pay_icon = "✅" if raw_pay_status == "paid" else "⏳" if raw_pay_status == "payment_pending" else "⚪"
        created_text = format_history_time(item.get("created_at"))
        paid_text = format_history_time(item.get("paid_at")) if item.get("paid_at") else "-"
        payout_amount = int(item.get("payout_amount") or 0)
        payout = ""
        if item.get("status") == "settled":
            payout = f"\n💰 结算：{bold_alnum(payout_amount)} 萝卜 / {payout_status_text(item.get('payout_status'))}"
        lines.append(
            "------------------\n"
            f"#{bold_alnum(index)}  {bold_alnum(username)}\n"
            f"🆔 EMOS：{bold_alnum(item.get('emos_user_id') or '-')}\n"
            f"🎯 预测：{item.get('result_pick')}  {bold_alnum(item.get('score_pick'))}\n"
            f"🥕 投入：{bold_alnum(item.get('stake'))} 萝卜    {pay_icon} {pay_status}\n"
            f"🕒 下单：{bold_alnum(created_text)}    支付：{bold_alnum(paid_text)}\n"
            f"🧾 订单：{bold_alnum(item.get('platform_order_no') or item.get('order_no') or '-')}"
            f"{payout}"
        )

    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"prediction_bets:{match_id}:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"prediction_bets:{match_id}:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([
        InlineKeyboardButton("🔄 刷新", callback_data=f"prediction_bets:{match_id}:{page}"),
        InlineKeyboardButton("🏆 发奖历史", callback_data=f"prediction_payout_match:{match_id}"),
    ])
    keyboard.append([InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_payout_history_matches(query, page=1):
    page = max(1, int(page or 1))
    page_size = 8
    rows, total = get_payout_history_matches(limit=page_size, offset=(page - 1) * page_size)
    total_pages = max(1, (total + page_size - 1) // page_size)
    if page > total_pages:
        page = total_pages
        rows, total = get_payout_history_matches(limit=page_size, offset=(page - 1) * page_size)
    keyboard = [[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]
    if not rows:
        await query.edit_message_text(
            "🏆 发奖历史\n\n还没有已结算的比赛。",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    lines = [
        "🏆 世界杯预测发奖历史",
        "━━━━━━━━━━━━━━",
        f"📄 第 {bold_alnum(f'{page}/{total_pages}')} 页    共 {bold_alnum(total)} 场",
        "🕒 最新结算排在最前面",
    ]
    keyboard = []
    for item in rows:
        settled_text = format_history_time(item.get("settled_at") or item.get("match_time"))
        result_text = f"{item.get('settled_result') or '未记录'} {item.get('settled_score') or ''}".strip()
        paid_amount = int(item.get("paid_amount") or 0)
        failed_amount = int(item.get("failed_amount") or 0)
        winner_count = int(item.get("winner_count") or 0)
        failed_text = f"\n   ⚠️ 待补：{failed_amount} 萝卜" if failed_amount else ""
        lines.append(
            "------------------\n"
            f"⚽ {bold_alnum(item['match_label'])}\n"
            f"📌 赛果：{bold_alnum(result_text)}\n"
            f"🕒 结算：{bold_alnum(settled_text)}\n"
            f"🎯 中奖票：{bold_alnum(winner_count)}    💰 已发：{bold_alnum(paid_amount)} 萝卜"
            f"{bold_alnum(failed_text)}"
        )
        keyboard.append([
            InlineKeyboardButton(
                item["match_label"][:32],
                callback_data=f"prediction_payout_match:{item['match_id']}",
            )
        ])
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"prediction_payout_history:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"prediction_payout_history:{page + 1}"))
    if nav:
        keyboard.append(nav)
    keyboard.append([InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")])
    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def show_payout_history_detail(query, match_id, page=1):
    data = get_payout_history_for_match(match_id)
    rows = data["predictions"]
    manual_rows = data["manual_payouts"]
    page = max(1, int(page or 1))
    page_size = 6
    if not rows:
        keyboard = [[InlineKeyboardButton("🔙 返回发奖历史", callback_data="prediction_payout_history")]]
        await query.edit_message_text(
            "🏆 发奖明细\n\n这场比赛没有找到已结算记录。",
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return

    first = rows[0]
    total_stake = sum(int(item.get("stake") or 0) for item in rows)
    platform_subsidy = get_match_subsidy(match_id)
    total_pool = total_stake + platform_subsidy
    paid_amount = sum(
        int(item.get("payout_amount") or 0)
        for item in rows
        if item.get("payout_status") == "paid"
    )
    failed_amount = sum(
        int(item.get("payout_amount") or 0)
        for item in rows
        if item.get("payout_status") == "failed"
    )
    winner_rows = [item for item in rows if int(item.get("payout_amount") or 0) > 0]
    winner_pages = (len(winner_rows) + page_size - 1) // page_size
    total_pages = max(1, 1 + winner_pages)
    if page > total_pages:
        page = total_pages
    record_page = page - 1
    page_start = (record_page - 1) * page_size if record_page > 0 else 0
    visible_winners = winner_rows[page_start:page_start + page_size] if record_page > 0 else []
    result_text = f"{first.get('settled_result') or '未记录'} {first.get('settled_score') or ''}".strip()
    planned_amount = paid_amount + failed_amount
    retained_amount = max(0, total_pool - planned_amount)

    if page == 1:
        lines = [
            "🏆 发奖明细",
            "",
            f"比赛：{bold_alnum(first['match_label'])}",
            f"赛果：{bold_alnum(result_text)}",
            f"结算时间：{bold_alnum(format_history_time(first.get('settled_at')))}",
            f"下注笔数：{bold_alnum(len(rows))}",
            f"用户下注：{bold_alnum(total_stake)} 萝卜",
            f"f1bb补贴：{bold_alnum(platform_subsidy)} 萝卜",
            f"总奖池：{bold_alnum(total_pool)} 萝卜",
            f"本场应发：{bold_alnum(planned_amount)} 萝卜",
            f"实际已发奖励：{bold_alnum(paid_amount)} 萝卜",
            f"平台留存：{bold_alnum(retained_amount)} 萝卜",
        ]
        if failed_amount:
            lines.append(f"失败待补：{bold_alnum(failed_amount)} 萝卜")
        lines.extend([
            "",
            f"中奖记录：共 {bold_alnum(len(winner_rows))} 条",
            "点下一页查看具体发奖明细。",
        ])
    else:
        lines = [
            "🏆 发奖明细",
            f"比赛：{bold_alnum(first['match_label'])}",
            f"中奖/发奖记录：第 {bold_alnum(f'{record_page}/{max(1, winner_pages)}')} 页，共 {bold_alnum(len(winner_rows))} 条",
        ]

    if page > 1 and winner_rows:
        for item in visible_winners:
            username = item.get("username") or str(item.get("telegram_user_id"))
            actual_payout = int(item.get("payout_amount") or 0)
            lines.append(
                f"------------------\n"
                f"• {bold_alnum(username)}\n"
                f"  预测：{item['result_pick']} {bold_alnum(item['score_pick'])} | 投入：{bold_alnum(item['stake'])} 萝卜\n"
                f"  发奖：{bold_alnum(actual_payout)} 萝卜 | 状态：{payout_status_text(item.get('payout_status'))}"
            )
            if item.get("payout_error"):
                lines.append(f"  失败原因：{bold_alnum(str(item['payout_error'])[:80])}")
    elif page > 1:
        lines.append("• 这场没有中奖票。")

    if page == 1 and manual_rows:
        lines.extend(["", "手动补账记录："])
        for item in manual_rows[:4]:
            username = item.get("username") or str(item.get("telegram_user_id"))
            notified = "已通知" if int(item.get("notified") or 0) else "未通知"
            lines.append(
                f"------------------\n"
                f"• {bold_alnum(username)} | {bold_alnum(item.get('score_pick') or '-')} | "
                f"{bold_alnum(item.get('payout_amount') or 0)} 萝卜 | "
                f"{payout_status_text(item.get('transfer_status'))} | {notified}"
            )
        if len(manual_rows) > 4:
            lines.append(f"• 还有 {bold_alnum(len(manual_rows) - 4)} 条补账记录未显示")

    keyboard = []
    nav = []
    if page > 1:
        nav.append(InlineKeyboardButton("⬅️ 上一页", callback_data=f"prediction_payout_match:{match_id}:{page - 1}"))
    if page < total_pages:
        nav.append(InlineKeyboardButton("下一页 ➡️", callback_data=f"prediction_payout_match:{match_id}:{page + 1}"))
    if nav:
        keyboard.append(nav)
    actions = [InlineKeyboardButton("🔄 刷新", callback_data=f"prediction_payout_match:{match_id}:{page}")]
    if is_ticket_card_admin(query.from_user.id):
        actions.append(InlineKeyboardButton("📒 下注详情", callback_data=f"prediction_bets:{match_id}:1"))
    keyboard.append(actions)
    keyboard.append([InlineKeyboardButton("🔙 返回发奖历史", callback_data="prediction_payout_history")])

    await query.edit_message_text(
        "\n".join(lines),
        reply_markup=InlineKeyboardMarkup(keyboard),
    )


async def prediction_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.info("打开世界杯预测面板")
    await send_prediction_panel(update, context)


async def prediction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "menu_prediction_main":
        await send_prediction_panel(update, context)
        return

    if data in ("prediction_today", "prediction_submit_help"):
        await show_today_matches(query)
        return

    if data == "prediction_refresh":
        await get_schedule(force=True)
        await show_today_matches(query)
        return

    if data == "prediction_payout_history":
        await show_payout_history_matches(query, page=1)
        return

    if data.startswith("prediction_payout_history:"):
        await show_payout_history_matches(query, page=int(data.split(":", 1)[1]))
        return

    if data.startswith("prediction_payout_match:"):
        parts = data.split(":")
        match_id = parts[1]
        page = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 1
        await show_payout_history_detail(query, match_id, page=page)
        return

    if data.startswith("prediction_bets:"):
        _, match_id, page = data.split(":", 2)
        await show_match_bet_details(query, match_id, page=int(page))
        return

    if data == "prediction_upload_bg":
        await ask_ticket_background_upload(query, context)
        return

    if data == "prediction_card_pool":
        await show_ticket_card_pool(query)
        return

    if data == "prediction_settle_scan":
        await run_settlement_scan(query, context)
        return

    if data == "prediction_demo_settle":
        await start_demo_settlement(query, context)
        return

    if data == "prediction_demo_confirm":
        await confirm_demo_settlement(query)
        return

    if data == "prediction_demo_manual":
        await ask_demo_manual_score(query, context)
        return

    if data.startswith("prediction_settle_fifa:"):
        await confirm_fifa_settlement(query, context, data.split(":", 1)[1])
        return

    if data.startswith("prediction_settle_manual_confirm:"):
        _, match_id, score_param = data.split(":", 2)
        await confirm_manual_settlement(query, context, match_id, score_param.replace("-", ":"))
        return

    if data.startswith("prediction_settle_manual:"):
        await ask_manual_settlement_score(query, context, data.split(":", 1)[1])
        return

    if data.startswith("prediction_settle_later:"):
        match_id = data.split(":", 1)[1]
        update_settlement_request_status(match_id, "later", "管理员选择稍后结算")
        await query.edit_message_text(
            "⏳ 已标记稍后结算。\n\n你可以之后点“检查结算”重新请求确认。",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]),
        )
        return

    if data.startswith("prediction_match:"):
        await show_result_options(query, context, data.split(":", 1)[1])
        return

    if data.startswith("prediction_pool:"):
        await show_pool_stats(query, context, data.split(":", 1)[1])
        return

    if data.startswith("prediction_subsidy:"):
        await show_match_subsidy_manager(query, context, data.split(":", 1)[1])
        return

    if data.startswith("prediction_pay:"):
        await show_payment_check_result(query, context, data.split(":", 1)[1])
        return

    if data.startswith("prediction_result:"):
        await show_score_options(query, context, data.split(":", 1)[1])
        return

    if data.startswith("prediction_score:"):
        await show_stake_options(query, context, data.split(":", 1)[1])
        return

    if data == "prediction_custom_score":
        await ask_custom_score(query, context)
        return

    if data == "prediction_custom_stake":
        await ask_custom_stake(query, context)
        return

    if data.startswith("prediction_stake:"):
        await show_confirm(query, context, int(data.split(":", 1)[1]))
        return

    if data == "prediction_confirm":
        await confirm_prediction(query, context)
        return

    if data == "prediction_mine":
        await show_my_predictions(query)
        return

    if data == "prediction_rules":
        keyboard = [[InlineKeyboardButton("🔙 返回预测面板", callback_data="menu_prediction_main")]]
        await query.edit_message_text(
            PREDICTION_RULES_TEXT,
            reply_markup=InlineKeyboardMarkup(keyboard),
        )
        return
