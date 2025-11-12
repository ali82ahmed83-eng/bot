import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters
from telegram.request import HTTPXRequest

# 🎯 توكن البوت
TOKEN = "8522161268:AAGXC8Vq1O79-M5mQuUZ8RqHLYkPG3b9rrg"

# 🔗 روابط مهمة
ADMIN_LINK = "https://t.me/alnajm_ali"
NEXT_COMP_LINK = "t.me/ai_go_vip"

# 🧮 بيانات المسابقة
participants = {}  # {user_id: {"name": str, "username": str}}
participants_queue = asyncio.Queue()
message_queue = asyncio.Queue()
start_time = None
duration = timedelta(minutes=10)
end_time = None
winner_announced = False
competition_started = False
competition_ended = False

# 📨 إرسال رسالة آمنة
async def send_safe(bot, chat_id, text):
    try:
        await bot.send_message(chat_id=chat_id, text=text)
        return True
    except Exception as e:
        err = str(e).lower()
        if "forbidden" in err or "blocked" in err or "chat not found" in err:
            return False
        print(f"⚠️ خطأ أثناء إرسال الرسالة إلى {chat_id}: {e}")
        return False

# 🔄 معالجة رسائل Queue تدريجيًا
async def process_messages(bot):
    while True:
        chat_id, text = await message_queue.get()
        await send_safe(bot, chat_id, text)
        await asyncio.sleep(0.2)
        message_queue.task_done()

# 🔄 معالجة المشاركين Queue وتخزينهم في ملف
async def process_participants():
    while True:
        user_id, data = await participants_queue.get()
        if user_id not in participants:
            participants[user_id] = data
            print(f"✅ تم تسجيل {data['name']} ({user_id}) — الإجمالي: {len(participants)}")

            # حفظ المشارك في ملف participants.txt
            try:
                with open("participants.txt", "a", encoding="utf-8") as f:
                    f.write(f"{user_id},{data['name']},{data['username']}\n")
            except Exception as e:
                print(f"❌ خطأ في كتابة المشارك في الملف: {e}")

        participants_queue.task_done()

# ⏱ تحديث الوقت المتبقي وإرسال للمشاركين
async def update_status(bot):
    global end_time, competition_ended
    while competition_started:
        now = datetime.now()
        remaining = end_time - now
        
        # إذا انتهى الوقت، نعلن الفائز
        if remaining.total_seconds() <= 0:
            print("⏰ انتهى الوقت، سيتم إعلان الفائز الآن...")
            competition_ended = True
            await announce_winner(bot)
            break

        # حساب الوقت المتبقي
        minutes = int(remaining.total_seconds() // 60)
        seconds = int(remaining.total_seconds() % 60)
        
        msg = (
            f"⏱ الوقت المتبقي: {minutes} دقيقة و {seconds} ثانية\n"
            f"👥 عدد المشاركين: {len(participants)}\n"
            f"🎯 سيتم اختيار فائز واحد قريبًا!"
        )

        # إرسال الرسالة لجميع المشاركين
        for uid in participants.keys():
            await message_queue.put((uid, msg))

        await asyncio.sleep(30)

# 🎉 إعلان الفائز
async def announce_winner(context_or_bot):
    global winner_announced, participants, competition_started
    if winner_announced or not participants:
        print("❌ لا يوجد مشاركين أو تم الإعلان مسبقاً")
        return

    winner_announced = True
    competition_started = False
    winner_id = random.choice(list(participants.keys()))
    winner_data = participants[winner_id]

    winner_name = winner_data["name"]
    username = winner_data["username"]
    
    # عرض المعلومات بشكل صحيح
    if username:
        user_link = f"@{username}"
        user_profile = f"https://t.me/{username}"
    else:
        user_link = "لا يوجد معرف"
        user_profile = f"المعرف: {winner_id}"

    winner_msg = (
        f"🎉 تهانينا {winner_name}! لقد فزت في المسابقة 🏆\n\n"
        f"📩 تواصل مع المشرف لاستلام جائزتك:\n{ADMIN_LINK}"
    )

    loser_msg = (
        "😔 حظًا أوفر! لم تفز هذه المرة.\n"
        f"تابع المسابقة القادمة على:\n{NEXT_COMP_LINK}"
    )

    await message_queue.put((winner_id, winner_msg))
    for uid in participants:
        if uid != winner_id:
            await message_queue.put((uid, loser_msg))

    summary = (
        "🎊 انتهت المسابقة!\n\n"
        "🏆 الفائز:\n"
        f"👤 الاسم: {winner_name}\n"
        f"🔗 اسم المستخدم: {user_link}\n"
        f"📎 الرابط: {user_profile}\n"
        f"🆔 المعرف: {winner_id}\n\n"
        f"👥 عدد المشاركين: {len(participants)}"
    )

    bot = context_or_bot.bot if hasattr(context_or_bot, "bot") else context_or_bot
    try:
        await bot.send_message(chat_id="@alnajm_ali", text=summary)
        print("✅ تم إرسال النتيجة للمشرف")
    except Exception as e:
        print(f"❌ فشل إرسال النتيجة للمشرف: {e}")

    print(summary)
    participants.clear()

# 🚀 بدء المسابقة (تعمل مرة واحدة عند أول مشارك)
def start_competition():
    global start_time, end_time, competition_started, competition_ended
    if competition_started:
        return
    
    competition_started = True
    competition_ended = False
    start_time = datetime.now()
    end_time = start_time + duration
    print(f"🚀 بدأت المسابقة | المدة: {duration.seconds // 60} دقيقة | ستنتهي في: {end_time.strftime('%H:%M:%S')}")

# 🎯 معالجة جميع الرسائل (بدلاً من /start فقط)
async def handle_all_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # إذا كانت المسابقة انتهت
    if competition_ended:
        ended_message = (
            "❌ المسابقة الحالية انتهت\n\n"
            "🎊 تم إعلان الفائز وإرسال الجوائز\n\n"
            "📢 تابع القناة لمعرفة موعد المسابقة القادمة:\n"
            f"{NEXT_COMP_LINK}"
        )
        keyboard = [[InlineKeyboardButton("📢 قناة المسابقات", url=NEXT_COMP_LINK)]]
        await update.message.reply_text(
            ended_message, 
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
        return

    user_id = user.id

    if user_id in participants:
        await update.message.reply_text(f"✅ أنت مشارك بالفعل يا {user.first_name}!")
        return

    keyboard = [[InlineKeyboardButton("🎯 اضغط هنا للمشاركة", callback_data="join")]]
    
    # حساب الوقت المتبقي إذا كانت المسابقة جارية
    remaining_text = ""
    if competition_started and end_time:
        now = datetime.now()
        remaining = end_time - now
        if remaining.total_seconds() > 0:
            minutes = int(remaining.total_seconds() // 60)
            seconds = int(remaining.total_seconds() % 60)
            remaining_text = f"\n⏰ الوقت المتبقي: {minutes} دقيقة و {seconds} ثانية"
        else:
            remaining_text = "\n⏰ المسابقة انتهت، جاري إعلان الفائز..."
    
    welcome = (
        "🎉 مرحبًا بك في المسابقة!\n\n"
        f"⏰ مدة المسابقة: {duration.seconds // 60} دقيقة\n"
        "🏆 فائز واحد عشوائي"
        f"{remaining_text}\n\n"
        "اضغط على الزر أدناه للمشاركة 👇"
    )
    await update.message.reply_text(welcome, reply_markup=InlineKeyboardMarkup(keyboard))

# 🎯 المشاركة
async def join_competition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user
    user_id = user.id

    # إذا كانت المسابقة انتهت
    if competition_ended:
        ended_message = (
            "❌ المسابقة الحالية انتهت\n\n"
            "🎊 تم إعلان الفائز وإرسال الجوائز\n\n"
            "📢 تابع القناة لمعرفة موعد المسابقة القادمة:\n"
            f"{NEXT_COMP_LINK}"
        )
        keyboard = [[InlineKeyboardButton("📢 قناة المسابقات", url=NEXT_COMP_LINK)]]
        await query.message.edit_text(
            ended_message,
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True
        )
        return

    # إذا كانت المسابقة جارية ولكن انتهى الوقت
    if competition_started and end_time and datetime.now() >= end_time:
        await query.answer("❌ المسابقة انتهت، لا يمكنك المشاركة الآن!", show_alert=True)
        return

    if user_id in participants:
        await query.answer("✅ أنت مشارك بالفعل!", show_alert=True)
        return

    await participants_queue.put((user_id, {"name": user.first_name, "username": user.username or ""}))
    await query.answer("🎉 تم تسجيلك بنجاح!", show_alert=True)

    # بدء المسابقة إذا كانت هذه هي أول مشاركة
    if not competition_started:
        start_competition()
        asyncio.create_task(update_status(context.bot))

# ⚙️ تشغيل البوت
def main():
    request = HTTPXRequest(connect_timeout=30, read_timeout=30)
    app = Application.builder().token(TOKEN).request(request).build()

    # إضافة المعالجات
    app.add_handler(CommandHandler("start", handle_all_messages))
    app.add_handler(CallbackQueryHandler(join_competition))
    
    # معالج لجميع الرسائل النصية
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_all_messages))

    loop = asyncio.get_event_loop()
    loop.create_task(process_participants())
    loop.create_task(process_messages(app.bot))

    print("🤖 البوت يعمل الآن (أي رسالة تعمل مثل /start)")
    print(f"⏰ مدة المسابقة: {duration.seconds // 60} دقيقة من بداية أول مشاركة")
    app.run_polling()

if __name__ == "__main__":
    main()