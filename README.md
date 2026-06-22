# ⚡ Tesrora – Full Stack Exam Platform

India ka #1 Mock Test Platform — Flask + HTML + SQLite

---

## 🚀 Features
- ✅ Student Register / Login / OTP Email Verify
- ✅ Forgot Password (OTP)
- ✅ Student Dashboard
- ✅ All Tests listing (subject-wise filter)
- ✅ Live Exam with Timer
- ✅ +4 / -1 Marking (configurable)
- ✅ Anti-Cheat (Tab switch + Fullscreen detection)
- ✅ Auto-Submit on time up
- ✅ Detailed Result Page
- ✅ All India Rank (AIR)
- ✅ Leaderboard
- ✅ Certificate PDF Download (Canvas)
- ✅ WhatsApp Result Share
- ✅ Admin Dashboard with Analytics Charts
- ✅ Multi-Role: superadmin / admin / teacher / student
- ✅ Manage Users, Subjects, Tests, Questions
- ✅ Excel Bulk Question Upload
- ✅ Subscription Modal (Free / Pro / Premium)
- ✅ PWA Support (Android App)
- ✅ Profile Page

---

## 📦 Local Setup (VS Code)

```bash
# 1. Project folder mein jaayein
cd tesrora

# 2. Virtual environment banayein
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate  # Mac/Linux

# 3. Packages install karein
pip install -r requirements.txt

# 4. .env file mein apni details bharein
# (MAIL_USER aur MAIL_PASS optional hain development mein)

# 5. App chalayein
python app.py

# 6. Browser mein kholein
# http://localhost:5000
```

---

## 🔑 Default Admin Login
- **Email:** admin@tesrora.com
- **Password:** admin123

---

## 🌐 Render par Free Deploy

1. GitHub par project upload karein
2. render.com par jaayein → New Web Service
3. GitHub repo connect karein
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `gunicorn app:app`
6. Environment variable: `SECRET_KEY` = (kuch bhi secret)
7. Deploy! ✅

---

## 📧 Email OTP Setup (Gmail)
1. Gmail → Settings → Security → 2-Step Verification ON
2. App Passwords → Generate → Copy
3. `.env` mein:
   ```
   MAIL_USER=yourmail@gmail.com
   MAIL_PASS=xxxx xxxx xxxx xxxx
   ```

---

## 💳 Razorpay Payment (Optional)
- razorpay.com par account banayein
- API keys lein
- `base.html` mein `payNow()` function mein integrate karein

---

## 📱 PWA / Android App
- Chrome mein website kholein
- Menu → "Add to Home Screen"
- Bilkul app jaisa kaam karega!

---

## 📁 Project Structure
```
tesrora/
├── app.py              ← Main Flask app (routes + models)
├── requirements.txt    ← Python packages
├── .env               ← Secret keys
├── Procfile           ← Render/Railway deploy
├── render.yaml        ← One-click Render config
├── templates/
│   ├── base.html      ← Main layout + navbar + subscription modal
│   ├── index.html     ← Homepage
│   ├── login.html
│   ├── register.html
│   ├── verify_otp.html
│   ├── forgot_password.html
│   ├── reset_password.html
│   ├── dashboard.html
│   ├── tests.html
│   ├── test_instructions.html
│   ├── exam.html      ← Live exam + anti-cheat + timer
│   ├── result.html    ← Score + AIR + Certificate
│   ├── leaderboard.html
│   ├── profile.html
│   ├── admin_dashboard.html ← Charts + Analytics
│   ├── admin_users.html
│   ├── admin_subjects.html
│   ├── admin_tests.html
│   ├── admin_questions.html ← Add/Bulk upload
│   └── admin_results.html
└── static/
    ├── manifest.json  ← PWA
    └── sw.js          ← Service Worker
```
