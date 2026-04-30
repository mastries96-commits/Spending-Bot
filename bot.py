import os
import csv
import logging
from datetime import datetime
from telegram import Update
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DATA_FILE = '/app/data/expenses.csv'

CATEGORIES = {
    'food': 'Food', 'lunch': 'Food', 'dinner': 'Food', 'breakfast': 'Food', 'restaurant': 'Food',
    'transport': 'Transport', 'taxi': 'Transport', 'uber': 'Transport', 'petrol': 'Transport', 'fuel': 'Transport', 'bus': 'Transport',
    'shopping': 'Shopping', 'shop': 'Shopping', 'clothes': 'Shopping', 'grocery': 'Shopping', 'groceries': 'Shopping', 'lulu': 'Shopping',
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

def init_storage():
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['date', 'category', 'amount', 'notes'])
    logger.info("Storage ready.")

def read_expenses():
    if not os.path.exists(DATA_FILE):
        return []
    with open(DATA_FILE, 'r') as f:
        reader = csv.DictReader(f)
        return list(reader)

def write_expense(date, category, amount, notes):
    with open(DATA_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([date, category, amount, notes])

def delete_last():
    rows = read_expenses()
    if not rows:
        return None
    last = rows[-1]
    with open(DATA_FILE, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['date', 'category', 'amount', 'notes'])
        for row in rows[:-1]:
            writer.writerow([row['date'], row['category'], row['amount'], row['notes']])
    return last

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
    rows = [r for r in read_expenses() if r['date'] == today]
    if not rows:
        await update.message.reply_text("No expenses logged today yet!")
        return
    total = sum(float(r['amount']) for r in rows)
    lines = [f"📅 *Today — {today}*\n"]
    for r in rows:
        icon = CAT_ICONS.get(r['category'], '📦')
        note = f" — {r['notes']}" if r['notes'] else ''
        lines.append(f"{icon} {r['category']}: BD {float(r['amount']):.3f}{note}")
    lines.append(f"\n💰 *Total: BD {total:.3f}*")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def summary_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    now = datetime.now()
    month = now.strftime('%Y-%m')
    rows = [r for r in read_expenses() if r['date'].startswith(month)]
    if not rows:
        await update.message.reply_text("No expenses this month yet!")
        return
    total = sum(float(r['amount']) for r in rows)
    cats = {}
    for r in rows:
        cats[r['category']] = cats.get(r['category'], 0) + float(r['amount'])
    lines = [f"📊 *{now.strftime('%B %Y')} Summary*\n"]
    for cat, amt in sorted(cats.items(), key=lambda x: -x[1]):
        icon = CAT_ICONS.get(cat, '📦')
        lines.append(f"{icon} {cat}: BD {amt:.3f}")
    lines.append(f"\n💰 *Total: BD {total:.3f}*")
    lines.append(f"🧾 {len(rows)} transactions")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def last_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    rows = read_expenses()[-5:]
    if not rows:
        await update.message.reply_text("No expenses yet!")
        return
    lines = ["🕐 *Last 5 expenses*\n"]
    for r in reversed(rows):
        icon = CAT_ICONS.get(r['category'], '📦')
        note = f" — {r['notes']}" if r['notes'] else ''
        lines.append(f"{icon} {r['category']}: BD {float(r['amount']):.3f}{note} _{r['date']}_")
    await update.message.reply_text('\n'.join(lines), parse_mode='Markdown')

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    row = delete_last()
    if not row:
        await update.message.reply_text("Nothing to delete!")
        return
    icon = CAT_ICONS.get(row['category'], '📦')
    await update.message.reply_text(
        f"🗑 *Deleted:*\n{icon} {row['category']}: BD {float(row['amount']):.3f} — {row['date']}",
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
    write_expense(date, parsed['category'], parsed['amount'], parsed['notes'])
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
    init_storage()
    token = os.environ['TELEGRAM_TOKEN']
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CommandHandler('help', start))
    app.add_handler(CommandHandler('today', today_cmd))
    app.add_handler(CommandHandler('summary', summary_cmd))
    app.add_handler(CommandHandler('last', last_cmd))
    app.add_handler(CommandHandler('delete', delete_cmd))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot started!")
    app.run_polling()

if __name__ == '__main__':
    main()
