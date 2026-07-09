# اول_از_همه_این_فایل_را_بخوان

**خوش آمدید!** این پروژه کمک می‌کند موزیک‌های Spotify را به YouTube Music منتقل کنید؛ رایگان، محلی و خصوصی.

![Animated transfer flow](assets/transfer-flow-animated.svg)

## انتخاب زبان

- فارسی: `docs/READ_ME_FIRST.fa.md`
- English: `docs/READ_ME_FIRST.md`

## خلاصه ۶۰ ثانیه‌ای

- گرفتن خروجی کتابخانه Spotify با Exportify
- وارد کردن خروجی به بکاپ `spyt`
- احراز هویت YouTube Music (یک بار)
- اجرای مهاجرت و تکمیل خودکار آهنگ‌های جا مانده
- بررسی آهنگ‌های unmatched در پایان

## شروع سریع (ویندوز)

1. نصب Python از [python.org](https://www.python.org/downloads/) و فعال کردن گزینه **Add python.exe to PATH**
2. اجرای `scripts\install.bat`
3. اجرای `scripts\Start Spyt.bat`
4. دنبال کردن مراحل راهنما داخل ترمینال

اگر Spotify یا Google در کشور شما فیلتر است، اول VPN را روشن کنید.

## اجرای دستی از ترمینال

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -e .
copy .env.example .env

python -m spyt export-spotify
python -m spyt import-exportify path\to\export.zip
python -m spyt setup-ytmusic
python -m spyt migrate-playlists --from-backup
```

## اگر تازه‌کار هستید، این ترتیب را بخوانید

1. `docs/GETTING_STARTED.md` (راهنمای ساده)
2. `README.md` (مستندات کامل + دستورات)
3. `docs/HANDOVER.md` (وضعیت پروژه و معماری)

## مشکلات رایج

- **خطای ورود YouTube Music:** دوباره `python -m spyt setup-ytmusic` را با یک درخواست تازه `youtubei/v1/browse` اجرا کنید.
- **بعضی آهنگ‌ها منتقل نشدند:** refill را اجرا کنید و فایل `.spyt/unmatched.json` را بررسی کنید.
- **پلی‌لیست تکراری در YTM:** کامل‌ترین پلی‌لیست را نگه دارید، بقیه را حذف کنید، سپس refill بزنید.

## ساختار مخزن

```text
spyt/
├── spyt/                # پکیج اصلی پایتون
├── scripts/             # اسکریپت‌های کمکی ویندوز
├── docs/                # مستندات کاربر و نگهداری پروژه
└── .spyt/               # داده‌های زمان اجرا (gitignored)
```

اگر اولین بار است از پروژه استفاده می‌کنید، با `scripts\Start Spyt.bat` شروع کنید.
