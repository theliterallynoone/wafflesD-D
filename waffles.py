import streamlit as st
import sqlite3
from pathlib import Path
import pandas as pd
from datetime import datetime, date, time, timedelta
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
			minutes INTEGER,
			utility TEXT DEFAULT 'General'
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
		cur.execute("INSERT OR IGNORE INTO users(username, password_hash) VALUES (?,?)", ("V", hash_pw("weball")))
		cur.execute("INSERT OR IGNORE INTO users(username, password_hash) VALUES (?,?)", ("beastboy", hash_pw("changeme")))
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

def add_screen_time(username, entry_date, minutes, utility="General"):
	conn = get_conn()
	cur = conn.cursor()
	cur.execute("INSERT INTO screen_time(username,entry_date,minutes,utility) VALUES (?,?,?,?)", (username, entry_date, minutes, utility))
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

PHYSICS_CHAPTERS = [
	"Physics and Measurement",
	"Kinematics",
	"Laws of Motion",
	"Work, Energy, and Power",
	"System of Particles and Rotational Motion",
	"Gravitation",
	"Mechanical Properties of Solids",
	"Mechanical Properties of Fluids",
	"Thermal Properties of Matter",
	"Thermodynamics",
	"Kinetic Theory of Gases",
	"Oscillations",
	"Waves",
	"Electrostatics",
	"Current Electricity",
	"Magnetic Effects of Current and Magnetism",
	"Electromagnetic Induction and Alternating Currents",
	"Electromagnetic Waves",
	"Ray Optics and Optical Instruments",
	"Wave Optics",
	"Dual Nature of Matter and Radiation",
	"Atoms and Nuclei",
	"Electronic Devices",
	"Communication Systems",
]

MATH_CHAPTERS = [
	"Sets, Relations, and Functions",
	"Complex Numbers",
	"Quadratic Equations",
	"Matrices",
	"Determinants",
	"Permutations and Combinations",
	"Binomial Theorem",
	"Sequences and Series",
	"Limits, Continuity, and Differentiability",
	"Differentiation (Application of Derivatives)",
	"Indefinite Integration",
	"Definite Integration (and Area Under Curves)",
	"Differential Equations",
	"Straight Lines",
	"Circles",
	"Conic Sections (Parabola, Ellipse, and Hyperbola)",
	"Vector Algebra",
	"Three-Dimensional Geometry (3D)",
	"Trigonometric Functions and Identities",
	"Trigonometric Equations",
	"Inverse Trigonometric Functions",
	"Statistics",
	"Probability",
	"Linear Programming",
]

CHEMISTRY_CHAPTERS = [
	"Some Basic Concepts in Chemistry",
	"Atomic Structure",
	"Chemical Bonding and Molecular Structure",
	"Chemical Thermodynamics",
	"Solutions",
	"Equilibrium",
	"Redox Reactions and Electrochemistry",
	"Chemical Kinetics",
	"Classification of Elements and Periodicity in Properties",
	"p-Block Elements",
	"d- and f-Block Elements",
	"Coordination Compounds",
	"Purification and Characterisation of Organic Compounds",
	"Some Basic Principles of Organic Chemistry",
	"Hydrocarbons",
	"Organic Compounds Containing Halogens",
	"Organic Compounds Containing Oxygen",
	"Organic Compounds Containing Nitrogen",
	"Biomolecules",
	"Principles Related to Practical Chemistry",
]

CHAPTER_MAPPING = {
	"Physics": PHYSICS_CHAPTERS,
	"Chemistry": CHEMISTRY_CHAPTERS,
	"Math": MATH_CHAPTERS,
}

DEF_SUBJECTS = ["Physics", "Chemistry", "Math"]
CHAPTER_COUNT = 24  # Max chapters across all subjects
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

# Theme definitions
THEMES = {
	"Dark Mode": {
		"bg_color": "#0b111c",
		"text_color": "#c9d1d9",
		"button_bg": "#161b2b",
		"button_text": "#f5f7ff",
		"input_bg": "#09101f",
		"input_text": "#f5f7ff",
		"expander_bg": "#12182b",
		"expander_text": "#c9d1d9",
	},
	"Beige": {
		"bg_color": "#FAF6F1",
		"text_color": "#1a1a1a",
		"button_bg": "#E8DCC8",
		"button_text": "#1a1a1a",
		"input_bg": "#FFFAF5",
		"input_text": "#1a1a1a",
		"expander_bg": "#F0E8DC",
		"expander_text": "#1a1a1a",
	},
	"Light Mode": {
		"bg_color": "#ffffff",
		"text_color": "#000000",
		"button_bg": "#e0e0e0",
		"button_text": "#000000",
		"input_bg": "#f5f5f5",
		"input_text": "#000000",
		"expander_bg": "#f0f0f0",
		"expander_text": "#000000",
	},
	"Pastel Pink": {
		"bg_color": "#fff5f7",
		"text_color": "#1a1a1a",
		"button_bg": "#FFD1DC",
		"button_text": "#1a1a1a",
		"input_bg": "#ffe6f0",
		"input_text": "#1a1a1a",
		"expander_bg": "#ffc9dd",
		"expander_text": "#1a1a1a",
	},
	"Teal": {
		"bg_color": "#f0f8f7",
		"text_color": "#1a1a1a",
		"button_bg": "#8fb6ab",
		"button_text": "#ffffff",
		"input_bg": "#d8e8e5",
		"input_text": "#1a1a1a",
		"expander_bg": "#a8c5bf",
		"expander_text": "#1a1a1a",
	},
	"Green": {
		"bg_color": "#f5faf3",
		"text_color": "#1a1a1a",
		"button_bg": "#afd69b",
		"button_text": "#1a1a1a",
		"input_bg": "#d9e8ce",
		"input_text": "#1a1a1a",
		"expander_bg": "#c2ddb5",
		"expander_text": "#1a1a1a",
	},
	"Sage": {
		"bg_color": "#f5f7f6",
		"text_color": "#1a1a1a",
		"button_bg": "#8ca19e",
		"button_text": "#ffffff",
		"input_bg": "#d3dbd9",
		"input_text": "#1a1a1a",
		"expander_bg": "#a8b8b4",
		"expander_text": "#1a1a1a",
	},
}

def apply_theme(theme_name):
	theme = THEMES.get(theme_name, THEMES["Dark Mode"])
	st.markdown(
		f"""
		<style>
			body, .main, .stApp {{
				background-color: {theme['bg_color']};
				color: {theme['text_color']};
			}}
			.stButton button {{
				background-color: {theme['button_bg']};
				color: {theme['button_text']};
			}}
			.stTextInput>div>div>input, .stNumberInput>div>div>input, .stDateInput>div>div>input, .stSelectbox>div>div>select {{
				background-color: {theme['input_bg']};
				color: {theme['input_text']};
			}}
			.stCheckbox>div {{
				color: {theme['text_color']};
			}}
			.stExpanderHeader {{
				background-color: {theme['expander_bg']};
				color: {theme['expander_text']};
			}}
		</style>
		""",
		unsafe_allow_html=True,
	)

st.set_page_config(page_title="D and D's Daily Tracker", page_icon=":guardsman:", layout="centered")


if "user" not in st.session_state:
	st.session_state.user = None
if "page" not in st.session_state:
	st.session_state.page = "home"
if "theme" not in st.session_state:
	st.session_state.theme = "Beige"

# Apply the current theme
apply_theme(st.session_state.theme)

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

# Theme selector in sidebar
st.sidebar.header("Settings")
new_theme = st.sidebar.selectbox("Choose Theme", list(THEMES.keys()), index=list(THEMES.keys()).index(st.session_state.theme))
if new_theme != st.session_state.theme:
	st.session_state.theme = new_theme
	st.rerun()

if st.sidebar.button("Log out"):
	logout()

st.sidebar.header("Navigation")
if st.sidebar.button("Home"):
	st.session_state.page = "home"
if st.sidebar.button("Preparation Tracker"):
	st.session_state.page = "prep"
if st.sidebar.button("Screen Time Tracker"):
	st.session_state.page = "screen"

if st.session_state.page == "home":
	st.markdown("## Welcome back")
	
elif st.session_state.page == "prep":
	st.header("Preparation Tracker")
	st.write("Track progress for Physics, Chemistry, and Math chapters. Check the tasks you have completed, then save progress for the selected subject.")
	selected_subject = st.selectbox("Choose subject", DEF_SUBJECTS)
	current_progress = load_chapter_progress(st.session_state.user, selected_subject)
	chapters = CHAPTER_MAPPING.get(selected_subject, [])
	
	with st.form("chapter_progress"):
		save_progress = st.form_submit_button("Save progress")
		for chapter_num, chapter_name in enumerate(chapters, 1):
			chapter_data = current_progress.get(chapter_num, {task: False for task in TASK_COLUMNS})
			with st.expander(f"{chapter_num}. {chapter_name}"):
				col1, col2, col3 = st.columns([1, 1, 1])
				col1.checkbox("Theory", value=chapter_data["theory"], key=f"{selected_subject}_{chapter_num}_theory")
				col1.checkbox("Notes", value=chapter_data["notes"], key=f"{selected_subject}_{chapter_num}_notes")
				col2.checkbox("Questions", value=chapter_data["questions"], key=f"{selected_subject}_{chapter_num}_questions")
				col2.checkbox("Board PYQs", value=chapter_data["board_pyqs"], key=f"{selected_subject}_{chapter_num}_board_pyqs")
				col3.checkbox("JEE Main PYQs", value=chapter_data["jee_main_pyqs"], key=f"{selected_subject}_{chapter_num}_jee_main_pyqs")
	if save_progress:
		progress_updates = {}
		for chapter_num in range(1, len(chapters) + 1):
			progress_updates[chapter_num] = {
				"theory": st.session_state[f"{selected_subject}_{chapter_num}_theory"],
				"notes": st.session_state[f"{selected_subject}_{chapter_num}_notes"],
				"questions": st.session_state[f"{selected_subject}_{chapter_num}_questions"],
				"board_pyqs": st.session_state[f"{selected_subject}_{chapter_num}_board_pyqs"],
				"jee_main_pyqs": st.session_state[f"{selected_subject}_{chapter_num}_jee_main_pyqs"],
			}
		save_chapter_progress(st.session_state.user, selected_subject, progress_updates)
		st.success(f"Saved {selected_subject} chapter progress.")

elif st.session_state.page == "screen":
	st.header("Screen Time Tracker")
	
	# Common utilities
	utilities = ["General", "Social Media", "Gaming", "Study", "Entertainment", "Work", "Other"]
	
	with st.form("screen_form"):
		ed = st.date_input("Date", value=date.today())
		utility = st.selectbox("Utility/App Category", utilities)
		hours = st.number_input("Hours", min_value=0, max_value=24, step=1)
		minutes = st.number_input("Additional Minutes", min_value=0, max_value=59, step=5)
		submit = st.form_submit_button("Log")
	if submit:
		total_minutes = hours * 60 + minutes
		if total_minutes > 0:
			add_screen_time(st.session_state.user, ed.isoformat(), total_minutes, utility)
			st.success(f"Logged {hours}h {minutes}m for {utility} on {ed.isoformat()}")
	
	st.subheader("History")
	sdf = get_screen_time(st.session_state.user)
	if sdf.empty:
		st.info("No screen time logged yet.")
	else:
		# Format display with hours and minutes
		display_df = sdf.copy()
		display_df['duration'] = display_df['minutes'].apply(lambda x: f"{x//60}h {x%60}m")
		display_df['entry_date'] = pd.to_datetime(display_df['entry_date']).dt.strftime('%Y-%m-%d')
		st.dataframe(display_df[['entry_date', 'utility', 'duration']], use_container_width=True)
	
	st.subheader("Daily Totals (Last 30 Days)")
	if not sdf.empty:
		sdf_daily = sdf.copy()
		sdf_daily['entry_date'] = pd.to_datetime(sdf_daily['entry_date']).dt.date
		daily_totals = sdf_daily.groupby('entry_date')['minutes'].sum().reset_index()
		daily_totals = daily_totals.sort_values('entry_date', ascending=False).head(30)
		daily_totals['hours'] = daily_totals['minutes'] // 60
		daily_totals['mins'] = daily_totals['minutes'] % 60
		daily_totals['duration'] = daily_totals.apply(lambda x: f"{int(x['hours'])}h {int(x['mins'])}m", axis=1)
		daily_totals = daily_totals.sort_values('entry_date')
		
		st.bar_chart(daily_totals.set_index('entry_date')[['minutes']])
	
	st.subheader("Weekly Totals")
	if not sdf.empty:
		sdf_weekly = sdf.copy()
		sdf_weekly['entry_date'] = pd.to_datetime(sdf_weekly['entry_date'])
		sdf_weekly['week'] = sdf_weekly['entry_date'].dt.strftime('%Y-W%U')
		weekly_totals = sdf_weekly.groupby('week')['minutes'].sum().reset_index()
		weekly_totals['hours'] = weekly_totals['minutes'] // 60
		weekly_totals['mins'] = weekly_totals['minutes'] % 60
		weekly_totals['duration'] = weekly_totals.apply(lambda x: f"{int(x['hours'])}h {int(x['mins'])}m", axis=1)
		
		st.dataframe(weekly_totals[['week', 'duration']], use_container_width=True)
		st.bar_chart(weekly_totals.set_index('week')[['minutes']])

