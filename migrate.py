import sqlite3
import os

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
conn = sqlite3.connect(DB)
c = conn.cursor()

# --- subject_marks: add semester column if missing ---
cols = [row[1] for row in c.execute('PRAGMA table_info(subject_marks)').fetchall()]
print('subject_marks columns:', cols)
if 'semester' not in cols:
    c.execute('ALTER TABLE subject_marks ADD COLUMN semester INTEGER DEFAULT 1')
    print('Added semester column to subject_marks')
else:
    print('semester column already OK')

# --- Create user_profile if missing ---
tables = [row[0] for row in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Existing tables:', tables)
if 'user_profile' not in tables:
    c.execute('''
        CREATE TABLE user_profile (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id         INTEGER UNIQUE NOT NULL,
            roll_no         TEXT,
            branch          TEXT,
            semester        INTEGER,
            year            INTEGER,
            phone           TEXT,
            college         TEXT,
            bio             TEXT,
            total_subjects  INTEGER DEFAULT 0,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    print('Created user_profile table')
else:
    print('user_profile table already exists')

conn.commit()
conn.close()
print('Migration complete.')
