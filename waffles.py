import streamlit as st
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime, date, time
import hashlib

DB_PATH = Path(__file__).parent / "waffles.db"

def hash_pw(pw: str) -> str:
	return hashlib.sha256(pw.encode()).hexdigest()

def get_conn():
	conn = sqlite3.connect(DB_PATH)
	conn.row_factory = sqlite3.Row
	return conn

def init_db():
	conn = get_conn()
	cur = conn.cursor()
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS users(
			username TEXT PRIMARY KEY,
			password_hash TEXT
		)
		"""
	)
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS prep_items(
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT,
			item_type TEXT,
			title TEXT,
			status TEXT,
			notes TEXT,
			date_added TEXT
		)
		"""
	)
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS screen_time(
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT,
			entry_date TEXT,
			minutes INTEGER
		)
		"""
	)
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS exams(
			username TEXT PRIMARY KEY,
			exam_datetime TEXT
		)
		"""
	)
	# insert two default users if not present (do not overwrite)
	try:
		cur.execute("INSERT OR IGNORE INTO users(username, password_hash) VALUES (?,?)", ("me", hash_pw("changeme")))
		cur.execute("INSERT OR IGNORE INTO users(username, password_hash) VALUES (?,?)", ("partner", hash_pw("changeme")))
	except Exception:
		pass
	conn.commit()
	conn.close()

def verify_user(username: str, password: str) -> bool:
	conn = get_conn()
	cur = conn.cursor()
	cur.execute("SELECT password_hash FROM users WHERE username=?", (username,))
	row = cur.fetchone()
	conn.close()
	if not row:
		return False
	return row["password_hash"] == hash_pw(password)

def user_count() -> int:
	conn = get_conn()
	cur = conn.cursor()
	cur.execute("SELECT COUNT(*) FROM users")
	n = cur.fetchone()[0]
	conn.close()
	return n

def create_user(username: str, password: str) -> bool:
	if user_count() >= 2:
		return False
	conn = get_conn()
	cur = conn.cursor()
	try:
		cur.execute("INSERT INTO users(username, password_hash) VALUES (?,?)", (username, hash_pw(password)))
		conn.commit()
		return True
	except sqlite3.IntegrityError:
		return False
	finally:
		conn.close()

def add_prep_item(username, item_type, title, status, notes):
	conn = get_conn()
	cur = conn.cursor()
	cur.execute("INSERT INTO prep_items(username,item_type,title,status,notes,date_added) VALUES (?,?,?,?,?,?)",
				(username, item_type, title, status, notes, datetime.now().isoformat()))
	conn.commit()
	conn.close()

def get_prep_items(username):
	conn = get_conn()
	df = pd.read_sql_query("SELECT * FROM prep_items WHERE username=? ORDER BY date_added DESC", conn, params=(username,))
	conn.close()
	return df

def add_screen_time(username, entry_date, minutes):
	conn = get_conn()
	cur = conn.cursor()
	cur.execute("INSERT INTO screen_time(username,entry_date,minutes) VALUES (?,?,?)", (username, entry_date, minutes))
	conn.commit()
	conn.close()

def get_screen_time(username):
	conn = get_conn()
	df = pd.read_sql_query("SELECT * FROM screen_time WHERE username=? ORDER BY entry_date DESC", conn, params=(username,))
	conn.close()
	return df

def set_exam_datetime(username, dt_iso):
	conn = get_conn()
	cur = conn.cursor()
	cur.execute("INSERT OR REPLACE INTO exams(username,exam_datetime) VALUES (?,?)", (username, dt_iso))
	conn.commit()
	conn.close()

def get_exam_datetime(username):
	conn = get_conn()
	cur = conn.cursor()
	cur.execute("SELECT exam_datetime FROM exams WHERE username=?", (username,))
	row = cur.fetchone()
	conn.close()
	return row[0] if row else None

DEF_SUBJECTS = ["Physics", "Chemistry", "Math"]
CHAPTER_COUNT = 20
TASK_COLUMNS = ["theory", "notes", "questions", "board_pyqs", "jee_main_pyqs"]

def init_chapter_progress():
	conn = get_conn()
	cur = conn.cursor()
	cur.execute(
		"""
		CREATE TABLE IF NOT EXISTS chapter_progress(
			id INTEGER PRIMARY KEY AUTOINCREMENT,
			username TEXT,
			subject TEXT,
			chapter INTEGER,
			theory INTEGER,
			notes INTEGER,
			questions INTEGER,
			board_pyqs INTEGER,
			jee_main_pyqs INTEGER,
			last_updated TEXT,
			UNIQUE(username, subject, chapter)
		)
		"""
	)
	conn.commit()
	conn.close()


def load_chapter_progress(username, subject):
	conn = get_conn()
	query = "SELECT chapter, theory, notes, questions, board_pyqs, jee_main_pyqs FROM chapter_progress WHERE username=? AND subject=? ORDER BY chapter"
	df = pd.read_sql_query(query, conn, params=(username, subject))
	conn.close()
	progress = {row["chapter"]: {
		"theory": bool(row["theory"]),
		"notes": bool(row["notes"]),
		"questions": bool(row["questions"]),
		"board_pyqs": bool(row["board_pyqs"]),
		"jee_main_pyqs": bool(row["jee_main_pyqs"]),
	} for row in df.to_dict(orient="records")}
	return progress


def save_chapter_progress(username, subject, progress):
	conn = get_conn()
	cur = conn.cursor()
	for chapter, tasks in progress.items():
		cur.execute(
			"INSERT INTO chapter_progress(username,subject,chapter,theory,notes,questions,board_pyqs,jee_main_pyqs,last_updated) VALUES (?,?,?,?,?,?,?,?,?) "
			"ON CONFLICT(username,subject,chapter) DO UPDATE SET theory=excluded.theory, notes=excluded.notes, questions=excluded.questions, board_pyqs=excluded.board_pyqs, jee_main_pyqs=excluded.jee_main_pyqs, last_updated=excluded.last_updated",
			(
				username,
				subject,
				chapter,
				int(tasks["theory"]),
				int(tasks["notes"]),
				int(tasks["questions"]),
				int(tasks["board_pyqs"]),
				int(tasks["jee_main_pyqs"]),
				datetime.now().isoformat(),
			)
		)
	conn.commit()
	conn.close()


init_db()
init_chapter_progress()

st.set_page_config(page_title="D and D's Daily Tracker", page_icon=":guardsman:", layout="centered")
st.markdown(
	"""
	<style>
		body, .main, .stApp {
			background-color: #0b111c;
			color: #c9d1d9;
		}
		.stButton button {
			background-color: #161b2b;
			color: #f5f7ff;
		}
		.stTextInput>div>div>input, .stNumberInput>div>div>input, .stDateInput>div>div>input {
			background-color: #09101f;
			color: #f5f7ff;
		}
		.stCheckbox>div {
			color: #c9d1d9;
		}
		.stExpanderHeader {
			background-color: #12182b;
			color: #c9d1d9;
		}
	</style>
	""",
	unsafe_allow_html=True,
)
st.title("Daily Tracker")

if "user" not in st.session_state:
	st.session_state.user = None
if "page" not in st.session_state:
	st.session_state.page = "home"

def logout():
	st.session_state.user = None
	st.session_state.page = "home"

if st.session_state.user is None:
	st.header("Login")
	with st.form("login_form"):
		username = st.text_input("Username")
		password = st.text_input("Password", type="password")
		submitted = st.form_submit_button("Log in")
	if submitted:
		if verify_user(username, password):
			st.session_state.user = username
			st.success("Logged in as %s" % username)
		else:
			st.error("Invalid credentials")
	st.write("Only two users are allowed. If you need another account, create one below (allowed only while two users are not yet registered).")
	if user_count() < 2:
		with st.form("create_form"):
			new_user = st.text_input("New username")
			new_pw = st.text_input("New password", type="password")
			create = st.form_submit_button("Create account")
		if create:
			ok = create_user(new_user, new_pw)
			if ok:
				st.success("Created user. Please log in.")
			else:
				st.error("Could not create user (maybe username exists or limit reached)")
	st.stop()

# Logged in UI
st.sidebar.write(f"Logged in as: {st.session_state.user}")
if st.sidebar.button("Log out"):
	logout()

st.sidebar.header("Navigation")
if st.sidebar.button("Home"):
	st.session_state.page = "home"
if st.sidebar.button("Preparation Tracker"):
	st.session_state.page = "prep"
if st.sidebar.button("Time Left"):
	st.session_state.page = "time"
if st.sidebar.button("Screen Time Tracker"):
	st.session_state.page = "screen"

if st.session_state.page == "home":
	st.header("Home")
	st.write("Quick links")
	col1, col2 = st.columns(2)
	if col1.button("Go to Preparation Tracker"):
		st.session_state.page = "prep"
		st.experimental_rerun()
	if col2.button("Go to Time Left"):
		st.session_state.page = "time"
		st.experimental_rerun()
	if col1.button("Go to Screen Time Tracker"):
		st.session_state.page = "screen"
		st.experimental_rerun()

	st.subheader("Waffle-style summary (simple)")
	st.write("This workspace keeps daily logs for screen time and preparation items. Use the pages to add and view data.")

elif st.session_state.page == "prep":
	st.header("Preparation Tracker")
	st.subheader("Add a preparation item")
	with st.form("add_prep"):
		itype = st.selectbox("Type", ["chapter", "subject", "pyq", "main", "other"])
		title = st.text_input("Title")
		status = st.selectbox("Status", ["todo", "in-progress", "done"])
		notes = st.text_area("Notes")
		add = st.form_submit_button("Add")
	if add and title:
		add_prep_item(st.session_state.user, itype, title, status, notes)
		st.success("Added")
	df = get_prep_items(st.session_state.user)
	if df.empty:
		st.info("No preparation items yet.")
	else:
		st.dataframe(df)

elif st.session_state.page == "time":
	st.header("Time Left to Exam")
	existing = get_exam_datetime(st.session_state.user)
	if existing:
		st.write("Saved exam:", existing)
	d = st.date_input("Exam date", value=date.today())
	t = st.time_input("Exam time", value=time(9,0))
	if st.button("Save exam datetime"):
		dt = datetime.combine(d, t)
		set_exam_datetime(st.session_state.user, dt.isoformat())
		st.success("Saved exam datetime")
	saved = get_exam_datetime(st.session_state.user)
	if saved:
		then = datetime.fromisoformat(saved)
		now = datetime.now()
		diff = then - now
		if diff.total_seconds() <= 0:
			st.warning("Exam time is in the past")
		else:
			days = diff.days
			hours = diff.seconds // 3600
			mins = (diff.seconds % 3600) // 60
			st.metric("Time left", f"{days}d {hours}h {mins}m")
			if st.button("Refresh countdown"):
				st.experimental_rerun()

elif st.session_state.page == "screen":
	st.header("Screen Time Tracker")
	with st.form("screen_form"):
		ed = st.date_input("Date", value=date.today())
		minutes = st.number_input("Minutes spent on screen", min_value=0, step=5)
		submit = st.form_submit_button("Log")
	if submit:
		add_screen_time(st.session_state.user, ed.isoformat(), int(minutes))
		st.success("Logged %s minutes for %s" % (minutes, ed.isoformat()))
	st.subheader("History")
	sdf = get_screen_time(st.session_state.user)
	if sdf.empty:
		st.info("No screen time logged yet.")
	else:
		st.dataframe(sdf)

	st.subheader("Daily totals (last 30)")
	if not sdf.empty:
		sdf2 = sdf.groupby('entry_date').minutes.sum().reset_index()
		st.bar_chart(sdf2.set_index('entry_date'))

