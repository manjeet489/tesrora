from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os, json, random, string, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'tesrora-secret-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///tesrora.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

db = SQLAlchemy(app)

# ─── MODELS ───────────────────────────────────────────────
class User(db.Model):
    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)
    email         = db.Column(db.String(100), unique=True, nullable=False)
    password      = db.Column(db.String(200), nullable=False)
    role          = db.Column(db.String(20), default='student')  # student/teacher/admin/superadmin
    is_verified   = db.Column(db.Boolean, default=False)
    otp           = db.Column(db.String(6))
    otp_expiry    = db.Column(db.DateTime)
    subscription  = db.Column(db.String(20), default='free')  # free/pro/premium
    sub_expiry    = db.Column(db.DateTime)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)
    avatar        = db.Column(db.String(200), default='')
    phone         = db.Column(db.String(15), default='')

class Subject(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    icon        = db.Column(db.String(50), default='book')
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'))

class TestPackage(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(200), nullable=False)
    subject_id  = db.Column(db.Integer, db.ForeignKey('subject.id'))
    description = db.Column(db.Text)
    price       = db.Column(db.Float, default=0)
    is_free     = db.Column(db.Boolean, default=True)
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'))

class Test(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    title        = db.Column(db.String(200), nullable=False)
    subject_id   = db.Column(db.Integer, db.ForeignKey('subject.id'))
    package_id   = db.Column(db.Integer, db.ForeignKey('test_package.id'), nullable=True)
    duration     = db.Column(db.Integer, default=60)  # minutes
    total_marks  = db.Column(db.Integer, default=100)
    correct_marks= db.Column(db.Float, default=4)
    neg_marks    = db.Column(db.Float, default=1)
    is_active    = db.Column(db.Boolean, default=True)
    created_by   = db.Column(db.Integer, db.ForeignKey('user.id'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    instructions = db.Column(db.Text, default='')

class Question(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    test_id     = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    text        = db.Column(db.Text, nullable=False)
    option_a    = db.Column(db.String(500), nullable=False)
    option_b    = db.Column(db.String(500), nullable=False)
    option_c    = db.Column(db.String(500), nullable=False)
    option_d    = db.Column(db.String(500), nullable=False)
    correct     = db.Column(db.String(1), nullable=False)  # A/B/C/D
    explanation = db.Column(db.Text, default='')
    image_url   = db.Column(db.String(300), default='')
    subject_tag = db.Column(db.String(100), default='')
    created_by  = db.Column(db.Integer, db.ForeignKey('user.id'))

class Result(db.Model):
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    test_id      = db.Column(db.Integer, db.ForeignKey('test.id'), nullable=False)
    score        = db.Column(db.Float, default=0)
    correct      = db.Column(db.Integer, default=0)
    wrong        = db.Column(db.Integer, default=0)
    skipped      = db.Column(db.Integer, default=0)
    total_q      = db.Column(db.Integer, default=0)
    accuracy     = db.Column(db.Float, default=0)
    time_taken   = db.Column(db.Integer, default=0)  # seconds
    answers      = db.Column(db.Text, default='{}')  # JSON
    air_rank     = db.Column(db.Integer, default=0)
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)

class Notification(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'))
    message    = db.Column(db.Text)
    is_read    = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# ─── HELPERS ──────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if user.role not in ['admin', 'superadmin', 'teacher']:
            flash('Access denied!', 'danger')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated

def send_otp_email(email, otp, name):
    try:
        smtp_user = os.environ.get('MAIL_USER', '')
        smtp_pass = os.environ.get('MAIL_PASS', '')
        if not smtp_user:
            return True  # Skip in dev
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Tesrora - OTP Verification: {otp}'
        msg['From'] = smtp_user
        msg['To'] = email
        html = f"""
        <div style="font-family:Arial;max-width:500px;margin:auto;padding:30px;border:1px solid #eee;border-radius:10px">
          <h2 style="color:#7c3aed">Tesrora</h2>
          <p>Hello <b>{name}</b>,</p>
          <p>Your OTP for email verification:</p>
          <div style="font-size:36px;font-weight:bold;color:#7c3aed;letter-spacing:10px;text-align:center;padding:20px">{otp}</div>
          <p style="color:#888">Valid for 10 minutes. Do not share with anyone.</p>
        </div>"""
        msg.attach(MIMEText(html, 'html'))
        server = smtplib.SMTP('smtp-relay.brevo.com', 587)
        server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_user, email, msg.as_string())
        server.quit()
        return True
    except:
        return False

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def calc_air_rank(result):
    all_results = Result.query.filter_by(test_id=result.test_id).order_by(Result.score.desc()).all()
    for i, r in enumerate(all_results, 1):
        if r.id == result.id:
            return i
    return 1

# ─── AUTH ROUTES ──────────────────────────────────────────
@app.route('/')
def index():
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        if user and user.role in ['admin','superadmin','teacher']:
            return redirect(url_for('admin_dashboard'))
        return redirect(url_for('dashboard'))
    subjects = Subject.query.all()
    return render_template('index.html', subjects=subjects)

@app.route('/register', methods=['GET','POST'])
def register():
    if request.method == 'POST':
        name  = request.form['name'].strip()
        email = request.form['email'].strip().lower()
        pwd   = request.form['password']
        phone = request.form.get('phone','').strip()
        if User.query.filter_by(email=email).first():
            flash('Email already registered!', 'danger')
            return redirect(url_for('register'))
        user = User(
            name=name,
            email=email,
            password=generate_password_hash(pwd),
            phone=phone,
            is_verified=True
        )
        db.session.add(user)
        db.session.commit()
        flash('Registration successful! Please login.', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/verify-otp', methods=['GET','POST'])
def verify_otp():
    email = session.get('verify_email')
    if not email:
        return redirect(url_for('register'))
    if request.method == 'POST':
        otp_input = request.form['otp'].strip()
        user = User.query.filter_by(email=email).first()
        if user and user.otp == otp_input and user.otp_expiry > datetime.utcnow():
            user.is_verified = True
            user.otp = None
            db.session.commit()
            session.pop('verify_email', None)
            flash('Email verified! Please login.', 'success')
            return redirect(url_for('login'))
        flash('Invalid or expired OTP!', 'danger')
    return render_template('verify_otp.html', email=email)

@app.route('/resend-otp')
def resend_otp():
    email = session.get('verify_email')
    if email:
        user = User.query.filter_by(email=email).first()
        if user:
            otp = generate_otp()
            user.otp = otp
            user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()
            send_otp_email(email, otp, user.name)
            flash('New OTP sent!', 'info')
    return redirect(url_for('verify_otp'))

@app.route('/login', methods=['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        pwd   = request.form['password']
        user  = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, pwd):
            session['user_id']   = user.id
            session['user_name'] = user.name
            session['user_role'] = user.role
            if user.role in ['admin','superadmin','teacher']:
                return redirect(url_for('admin_dashboard'))
            return redirect(url_for('dashboard'))
        flash('Invalid email or password!', 'danger')
    return render_template('login.html')

@app.route('/forgot-password', methods=['GET','POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        user  = User.query.filter_by(email=email).first()
        if user:
            otp = generate_otp()
            user.otp = otp
            user.otp_expiry = datetime.utcnow() + timedelta(minutes=10)
            db.session.commit()
            send_otp_email(email, otp, user.name)
            session['reset_email'] = email
            flash('Password reset OTP sent!', 'info')
            return redirect(url_for('reset_password'))
        flash('Email not found!', 'danger')
    return render_template('forgot_password.html')

@app.route('/reset-password', methods=['GET','POST'])
def reset_password():
    email = session.get('reset_email')
    if not email:
        return redirect(url_for('forgot_password'))
    if request.method == 'POST':
        otp   = request.form['otp'].strip()
        pwd   = request.form['password']
        user  = User.query.filter_by(email=email).first()
        if user and user.otp == otp and user.otp_expiry > datetime.utcnow():
            user.password = generate_password_hash(pwd)
            user.otp = None
            db.session.commit()
            session.pop('reset_email', None)
            flash('Password reset successful! Please login.', 'success')
            return redirect(url_for('login'))
        flash('Invalid or expired OTP!', 'danger')
    return render_template('reset_password.html', email=email)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ─── STUDENT ROUTES ───────────────────────────────────────
@app.route('/dashboard')
@login_required
def dashboard():
    user     = User.query.get(session['user_id'])
    subjects = Subject.query.all()
    tests    = Test.query.filter_by(is_active=True).order_by(Test.created_at.desc()).limit(10).all()
    results  = Result.query.filter_by(user_id=user.id).order_by(Result.submitted_at.desc()).limit(5).all()
    total_tests  = Result.query.filter_by(user_id=user.id).count()
    avg_score    = db.session.query(db.func.avg(Result.score)).filter_by(user_id=user.id).scalar() or 0
    best_rank    = db.session.query(db.func.min(Result.air_rank)).filter_by(user_id=user.id).scalar() or 0
    notifications = Notification.query.filter_by(user_id=user.id, is_read=False).count()
    return render_template('dashboard.html', user=user, subjects=subjects, tests=tests,
                           results=results, total_tests=total_tests,
                           avg_score=round(avg_score,1), best_rank=best_rank,
                           notifications=notifications)

@app.route('/tests')
@login_required
def tests():
    subject_id = request.args.get('subject', type=int)
    search     = request.args.get('q','')
    query      = Test.query.filter_by(is_active=True)
    if subject_id:
        query = query.filter_by(subject_id=subject_id)
    if search:
        query = query.filter(Test.title.ilike(f'%{search}%'))
    tests    = query.order_by(Test.created_at.desc()).all()
    subjects = Subject.query.all()
    return render_template('tests.html', tests=tests, subjects=subjects,
                           selected_subject=subject_id, search=search)

@app.route('/test/<int:test_id>/instructions')
@login_required
def test_instructions(test_id):
    test = Test.query.get_or_404(test_id)
    q_count = Question.query.filter_by(test_id=test_id).count()
    return render_template('test_instructions.html', test=test, q_count=q_count)

@app.route('/test/<int:test_id>/start')
@login_required
def start_test(test_id):
    test      = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    if not questions:
        flash('No questions in this test!', 'warning')
        return redirect(url_for('tests'))
    return render_template('exam.html', test=test, questions=questions)

@app.route('/test/<int:test_id>/submit', methods=['POST'])
@login_required
def submit_test(test_id):
    test      = Test.query.get_or_404(test_id)
    questions = Question.query.filter_by(test_id=test_id).all()
    data      = request.get_json()
    answers   = data.get('answers', {})
    time_taken= data.get('time_taken', 0)

    correct = wrong = skipped = 0
    score   = 0.0
    for q in questions:
        ans = answers.get(str(q.id), '')
        if not ans:
            skipped += 1
        elif ans == q.correct:
            correct += 1
            score   += test.correct_marks
        else:
            wrong += 1
            score -= test.neg_marks

    score    = max(0, score)
    accuracy = round((correct / len(questions)) * 100, 1) if questions else 0

    result = Result(
        user_id=session['user_id'], test_id=test_id,
        score=score, correct=correct, wrong=wrong,
        skipped=skipped, total_q=len(questions),
        accuracy=accuracy, time_taken=time_taken,
        answers=json.dumps(answers)
    )
    db.session.add(result)
    db.session.commit()
    result.air_rank = calc_air_rank(result)
    db.session.commit()
    return jsonify({'result_id': result.id})

@app.route('/result/<int:result_id>')
@login_required
def result(result_id):
    res       = Result.query.get_or_404(result_id)
    test      = Test.query.get(res.test_id)
    user      = User.query.get(res.user_id)
    questions = Question.query.filter_by(test_id=res.test_id).all()
    answers   = json.loads(res.answers)
    total_students = Result.query.filter_by(test_id=res.test_id).count()
    return render_template('result.html', res=res, test=test, user=user,
                           questions=questions, answers=answers,
                           total_students=total_students)

@app.route('/leaderboard/<int:test_id>')
@login_required
def leaderboard(test_id):
    test    = Test.query.get_or_404(test_id)
    results = Result.query.filter_by(test_id=test_id).order_by(Result.score.desc()).limit(50).all()
    users   = {u.id: u for u in User.query.all()}
    return render_template('leaderboard.html', test=test, results=results, users=users,
                           current_user_id=session['user_id'])

@app.route('/profile')
@login_required
def profile():
    user    = User.query.get(session['user_id'])
    results = Result.query.filter_by(user_id=user.id).order_by(Result.submitted_at.desc()).all()
    return render_template('profile.html', user=user, results=results)

@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    user       = User.query.get(session['user_id'])
    user.name  = request.form['name'].strip()
    user.phone = request.form.get('phone','').strip()
    db.session.commit()
    session['user_name'] = user.name
    flash('Profile updated!', 'success')
    return redirect(url_for('profile'))

# ─── ADMIN ROUTES ─────────────────────────────────────────
@app.route('/admin')
@admin_required
def admin_dashboard():
    total_users    = User.query.filter_by(role='student').count()
    total_tests    = Test.query.count()
    total_results  = Result.query.count()
    total_subjects = Subject.query.count()
    recent_results = Result.query.order_by(Result.submitted_at.desc()).limit(10).all()
    users          = {u.id: u for u in User.query.all()}
    tests          = {t.id: t for t in Test.query.all()}
    avg_score      = db.session.query(db.func.avg(Result.score)).scalar() or 0
    user = User.query.get(session['user_id'])
    return render_template('admin_dashboard.html',
                           total_users=total_users, total_tests=total_tests,
                           total_results=total_results, total_subjects=total_subjects,
                           recent_results=recent_results, users=users, tests=tests,
                           avg_score=round(avg_score,1), user=user)

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.order_by(User.created_at.desc()).all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/<int:uid>/role', methods=['POST'])
@admin_required
def change_role(uid):
    user      = User.query.get_or_404(uid)
    user.role = request.form['role']
    db.session.commit()
    flash(f'Role updated to {user.role}!', 'success')
    return redirect(url_for('admin_users'))

@app.route('/admin/subjects', methods=['GET','POST'])
@admin_required
def admin_subjects():
    if request.method == 'POST':
        s = Subject(name=request.form['name'],
                    description=request.form.get('description',''),
                    icon=request.form.get('icon','book'),
                    created_by=session['user_id'])
        db.session.add(s)
        db.session.commit()
        flash('Subject added!', 'success')
    subjects = Subject.query.all()
    return render_template('admin_subjects.html', subjects=subjects)

@app.route('/admin/subjects/<int:sid>/delete')
@admin_required
def delete_subject(sid):
    Subject.query.filter_by(id=sid).delete()
    db.session.commit()
    flash('Subject deleted!', 'success')
    return redirect(url_for('admin_subjects'))

@app.route('/admin/tests', methods=['GET','POST'])
@admin_required
def admin_tests():
    if request.method == 'POST':
        t = Test(
            title=request.form['title'],
            subject_id=request.form.get('subject_id', type=int),
            duration=int(request.form.get('duration',60)),
            total_marks=int(request.form.get('total_marks',100)),
            correct_marks=float(request.form.get('correct_marks',4)),
            neg_marks=float(request.form.get('neg_marks',1)),
            instructions=request.form.get('instructions',''),
            created_by=session['user_id']
        )
        db.session.add(t)
        db.session.commit()
        flash('Test created!', 'success')
    tests    = Test.query.order_by(Test.created_at.desc()).all()
    subjects = Subject.query.all()
    users    = {u.id: u for u in User.query.all()}
    return render_template('admin_tests.html', tests=tests, subjects=subjects, users=users)

@app.route('/admin/tests/<int:tid>/delete')
@admin_required
def delete_test(tid):
    Question.query.filter_by(test_id=tid).delete()
    Result.query.filter_by(test_id=tid).delete()
    Test.query.filter_by(id=tid).delete()
    db.session.commit()
    flash('Test deleted!', 'success')
    return redirect(url_for('admin_tests'))

@app.route('/admin/tests/<int:tid>/toggle')
@admin_required
def toggle_test(tid):
    test = Test.query.get_or_404(tid)
    test.is_active = not test.is_active
    db.session.commit()
    return redirect(url_for('admin_tests'))

@app.route('/admin/questions/<int:test_id>', methods=['GET','POST'])
@admin_required
def admin_questions(test_id):
    test = Test.query.get_or_404(test_id)
    if request.method == 'POST':
        action = request.form.get('action','add')
        if action == 'add':
            q = Question(
                test_id=test_id,
                text=request.form['text'],
                option_a=request.form['option_a'],
                option_b=request.form['option_b'],
                option_c=request.form['option_c'],
                option_d=request.form['option_d'],
                correct=request.form['correct'],
                explanation=request.form.get('explanation',''),
                subject_tag=request.form.get('subject_tag',''),
                created_by=session['user_id']
            )
            db.session.add(q)
            db.session.commit()
            flash('Question added!', 'success')
        elif action == 'bulk':
            file = request.files.get('excel_file')
            if file:
                import io
                try:
                    import openpyxl
                    wb   = openpyxl.load_workbook(io.BytesIO(file.read()))
                    ws   = wb.active
                    count = 0
                    for row in ws.iter_rows(min_row=2, values_only=True):
                        if row[0]:
                            q = Question(test_id=test_id,
                                text=str(row[0]), option_a=str(row[1] or ''),
                                option_b=str(row[2] or ''), option_c=str(row[3] or ''),
                                option_d=str(row[4] or ''), correct=str(row[5] or 'A').upper(),
                                explanation=str(row[6] or ''), created_by=session['user_id'])
                            db.session.add(q)
                            count += 1
                    db.session.commit()
                    flash(f'{count} questions imported!', 'success')
                except Exception as e:
                    flash(f'Import error: {str(e)}', 'danger')
    questions = Question.query.filter_by(test_id=test_id).all()
    return render_template('admin_questions.html', test=test, questions=questions)

@app.route('/admin/questions/<int:qid>/delete')
@admin_required
def delete_question(qid):
    q = Question.query.get_or_404(qid)
    test_id = q.test_id
    db.session.delete(q)
    db.session.commit()
    flash('Question deleted!', 'success')
    return redirect(url_for('admin_questions', test_id=test_id))

@app.route('/admin/results')
@admin_required
def admin_results():
    results = Result.query.order_by(Result.submitted_at.desc()).all()
    users   = {u.id: u for u in User.query.all()}
    tests   = {t.id: t for t in Test.query.all()}
    return render_template('admin_results.html', results=results, users=users, tests=tests)

@app.route('/admin/subscription/<int:uid>', methods=['POST'])
@admin_required
def set_subscription(uid):
    user = User.query.get_or_404(uid)
    plan = request.form['plan']
    user.subscription = plan
    if plan != 'free':
        user.sub_expiry = datetime.utcnow() + timedelta(days=30)
    db.session.commit()
    flash('Subscription updated!', 'success')
    return redirect(url_for('admin_users'))

# ─── API ROUTES ───────────────────────────────────────────
@app.route('/api/stats')
@admin_required
def api_stats():
    days   = []
    counts = []
    for i in range(7):
        d     = datetime.utcnow().date() - timedelta(days=6-i)
        count = Result.query.filter(db.func.date(Result.submitted_at) == d).count()
        days.append(d.strftime('%d %b'))
        counts.append(count)
    subjects = Subject.query.all()
    sub_data = []
    for s in subjects:
        test_ids = [t.id for t in Test.query.filter_by(subject_id=s.id).all()]
        cnt = Result.query.filter(Result.test_id.in_(test_ids)).count() if test_ids else 0
        sub_data.append({'name': s.name, 'count': cnt})
    return jsonify({'days': days, 'counts': counts, 'subjects': sub_data})

@app.route('/api/notify-read', methods=['POST'])
@login_required
def notify_read():
    Notification.query.filter_by(user_id=session['user_id']).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})

# ─── INIT ─────────────────────────────────────────────────
def create_defaults():
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(email='admin@tesrora.com').first():
            admin = User(name='Super Admin', email='admin@tesrora.com',
                         password=generate_password_hash('admin123'),
                         role='superadmin', is_verified=True)
            db.session.add(admin)
            db.session.commit()
        if not Subject.query.first():
            for name, icon in [('Physics','atom'),('Chemistry','flask'),
                                ('Mathematics','calculator'),('Biology','leaf'),
                                ('English','book'),('GK','globe')]:
                db.session.add(Subject(name=name, icon=icon, created_by=1))
            db.session.commit()
        if not Test.query.first():
            t = Test(title='JEE Main Mock Test 1', subject_id=1,
                     duration=180, total_marks=300,
                     correct_marks=4, neg_marks=1,
                     instructions='Read all questions carefully. +4 for correct, -1 for wrong.',
                     created_by=1, is_active=True)
            db.session.add(t)
            db.session.commit()
            sample_qs = [
                ('A ball is thrown vertically upward. At the highest point:',
                 'Velocity is zero, acceleration is zero',
                 'Velocity is zero, acceleration is g downward',
                 'Velocity is maximum, acceleration is zero',
                 'Both velocity and acceleration are maximum', 'B',
                 'At highest point, velocity becomes zero but acceleration due to gravity still acts downward.'),
                ('Which of the following has highest electronegativity?',
                 'Oxygen','Fluorine','Nitrogen','Chlorine','B',
                 'Fluorine has highest electronegativity (3.98) on Pauling scale.'),
                ('The value of sin²θ + cos²θ is:',
                 '0','2','1','Depends on θ','C',
                 'This is a fundamental trigonometric identity: sin²θ + cos²θ = 1'),
                ('What is the SI unit of electric current?',
                 'Volt','Watt','Ampere','Ohm','C',
                 'Ampere (A) is the SI unit of electric current.'),
                ('Photosynthesis takes place in which part of plant?',
                 'Root','Stem','Chloroplast','Mitochondria','C',
                 'Chloroplasts contain chlorophyll which is essential for photosynthesis.'),
            ]
            for q in sample_qs:
                db.session.add(Question(test_id=t.id, text=q[0],
                    option_a=q[1], option_b=q[2], option_c=q[3], option_d=q[4],
                    correct=q[5], explanation=q[6], created_by=1))
            db.session.commit()

create_defaults()

if __name__ == '__main__':
    app.run(debug=True, port=5000)
