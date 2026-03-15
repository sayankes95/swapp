import os
from flask import Flask, render_template, request, redirect, session, jsonify
import sqlite3
import hashlib
import numpy as np
from datetime import date, datetime
from collections import defaultdict
import random

app = Flask(__name__)
app.secret_key = 'swapp_secret_key_2026'

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH  = os.path.join(BASE_DIR, 'database.db')

# ════════════════════════════════════════════════
#  DATABASE SETUP
# ════════════════════════════════════════════════

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id       INTEGER PRIMARY KEY AUTOINCREMENT,
            name     TEXT NOT NULL,
            email    TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS user_profile (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER UNIQUE NOT NULL,
            roll_no      TEXT,
            branch       TEXT,
            semester     INTEGER,
            year         INTEGER,
            phone        TEXT,
            college      TEXT,
            bio          TEXT,
            total_subjects INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS wellness_data (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id               INTEGER NOT NULL,
            date                  TEXT NOT NULL,
            sleep_hours           REAL NOT NULL,
            study_hours           REAL NOT NULL,
            screen_time           REAL NOT NULL,
            assignments           INTEGER NOT NULL,
            attendance            REAL NOT NULL,
            marks                 REAL,
            stress_score          REAL,
            predicted_performance TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    c.execute('''
        CREATE TABLE IF NOT EXISTS subject_marks (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id      INTEGER NOT NULL,
            date         TEXT NOT NULL,
            subject_name TEXT NOT NULL,
            marks        REAL NOT NULL,
            max_marks    REAL NOT NULL DEFAULT 100,
            exam_type    TEXT NOT NULL DEFAULT 'Test',
            semester     INTEGER DEFAULT 1,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    conn.commit()
    conn.close()

init_db()

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# ════════════════════════════════════════════════
#  MOTIVATIONAL QUOTES
# ════════════════════════════════════════════════
QUOTES = [
    ("Push yourself, because no one else is going to do it for you.", "Unknown"),
    ("Great things never come from comfort zones.", "Unknown"),
    ("Dream it. Wish it. Do it.", "Unknown"),
    ("Success doesn't just find you. You have to go out and get it.", "Unknown"),
    ("The harder you work for something, the greater you'll feel when you achieve it.", "Unknown"),
    ("Don't stop when you're tired. Stop when you're done.", "Unknown"),
    ("Wake up with determination. Go to bed with satisfaction.", "Unknown"),
    ("Little things make big days.", "Unknown"),
    ("It's going to be hard, but hard does not mean impossible.", "Unknown"),
    ("Don't wait for opportunity. Create it.", "Unknown"),
    ("Study hard, for the well is deep, and our brains are shallow.", "Richard Baxter"),
    ("Education is the passport to the future.", "Malcolm X"),
    ("The beautiful thing about learning is nobody can take it away from you.", "B.B. King"),
    ("An investment in knowledge pays the best interest.", "Benjamin Franklin"),
    ("The more that you read, the more things you will know.", "Dr. Seuss"),
]

def get_daily_quote():
    idx = datetime.now().timetuple().tm_yday % len(QUOTES)
    text, author = QUOTES[idx]
    return {'text': text, 'author': author}


# ════════════════════════════════════════════════
#  STRESS SCORE
# ════════════════════════════════════════════════

def calculate_stress_score(sleep, study, screen, assignments, attendance):
    raw = (8 * max(0.0, 8.0 - sleep) + 5 * screen + 6 * assignments
           + 3 * max(0.0, (100 - attendance) / 10) - 4 * study)
    return max(0.0, min(100.0, round(raw, 1)))

def get_stress_level(score):
    if score <= 25:    return 'Low',       '#22c55e'
    elif score <= 50:  return 'Moderate',  '#f59e0b'
    elif score <= 75:  return 'High',      '#f97316'
    else:              return 'Very High', '#ef4444'


# ════════════════════════════════════════════════
#  MODEL 1 — Random Forest (Performance)
# ════════════════════════════════════════════════

def _build_rf_model():
    from sklearn.ensemble import RandomForestClassifier
    X = np.array([
        [8,6,2,1,95],[7.5,7,1.5,2,92],[8,5,2,1,98],[7,6,3,2,90],[8.5,5.5,1,1,96],[7.5,8,2,1,94],
        [7,4,3,3,85],[6.5,5,3.5,2,82],[7,4.5,4,3,88],[6,5,4,2,80],[7.5,3.5,3,3,86],[6.5,4,3,2,84],
        [6,3,5,4,72],[5.5,3.5,5,3,68],[6,2.5,6,4,75],[5,4,5,5,70],[6.5,2,5.5,4,65],[5.5,3,6,3,73],
        [4,1,8,6,50],[3.5,2,7,5,55],[4.5,1.5,9,7,45],[3,1,8,8,40],[5,0.5,7,6,52],[4,1,10,5,48],
    ], dtype=float)
    y = np.array(['Excellent']*6 + ['Good']*6 + ['Average']*6 + ['At Risk']*6)
    m = RandomForestClassifier(n_estimators=100, random_state=42)
    m.fit(X, y)
    return m

ml_model = _build_rf_model()

def predict_performance(sleep, study, screen, assignments, attendance):
    feat = np.array([[float(sleep), float(study), float(screen), float(assignments), float(attendance)]])
    pred       = ml_model.predict(feat)[0]
    confidence = round(float(max(ml_model.predict_proba(feat)[0])) * 100, 1)
    return pred, confidence

def get_performance_style(prediction):
    styles = {
        'Excellent': ('🌟', '#22c55e', 'Keep up the amazing work!'),
        'Good':      ('👍', '#3b82f6', "You're doing well! Small improvements can make a big difference."),
        'Average':   ('⚡', '#f59e0b', 'Try to improve sleep and reduce screen time.'),
        'At Risk':   ('⚠️', '#ef4444', 'Your wellness habits need attention. Focus on sleep and study hours.'),
    }
    return styles.get(prediction, ('📊', '#888888', 'Keep tracking your data.'))


# ════════════════════════════════════════════════
#  MODEL 2 — Gradient Boosting (Academic Risk)
# ════════════════════════════════════════════════

def _build_risk_model():
    from sklearn.ensemble import GradientBoostingClassifier
    X = np.array([
        [8,6,15,95,88],[7.5,7,10,90,92],[8,5,20,98,85],[7,6,25,88,80],[8.5,5.5,12,96,91],[7.5,8,8,94,87],
        [6.5,4,45,80,68],[6,4.5,50,75,65],[7,3.5,40,82,70],[5.5,5,48,78,72],[6,3,55,70,60],[6.5,4,42,85,74],
        [4,1,80,55,40],[3.5,2,85,50,35],[4.5,1.5,78,48,42],[3,1,90,40,30],[5,0.5,75,52,38],[4,1.5,88,45,28],
    ], dtype=float)
    y = np.array(['LOW']*6 + ['MEDIUM']*6 + ['HIGH']*6)
    m = GradientBoostingClassifier(n_estimators=100, random_state=42)
    m.fit(X, y)
    return m

risk_model = _build_risk_model()

def predict_academic_risk(sleep, study, stress, attendance, recent_marks):
    feat    = np.array([[float(sleep), float(study), float(stress), float(attendance), float(recent_marks)]])
    risk    = risk_model.predict(feat)[0]
    proba   = risk_model.predict_proba(feat)[0]
    classes = list(risk_model.classes_)
    high_idx  = classes.index('HIGH')   if 'HIGH'   in classes else 0
    med_idx   = classes.index('MEDIUM') if 'MEDIUM' in classes else 1
    drop_prob = round((float(proba[high_idx]) * 0.7 + float(proba[med_idx]) * 0.35) * 100, 1)
    return {
        'risk':      risk,
        'drop_prob': drop_prob,
        'color':     {'LOW': '#22c55e', 'MEDIUM': '#f59e0b', 'HIGH': '#ef4444'}.get(risk, '#888'),
        'icon':      {'LOW': '✅', 'MEDIUM': '⚡', 'HIGH': '🚨'}.get(risk, '📊'),
        'advice':    {
            'LOW':    'Your academic trajectory looks healthy. Keep it up!',
            'MEDIUM': 'There are signs of strain. Boost sleep and study consistency.',
            'HIGH':   'Immediate attention needed — increase sleep, study hours, and attendance.',
        }.get(risk, ''),
    }


# ════════════════════════════════════════════════
#  MODEL 3 — ANN / MLP (Stress Level Classifier)
# ════════════════════════════════════════════════

def _build_ann_model():
    from sklearn.neural_network import MLPClassifier
    from sklearn.preprocessing import StandardScaler
    # All values explicitly float to avoid numpy dtype issues
    X = np.array([
        [8.0,6.0,2.0,0.0,95.0],[7.5,7.0,1.5,1.0,92.0],[8.5,5.5,1.0,0.0,98.0],
        [7.0,6.5,2.5,1.0,90.0],[8.0,5.0,2.0,0.0,96.0],[7.5,8.0,1.5,1.0,94.0],
        [8.0,4.5,3.0,0.0,88.0],[9.0,6.0,1.0,0.0,99.0],[7.0,7.0,2.0,1.0,91.0],
        [7.0,4.0,3.5,2.0,85.0],[6.5,5.0,3.0,2.0,82.0],[6.0,4.5,4.0,3.0,80.0],
        [7.5,3.5,3.5,2.0,86.0],[6.5,4.0,3.0,2.0,84.0],[6.0,5.0,4.0,2.0,78.0],
        [7.0,3.0,4.0,3.0,80.0],[6.5,4.5,3.5,2.0,83.0],[7.0,3.5,3.0,3.0,85.0],
        [6.0,3.0,5.5,4.0,72.0],[5.5,3.5,5.0,3.0,68.0],[6.0,2.5,6.0,4.0,75.0],
        [5.0,4.0,5.0,5.0,70.0],[6.5,2.0,5.5,4.0,65.0],[5.5,3.0,6.0,3.0,73.0],
        [5.0,2.5,6.0,5.0,68.0],[6.0,2.0,5.5,4.0,72.0],[5.5,3.5,5.0,4.0,70.0],
        [4.0,1.0,8.0,6.0,50.0],[3.5,2.0,7.0,5.0,55.0],[4.5,1.5,9.0,7.0,45.0],
        [3.0,1.0,8.0,8.0,40.0],[5.0,0.5,7.0,6.0,52.0],[4.0,1.0,10.0,5.0,48.0],
        [3.5,0.5,9.0,7.0,42.0],[4.0,1.5,8.0,6.0,45.0],[3.0,1.0,9.0,8.0,38.0],
    ], dtype=np.float64)
    y = np.array(['Low']*9 + ['Moderate']*9 + ['High']*9 + ['Very High']*9)
    scaler = StandardScaler()
    Xs = scaler.fit_transform(X)
    ann = MLPClassifier(hidden_layer_sizes=(64, 32), activation='relu', solver='adam',
                        max_iter=2000, random_state=42)
    ann.fit(Xs, y)
    return ann, scaler

try:
    ann_model, ann_scaler = _build_ann_model()
    ANN_AVAILABLE = True
    print('[SWAPP] ANN model built OK')
except Exception as e:
    ANN_AVAILABLE = False
    print('[SWAPP] ANN unavailable:', str(e)[:120])

def predict_stress_ann(sleep, study, screen, assignments, attendance):
    if not ANN_AVAILABLE:
        return None
    try:
        feat   = np.array([[float(sleep), float(study), float(screen), float(assignments), float(attendance)]], dtype=np.float64)
        scaled = ann_scaler.transform(feat)
        label  = ann_model.predict(scaled)[0]
        proba  = float(max(ann_model.predict_proba(scaled)[0])) * 100
        return {
            'label':      label,
            'confidence': round(proba, 1),
            'color':      {'Low': '#22c55e', 'Moderate': '#f59e0b', 'High': '#f97316', 'Very High': '#ef4444'}.get(label, '#888'),
            'emoji':      {'Low': '😊', 'Moderate': '😐', 'High': '😰', 'Very High': '🤯'}.get(label, '🧠'),
            'tip':        {
                'Low':       'Your stress is well-managed. Keep up healthy routines!',
                'Moderate':  'Manageable stress. A short break or walk can help.',
                'High':      'Stress is building. Try to sleep more and reduce screen time.',
                'Very High': 'Critical stress level! Take immediate rest and talk to someone.',
            }.get(label, ''),
        }
    except Exception:
        return None


# ════════════════════════════════════════════════
#  PRODUCTIVITY SCORE
# ════════════════════════════════════════════════

def calculate_productivity_score(study_hours, attendance, stress_score, sleep_hours, screen_time):
    raw = (study_hours * 10) + attendance - (stress_score * 0.5) + (sleep_hours * 3) - (screen_time * 2)
    return max(0.0, min(100.0, round(raw, 1)))

def get_productivity_tier(score):
    if score >= 80:   return '🔥 On Fire!',   '#22c55e'
    elif score >= 60: return '💪 Productive',  '#3b82f6'
    elif score >= 40: return '📖 Moderate',    '#f59e0b'
    else:             return '😴 Low Energy',  '#ef4444'


# ════════════════════════════════════════════════
#  BURNOUT DETECTION
# ════════════════════════════════════════════════

def detect_burnout(entries):
    entries = list(entries)
    if len(entries) < 3:
        return {'detected': False}
    check = entries[:7]
    high_stress_count = sum(1 for e in check if e['stress_score'] and e['stress_score'] >= 60)
    avg_sleep = sum(e['sleep_hours'] for e in check) / len(check)
    if high_stress_count >= 3 and avg_sleep < 6.5:
        severity = 'Critical' if high_stress_count >= 5 and avg_sleep < 5.5 else 'Warning'
        msg = (
            "⚠️ Critical Burnout Risk! You've had high stress for several days with very little sleep. Take a break, reduce your workload, and prioritize rest."
            if severity == 'Critical' else
            "⚠️ Burnout Warning! High stress levels combined with low sleep detected. Consider a lighter schedule and aim for 7+ hours of sleep."
        )
        return {'detected': True, 'severity': severity,
                'high_stress_days': high_stress_count,
                'avg_sleep': round(avg_sleep, 1), 'message': msg}
    return {'detected': False}


# ════════════════════════════════════════════════
#  STUDY PATTERN INSIGHTS
# ════════════════════════════════════════════════

DAYS = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

def compute_study_patterns(entries):
    if not entries:
        return None
    day_study = defaultdict(list)
    for e in entries:
        try:
            dt = datetime.strptime(str(e['date']), '%Y-%m-%d')
            day_study[DAYS[dt.weekday()]].append(float(e['study_hours']))
        except Exception:
            pass
    if not day_study:
        return None
    avg_by_day  = {d: sum(v)/len(v) for d, v in day_study.items()}
    best_day    = max(avg_by_day, key=avg_by_day.get)
    avg_focus   = round(sum(float(e['study_hours']) for e in entries) / len(entries), 1)
    consistent  = sum(1 for e in entries if float(e['study_hours']) >= 2)
    consistency = round((consistent / len(entries)) * 100)
    mid         = len(entries) // 2
    recent_avg  = sum(float(e['study_hours']) for e in entries[:mid])  / max(1, mid)
    older_avg   = sum(float(e['study_hours']) for e in entries[mid:])  / max(1, len(entries) - mid)
    trend = ('Improving ↑' if recent_avg > older_avg + 0.3
             else 'Declining ↓' if recent_avg < older_avg - 0.3
             else 'Stable →')
    return {'best_day': best_day, 'avg_focus': avg_focus,
            'consistency': consistency, 'trend': trend}


# ════════════════════════════════════════════════
#  LONG-TERM ANALYTICS
# ════════════════════════════════════════════════

def build_monthly_trend(entries):
    monthly = defaultdict(lambda: {'stress': [], 'study': [], 'sleep': []})
    for e in entries:
        try:
            month = str(e['date'])[:7]
            monthly[month]['stress'].append(float(e['stress_score'] or 0))
            monthly[month]['study'].append(float(e['study_hours']))
            monthly[month]['sleep'].append(float(e['sleep_hours']))
        except Exception:
            pass
    months = sorted(monthly.keys())
    if not months:
        return {'labels': [], 'avg_stress': [], 'avg_study': [], 'avg_sleep': []}
    return {
        'labels':     months,
        'avg_stress': [round(sum(monthly[m]['stress']) / len(monthly[m]['stress']), 1) for m in months],
        'avg_study':  [round(sum(monthly[m]['study'])  / len(monthly[m]['study']),  1) for m in months],
        'avg_sleep':  [round(sum(monthly[m]['sleep'])  / len(monthly[m]['sleep']),  1) for m in months],
    }

def build_study_consistency(entries):
    result = [{'date': e['date'], 'study': e['study_hours']} for e in reversed(list(entries))]
    return result[-14:] if len(result) > 14 else result


# ════════════════════════════════════════════════
#  WEEKLY REPORT
# ════════════════════════════════════════════════

def generate_weekly_report(entries_7, subject_avgs):
    if not entries_7:
        return None
    avg_stress = round(sum(float(e['stress_score'] or 0) for e in entries_7) / len(entries_7), 1)
    avg_study  = round(sum(float(e['study_hours'])       for e in entries_7) / len(entries_7), 1)
    avg_sleep  = round(sum(float(e['sleep_hours'])       for e in entries_7) / len(entries_7), 1)
    avg_screen = round(sum(float(e['screen_time'])       for e in entries_7) / len(entries_7), 1)
    stress_label, stress_color = get_stress_level(avg_stress)
    strongest = max(subject_avgs, key=subject_avgs.get) if subject_avgs else '—'
    weakest   = min(subject_avgs, key=subject_avgs.get) if subject_avgs else '—'
    recs = []
    if avg_sleep  < 7:  recs.append(f'Increase sleep to 7+ hrs (currently {avg_sleep} hrs) to improve concentration.')
    if avg_stress > 50: recs.append('Stress is elevated. Try mindfulness or short breaks between study sessions.')
    if avg_screen > 5:  recs.append(f'Reduce screen time (currently {avg_screen} hrs/day). Aim for under 4 hours.')
    if avg_study  < 4:  recs.append(f'Study hours are low ({avg_study} hrs/day). Aim for at least 5 hours on weekdays.')
    if not recs:
        recs.append('Great week! Keep maintaining healthy habits and consistent study patterns.')
    return {
        'avg_stress': avg_stress, 'stress_label': stress_label, 'stress_color': stress_color,
        'avg_study': avg_study, 'avg_sleep': avg_sleep, 'avg_screen': avg_screen,
        'strongest': strongest, 'weakest': weakest,
        'recommendations': recs, 'entries_count': len(entries_7),
    }


# ════════════════════════════════════════════════
#  HELPER: get user profile
# ════════════════════════════════════════════════

def get_user_profile(user_id):
    conn = get_db()
    p = conn.execute('SELECT * FROM user_profile WHERE user_id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(p) if p else {}


# ════════════════════════════════════════════════
#  ROUTES
# ════════════════════════════════════════════════

@app.route('/')
def login_page():
    return render_template('login.html')

@app.route('/login', methods=['POST'])
def login():
    email    = request.form['email']
    password = hash_password(request.form['password'])
    conn = get_db()
    user = conn.execute('SELECT * FROM users WHERE email = ? AND password = ?', (email, password)).fetchone()
    conn.close()
    if user:
        session['user_id']   = user['id']
        session['user_name'] = user['name']
        return redirect('/dashboard')
    return render_template('login.html', error='Invalid email or password!')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name    = request.form['name']
        email   = request.form['email']
        pw      = request.form['password']
        confirm = request.form['confirm_password']
        if pw != confirm:
            return render_template('register.html', error='Passwords do not match!')
        conn = get_db()
        if conn.execute('SELECT id FROM users WHERE email = ?', (email,)).fetchone():
            conn.close()
            return render_template('register.html', error='Email already registered!')
        conn.execute('INSERT INTO users (name, email, password) VALUES (?, ?, ?)',
                     (name, email, hash_password(pw)))
        conn.commit()
        conn.close()
        return render_template('login.html', success='Account created! Please login.')
    return render_template('register.html')

@app.route('/profile', methods=['GET', 'POST'])
def profile():
    if 'user_id' not in session:
        return redirect('/')
    conn    = get_db()
    success = error = None
    if request.method == 'POST':
        try:
            roll_no   = request.form.get('roll_no', '').strip()
            branch    = request.form.get('branch', '').strip()
            semester  = int(request.form.get('semester', 1))
            year      = int(request.form.get('year', 1))
            phone     = request.form.get('phone', '').strip()
            college   = request.form.get('college', '').strip()
            bio       = request.form.get('bio', '').strip()
            total_sub = int(request.form.get('total_subjects', 0))
            existing  = conn.execute('SELECT id FROM user_profile WHERE user_id = ?', (session['user_id'],)).fetchone()
            if existing:
                conn.execute('''UPDATE user_profile SET roll_no=?,branch=?,semester=?,year=?,phone=?,college=?,bio=?,total_subjects=?
                                WHERE user_id=?''',
                             (roll_no, branch, semester, year, phone, college, bio, total_sub, session['user_id']))
            else:
                conn.execute('''INSERT INTO user_profile (user_id,roll_no,branch,semester,year,phone,college,bio,total_subjects)
                                VALUES (?,?,?,?,?,?,?,?,?)''',
                             (session['user_id'], roll_no, branch, semester, year, phone, college, bio, total_sub))
            conn.commit()
            success = 'Profile updated successfully!'
        except Exception as exc:
            error = f'Error saving profile: {exc}'

    profile_data = conn.execute('SELECT * FROM user_profile WHERE user_id = ?', (session['user_id'],)).fetchone()
    user_data    = conn.execute('SELECT name, email FROM users WHERE id = ?', (session['user_id'],)).fetchone()
    # Stats
    total_entries = conn.execute('SELECT COUNT(*) FROM wellness_data WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    total_marks   = conn.execute('SELECT COUNT(*) FROM subject_marks WHERE user_id = ?', (session['user_id'],)).fetchone()[0]
    avg_stats     = conn.execute('''SELECT ROUND(AVG(stress_score),1) as avg_stress,
                                           ROUND(AVG(study_hours),1) as avg_study,
                                           ROUND(AVG(sleep_hours),1) as avg_sleep,
                                           ROUND(AVG(attendance),1) as avg_attendance
                                    FROM wellness_data WHERE user_id=?''', (session['user_id'],)).fetchone()
    # Marks by semester
    sem_marks = conn.execute('''SELECT semester, subject_name, AVG(marks*100.0/max_marks) as avg_pct
                                FROM subject_marks WHERE user_id=? GROUP BY semester, subject_name ORDER BY semester''',
                             (session['user_id'],)).fetchall()
    conn.close()
    return render_template('profile.html',
        user_name=session['user_name'], profile=profile_data, user=user_data,
        success=success, error=error,
        total_entries=total_entries, total_marks=total_marks, avg_stats=avg_stats,
        sem_marks=sem_marks)

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect('/')
    conn = get_db()
    all_entries = conn.execute('SELECT * FROM wellness_data WHERE user_id=? ORDER BY date DESC', (session['user_id'],)).fetchall()
    entries     = all_entries[:7]
    stats       = conn.execute('''
        SELECT ROUND(AVG(sleep_hours),1) AS avg_sleep, ROUND(AVG(study_hours),1) AS avg_study,
               ROUND(AVG(screen_time),1) AS avg_screen, ROUND(AVG(stress_score),1) AS avg_stress,
               ROUND(AVG(attendance),1) AS avg_attendance, COUNT(*) AS total_entries
        FROM wellness_data WHERE user_id=?''', (session['user_id'],)).fetchone()
    all_marks = conn.execute('SELECT * FROM subject_marks WHERE user_id=? ORDER BY date ASC', (session['user_id'],)).fetchall()
    profile   = conn.execute('SELECT * FROM user_profile WHERE user_id=?', (session['user_id'],)).fetchone()
    conn.close()

    chart_labels, chart_stress, chart_study, chart_sleep, chart_productivity = [], [], [], [], []
    for e in reversed(list(entries)):
        chart_labels.append(e['date'])
        chart_stress.append(float(e['stress_score'] or 0))
        chart_study.append(float(e['study_hours']))
        chart_sleep.append(float(e['sleep_hours']))
        chart_productivity.append(calculate_productivity_score(
            float(e['study_hours']), float(e['attendance']),
            float(e['stress_score'] or 0), float(e['sleep_hours']), float(e['screen_time'])))

    stress_label, stress_color = 'N/A', '#888888'
    if stats['avg_stress']:
        stress_label, stress_color = get_stress_level(float(stats['avg_stress']))

    latest_prediction = latest_risk = latest_productivity = ann_result = None
    if entries:
        latest = entries[0]
        pred, confidence = predict_performance(latest['sleep_hours'], latest['study_hours'],
                                               latest['screen_time'], latest['assignments'], latest['attendance'])
        emoji, color, tip = get_performance_style(pred)
        latest_prediction = {'label': pred, 'confidence': confidence, 'emoji': emoji, 'color': color, 'tip': tip}
        avg_marks   = float(latest['marks']) if latest['marks'] else 70.0
        latest_risk = predict_academic_risk(latest['sleep_hours'], latest['study_hours'],
                                            float(latest['stress_score'] or 0), latest['attendance'], avg_marks)
        prod_score  = calculate_productivity_score(latest['study_hours'], latest['attendance'],
                                                   float(latest['stress_score'] or 0), latest['sleep_hours'], latest['screen_time'])
        prod_tier, prod_color = get_productivity_tier(prod_score)
        latest_productivity = {'score': prod_score, 'tier': prod_tier, 'color': prod_color}
        ann_result  = predict_stress_ann(latest['sleep_hours'], latest['study_hours'],
                                         latest['screen_time'], latest['assignments'], latest['attendance'])

    burnout  = detect_burnout(entries)
    patterns = compute_study_patterns(list(all_entries))

    subj_map = {}
    for row in all_marks:
        pct = round((float(row['marks']) / float(row['max_marks'])) * 100, 1)
        subj_map.setdefault(row['subject_name'], []).append(pct)
    subject_avgs = {s: round(sum(v)/len(v), 1) for s, v in subj_map.items()}

    monthly     = build_monthly_trend(list(all_entries))
    consistency = build_study_consistency(list(all_entries))
    quote       = get_daily_quote()

    return render_template('dashboard.html',
        user_name=session['user_name'], entries=entries, stats=stats, profile=profile,
        chart_labels=chart_labels, chart_stress=chart_stress, chart_study=chart_study,
        chart_sleep=chart_sleep, chart_productivity=chart_productivity,
        stress_label=stress_label, stress_color=stress_color,
        prediction=latest_prediction, risk=latest_risk, productivity=latest_productivity,
        ann=ann_result, burnout=burnout, patterns=patterns, subject_avgs=subject_avgs,
        monthly=monthly, consistency=consistency, quote=quote)

@app.route('/add_data', methods=['GET', 'POST'])
def add_data():
    if 'user_id' not in session:
        return redirect('/')
    if request.method == 'POST':
        try:
            sleep_hours = float(request.form['sleep_hours'])
            study_hours = float(request.form['study_hours'])
            screen_time = float(request.form['screen_time'])
            assignments = int(request.form['assignments'])
            attendance  = float(request.form['attendance'])
            marks_raw   = request.form.get('marks', '').strip()
            marks       = float(marks_raw) if marks_raw else None
            entry_date  = request.form.get('entry_date', str(date.today()))

            stress          = calculate_stress_score(sleep_hours, study_hours, screen_time, assignments, attendance)
            pred, confidence= predict_performance(sleep_hours, study_hours, screen_time, assignments, attendance)
            ann_result      = predict_stress_ann(sleep_hours, study_hours, screen_time, assignments, attendance)

            conn = get_db()
            conn.execute('''INSERT INTO wellness_data
                (user_id,date,sleep_hours,study_hours,screen_time,assignments,attendance,marks,stress_score,predicted_performance)
                VALUES (?,?,?,?,?,?,?,?,?,?)''',
                (session['user_id'], entry_date, sleep_hours, study_hours,
                 screen_time, assignments, attendance, marks, stress, pred))
            conn.commit()
            conn.close()

            emoji, color, tip     = get_performance_style(pred)
            stress_label, s_color = get_stress_level(stress)
            prod_score            = calculate_productivity_score(study_hours, attendance, stress, sleep_hours, screen_time)
            prod_tier, prod_color = get_productivity_tier(prod_score)

            return render_template('add_data.html', success='Data saved successfully!',
                result={'stress_score': stress, 'stress_label': stress_label, 'stress_color': s_color,
                        'prediction': pred, 'confidence': confidence, 'emoji': emoji, 'pred_color': color, 'tip': tip,
                        'productivity': prod_score, 'prod_tier': prod_tier, 'prod_color': prod_color,
                        'ann': ann_result})
        except (ValueError, KeyError) as exc:
            return render_template('add_data.html', error=f'Invalid input: {exc}')
    return render_template('add_data.html')

@app.route('/academics', methods=['GET', 'POST'])
def academics():
    if 'user_id' not in session:
        return redirect('/')
    conn    = get_db()
    success = error = None
    profile = conn.execute('SELECT semester FROM user_profile WHERE user_id=?', (session['user_id'],)).fetchone()
    current_sem = profile['semester'] if profile else 1

    if request.method == 'POST':
        try:
            subject_name = request.form['subject_name'].strip()
            marks        = float(request.form['marks'])
            max_marks    = float(request.form.get('max_marks', 100))
            exam_type    = request.form.get('exam_type', 'Test')
            entry_date   = request.form.get('entry_date', str(date.today()))
            semester     = int(request.form.get('semester', current_sem))
            if not subject_name:           raise ValueError('Subject name is required.')
            if max_marks <= 0:             raise ValueError('Max marks must be > 0.')
            if marks < 0 or marks > max_marks: raise ValueError('Marks out of range.')
            conn.execute('''INSERT INTO subject_marks (user_id,date,subject_name,marks,max_marks,exam_type,semester)
                            VALUES (?,?,?,?,?,?,?)''',
                         (session['user_id'], entry_date, subject_name, marks, max_marks, exam_type, semester))
            conn.commit()
            success = f"Marks for '{subject_name}' saved!"
        except ValueError as exc:
            error = str(exc)

    all_marks = conn.execute('SELECT * FROM subject_marks WHERE user_id=? ORDER BY date ASC', (session['user_id'],)).fetchall()
    wellness  = conn.execute('''SELECT date, study_hours, sleep_hours, screen_time,
                                       marks AS overall_marks, stress_score
                                FROM wellness_data WHERE user_id=? AND marks IS NOT NULL ORDER BY date ASC''',
                             (session['user_id'],)).fetchall()
    # Semester summary
    sem_summary = conn.execute('''SELECT semester, subject_name,
                                         ROUND(AVG(marks*100.0/max_marks),1) as avg_pct,
                                         COUNT(*) as num_tests,
                                         MAX(marks*100.0/max_marks) as best,
                                         MIN(marks*100.0/max_marks) as worst
                                  FROM subject_marks WHERE user_id=?
                                  GROUP BY semester, subject_name ORDER BY semester, subject_name''',
                               (session['user_id'],)).fetchall()
    conn.close()

    subjects = {}
    for row in all_marks:
        subj = row['subject_name']
        pct  = round((float(row['marks']) / float(row['max_marks'])) * 100, 1)
        if subj not in subjects:
            subjects[subj] = {'dates': [], 'percentages': [], 'raw': []}
        subjects[subj]['dates'].append(row['date'])
        subjects[subj]['percentages'].append(pct)
        subjects[subj]['raw'].append({'marks': row['marks'], 'max': row['max_marks'],
                                      'type': row['exam_type'], 'date': row['date'], 'sem': row['semester']})
    subject_avgs = {s: round(sum(d['percentages'])/len(d['percentages']), 1) for s, d in subjects.items()}

    cmp_dates  = [r['date']          for r in wellness]
    cmp_marks  = [r['overall_marks'] for r in wellness]
    cmp_study  = [r['study_hours']   for r in wellness]
    cmp_sleep  = [r['sleep_hours']   for r in wellness]
    cmp_screen = [r['screen_time']   for r in wellness]
    cmp_stress = [float(r['stress_score']) if r['stress_score'] else 0 for r in wellness]

    recent = list(reversed(list(all_marks)[-10:])) if all_marks else []

    return render_template('academics.html',
        user_name=session['user_name'], success=success, error=error,
        subjects=subjects, subject_avgs=subject_avgs, current_sem=current_sem,
        sem_summary=sem_summary, cmp_dates=cmp_dates, cmp_marks=cmp_marks,
        cmp_study=cmp_study, cmp_sleep=cmp_sleep, cmp_screen=cmp_screen, cmp_stress=cmp_stress,
        recent=recent, total_entries=len(all_marks))

@app.route('/delete_mark/<int:mark_id>', methods=['POST'])
def delete_mark(mark_id):
    if 'user_id' not in session:
        return redirect('/')
    conn = get_db()
    conn.execute('DELETE FROM subject_marks WHERE id=? AND user_id=?', (mark_id, session['user_id']))
    conn.commit()
    conn.close()
    return redirect('/academics')

@app.route('/weekly_report')
def weekly_report():
    if 'user_id' not in session:
        return redirect('/')
    conn      = get_db()
    entries_7 = conn.execute('SELECT * FROM wellness_data WHERE user_id=? ORDER BY date DESC LIMIT 7', (session['user_id'],)).fetchall()
    all_marks = conn.execute('SELECT * FROM subject_marks WHERE user_id=? ORDER BY date ASC', (session['user_id'],)).fetchall()
    conn.close()

    subj_map = {}
    for row in all_marks:
        pct = round((float(row['marks']) / float(row['max_marks'])) * 100, 1)
        subj_map.setdefault(row['subject_name'], []).append(pct)
    subject_avgs = {s: round(sum(v)/len(v), 1) for s, v in subj_map.items()}
    report = generate_weekly_report(list(entries_7), subject_avgs)

    e7 = list(reversed(list(entries_7)))
    return render_template('weekly_report.html',
        user_name=session['user_name'], report=report, subject_avgs=subject_avgs,
        labels   = [e['date'] for e in e7],
        stresses = [float(e['stress_score'] or 0) for e in e7],
        studies  = [float(e['study_hours']) for e in e7],
        sleeps   = [float(e['sleep_hours']) for e in e7],
        prods    = [calculate_productivity_score(float(e['study_hours']), float(e['attendance']),
                    float(e['stress_score'] or 0), float(e['sleep_hours']), float(e['screen_time'])) for e in e7])

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

if __name__ == '__main__':
    app.run(debug=True)
