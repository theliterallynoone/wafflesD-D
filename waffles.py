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


if "user" not in st.session_state:
	st.session_state.user = None
if "page" not in st.session_state:
	st.session_state.page = "home"

def logout():
	st.session_state.user = None
	st.session_state.page = "home"

if st.session_state.user is None:
	if st.session_state.page != "home":
		st.session_state.page = "home"
	st.header("Waffles D$D")
	st.subheader("(secure) daily tracking for you and me <3")
	st.write("Use your login below to access the preparation tracker, exam countdown, and screen time logger.")
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
	st.write("Only two users are allowed (u & me gurll)")
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
	st.markdown("## Welcome back")
	
elif st.session_state.page == "prep":
	st.header("Preparation Tracker")
	st.write("Track progress for Physics, Chemistry, and Math chapters. Check the tasks you have completed, then save progress for the selected subject.")
	selected_subject = st.selectbox("Choose subject", DEF_SUBJECTS)
	current_progress = load_chapter_progress(st.session_state.user, selected_subject)
	with st.form("chapter_progress"):
		save_progress = st.form_submit_button("Save progress")
		for chapter in range(1, CHAPTER_COUNT + 1):
			chapter_data = current_progress.get(chapter, {task: False for task in TASK_COLUMNS})
			with st.expander(f"Chapter {chapter}"):
				col1, col2, col3 = st.columns([1, 1, 1])
				col1.checkbox("Theory", value=chapter_data["theory"], key=f"{selected_subject}_{chapter}_theory")
				col1.checkbox("Notes", value=chapter_data["notes"], key=f"{selected_subject}_{chapter}_notes")
				col2.checkbox("Questions", value=chapter_data["questions"], key=f"{selected_subject}_{chapter}_questions")
				col2.checkbox("Board PYQs", value=chapter_data["board_pyqs"], key=f"{selected_subject}_{chapter}_board_pyqs")
				col3.checkbox("JEE Main PYQs", value=chapter_data["jee_main_pyqs"], key=f"{selected_subject}_{chapter}_jee_main_pyqs")
	if save_progress:
		progress_updates = {}
		for chapter in range(1, CHAPTER_COUNT + 1):
			progress_updates[chapter] = {
				"theory": st.session_state[f"{selected_subject}_{chapter}_theory"],
				"notes": st.session_state[f"{selected_subject}_{chapter}_notes"],
				"questions": st.session_state[f"{selected_subject}_{chapter}_questions"],
				"board_pyqs": st.session_state[f"{selected_subject}_{chapter}_board_pyqs"],
				"jee_main_pyqs": st.session_state[f"{selected_subject}_{chapter}_jee_main_pyqs"],
			}
		save_chapter_progress(st.session_state.user, selected_subject, progress_updates)
		st.success(f"Saved {selected_subject} chapter progress.")

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

