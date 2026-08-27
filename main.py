import os
import sqlite3
import random
import threading
import time

from flask import Flask, jsonify, render_template_string, request
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update, WebAppInfo
from telegram.ext import Application, CommandHandler, ContextTypes


# =========================
# SETTINGS
# =========================

BOT_TOKEN = os.getenv("BOT_TOKEN", "PUT_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))
PORT = int(os.getenv("PORT", "8080"))
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://YOUR-HTTPS-URL-HERE")

DB_FILE = "epic_gift.db"

app = Flask(__name__)


# =========================
# DATABASE
# =========================

def db():
    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    connection = db()

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT DEFAULT '',
            first_name TEXT DEFAULT '',
            balance REAL NOT NULL DEFAULT 100,
            created_at INTEGER NOT NULL
        )
        """
    )

    connection.execute(
        """
        CREATE TABLE IF NOT EXISTS gifts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            gift_name TEXT NOT NULL,
            created_at INTEGER NOT NULL
        )
        """
    )

    connection.commit()
    connection.close()


def ensure_user(user_id, username="", first_name=""):
    connection = db()

    row = connection.execute(
        "SELECT id FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    if row is None:
        connection.execute(
            """
            INSERT INTO users
            (id, username, first_name, balance, created_at)
            VALUES (?, ?, ?, 100, ?)
            """,
            (
                user_id,
                username or "",
                first_name or "",
                int(time.time())
            )
        )
    else:
        connection.execute(
            """
            UPDATE users
            SET username = ?, first_name = ?
            WHERE id = ?
            """,
            (
                username or "",
                first_name or "",
                user_id
            )
        )

    connection.commit()
    connection.close()


def is_admin(user_id):
    return int(user_id) == ADMIN_ID


def get_balance(user_id):
    if is_admin(user_id):
        return None

    connection = db()

    row = connection.execute(
        "SELECT balance FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    connection.close()

    if row is None:
        return 0.0

    return float(row["balance"])


def change_balance(user_id, amount):
    if is_admin(user_id):
        return

    connection = db()

    connection.execute(
        "UPDATE users SET balance = balance + ? WHERE id = ?",
        (amount, user_id)
    )

    connection.commit()
    connection.close()


def request_user_id():
    value = request.headers.get("X-User-ID")

    if not value:
        value = request.args.get("user_id")

    try:
        return int(value)
    except (TypeError, ValueError):
        return None


# =========================
# MINI APP
# =========================

HTML = r"""
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1,maximum-scale=1,user-scalable=no">
<title>Epic Gift Demo</title>
<script src="https://telegram.org/js/telegram-web-app.js"></script>

<style>
* {
    box-sizing: border-box;
    -webkit-tap-highlight-color: transparent;
}

body {
    margin: 0;
    background: #151515;
    color: #ffffff;
    font-family: Arial, Helvetica, sans-serif;
    padding-bottom: 90px;
}

.header {
    padding: 18px;
    border-bottom: 1px solid #333;
}

.top {
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.logo {
    font-size: 24px;
    font-weight: 900;
}

.demo {
    background: #303030;
    color: #aaa;
    padding: 6px 10px;
    border-radius: 10px;
    font-size: 11px;
}

.profile {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 18px;
}

.user {
    display: flex;
    align-items: center;
}

.avatar {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    background: linear-gradient(135deg, #8061e8, #24b9e8);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 23px;
}

.balance-box {
    margin-left: 12px;
}

.label {
    color: #888;
    font-size: 12px;
}

.balance {
    font-size: 25px;
    font-weight: 900;
    margin-top: 3px;
}

button {
    border: 0;
    color: #fff;
    font-weight: 900;
    cursor: pointer;
}

.gift-button {
    background: #8061e8;
    padding: 13px 17px;
    border-radius: 16px;
}

.live {
    display: flex;
    gap: 9px;
    overflow: hidden;
    padding: 14px 18px;
    border-bottom: 1px solid #333;
}

.live-item {
    min-width: 70px;
    height: 55px;
    border-radius: 14px;
    background: linear-gradient(135deg, #20d09e, #21aeea);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 27px;
}

.card {
    margin: 14px 18px;
    height: 145px;
    border-radius: 26px;
    padding: 23px;
    display: flex;
    flex-direction: column;
    justify-content: center;
    cursor: pointer;
}

.tag {
    background: #fff;
    color: #555;
    padding: 7px 12px;
    border-radius: 17px;
    width: max-content;
    font-size: 12px;
    font-weight: 900;
}

.title {
    font-size: 32px;
    font-weight: 900;
    margin-top: 8px;
}

.desc {
    font-size: 12px;
    opacity: .8;
    margin-top: 4px;
}

.rocket {
    background: linear-gradient(135deg, #5796e7, #73b8ff);
}

.pvp {
    background: linear-gradient(135deg, #ffab00, #ffd03b);
}

.play {
    background: linear-gradient(135deg, #371078, #7726d8);
}

.section {
    padding: 8px 18px;
    font-size: 20px;
    font-weight: 900;
}

.grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 14px;
    padding: 0 18px;
}

.game {
    min-height: 145px;
    border-radius: 21px;
    padding: 18px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    cursor: pointer;
}

.game-icon {
    font-size: 40px;
}

.game-title {
    font-size: 18px;
    font-weight: 900;
}

.free {
    background: linear-gradient(135deg, #322718, #9c6b15);
}

.mystery {
    background: linear-gradient(135deg, #25152f, #bd3ac5);
}

.games {
    background: #24203b;
}

.gifts {
    background: #183b35;
}

.bottom {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    height: 76px;
    background: #1b1b1b;
    border-top: 1px solid #333;
    display: flex;
    align-items: center;
    justify-content: space-around;
}

.nav {
    color: #888;
    text-align: center;
    font-size: 11px;
}

.nav-icon {
    font-size: 22px;
    margin-bottom: 3px;
}

.nav.active {
    color: #fff;
}

.modal {
    display: none;
    position: fixed;
    inset: 0;
    background: rgba(0,0,0,.75);
    z-index: 100;
    align-items: flex-end;
}

.modal-box {
    width: 100%;
    background: #222;
    border-radius: 25px 25px 0 0;
    padding: 24px;
}

.modal-title {
    font-size: 25px;
    font-weight: 900;
    margin-bottom: 20px;
}

.input {
    width: 100%;
    background: #333;
    color: #fff;
    border: 1px solid #555;
    padding: 15px;
    border-radius: 14px;
    outline: none;
    font-size: 16px;
    margin-bottom: 12px;
}

.action {
    width: 100%;
    padding: 15px;
    border-radius: 15px;
    background: #8061e8;
    font-size: 16px;
    margin-top: 6px;
}

.close {
    background: #333;
}

.result {
    text-align: center;
    font-size: 22px;
    font-weight: 900;
    margin: 15px 0;
}
</style>
</head>

<body>

<div class="header">
    <div class="top">
        <div class="logo">Epic Gift</div>
        <div class="demo">DEMO</div>
    </div>

    <div class="profile">
        <div class="user">
            <div class="avatar">🎁</div>

            <div class="balance-box">
                <div class="label">Demo balance</div>
                <div class="balance" id="balance">100</div>
            </div>
        </div>

        <button class="gift-button" onclick="openGift()">Gift</button>
    </div>
</div>

<div class="live">
    <div class="live-item">💎</div>
    <div class="live-item">💎</div>
    <div class="live-item">💎</div>
    <div class="live-item">💍</div>
    <div class="live-item">⌚</div>
    <div class="live-item">🚀</div>
</div>

<div class="card rocket" onclick="openRocket()">
    <div class="tag">HOT</div>
    <div class="title">ROCKET</div>
    <div class="desc">Virtual demo game</div>
</div>

<div class="card pvp">
    <div class="tag">NEW</div>
    <div class="title">PVP</div>
    <div class="desc">Arena & Cards</div>
</div>

<div class="card play">
    <div class="tag">PLAY</div>
    <div class="title">PLAY HUB</div>
    <div class="desc">Mini Games</div>
</div>

<div class="section">Free & Gifts</div>

<div class="grid">

    <div class="game free" onclick="freeGift()">
        <div class="game-icon">💍</div>
        <div class="game-title">FREE GIFT</div>
    </div>

    <div class="game mystery" onclick="openGift()">
        <div class="game-icon">🎁</div>
        <div class="game-title">MYSTERY GIFT</div>
    </div>

    <div class="game games" onclick="openRocket()">
        <div class="game-icon">🚀</div>
        <div class="game-title">ROCKET</div>
    </div>

    <div class="game gifts" onclick="openGift()">
        <div class="game-icon">💎</div>
        <div class="game-title">GIFTS</div>
    </div>

</div>

<div class="bottom">
    <div class="nav active">
        <div class="nav-icon">🏠</div>
        Home
    </div>

    <div class="nav">
        <div class="nav-icon">🎒</div>
        Backpack
    </div>

    <div class="nav">
        <div class="nav-icon">👥</div>
        Invite
    </div>

    <div class="nav">
        <div class="nav-icon">🏆</div>
        Leaderboard
    </div>

    <div class="nav">
        <div class="nav-icon">💰</div>
        Earn
    </div>
</div>

<div class="modal" id="rocketModal">
    <div class="modal-box">
        <div class="modal-title">Rocket Demo</div>

        <input type="number" id="betAmount" class="input" placeholder="Bet Amount (e.g. 10)" value="10">
        <input type="number" id="targetMult" class="input" placeholder="Target Multiplier (e.g. 2.0)" value="2.0" step="0.1">

        <div class="result" id="rocketResult">🚀 Ready to Launch</div>

        <button class="action" onclick="playRocket()">
            Launch
        </button>

        <button class="action close" onclick="closeModals()">
            Close
        </button>
    </div>
</div>

<div class="modal" id="giftModal">
    <div class="modal-box">
        <div class="modal-title">Mystery Gift</div>

        <div style="text-align:center;font-size:75px;margin:20px;">
            🎁
        </div>

        <button class="action" onclick="buyGift()">
            Open for 10 demo credits
        </button>

        <button class="action close" onclick="closeModals()">
            Close
        </button>
    </div>
</div>

<script>
const tg = window.Telegram && window.Telegram.WebApp
    ? window.Telegram.WebApp
    : null;

if (tg) {
    tg.ready();
    tg.expand();
}

let userId = null;

function getTelegramUser() {
    if (tg && tg.initDataUnsafe && tg.initDataUnsafe.user) {
        return tg.initDataUnsafe.user;
    }

    return null;
}

function loadUser() {
    const user = getTelegramUser();

    if (user) {
        userId = user.id;
    }

    if (!userId) {
        userId = localStorage.getItem("demo_user_id");
    }

    if (!userId) {
        userId = Math.floor(Math.random() * 1000000000);
        localStorage.setItem("demo_user_id", userId);
    }

    fetch("/api/me?user_id=" + encodeURIComponent(userId))
        .then(function(response) {
            return response.json();
        })
        .then(function(data) {
            if (!data.error) {
                updateBalance(data);
            }
        });
}

function updateBalance(data) {
    const element = document.getElementById("balance");

    if (data.infinite) {
        element.innerText = "∞";
    } else {
        element.innerText = Number(data.balance).toFixed(2);
    }
}

function headers() {
    return {
        "Content-Type": "application/json",
        "X-User-ID": String(userId)
    };
}

function openRocket() {
    document.getElementById("rocketModal").style.display = "flex";
}

function openGift() {
    document.getElementById("giftModal").style.display = "flex";
}

function closeModals() {
    document.querySelectorAll(".modal").forEach(function(modal) {
        modal.style.display = "none";
    });
}

function playRocket() {
    const result = document.getElementById("rocketResult");
    const bet = parseFloat(document.getElementById("betAmount").value);
    const target = parseFloat(document.getElementById("targetMult").value);

    if (!bet || !target || bet <= 0 || target <= 1.0) {
        alert("Enter valid Bet Amount and Target Multiplier (> 1.0)");
        return;
    }

    result.innerText = "🚀 Launching...";

    fetch("/api/rocket", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
            bet: bet,
            target: target
        })
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        if (data.error) {
            result.innerText = "Error: " + data.error;
            return;
        }

        if (data.win) {
            result.innerText = "🎉 Win! Crash: " + data.crash_point + "x (+" + data.profit + ")";
        } else {
            result.innerText = "💥 Crash at " + data.crash_point + "x (-" + bet + ")";
        }

        updateBalance(data);
    });
}

function buyGift() {
    fetch("/api/gift", {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
            name: "Mystery Gift"
        })
    })
    .then(function(response) {
        return response.json();
    })
    .then(function(data) {
        if (data.error) {
            alert(data.error);
            return;
        }

        updateBalance(data);
        alert("🎁 Mystery Gift received!");
    });
}

function freeGift() {
    alert("Your first-login bonus is 100 demo credits.");
}

loadUser();
</script>

</body>
</html>
"""


# =========================
# WEB ROUTES
# =========================

@app.route("/")
def home():
    return render_template_string(HTML)


@app.route("/api/me")
def api_me():
    user_id = request_user_id()

    if not user_id:
        return jsonify({"error": "Missing user ID"}), 400

    ensure_user(user_id)

    return jsonify({
        "id": user_id,
        "balance": get_balance(user_id),
        "infinite": is_admin(user_id)
    })


@app.route("/api/rocket", methods=["POST"])
def api_rocket():
    user_id = request_user_id()

    if not user_id:
        return jsonify({"error": "Missing user ID"}), 400

    ensure_user(user_id)

    data = request.json or {}
    bet = float(data.get("bet", 0))
    target = float(data.get("target", 0))

    if bet <= 0 or target <= 1.0:
        return jsonify({"error": "Invalid bet parameters"}), 400

    current_bal = get_balance(user_id)
    infinite = is_admin(user_id)

    if not infinite and current_bal < bet:
        return jsonify({"error": "Insufficient balance"}), 400

    multiplier = round(random.uniform(1.00, 5.00), 2)
    win = target <= multiplier

    if not infinite:
        if win:
            profit = round(bet * (target - 1), 2)
            change_balance(user_id, profit)
        else:
            profit = -bet
            change_balance(user_id, -bet)
    else:
        profit = 0

    return jsonify({
        "win": win,
        "crash_point": multiplier,
        "profit": profit if win else bet,
        "balance": get_balance(user_id),
        "infinite": infinite
    })


@app.route("/api/gift", methods=["POST"])
def api_gift():
    user_id = request_user_id()

    if not user_id:
        return jsonify({"error": "Missing user ID"}), 400

    ensure_user(user_id)

    cost = 10.0
    current_bal = get_balance(user_id)
    infinite = is_admin(user_id)

    if not infinite and current_bal < cost:
        return jsonify({"error": "Insufficient balance"}), 400

    if not infinite:
        change_balance(user_id, -cost)

    gift_name = "Mystery Gift"

    connection = db()

    connection.execute(
        """
        INSERT INTO gifts
        (user_id, gift_name, created_at)
        VALUES (?, ?, ?)
        """,
        (
            user_id,
            gift_name,
            int(time.time())
        )
    )

    connection.commit()
    connection.close()

    return jsonify({
        "ok": True,
        "gift": gift_name,
        "balance": get_balance(user_id),
        "infinite": infinite
    })


@app.route("/api/gifts")
def api_gifts():
    user_id = request_user_id()

    if not user_id:
        return jsonify({"error": "Missing user ID"}), 400

    ensure_user(user_id)

    connection = db()

    rows = connection.execute(
        """
        SELECT gift_name, created_at
        FROM gifts
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT 50
        """,
        (user_id,)
    ).fetchall()

    connection.close()

    return jsonify({
        "gifts": [dict(row) for row in rows]
    })


@app.route("/api/leaderboard")
def api_leaderboard():
    connection = db()

    rows = connection.execute(
        """
        SELECT username, first_name, balance
        FROM users
        ORDER BY balance DESC
        LIMIT 20
        """
    ).fetchall()

    connection.close()

    users = []

    for row in rows:
        users.append({
            "name": row["username"] or row["first_name"] or "Player",
            "balance": round(float(row["balance"]), 2)
        })

    return jsonify({"users": users})


# =========================
# TELEGRAM BOT
# =========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    ensure_user(
        user.id,
        user.username,
        user.first_name
    )

    keyboard = [
        [
            InlineKeyboardButton(
                "Open Epic Gift",
                web_app=WebAppInfo(url=WEBAPP_URL)
            )
        ]
    ]

    if is_admin(user.id):
        text = (
            "Welcome Admin.\n\n"
            "Your demo balance: ∞\n\n"
            "You have unlimited virtual credits."
        )
    else:
        text = (
            "Welcome to Epic Gift.\n\n"
            "You received 100 DEMO credits.\n\n"
            "This balance is virtual and has no real TON value."
        )

    await update.message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    connection = db()

    users = connection.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    gifts = connection.execute(
        "SELECT COUNT(*) AS count FROM gifts"
    ).fetchone()["count"]

    connection.close()

    await update.message.reply_text(
        f"ADMIN\n\nUsers: {users}\nGifts: {gifts}\nBalance: ∞"
    )


async def add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return

    if len(context.args) != 2:
        await update.message.reply_text(
            "Usage:\n/add USER_ID AMOUNT"
        )
        return

    try:
        user_id = int(context.args[0])
        amount = float(context.args[1])
    except ValueError:
        await update.message.reply_text("Invalid values.")
        return

    ensur
