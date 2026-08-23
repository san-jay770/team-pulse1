# ============================================================
# TEAM PULSE
# Complete Team Task Management App
# Flask + SQLite Database
# ============================================================

from flask import Flask, request, redirect, session, render_template_string, send_from_directory, jsonify, Response
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from functools import wraps
import sqlite3
import os
from datetime import datetime, date, timedelta

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-secret-key")
app.permanent_session_lifetime = timedelta(days=3650)

DATABASE = "team_pulse.db"
UPLOAD_FOLDER = "uploads"

os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ============================================================
# DATABASE
# ============================================================

def db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():

    conn = db()

    conn.executescript("""

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        active INTEGER DEFAULT 1,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS roles (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        role TEXT NOT NULL,
        UNIQUE(user_id, role),
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        email TEXT NOT NULL,
        created_at TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS team_members (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        team_id INTEGER NOT NULL,
        user_id INTEGER NOT NULL,
        UNIQUE(team_id, user_id),
        FOREIGN KEY(team_id) REFERENCES teams(id) ON DELETE CASCADE,
        FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        team_id INTEGER,
        assigned_to INTEGER,
        priority TEXT DEFAULT 'MEDIUM',
        status TEXT DEFAULT 'NEW',
        result TEXT,
        created_at TEXT NOT NULL,
        completed_at TEXT,
        FOREIGN KEY(team_id) REFERENCES teams(id),
        FOREIGN KEY(assigned_to) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS doubts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        question TEXT NOT NULL,
        response TEXT,
        status TEXT DEFAULT 'OPEN',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        response TEXT,
        status TEXT DEFAULT 'SUBMITTED',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS hit_points (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        title TEXT NOT NULL,
        description TEXT NOT NULL,
        importance TEXT DEFAULT 'MEDIUM',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message TEXT NOT NULL,
        icon TEXT DEFAULT '🔵',
        created_at TEXT NOT NULL,
        FOREIGN KEY(user_id) REFERENCES users(id)
    );

    """)

    # ------------------------------------------------------
    # MIGRATIONS - add new columns if upgrading an old DB
    # ------------------------------------------------------

    existing_cols = [
        r["name"]
        for r in conn.execute("PRAGMA table_info(tasks)").fetchall()
    ]

    if "due_date" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN due_date TEXT")

    if "attachment" not in existing_cols:
        conn.execute("ALTER TABLE tasks ADD COLUMN attachment TEXT")

    conn.commit()
    conn.close()


def time_now():
    return datetime.now().strftime("%d %b %Y, %I:%M %p")


def add_activity(message, icon="🔵", user_id=None):

    conn = db()

    conn.execute("""
        INSERT INTO activities
        (user_id, message, icon, created_at)
        VALUES (?, ?, ?, ?)
    """, (user_id, message, icon, time_now()))

    conn.commit()
    conn.close()


# ============================================================
# USER / ROLE FUNCTIONS
# ============================================================

def create_user(name, email, password, role):

    conn = db()

    email = email.lower()

    user = conn.execute(
        "SELECT id FROM users WHERE email=?",
        (email,)
    ).fetchone()

    if user:
        user_id = user["id"]
    else:
        cur = conn.execute("""
            INSERT INTO users
            (name, email, password_hash, created_at)
            VALUES (?, ?, ?, ?)
        """, (
            name,
            email,
            generate_password_hash(password),
            time_now()
        ))

        user_id = cur.lastrowid

    conn.execute("""
        INSERT OR IGNORE INTO roles
        (user_id, role)
        VALUES (?, ?)
    """, (user_id, role))

    conn.commit()
    conn.close()

    return user_id


def create_team(name, email):

    conn = db()

    conn.execute("""
        INSERT OR IGNORE INTO teams
        (name, email, created_at)
        VALUES (?, ?, ?)
    """, (name, email, time_now()))

    conn.commit()
    conn.close()


def add_member_to_team(user_id, team_name):

    conn = db()

    team = conn.execute(
        "SELECT id FROM teams WHERE name=?",
        (team_name,)
    ).fetchone()

    if team:

        conn.execute("""
            INSERT OR IGNORE INTO team_members
            (team_id, user_id)
            VALUES (?, ?)
        """, (team["id"], user_id))

    conn.commit()
    conn.close()


def seed_data():

    conn = db()

    existing = conn.execute(
        "SELECT COUNT(*) AS count FROM users"
    ).fetchone()["count"]

    conn.close()

    if existing > 0:
        return

    # --------------------------------------------------------
    # TEAMS
    # --------------------------------------------------------

    create_team("Alpha", "alpha@gmail.com")
    create_team("Beta", "beta@gmail.com")
    create_team("Gamma", "gamma@gmail.com")

    # --------------------------------------------------------
    # SUPER ADMINS
    # --------------------------------------------------------

    create_user(
        "Prem Kumar",
        "premkumarsir@gmail.com",
        "Premkumar123",
        "SUPER_ADMIN"
    )

    create_user(
        "Sanjay",
        "sanjayt@gmail.com",
        "Siva1908",
        "SUPER_ADMIN"
    )

    create_user(
        "Parthasharathy",
        "parthasharathy87@gmail.com",
        "partha2006",
        "SUPER_ADMIN"
    )

    # --------------------------------------------------------
    # ADMINS
    # --------------------------------------------------------

    sanjay = create_user(
        "Sanjay",
        "sanjayt@gmail.com",
        "Siva1908",
        "ADMIN"
    )

    partha = create_user(
        "Parthasharathy",
        "parthasharathy87@gmail.com",
        "partha2006",
        "ADMIN"
    )

    prem = create_user(
        "Prem Kumar",
        "premkumarsir@gmail.com",
        "Premkumar123",
        "ADMIN"
    )

    # Store admin team memberships
    add_member_to_team(sanjay, "Alpha")
    add_member_to_team(partha, "Beta")
    add_member_to_team(prem, "Gamma")

    # --------------------------------------------------------
    # MEMBERS
    # --------------------------------------------------------

    alpha1 = create_user(
        "Alpha Member 1",
        "alpha1@gmail.com",
        "alpha123",
        "TEAM_MEMBER"
    )

    alpha2 = create_user(
        "Alpha Member 2",
        "alpha2@gmail.com",
        "alpha123",
        "TEAM_MEMBER"
    )

    beta1 = create_user(
        "Beta Member 1",
        "beta1@gmail.com",
        "beta123",
        "TEAM_MEMBER"
    )

    beta2 = create_user(
        "Beta Member 2",
        "beta2@gmail.com",
        "beta123",
        "TEAM_MEMBER"
    )

    gamma1 = create_user(
        "Gamma Member 1",
        "gamma1@gmail.com",
        "gamma123",
        "TEAM_MEMBER"
    )

    gamma2 = create_user(
        "Gamma Member 2",
        "gamma2@gmail.com",
        "gamma123",
        "TEAM_MEMBER"
    )

    add_member_to_team(alpha1, "Alpha")
    add_member_to_team(alpha2, "Alpha")

    add_member_to_team(beta1, "Beta")
    add_member_to_team(beta2, "Beta")

    add_member_to_team(gamma1, "Gamma")
    add_member_to_team(gamma2, "Gamma")

    add_activity(
        "Team Pulse database initialized",
        "🚀"
    )

    add_activity(
        "Alpha, Beta and Gamma teams created",
        "🏢"
    )

    add_activity(
        "6 team members registered",
        "👥"
    )


# ============================================================
# AUTH
# ============================================================

def current_user():

    email = session.get("email")

    if not email:
        return None

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE email=?",
        (email,)
    ).fetchone()

    conn.close()

    return user


def current_role():
    return session.get("role")


def get_user_roles(user_id):

    conn = db()

    rows = conn.execute("""
        SELECT role
        FROM roles
        WHERE user_id=?
    """, (user_id,)).fetchall()

    conn.close()

    return [r["role"] for r in rows]


def get_team_for_user(user_id):

    conn = db()

    team = conn.execute("""
        SELECT t.name
        FROM teams t
        JOIN team_members tm
        ON t.id = tm.team_id
        WHERE tm.user_id=?
        LIMIT 1
    """, (user_id,)).fetchone()

    conn.close()

    return team["name"] if team else None


def login_required(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if not current_user():
            return redirect("/login")

        return fn(*args, **kwargs)

    return wrapper


def role_required(*allowed):

    def decorator(fn):

        @wraps(fn)
        def wrapper(*args, **kwargs):

            if not current_user():
                return redirect("/login")

            if current_role() not in allowed:
                return "Access denied", 403

            return fn(*args, **kwargs)

        return wrapper

    return decorator


# ============================================================
# UI
# ============================================================

CSS = """

* {
    box-sizing:border-box;
}

body {
    margin:0;
    font-family:Arial,sans-serif;
    background:#f1f5f9;
    color:#172033;
    -webkit-tap-highlight-color:transparent;
}

.sidebar {
    position:fixed;
    left:0;
    top:0;
    bottom:0;
    width:245px;
    padding:25px 15px;
    padding-top:calc(25px + env(safe-area-inset-top));
    padding-bottom:calc(25px + env(safe-area-inset-bottom));
    color:white;
    background:linear-gradient(
        180deg,
        #0f3b82,
        #071b3b
    );
    z-index:100;
    transition:transform 0.25s ease;
    overflow-y:auto;
}

.hamburger {
    display:none;
    background:none;
    border:0;
    font-size:24px;
    cursor:pointer;
    color:#172033;
    padding:4px 8px;
}

.overlay {
    display:none;
    position:fixed;
    inset:0;
    background:#00000060;
    z-index:99;
}

.overlay.show {
    display:block;
}

.logo {
    font-size:23px;
    font-weight:900;
    margin:10px 15px 30px;
}

.logo span {
    color:#38bdf8;
}

.nav {
    display:block;
    color:#dbeafe;
    text-decoration:none;
    padding:13px 15px;
    border-radius:12px;
    margin:6px 0;
}

.nav:hover {
    background:#ffffff20;
}

.main {
    margin-left:245px;
}

.topbar {
    height:70px;
    background:white;
    display:flex;
    align-items:center;
    justify-content:space-between;
    padding:0 30px;
    padding-top:env(safe-area-inset-top);
    border-bottom:1px solid #e2e8f0;
}

.content {
    padding:30px;
    padding-bottom:calc(30px + env(safe-area-inset-bottom));
    max-width:1400px;
    margin:auto;
}

h1 {
    margin-bottom:8px;
}

.subtitle {
    color:#64748b;
    margin-bottom:25px;
}

.grid {
    display:grid;
    grid-template-columns:
    repeat(auto-fit,minmax(190px,1fr));
    gap:18px;
}

.card {
    background:white;
    padding:22px;
    border-radius:18px;
    margin-bottom:20px;
    box-shadow:0 8px 25px #0f172a0d;
}

.stat-number {
    font-size:32px;
    font-weight:900;
    margin-top:12px;
}

.stat-label {
    color:#64748b;
}

.quick {
    display:grid;
    grid-template-columns:
    repeat(auto-fit,minmax(130px,1fr));
    gap:15px;
}

.quick a {
    text-decoration:none;
    color:#172033;
}

.quick-card {
    background:white;
    padding:20px;
    border-radius:16px;
    text-align:center;
    box-shadow:0 6px 20px #0f172a0d;
}

.quick-icon {
    font-size:30px;
    margin-bottom:8px;
}

.btn {
    border:0;
    background:#2563eb;
    color:white;
    padding:12px 18px;
    border-radius:11px;
    text-decoration:none;
    cursor:pointer;
    font-weight:bold;
}

.green {
    background:#10b981;
}

.yellow {
    background:#f59e0b;
}

.purple {
    background:#8b5cf6;
}

input,
textarea,
select {
    width:100%;
    padding:13px;
    margin:7px 0 16px;
    border:1px solid #cbd5e1;
    border-radius:11px;
}

textarea {
    min-height:120px;
}

label {
    font-weight:bold;
}

.badge {
    display:inline-block;
    padding:6px 10px;
    border-radius:20px;
    background:#dbeafe;
    color:#1e40af;
    font-size:12px;
    font-weight:bold;
}

.progress {
    height:10px;
    background:#e2e8f0;
    border-radius:20px;
    overflow:hidden;
}

.progress-bar {
    height:100%;
    background:linear-gradient(
        90deg,#2563eb,#06b6d4
    );
}

.activity {
    padding:14px 0;
    border-bottom:1px solid #e2e8f0;
}

.login {
    min-height:100vh;
    display:flex;
    align-items:center;
    justify-content:center;
    background:linear-gradient(
        135deg,#071b3b,#0f3b82
    );
    padding:20px;
}

.login-card {
    width:420px;
    max-width:100%;
    background:white;
    padding:35px;
    border-radius:25px;
}

.login-logo {
    text-align:center;
    font-size:32px;
    font-weight:900;
    color:#123c73;
    margin-bottom:25px;
}

.pwd-wrap {
    position:relative;
}

.pwd-wrap input {
    padding-right:45px;
}

.pwd-toggle {
    position:absolute;
    right:14px;
    top:22px;
    cursor:pointer;
    user-select:none;
    color:#64748b;
    display:flex;
    align-items:center;
}

.pwd-toggle:hover {
    color:#2563eb;
}

.pwd-toggle svg {
    width:20px;
    height:20px;
}

@media(max-width:800px) {

    .sidebar {
        transform:translateX(-100%);
        width:80%;
        max-width:280px;
        box-shadow:4px 0 25px #00000040;
    }

    .sidebar.open {
        transform:translateX(0);
    }

    .hamburger {
        display:block;
    }

    .main {
        margin-left:0;
    }

    .content {
        padding:18px;
    }

    .topbar {
        padding:0 15px;
        padding-top:env(safe-area-inset-top);
    }

    .btn,
    input,
    textarea,
    select {
        font-size:16px;
    }

    .btn {
        padding:14px 18px;
    }
}

"""


PWA_HEAD = """
<meta name="viewport"
content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f3b82">
<meta name="mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="Team Pulse">
<link rel="manifest" href="/manifest.json">
<link rel="apple-touch-icon" href="/static/icon-192.png">
<link rel="icon" href="/static/icon-192.png">
"""


def page(title, body):

    user = current_user()

    if not user:

        return render_template_string("""
        <!DOCTYPE html>
        <html>
        <head>
        <title>Team Pulse</title>
        {{ pwa_head|safe }}
        <style>{{ css }}</style>
        </head>
        <body>
        {{ body|safe }}
        </body>
        </html>
        """, css=CSS, body=body, pwa_head=PWA_HEAD)

    return render_template_string("""
    <!DOCTYPE html>
    <html>
    <head>
    <title>{{ title }} - Team Pulse</title>
    {{ pwa_head|safe }}
    <style>{{ css }}</style>
    </head>

    <body>

    <div class="overlay" id="navOverlay" onclick="closeNav()"></div>

    <aside class="sidebar" id="sidebar">

        <div class="logo">
            ⚡ TEAM <span>PULSE</span>
        </div>

        <a class="nav" href="/dashboard">
            🏠 Dashboard
        </a>

        <a class="nav" href="/tasks">
            📋 Tasks
        </a>

        <a class="nav" href="/doubts">
            💬 Doubts
        </a>

        <a class="nav" href="/suggestions">
            💡 Suggestions
        </a>

        <a class="nav" href="/hit-points">
            ⭐ Hit Points
        </a>

        {% if role in ["SUPER_ADMIN","ADMIN"] %}
        <a class="nav" href="/add-task">
            ➕ Add Task
        </a>
        {% endif %}

        {% if role == "SUPER_ADMIN" %}
        <a class="nav" href="/users">
            👥 Users
        </a>

        <a class="nav" href="/add-team">
            🏢 Add Team
        </a>
        {% endif %}

        <br>

        <a class="nav" href="/logout">
            🚪 Logout
        </a>

    </aside>

    <main class="main">

        <header class="topbar">

            <span style="display:flex;align-items:center;gap:12px">

                <button class="hamburger"
                id="hamburgerBtn"
                onclick="openNav()"
                aria-label="Menu">
                    ☰
                </button>

                <b>{{ role.replace("_"," ") }}</b>

            </span>

            <span>
                👤 {{ user["name"] }}
            </span>

        </header>

        <section class="content">

            {{ body|safe }}

        </section>

    </main>

    <script>
    function openNav() {
        document.getElementById('sidebar').classList.add('open');
        document.getElementById('navOverlay').classList.add('show');
    }
    function closeNav() {
        document.getElementById('sidebar').classList.remove('open');
        document.getElementById('navOverlay').classList.remove('show');
    }
    if ('serviceWorker' in navigator) {
        navigator.serviceWorker.register('/service-worker.js').catch(function(){});
    }
    </script>

    </body>
    </html>
    """,
    css=CSS,
    title=title,
    body=body,
    user=user,
    role=current_role(),
    pwa_head=PWA_HEAD)


# ============================================================
# PWA - MANIFEST & SERVICE WORKER
# ============================================================

@app.route("/manifest.json")
def manifest():

    return jsonify({
        "name": "Team Pulse",
        "short_name": "TeamPulse",
        "start_url": "/dashboard",
        "display": "standalone",
        "background_color": "#071b3b",
        "theme_color": "#0f3b82",
        "orientation": "portrait-primary",
        "icons": [
            {
                "src": "/static/icon-192.png",
                "sizes": "192x192",
                "type": "image/png",
                "purpose": "any maskable"
            },
            {
                "src": "/static/icon-512.png",
                "sizes": "512x512",
                "type": "image/png",
                "purpose": "any maskable"
            }
        ]
    })


@app.route("/service-worker.js")
def service_worker():

    js = """
    const CACHE_NAME = 'team-pulse-v1';

    self.addEventListener('install', function(event) {
        self.skipWaiting();
    });

    self.addEventListener('activate', function(event) {
        self.clients.claim();
    });

    self.addEventListener('fetch', function(event) {
        event.respondWith(
            fetch(event.request).catch(function() {
                return caches.match(event.request);
            })
        );
    });
    """

    return Response(js, mimetype="application/javascript")


# ============================================================
# LOGIN
# ============================================================

@app.route("/", methods=["GET", "POST"])
@app.route("/login", methods=["GET", "POST"])
def login():

    error = ""

    if request.method == "POST":

        email = request.form["email"].lower().strip()
        password = request.form["password"]

        conn = db()

        user = conn.execute(
            "SELECT * FROM users WHERE email=?",
            (email,)
        ).fetchone()

        conn.close()

        if user and check_password_hash(
            user["password_hash"],
            password
        ):

            session.permanent = True
            session["email"] = email

            roles = get_user_roles(user["id"])

            if "SUPER_ADMIN" in roles:
                session["role"] = "SUPER_ADMIN"

            elif "ADMIN" in roles:
                session["role"] = "ADMIN"

            else:
                session["role"] = "TEAM_MEMBER"

            add_activity(
                f"{user['name']} logged in",
                "🔐",
                user["id"]
            )

            return redirect("/dashboard")

        error = "Invalid email or password."

    body = f"""

    <div class="login">

    <div class="login-card">

        <div class="login-logo">
            ⚡ TEAM <span>PULSE</span>
        </div>

        <p style="text-align:center;color:#64748b">
            Connect • Assign • Track • Achieve
        </p>

        <p style="color:red">
            {error}
        </p>

        <form method="POST" action="/login">

            <label>Email</label>

            <input
            type="email"
            name="email"
            placeholder="Enter email"
            required>

            <label>Password</label>

            <div class="pwd-wrap">

                <input
                type="password"
                id="pwd"
                name="password"
                placeholder="Enter password"
                required>

                <span class="pwd-toggle"
                onclick="togglePwd()"
                id="pwdIcon">

                    <svg id="eyeOpen" xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round">
                        <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>
                        <circle cx="12" cy="12" r="3"/>
                    </svg>

                    <svg id="eyeClosed" xmlns="http://www.w3.org/2000/svg"
                    viewBox="0 0 24 24" fill="none"
                    stroke="currentColor" stroke-width="2"
                    stroke-linecap="round" stroke-linejoin="round"
                    style="display:none">
                        <path d="M17.94 17.94A10.94 10.94 0 0 1 12 20c-7 0-11-8-11-8a18.6 18.6 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"/>
                        <line x1="1" y1="1" x2="23" y2="23"/>
                    </svg>

                </span>

            </div>

            <button class="btn"
            style="width:100%">
                LOGIN →
            </button>

        </form>

    </div>

    </div>

    <script>
    function togglePwd() {{
        const el = document.getElementById('pwd');
        const eyeOpen = document.getElementById('eyeOpen');
        const eyeClosed = document.getElementById('eyeClosed');
        if (el.type === 'password') {{
            el.type = 'text';
            eyeOpen.style.display = 'none';
            eyeClosed.style.display = 'block';
        }} else {{
            el.type = 'password';
            eyeOpen.style.display = 'block';
            eyeClosed.style.display = 'none';
        }}
    }}
    </script>

    """

    return page("Login", body)


# ============================================================
# UPLOADED FILES
# ============================================================

@app.route("/uploads/<path:filename>")
@login_required
def uploaded_file(filename):

    return send_from_directory(UPLOAD_FOLDER, filename)


# ============================================================
# LOGOUT
# ============================================================

@app.route("/logout")
def logout():

    session.clear()

    return redirect("/login")


# ============================================================
# DASHBOARD
# ============================================================

@app.route("/dashboard")
@login_required
def dashboard():

    user = current_user()
    role = current_role()

    conn = db()

    users_count = conn.execute(
        "SELECT COUNT(*) c FROM users"
    ).fetchone()["c"]

    teams_count = conn.execute(
        "SELECT COUNT(*) c FROM teams"
    ).fetchone()["c"]

    tasks_count = conn.execute(
        "SELECT COUNT(*) c FROM tasks"
    ).fetchone()["c"]

    doubts_count = conn.execute(
        "SELECT COUNT(*) c FROM doubts"
    ).fetchone()["c"]

    suggestions_count = conn.execute(
        "SELECT COUNT(*) c FROM suggestions"
    ).fetchone()["c"]

    hits_count = conn.execute(
        "SELECT COUNT(*) c FROM hit_points"
    ).fetchone()["c"]

    completed = conn.execute(
        "SELECT COUNT(*) c FROM tasks WHERE status='COMPLETED'"
    ).fetchone()["c"]

    activities = conn.execute("""
        SELECT *
        FROM activities
        ORDER BY id DESC
        LIMIT 8
    """).fetchall()

    conn.close()

    progress = (
        int(completed / tasks_count * 100)
        if tasks_count else 0
    )

    team = get_team_for_user(user["id"])

    body = f"""

    <h1>Good Morning, {user["name"]} 👋</h1>

    <div class="subtitle">
        Welcome to your Team Pulse workspace.
    </div>

    <div class="grid">

        <div class="card">
            👥
            <div class="stat-number">
                {users_count}
            </div>
            <div class="stat-label">
                Users
            </div>
        </div>

        <div class="card">
            🏢
            <div class="stat-number">
                {teams_count}
            </div>
            <div class="stat-label">
                Teams
            </div>
        </div>

        <div class="card">
            📋
            <div class="stat-number">
                {tasks_count}
            </div>
            <div class="stat-label">
                Tasks
            </div>
        </div>

        <div class="card">
            💬
            <div class="stat-number">
                {doubts_count}
            </div>
            <div class="stat-label">
                Doubts
            </div>
        </div>

        <div class="card">
            💡
            <div class="stat-number">
                {suggestions_count}
            </div>
            <div class="stat-label">
                Suggestions
            </div>
        </div>

        <div class="card">
            ⭐
            <div class="stat-number">
                {hits_count}
            </div>
            <div class="stat-label">
                Hit Points
            </div>
        </div>

    </div>

    <div class="card">

        <h2>📊 Task Progress</h2>

        <div class="progress">
            <div
            class="progress-bar"
            style="width:{progress}%">
            </div>
        </div>

        <br>

        <b>{progress}%</b>
        completed

    </div>

    <h2>⚡ Quick Actions</h2>

    <div class="quick">

        <a href="/tasks">
            <div class="quick-card">
                <div class="quick-icon">📋</div>
                Tasks
            </div>
        </a>

        <a href="/doubts">
            <div class="quick-card">
                <div class="quick-icon">💬</div>
                Doubts
            </div>
        </a>

        <a href="/suggestions">
            <div class="quick-card">
                <div class="quick-icon">💡</div>
                Ideas
            </div>
        </a>

        <a href="/hit-points">
            <div class="quick-card">
                <div class="quick-icon">⭐</div>
                Hit Points
            </div>
        </a>

    </div>

    <br>

    <div class="card">

        <h2>🔥 Recent Activity</h2>

    """

    for a in activities:

        body += f"""

        <div class="activity">

            {a["icon"]}
            <b>{a["message"]}</b>

            <small>
                — {a["created_at"]}
            </small>

        </div>

        """

    body += "</div>"

    # Multiple-role account
    roles = get_user_roles(user["id"])

    if len(roles) > 1:

        body += """

        <div class="card">

        <h2>🔄 Switch Access</h2>

        """

        for r in roles:

            body += f"""

            <a class="btn"
            href="/switch/{r}"
            style="margin-right:8px">
                {r.replace("_"," ")}
            </a>

            """

        body += "</div>"

    return page("Dashboard", body)


# ============================================================
# SWITCH ROLE
# ============================================================

@app.route("/switch/<role>")
@login_required
def switch_role(role):

    user = current_user()

    if role not in get_user_roles(user["id"]):
        return "Role not available", 403

    session["role"] = role

    return redirect("/dashboard")


# ============================================================
# TASKS
# ============================================================

@app.route("/tasks")
@login_required
def tasks_page():

    user = current_user()
    role = current_role()

    conn = db()

    if role == "SUPER_ADMIN":

        tasks = conn.execute("""
            SELECT
                tasks.*,
                teams.name team_name,
                users.name member_name
            FROM tasks
            LEFT JOIN teams
            ON tasks.team_id=teams.id
            LEFT JOIN users
            ON tasks.assigned_to=users.id
            ORDER BY tasks.id DESC
        """).fetchall()

    elif role == "ADMIN":

        team = get_team_for_user(user["id"])

        tasks = conn.execute("""
            SELECT
                tasks.*,
                teams.name team_name,
                users.name member_name
            FROM tasks
            LEFT JOIN teams
            ON tasks.team_id=teams.id
            LEFT JOIN users
            ON tasks.assigned_to=users.id
            WHERE teams.name=?
            ORDER BY tasks.id DESC
        """, (team,)).fetchall()

    else:

        tasks = conn.execute("""
            SELECT
                tasks.*,
                teams.name team_name,
                users.name member_name
            FROM tasks
            LEFT JOIN teams
            ON tasks.team_id=teams.id
            LEFT JOIN users
            ON tasks.assigned_to=users.id
            WHERE tasks.assigned_to=?
            ORDER BY tasks.id DESC
        """, (user["id"],)).fetchall()

    conn.close()

    today_str = date.today().isoformat()

    overdue_tasks = [
        t for t in tasks
        if t["due_date"]
        and t["due_date"] < today_str
        and t["status"] != "COMPLETED"
    ]

    body = """

    <div style="
    display:flex;
    justify-content:space-between;
    align-items:center">

        <div>
            <h1>📋 Tasks</h1>
            <div class="subtitle">
                Track team work and results.
            </div>
        </div>

    """

    if role in ["SUPER_ADMIN", "ADMIN"]:

        body += """
        <a class="btn" href="/add-task">
            + Add Task
        </a>
        """

    body += "</div>"

    if role in ["SUPER_ADMIN", "ADMIN"] and overdue_tasks:

        body += f"""

        <div class="card"
        style="border:2px solid #ef4444">

            <h2 style="color:#ef4444">
                ⏰ Overdue Tasks ({len(overdue_tasks)})
            </h2>

        """

        for ot in overdue_tasks:

            body += f"""

            <div class="activity">

                🔴 <b>{ot["title"]}</b>
                — 👤 {ot["member_name"] or "-"}
                — due {ot["due_date"]}

            </div>

            """

        body += "</div>"

    if not tasks:

        body += """

        <div class="card">
            No tasks found.
        </div>

        """

    for t in tasks:

        is_overdue = (
            t["due_date"]
            and t["due_date"] < today_str
            and t["status"] != "COMPLETED"
        )

        status = (
            "🟢 COMPLETED"
            if t["status"] == "COMPLETED"
            else "🔴 OVERDUE"
            if is_overdue
            else "🟡 " + t["status"]
        )

        card_style = (
            'style="border:2px solid #ef4444"'
            if is_overdue
            else ""
        )

        body += f"""

        <div class="card" {card_style}>

            <h2>
                {t["title"]}
            </h2>

            <p>
                {t["description"]}
            </p>

            <p>
                🏢 Team:
                <b>{t["team_name"] or "-"}</b>
            </p>

            <p>
                👤 Assigned:
                <b>{t["member_name"] or "-"}</b>
            </p>

            <p>
                🔥 Priority:
                <b>{t["priority"]}</b>
            </p>

            <p>
                📅 Due Date:
                <b>{t["due_date"] or "Not set"}</b>
            </p>

            <span class="badge">
                {status}
            </span>

        """

        if t["result"]:

            body += f"""

            <div class="card">

                <b>✅ Task Result</b>

                <p>
                    {t["result"]}
                </p>

            """

            if t["attachment"]:

                body += f"""

                <a class="btn purple"
                href="/uploads/{t["attachment"]}"
                target="_blank">
                    📎 Download Attachment
                </a>

                """

            body += "</div>"

        if (
            role == "TEAM_MEMBER"
            and t["assigned_to"] == user["id"]
            and t["status"] != "COMPLETED"
        ):

            body += f"""

            <form method="POST"
            action="/result/{t["id"]}"
            enctype="multipart/form-data">

                <label>
                    Add Task Result
                </label>

                <textarea
                name="result"
                placeholder="Explain your completed work..."
                required></textarea>

                <label>
                    Attach File (optional)
                </label>

                <input
                type="file"
                name="attachment">

                <button class="btn green">
                    ✅ SUBMIT RESULT
                </button>

            </form>

            """

        body += "</div>"

    return page("Tasks", body)


# ============================================================
# ADD TASK
# ============================================================

@app.route("/add-task", methods=["GET", "POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def add_task():

    user = current_user()
    role = current_role()

    message = ""

    conn = db()

    if request.method == "POST":

        title = request.form["title"]
        description = request.form["description"]
        team_name = request.form["team"]
        assigned_email = request.form["assigned"]
        priority = request.form["priority"]
        due_date = request.form.get("due_date") or None

        team = conn.execute(
            "SELECT id FROM teams WHERE name=?",
            (team_name,)
        ).fetchone()

        assigned = conn.execute(
            "SELECT id FROM users WHERE email=?",
            (assigned_email,)
        ).fetchone()

        if team and assigned:

            conn.execute("""
                INSERT INTO tasks
                (
                    title,
                    description,
                    team_id,
                    assigned_to,
                    priority,
                    status,
                    due_date,
                    created_at
                )
                VALUES (?, ?, ?, ?, ?, 'NEW', ?, ?)
            """, (
                title,
                description,
                team["id"],
                assigned["id"],
                priority,
                due_date,
                time_now()
            ))

            conn.commit()

            add_activity(
                f"New task '{title}' created",
                "📋",
                user["id"]
            )

            message = "Task created successfully."

    if role == "ADMIN":

        team_name = get_team_for_user(user["id"])

        team_rows = conn.execute(
            "SELECT * FROM teams WHERE name=?",
            (team_name,)
        ).fetchall()

        member_rows = conn.execute("""
            SELECT users.*
            FROM users
            JOIN team_members
            ON users.id=team_members.user_id
            JOIN teams
            ON teams.id=team_members.team_id
            WHERE teams.name=?
            AND users.id != ?
        """, (team_name, user["id"])).fetchall()

    else:

        team_rows = conn.execute(
            "SELECT * FROM teams"
        ).fetchall()

        member_rows = conn.execute("""
            SELECT *
            FROM users
            WHERE id IN (
                SELECT user_id
                FROM roles
                WHERE role='TEAM_MEMBER'
            )
        """).fetchall()

    conn.close()

    team_options = ""

    for t in team_rows:

        team_options += f"""
        <option value="{t["name"]}">
            {t["name"]}
        </option>
        """

    member_options = ""

    for m in member_rows:

        member_options += f"""
        <option value="{m["email"]}">
            {m["name"]} — {m["email"]}
        </option>
        """

    body = f"""

    <h1>➕ Create New Task</h1>

    <div class="subtitle">
        Assign a task to a team member.
    </div>

    <div class="card">

        <p style="color:#10b981">
            {message}
        </p>

        <form method="POST">

            <label>Task Title</label>

            <input
            name="title"
            placeholder="Build Login Page"
            required>

            <label>Description</label>

            <textarea
            name="description"
            placeholder="Describe the task..."
            required></textarea>

            <label>Team</label>

            <select name="team">
                {team_options}
            </select>

            <label>Assign To</label>

            <select name="assigned">
                {member_options}
            </select>

            <label>Priority</label>

            <select name="priority">
                <option>LOW</option>
                <option selected>MEDIUM</option>
                <option>HIGH</option>
                <option>CRITICAL</option>
            </select>

            <label>Due Date</label>

            <input
            type="date"
            name="due_date">

            <button class="btn">
                🚀 CREATE TASK
            </button>

        </form>

    </div>

    """

    return page("Add Task", body)


# ============================================================
# TASK RESULT
# ============================================================

@app.route("/result/<int:task_id>", methods=["POST"])
@login_required
def task_result(task_id):

    user = current_user()

    result = request.form["result"]

    conn = db()

    task = conn.execute(
        "SELECT * FROM tasks WHERE id=?",
        (task_id,)
    ).fetchone()

    if not task:
        conn.close()
        return "Task not found", 404

    if task["assigned_to"] != user["id"]:
        conn.close()
        return "Access denied", 403

    attachment_name = task["attachment"]

    uploaded = request.files.get("attachment")

    if uploaded and uploaded.filename:

        safe_name = secure_filename(uploaded.filename)
        attachment_name = f"task{task_id}_{safe_name}"

        uploaded.save(
            os.path.join(UPLOAD_FOLDER, attachment_name)
        )

    conn.execute("""
        UPDATE tasks
        SET result=?,
            status='COMPLETED',
            completed_at=?,
            attachment=?
        WHERE id=?
    """, (
        result,
        time_now(),
        attachment_name,
        task_id
    ))

    conn.commit()
    conn.close()

    add_activity(
        f"{user['name']} completed task",
        "✅",
        user["id"]
    )

    return redirect("/tasks")


# ============================================================
# DOUBTS
# ============================================================

@app.route("/doubts")
@login_required
def doubts_page():

    user = current_user()
    role = current_role()

    conn = db()

    if role == "TEAM_MEMBER":

        rows = conn.execute("""
            SELECT doubts.*, users.name
            FROM doubts
            JOIN users
            ON doubts.user_id=users.id
            WHERE doubts.user_id=?
            ORDER BY doubts.id DESC
        """, (user["id"],)).fetchall()

    else:

        rows = conn.execute("""
            SELECT doubts.*, users.name
            FROM doubts
            JOIN users
            ON doubts.user_id=users.id
            ORDER BY doubts.id DESC
        """).fetchall()

    conn.close()

    body = """

    <div style="
    display:flex;
    justify-content:space-between">

    <h1>💬 Doubts</h1>

    <a class="btn"
    href="/add-doubt">
        + Ask Doubt
    </a>

    </div>

    """

    for d in rows:

        body += f"""

        <div class="card">

            <h2>{d["title"]}</h2>

            <p>
                {d["question"]}
            </p>

            <span class="badge">
                {d["status"]}
            </span>

            <p>
                👤 {d["name"]}
            </p>

            <hr>

            <b>Admin Response</b>

            <p>
                {d["response"] or
                "Waiting for admin response..."}
            </p>

        </div>

        """

    return page("Doubts", body)


@app.route("/add-doubt", methods=["GET", "POST"])
@login_required
def add_doubt():

    user = current_user()
    message = ""

    if request.method == "POST":

        conn = db()

        conn.execute("""
            INSERT INTO doubts
            (
                user_id,
                title,
                question,
                status,
                created_at
            )
            VALUES (?, ?, ?, 'OPEN', ?)
        """, (
            user["id"],
            request.form["title"],
            request.form["question"],
            time_now()
        ))

        conn.commit()
        conn.close()

        add_activity(
            f"{user['name']} asked a doubt",
            "💬",
            user["id"]
        )

        message = "Doubt submitted successfully."

    body = f"""

    <h1>💬 Ask Doubt</h1>

    <div class="card">

        <p style="color:#10b981">
            {message}
        </p>

        <form method="POST">

            <label>Title</label>

            <input
            name="title"
            placeholder="What is your doubt?"
            required>

            <label>Doubt</label>

            <textarea
            name="question"
            placeholder="Explain your doubt..."
            required></textarea>

            <button class="btn">
                💬 SEND DOUBT
            </button>

        </form>

    </div>

    """

    return page("Ask Doubt", body)


# ============================================================
# SUGGESTIONS
# ============================================================

@app.route("/suggestions")
@login_required
def suggestions_page():

    user = current_user()
    role = current_role()

    conn = db()

    if role == "TEAM_MEMBER":

        rows = conn.execute("""
            SELECT suggestions.*, users.name
            FROM suggestions
            JOIN users
            ON suggestions.user_id=users.id
            WHERE suggestions.user_id=?
            ORDER BY suggestions.id DESC
        """, (user["id"],)).fetchall()

    else:

        rows = conn.execute("""
            SELECT suggestions.*, users.name
            FROM suggestions
            JOIN users
            ON suggestions.user_id=users.id
            ORDER BY suggestions.id DESC
        """).fetchall()

    conn.close()

    body = """

    <div style="
    display:flex;
    justify-content:space-between">

    <h1>💡 Suggestions</h1>

    <a class="btn purple"
    href="/add-suggestion">
        + Add Suggestion
    </a>

    </div>

    """

    for s in rows:

        body += f"""

        <div class="card">

            <h2>💡 {s["title"]}</h2>

            <p>
                {s["description"]}
            </p>

            <span class="badge">
                {s["status"]}
            </span>

            <p>
                👤 {s["name"]}
            </p>

            <hr>

            <b>Admin Response</b>

            <p>
                {s["response"] or
                "Waiting for admin response..."}
            </p>

        </div>

        """

    return page("Suggestions", body)


@app.route("/add-suggestion", methods=["GET", "POST"])
@login_required
def add_suggestion():

    user = current_user()
    message = ""

    if request.method == "POST":

        conn = db()

        conn.execute("""
            INSERT INTO suggestions
            (
                user_id,
                title,
                description,
                status,
                created_at
            )
            VALUES (?, ?, ?, 'SUBMITTED', ?)
        """, (
            user["id"],
            request.form["title"],
            request.form["description"],
            time_now()
        ))

        conn.commit()
        conn.close()

        add_activity(
            f"{user['name']} added a suggestion",
            "💡",
            user["id"]
        )

        message = "Suggestion submitted."

    body = f"""

    <h1>💡 Suggest an Idea</h1>

    <div class="card">

        <p style="color:#10b981">
            {message}
        </p>

        <form method="POST">

            <label>Idea Title</label>

            <input
            name="title"
            placeholder="Enter your idea"
            required>

            <label>Description</label>

            <textarea
            name="description"
            placeholder="Explain your suggestion..."
            required></textarea>

            <button class="btn purple">
                💡 SEND SUGGESTION
            </button>

        </form>

    </div>

    """

    return page("Suggestion", body)


# ============================================================
# HIT POINTS
# ============================================================

@app.route("/hit-points")
@login_required
def hit_points_page():

    user = current_user()
    role = current_role()

    conn = db()

    if role == "TEAM_MEMBER":

        rows = conn.execute("""
            SELECT hit_points.*, users.name
            FROM hit_points
            JOIN users
            ON hit_points.user_id=users.id
            WHERE hit_points.user_id=?
            ORDER BY hit_points.id DESC
        """, (user["id"],)).fetchall()

    else:

        rows = conn.execute("""
            SELECT hit_points.*, users.name
            FROM hit_points
            JOIN users
            ON hit_points.user_id=users.id
            ORDER BY hit_points.id DESC
        """).fetchall()

    conn.close()

    body = """

    <div style="
    display:flex;
    justify-content:space-between">

    <h1>⭐ Hit Points</h1>

    <a class="btn yellow"
    href="/add-hit-point">
        + Add Hit Point
    </a>

    </div>

    """

    for h in rows:

        body += f"""

        <div class="card">

            <h2>⭐ {h["title"]}</h2>

            <p>
                {h["description"]}
            </p>

            <span class="badge">
                {h["importance"]}
            </span>

            <p>
                👤 {h["name"]}
            </p>

        </div>

        """

    return page("Hit Points", body)


@app.route("/add-hit-point", methods=["GET", "POST"])
@login_required
def add_hit_point():

    user = current_user()
    message = ""

    if request.method == "POST":

        conn = db()

        conn.execute("""
            INSERT INTO hit_points
            (
                user_id,
                title,
                description,
                importance,
                created_at
            )
            VALUES (?, ?, ?, ?, ?)
        """, (
            user["id"],
            request.form["title"],
            request.form["description"],
            request.form["importance"],
            time_now()
        ))

        conn.commit()
        conn.close()

        add_activity(
            f"{user['name']} added a hit point",
            "⭐",
            user["id"]
        )

        message = "Hit Point added."

    body = f"""

    <h1>⭐ Add Hit Point</h1>

    <div class="card">

        <p style="color:#10b981">
            {message}
        </p>

        <form method="POST">

            <label>Title</label>

            <input
            name="title"
            placeholder="Important point"
            required>

            <label>Description</label>

            <textarea
            name="description"
            placeholder="Explain the point..."
            required></textarea>

            <label>Importance</label>

            <select name="importance">

                <option>LOW</option>
                <option>MEDIUM</option>
                <option>HIGH</option>
                <option>CRITICAL</option>

            </select>

            <button class="btn yellow">
                ⭐ ADD HIT POINT
            </button>

        </form>

    </div>

    """

    return page("Hit Point", body)


# ============================================================
# USER MANAGEMENT
# ============================================================

@app.route("/users")
@role_required("SUPER_ADMIN")
def users_page():

    conn = db()

    users = conn.execute("""
        SELECT *
        FROM users
        ORDER BY id
    """).fetchall()

    conn.close()

    body = """

    <h1>👥 User Management</h1>

    <div class="subtitle">
        Manage Team Pulse users.
    </div>

    <div class="card">

    <a class="btn"
    href="/add-user">
        + Add User
    </a>

    <br><br>

    <div style="overflow-x:auto">

    <table width="100%">

    <tr>
        <th>Name</th>
        <th>Email</th>
        <th>Action</th>
    </tr>

    """

    for u in users:

        body += f"""

        <tr>

            <td>{u["name"]}</td>

            <td>{u["email"]}</td>

            <td>

            <a class="btn"
            href="/password/{u["id"]}">
                🔐 Password
            </a>

            <a class="btn"
            style="background:#ef4444"
            href="/delete-user/{u["id"]}"
            onclick="return confirm('Delete this user? This cannot be undone.')">
                🗑️ Delete
            </a>

            </td>

        </tr>

        """

    body += """

    </table>

    </div>

    </div>

    """

    return page("Users", body)


# ============================================================
# ADD USER
# ============================================================

@app.route("/add-user", methods=["GET", "POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def add_user():

    current = current_user()
    role = current_role()

    message = ""

    conn = db()

    teams = conn.execute(
        "SELECT * FROM teams"
    ).fetchall()

    conn.close()

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"].lower()
        password = request.form["password"]

        selected_role = request.form["role"]
        team_name = request.form["team"]

        if role == "ADMIN":
            selected_role = "TEAM_MEMBER"
            team_name = get_team_for_user(current["id"])

        try:

            user_id = create_user(
                name,
                email,
                password,
                selected_role
            )

            add_member_to_team(
                user_id,
                team_name
            )

            add_activity(
                f"{name} added to Team Pulse",
                "👤",
                current["id"]
            )

            message = "User created successfully."

        except sqlite3.IntegrityError:

            message = "Email already exists."

    team_options = ""

    for t in teams:

        team_options += f"""
        <option>
            {t["name"]}
        </option>
        """

    if role == "ADMIN":

        roles = """
        <option>TEAM_MEMBER</option>
        """

    else:

        roles = """
        <option>TEAM_MEMBER</option>
        <option>TEAM_LEADER</option>
        <option>ADMIN</option>
        """

    body = f"""

    <h1>👤 Add New User</h1>

    <div class="card">

        <p style="color:#10b981">
            {message}
        </p>

        <form method="POST">

            <label>Name</label>

            <input
            name="name"
            required>

            <label>Email</label>

            <input
            type="email"
            name="email"
            required>

            <label>Password</label>

            <input
            type="password"
            name="password"
            required>

            <label>Role</label>

            <select name="role">
                {roles}
            </select>

            <label>Team</label>

            <select name="team">
                {team_options}
            </select>

            <button class="btn green">
                CREATE USER
            </button>

        </form>

    </div>

    """

    return page("Add User", body)


# ============================================================
# DELETE USER
# ============================================================

@app.route("/delete-user/<int:user_id>")
@role_required("SUPER_ADMIN")
def delete_user(user_id):

    current = current_user()

    if user_id == current["id"]:
        return "You cannot delete your own account", 403

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return "User not found", 404

    conn.execute(
        "DELETE FROM users WHERE id=?",
        (user_id,)
    )

    conn.commit()
    conn.close()

    add_activity(
        f"{user['name']} removed from Team Pulse",
        "🗑️",
        current["id"]
    )

    return redirect("/users")


# ============================================================
# PASSWORD CHANGE
# ============================================================

@app.route("/password/<int:user_id>", methods=["GET", "POST"])
@role_required("SUPER_ADMIN")
def password_change(user_id):

    conn = db()

    user = conn.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not user:
        conn.close()
        return "User not found", 404

    message = ""

    if request.method == "POST":

        new_password = request.form["password"]

        conn.execute("""
            UPDATE users
            SET password_hash=?
            WHERE id=?
        """, (
            generate_password_hash(new_password),
            user_id
        ))

        conn.commit()

        message = "Password changed successfully."

        add_activity(
            f"Password changed for {user['email']}",
            "🔐"
        )

    conn.close()

    body = f"""

    <h1>🔐 Change Password</h1>

    <div class="card">

        <p>
            Account:
            <b>{user["email"]}</b>
        </p>

        <p style="color:#10b981">
            {message}
        </p>

        <form method="POST">

            <label>New Password</label>

            <input
            type="password"
            name="password"
            minlength="6"
            required>

            <button class="btn">
                CHANGE PASSWORD
            </button>

        </form>

    </div>

    """

    return page("Change Password", body)


# ============================================================
# ADD TEAM
# ============================================================

@app.route("/add-team", methods=["GET", "POST"])
@role_required("SUPER_ADMIN")
def add_team():

    message = ""

    if request.method == "POST":

        name = request.form["name"]
        email = request.form["email"]

        try:

            create_team(name, email)

            add_activity(
                f"New team {name} created",
                "🏢"
            )

            message = "Team created successfully."

        except sqlite3.IntegrityError:

            message = "Team already exists."

    body = f"""

    <h1>🏢 Add New Team</h1>

    <div class="card">

        <p style="color:#10b981">
            {message}
        </p>

        <form method="POST">

            <label>Team Name</label>

            <input
            name="name"
            placeholder="Delta"
            required>

            <label>Team Email</label>

            <input
            type="email"
            name="email"
            placeholder="delta@gmail.com"
            required>

            <button class="btn">
                CREATE TEAM
            </button>

        </form>

    </div>

    """

    return page("Add Team", body)


# ============================================================
# START
# ============================================================

if __name__ == "__main__":

    init_db()
    seed_data()

    print()
    print("=" * 60)
    print("                 ⚡ TEAM PULSE")
    print("=" * 60)
    print("Team Task & Collaboration System")
    print()
    print("Database : team_pulse.db")
    print("Server   : http://127.0.0.1:5000")
    print()
    print("Teams    : Alpha | Beta | Gamma")
    print("Members  : 6")
    print("Admins   : 3")
    print("Super    : 3")
    print("=" * 60)
    print()

    app.run(
        host="0.0.0.0",
        port=5000,
        debug=True
    )
