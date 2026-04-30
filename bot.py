import os
import pg8000  # v3.1
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CATEGORIES = {
    'food': 'Food', 'lunch': 'Food', 'dinner': 'Food', 'breakfast': 'Food', 'restaurant': 'Food', 'eat': 'Food',
    'transport': 'Transport', 'taxi': 'Transport', 'uber': 'Transport', 'petrol': 'Transport', 'fuel': 'Transport', 'car': 'Transport', 'bus': 'Transport',
    'shopping': 'Shopping', 'shop': 'Shopping', 'clothes': 'Shopping', 'grocery': 'Shopping', 'groceries': 'Shopping', 'lulu': 'Shopping', 'carrefour': 'Shopping',
    'health': 'Health', 'doctor': 'Health', 'pharmacy': 'Health', 'medicine': 'Health', 'clinic': 'Health',
    'entertainment': 'Entertainment', 'movie': 'Entertainment', 'cinema': 'Entertainment', 'games': 'Entertainment',
    'bills': 'Bills', 'bill': 'Bills', 'electricity': 'Bills', 'water': 'Bills', 'internet': 'Bills', 'phone': 'Bills',
    'cafe': 'Cafe', 'coffee': 'Cafe', 'tea': 'Cafe', 'starbucks': 'Cafe',
    'other': 'Other',
}

CAT_ICONS = {
    'Food': '🍽', 'Transport': '🚗', 'Shopping': '🛍', 'Health': '💊',
    'Entertainment': '🎬', 'Bills': '💡', 'Cafe': '☕', 'Other': '📦',
}

def get_db():
    conn = pg8000.connect(
        host=os.environ['PGHOST'],
        port=int(os.environ.get('PGPORT', 5432)),
        database=os.environ['PGDATABASE'],
        user=os.environ['PGUSER'],
        password=os.environ['PGPASSWORD'],
        ssl_context=True
    )
    return conn

def init_db():
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id SERIAL PRIMARY KEY,
            date VARCHAR(10) NOT NULL,
            category VARCHAR(50) NOT NULL,
            amount NUMERIC(10,3) NOT NULL,
            notes TEXT DEFAULT '',
            created_at TIMESTAMP DEFAULT NOW()
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database ready.")

def parse_message(text):
    parts = text.strip().split()
    if len(parts) < 2:
        return None
    raw_cat = parts[0].lower()
    category = CATEGORIES.get(raw_cat, parts[0].capitalize())
    try:
        amount = float(parts[1])
        notes = ' '.join(parts[2:])
    except ValueError:
        try:
            amount = float(parts[0])
            raw_cat = parts[1].lower()
            category = CATEGORIES.get(raw_cat, parts[1].capitalize())
            notes = ' '.join(parts[2:])
        except ValueError:
            return None
    if amount <= 0:
        return None
    return {'category': category, 'amount': amount, 'notes': notes}

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = (
        "👋 *Spending Tracker*\n\n"
        "Log an expense by typing:\n"
        "`Category Amount Notes`\n\n"
        "*Examples:*\n"
        "• `Coffee 1.5`\n"
        "• `Groceries 12 lulu`\n"
        "• `Petrol 8.5 fill up`\n"
        "• `Transport 2.5 taxi`\n\n"
        "*Commands:*\n"
        "/today — today's expenses\n"
        "/summary — this month's summary\n"
        "/last — last 5 expenses\n"
        "/delete — delete last expense\n"
        "/help — show this message"
    )
    await update.message.reply_text(msg, parse_mode='Markdown')

async def today_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT category, amount, notes FROM expenses WHERE date = %s ORDER BY created_at", (today,))
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("No expenses logged today yet!")
        return
    total = sum(float(r[1]) for r in rows)
    lines = [f"📅 *Today — {today}*\n"]
    for r in rows:
        icon = CAT_ICONS.get(r[0], '📦')
        note = f" — {r[2]}" if r[2] else ''
        lines.append(f"{icon} {r[0]}: BD {float(r[1]):.3f}{note}")
    lines.append(f"\n💰 *Total: BD {total:.3f}*")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    month = now.strftime('%Y-%m')
    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT category, SUM(amount) as total, COUNT(*) as count
        FROM expenses WHERE date LIKE %s
        GROUP BY category ORDER BY total DESC
    """, (month + '%',))
    rows = cur.fetchall()
    cur.execute("SELECT SUM(amount), COUNT(*) FROM expenses WHERE date LIKE %s", (month + '%',))
    totals = cur.fetchone()
    conn.close()
    if not rows:
        await update.message.reply_text("No expenses this month yet!")
        return
    lines = [f"📊 *{now.strftime('%B %Y')} Summary*\n"]
    for r in rows:
        icon = CAT_ICONS.get(r[0], '📦')
        lines.append(f"{icon} {r[0]}: BD {float(r[1]):.3f} ({r[2]} items)")
    lines.append(f"\n💰 *Total: BD {float(totals[0]):.3f}*")
    lines.append(f"🧾 {totals[1]} transactions")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def last_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT category, amount, notes, date FROM expenses ORDER BY created_at DESC LIMIT 5")
    rows = cur.fetchall()
    conn.close()
    if not rows:
        await update.message.reply_text("No expenses yet!")
        return
    lines = ["🕐 *Last 5 expenses*\n"]
    for r in rows:
        icon = CAT_ICONS.get(r[0], '📦')
        note = f" — {r[2]}" if r[2] else ''
        lines.append(f"{icon} {r[0]}: BD {float(r[1]):.3f}{note} _{r[3]}_")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = get_db()
    cur = conn.cursor()
    cur.execute("SELECT id, category, amount, date FROM expenses ORDER BY created_at DESC LIMIT 1")
    row = cur.fetchone()
    if not row:
        await update.message.reply_text("Nothing to delete!")
        conn.close()
        return
    cur.execute("DELETE FROM expenses WHERE id = %s", (row[0],))
    conn.commit()
    conn.close()
    icon = CAT_ICONS.get(row[1], '📦')
    await update.message.reply_text(
        f"🗑 *Deleted:*\n{icon} {row[1]}: BD {float(row[2]):.3f} — {row[3]}",
        parse_mode='Markdown'
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    parsed = parse_message(text)
    if not parsed:
        await update.message.reply_text(
            "❓ Format: `Category Amount`\nExample: `Coffee 1.5`",
            parse_mode='Markdown'
        )
        return
    date = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO expenses (date, category, amount, notes) VALUES (%s, %s, %s, %s)",
        (date, parsed['category'], parsed['amount'], parsed['notes'])
    )
    conn.commit()
    conn.close()
    icon = CAT_ICONS.get(parsed['category'], '📦')
    reply = (
        f"✅ *Logged!*\n"
        f"📅 {date}\n"
        f"{icon} {parsed['category']}\n"
        f"💰 BD {parsed['amount']:.3f}\n"
    )
    if parsed['notes']:
        reply += f"📝 {parsed['notes']}"
    await update.message.reply_text(reply, parse_mode='Markdown')

def main():
    init_db()
    token = os.environ['TELEGRAM_TOKEN']
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', start))
    app.add_handler(CommandHandler('today', today_cmd))
    app.add_handler(CommandHandler('summary', summary_cmd))
    app.add_handler(CommandHandler('last', last_cmd))
    app.add_handler(CommandHandler('delete', delete_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started...")
    app.run_polling()

if __name__ == '__main__':
    main()
