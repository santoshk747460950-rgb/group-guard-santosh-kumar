import telebot
import sqlite3
import os
from flask import Flask
from threading import Thread, Timer

# Apna bot token yahan daalein ya Render environment variables me set karein
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8863140400:AAEN0HVEgFq1x5t-DDCy96pJMRzzTtAzUP8')
bot = telebot.TeleBot(BOT_TOKEN)

MUST_JOIN_GROUP = '@current_affairs_live_quiz'

# Render ke liye ek simple web server
app = Flask(__name__)

# Database setup karna (Users ka data save rakhne ke liye)
def init_db():
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS user_stats
                 (user_id INTEGER, chat_id INTEGER, added_count INTEGER,
                 PRIMARY KEY(user_id, chat_id))''')
    conn.commit()
    conn.close()

init_db()

# User ne kitne member add kiye ye check karne ka function
def get_added_count(user_id, chat_id):
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('SELECT added_count FROM user_stats WHERE user_id=? AND chat_id=?', (user_id, chat_id))
    result = c.fetchone()
    conn.close()
    return result[0] if result else 0

# User ka add count badhane ka function
def increment_added_count(user_id, chat_id, count=1):
    current = get_added_count(user_id, chat_id)
    new_count = current + count
    conn = sqlite3.connect('bot_data.db')
    c = conn.cursor()
    c.execute('INSERT OR REPLACE INTO user_stats (user_id, chat_id, added_count) VALUES (?, ?, ?)', (user_id, chat_id, new_count))
    conn.commit()
    conn.close()
    return new_count

# Check karna ki user admin hai ya nahi (Admins par rule laagu nahi hoga)
def is_admin(message):
    if message.chat.type == 'private':
        return True
    try:
        admins = bot.get_chat_administrators(message.chat.id)
        admin_ids = [admin.user.id for admin in admins]
        return message.from_user.id in admin_ids
    except:
        return False

# Warning message delete karne ka function
def delete_warning(chat_id, message_id):
    try:
        bot.delete_message(chat_id, message_id)
    except:
        pass

# Jab koi naya member add hota hai tab ye function chalega
@bot.message_handler(content_types=['new_chat_members'])
def handle_new_members(message):
    adder_id = message.from_user.id
    adder_name = message.from_user.first_name
    chat_id = message.chat.id

    added_users = 0
    for member in message.new_chat_members:
        # CHECK: Agar kisi ne bot ko add kiya hai
        if member.id == bot.get_me().id:
            bot.send_message(chat_id, "Hello!")
                
        # Khud ko ya bot ko add karne par count nahi badhega
        elif member.id != bot.get_me().id and member.id != adder_id:
            added_users += 1

    if added_users > 0:
        new_total = increment_added_count(adder_id, chat_id, added_users)
        if new_total >= 5:
            bot.send_message(chat_id, f"🎉 Badhai ho {adder_name}! Aapne {new_total} members add kar diye hain. Ab agar aapne hamara main group join kiya hai to aap message kar sakte hain.")
        else:
            bot.send_message(chat_id, f"👍 {adder_name} ne {added_users} naye member add kiye. Total: {new_total}/5. Message karne ke liye {5 - new_total} aur members add karein.")

# Har ek message par ye check hoga
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'])
def handle_all_messages(message):
    if message.chat.type == 'private':
        bot.reply_to(message, "Bhai, ye bot sirf groups me kaam karta hai. Mujhe kisi group me add karein aur admin banayein.")
        return

    # Admins kuch bhi message kar sakte hain
    if is_admin(message):
        return 

    user_id = message.from_user.id
    chat_id = message.chat.id
    username_or_name = message.from_user.username or message.from_user.first_name

    # CONDITION 1: Check karna ki user ne @current_affairs_live_quiz join kiya hai ya nahi
    try:
        chat_member = bot.get_chat_member(MUST_JOIN_GROUP, user_id)
        if chat_member.status in ['left', 'kicked']:
            bot.delete_message(chat_id, message.message_id)
            warning_text = f"⚠️ @{username_or_name}, yahan message karne se pehle hamara main group {MUST_JOIN_GROUP} join karna zaroori hai!"
            warning_msg = bot.send_message(chat_id, warning_text)
            Timer(7.0, delete_warning, args=(chat_id, warning_msg.message_id)).start()
            return # Agar join nahi kiya to aage mat check karo
    except Exception as e:
        print(f"Error checking channel membership: {e}")
        # Agar error aaye (jaise bot us group me admin nahi hai) to hum error log karenge
        pass

    # CONDITION 2: Check karna ki 5 member add kiye hain ya nahi (Purana Logic)
    count = get_added_count(user_id, chat_id)
    if count < 5:
        try:
            bot.delete_message(chat_id, message.message_id)
            warning_text = f"⚠️ @{username_or_name}, group me message karne ke liye pehle 5 members add karein! (Aapne {count}/5 add kiye hain)"
            warning_msg = bot.send_message(chat_id, warning_text)
            
            # 7 seconds baad warning message automatic delete ho jayega taaki group me spam na ho
            Timer(7.0, delete_warning, args=(chat_id, warning_msg.message_id)).start()
        except Exception as e:
            print(f"Error: Bot ko message delete karne ki permission nahi hai - {e}")

# Render par Web Service ko zinda rakhne ke liye Route
@app.route('/')
def index():
    return "Telegram Bot Render par successfully chal raha hai!"

def run_flask():
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    # Flask ko alag thread me run karna
    flask_thread = Thread(target=run_flask)
    flask_thread.start()
    
    print("Bot start ho raha hai...")
    # Bot ko lagataar chalane ke liye
    bot.infinity_polling()
