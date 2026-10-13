import os, re, time, threading, requests

TOKEN = os.environ['BOT_TOKEN']
API = f'https://tapi.bale.ai/bot{TOKEN}'
CHANNEL_ID = int(os.getenv('CHANNEL_ID', '5655498921'))
OWNER_ID = int(os.getenv('OWNER_ID', '0'))  # Required for editing/publishing
TGJU = 'https://www.tgju.org/profile/geram18'

session = requests.Session()
editing = {}  # private chat id -> channel message id
last_price = None
last_update = 0
lock = threading.Lock()


def api(method, data, timeout=15):
    response = session.post(f'{API}/{method}', json=data, timeout=timeout)
    result = response.json()
    if not result.get('ok'):
        raise RuntimeError(f'{method}: {result}')
    return result.get('result')


def digits(value):
    return str(value or '').translate(str.maketrans('۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩٫', '01234567890123456789.'))


def product(text):
    t = digits(text)
    w = re.search(r'وزن\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)', t)
    a = re.search(r'اجرت(?:\s*فقط)?\s*[:：]?\s*([0-9]+(?:\.[0-9]+)?)', t)
    if not (w and a):
        return None
    return float(w.group(1)), float(a.group(1))


def keyboard(weight, labor):
    return {'inline_keyboard': [
        [{'text': '💰 مشاهده قیمت روز این محصول', 'callback_data': f'price:{weight:g}:{labor:g}'}],
        [{'text': '💰 مشاهده قیمت طلا', 'callback_data': 'gold'}]
    ]}


def gold_worker():
    global last_price, last_update
    while True:
        try:
            response = requests.get(TGJU, headers={'User-Agent': 'Mozilla/5.0'}, timeout=(4, 8))
            response.raise_for_status()
            match = re.search(r'data-col=["\']info\.last_trade\.PDrCotVal["\'][^>]*>\s*([0-9۰-۹٠-٩,٬]+)', response.text, re.I)
            if not match:
                raise ValueError('TGJU price field not found')
            rial = int(digits(match.group(1)).replace(',', '').replace('٬', ''))
            if not 100_000_000 < rial < 1_000_000_000:
                raise ValueError('Invalid rial value')
            with lock:
                last_price = rial // 10
                last_update = time.time()
            print('GOLD UPDATED', last_price, flush=True)
        except Exception as exc:
            print('GOLD ERROR', repr(exc), flush=True)
        time.sleep(60)


def send(chat_id, text):
    return api('sendMessage', {'chat_id': chat_id, 'text': text})


def callback(cb):
    cid = cb.get('id')
    data = cb.get('data') or ''
    with lock:
        gram, timestamp = last_price, last_update
    if not gram or time.time() - timestamp > 900:
        text = '⚠️ نرخ معتبر و تازه طلا فعلاً در دسترس نیست. لطفاً بعداً امتحان کنید.'
    elif data == 'gold':
        text = f'💰 قیمت طلای ۱۸ عیار\n\n🟡 هر گرم: {gram:,} تومان'
    elif data.startswith('price:'):
        try:
            _, w, a = data.split(':')
            w, a = float(w), float(a)
            total = round(w * gram * (1 + a / 100))
            text = (f'✨ قیمت روز محصول\n\n🟡 طلای ۱۸ عیار: {gram:,} تومان\n'
                    f'⚖️ وزن: {w:g} گرم\n💎 اجرت: {a:g}٪\n\n💰 مبلغ نهایی: {total:,} تومان')
        except (ValueError, TypeError):
            text = 'اطلاعات این دکمه نامعتبر است.'
    else:
        text = 'دکمه نامعتبر است.'
    api('answerCallbackQuery', {'callback_query_id': cid, 'text': text, 'show_alert': True})


def edit_existing(chat_id, message_id, msg):
    caption = msg.get('caption') or msg.get('text') or ''
    photos = msg.get('photo') or []
    parsed = product(caption) if caption else None
    if caption and not parsed:
        send(chat_id, '❌ در متن جدید «وزن» و «اجرت» را بنویس. مثال:\nوزن: ۰.۳۰ گرم\nاجرت فقط: ۵٪')
        return
    if not caption and not photos:
        send(chat_id, 'متن کامل جدید یا عکس جدید (با کپشن کامل) بفرست.')
        return
    # A new photo without caption retains the old caption, but its old keyboard is kept.
    # If caption is supplied, the callback data is updated to match it.
    markup = keyboard(*parsed) if parsed else None
    if photos:
        payload = {'chat_id': CHANNEL_ID, 'message_id': message_id,
                   'media': {'type': 'photo', 'media': photos[-1]['file_id']}}
        if caption:
            payload['media']['caption'] = caption
        if markup:
            payload['reply_markup'] = markup
        api('editMessageMedia', payload)
    else:
        api('editMessageCaption', {'chat_id': CHANNEL_ID, 'message_id': message_id,
                                   'caption': caption, 'reply_markup': markup})
    editing.pop(chat_id, None)
    send(chat_id, '✅ پست قبلی کانال ویرایش شد. اگر دکمه قیمت داشت، مشخصاتش هم اصلاح شد.')


def handle_message(msg):
    chat = msg.get('chat') or {}
    if chat.get('type') != 'private':
        return
    chat_id = chat.get('id')
    sender_id = (msg.get('from') or {}).get('id')
    text = (msg.get('text') or '').strip()
    if text == '/id':
        send(chat_id, f'شناسه عددی حساب شما: {sender_id}\nاین عدد را به‌عنوان OWNER_ID در GitHub Secrets ثبت کن.')
        return
    if not OWNER_ID:
        send(chat_id, '⚠️ ابتدا Secret با نام OWNER_ID را در GitHub تنظیم کن. برای دریافت عدد /id را بفرست.')
        return
    if sender_id != OWNER_ID:
        send(chat_id, '⛔ دسترسی انتشار و ویرایش فقط برای مدیر فروشگاه است.')
        return
    if text == '/cancel':
        editing.pop(chat_id, None)
        send(chat_id, 'ویرایش لغو شد.')
        return
    if text.startswith('/edit'):
        parts = digits(text).split()
        if len(parts) != 2 or not parts[1].isdigit():
            send(chat_id, 'برای ویرایش بنویس:\n/edit 176\nبه جای 176 شناسه پیام پست کانال را وارد کن.')
            return
        editing[chat_id] = int(parts[1])
        send(chat_id, '✏️ حالا کپشن کامل جدید یا عکس جدید را بفرست. برای انصراف /cancel را بزن.\n'
                      'توجه: اگر عکس را تغییر می‌دهی، بهتر است کپشن کامل را هم همراه آن بفرستی.')
        return
    if chat_id in editing:
        try:
            edit_existing(chat_id, editing[chat_id], msg)
        except Exception as exc:
            print('EDIT ERROR', repr(exc), flush=True)
            send(chat_id, '❌ ویرایش انجام نشد. ممکن است بله تغییر عکس این نوع پست را نپذیرد یا شناسه پیام اشتباه باشد. خطا در Actions ثبت شد.')
        return
    caption = msg.get('caption') or msg.get('text') or ''
    parsed = product(caption)
    photos = msg.get('photo') or []
    if parsed and photos:
        try:
            result = api('sendPhoto', {'chat_id': CHANNEL_ID, 'photo': photos[-1]['file_id'],
                                       'caption': caption, 'reply_markup': keyboard(*parsed)})
            mid = result.get('message_id') if isinstance(result, dict) else None
            send(chat_id, f'✅ محصول منتشر شد.\nشناسه پیام: {mid}\nبرای ویرایش بعدی: /edit {mid}')
        except Exception as exc:
            print('PUBLISH ERROR', repr(exc), flush=True)
            send(chat_id, '❌ انتشار ناموفق بود. گزارش خطا را در GitHub Actions ببین.')
    else:
        send(chat_id, 'برای انتشار: عکس با کپشن وزن و اجرت بفرست.\nبرای ویرایش: /edit شماره_پیام\nبرای دریافت شناسه خودت: /id')


def main():
    api('deleteWebhook', {'drop_pending_updates': False})
    threading.Thread(target=gold_worker, daemon=True).start()
    offset = 0
    print('SALAR EDIT BOT STARTED', flush=True)
    while True:
        try:
            updates = api('getUpdates', {'offset': offset, 'timeout': 20}, timeout=30)
            for update in updates or []:
                offset = max(offset, update['update_id'] + 1)
                try:
                    if update.get('callback_query'):
                        callback(update['callback_query'])
                    else:
                        msg = update.get('message') or update.get('edited_message')
                        if msg:
                            handle_message(msg)
                except Exception as exc:
                    print('UPDATE ERROR', repr(exc), flush=True)
        except Exception as exc:
            print('POLL ERROR', repr(exc), flush=True)
            time.sleep(2)


if __name__ == '__main__':
    main()
