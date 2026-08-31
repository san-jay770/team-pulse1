"""TEAM PULSE - Team Task Management & Performance Monitoring System
Flask + SQLite single-file application

Run:
    python team_pulse.py

Main fix:
- Login success now reliably redirects to the role dashboard.
- Session is refreshed from the database on every protected request.
- Missing/invalid team records are handled safely.
- Dashboard routes are kept role-based.
- Better error logging is enabled so dashboard errors are visible in the terminal.
"""

import sqlite3
import csv
import io
import os
import traceback
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, session, redirect, url_for, render_template,
    flash, g, Response
)
from werkzeug.security import generate_password_hash, check_password_hash


# ---------------------------------------------------------------------------
# APP CONFIG
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "team_pulse.db")

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY",
    "teampulse-dev-secret-change-in-production"
)

# Do not let Flask silently hide the real dashboard error during development.
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"


# ---------------------------------------------------------------------------
# DEFAULT DATA
# ---------------------------------------------------------------------------

TEAMS_DEFAULT = [
    (1, "Development Team"),
    (2, "Testing Team"),
    (3, "AI & ML Team"),
    (4, "Backend Team"),
    (5, "Frontend Team"),
    (6, "Data Science Team"),
    (7, "Cloud & DevOps Team"),
    (8, "UI/UX Team"),
    (9, "Research Team"),
    (10, "Support Team"),
]

ADMINS_DEFAULT = [
    {
        "team": 1, "name": "Parthasharathy",
        "email": "parthasharathy87@gmail.com",
        "password": "partha2006", "super_admin": True
    },
    {
        "team": 2, "name": "Sanjay",
        "email": "sanjaysanjayt19@gmail.com",
        "password": "Siva1908", "super_admin": True
    },
    {
        "team": 3, "name": "Premkumar",
        "email": "premkumarm.aids@scteng.co.in",
        "password": "premkumar15", "super_admin": True
    },
    {
        "team": 4, "name": "Sowndar",
        "email": "sowndar706@gmail.com",
        "password": "kira@20", "super_admin": False
    },
    {
        "team": 5, "name": "Ajaysaagar",
        "email": "ajaysaagar.dev@gmail.com",
        "password": "AjaysaagarME", "super_admin": False
    },
    {
        "team": 6, "name": "Harshar",
        "email": "harsharamutha@gmail.com",
        "password": "sunisblue", "super_admin": False
    },
    {
        "team": 7, "name": "Balaji",
        "email": "balajiv.works@gmail.com",
        "password": "Balaji2006", "super_admin": False
    },
    {
        "team": 8, "name": "Kavihaiarasu",
        "email": "kavihaiarasusampath@gmail.com",
        "password": "Kavi@2004", "super_admin": False
    },
    {
        "team": 9, "name": "Sam",
        "email": "sam.seba1905@gmail.com",
        "password": "123456@sam", "super_admin": False
    },
    {
        "team": 10, "name": "Team 10 Admin",
        "email": "admin07@teampulse.com",
        "password": "TeamPulse@123", "super_admin": False
    },
]

POINTS_PER_TASK = 10


# ---------------------------------------------------------------------------
# DATABASE
# ---------------------------------------------------------------------------

def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(exception=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Create all tables and seed default teams/admins once."""
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    cur = db.cursor()

    cur.executescript("""
    CREATE TABLE IF NOT EXISTS teams (
        id INTEGER PRIMARY KEY,
        name TEXT NOT NULL,
        description TEXT,
        admin_id INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('SUPER_ADMIN','ADMIN','TEAM_MEMBER')),
        team_id INTEGER,
        points INTEGER DEFAULT 0,
        status TEXT DEFAULT 'Active',
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(team_id) REFERENCES teams(id),
        UNIQUE(email, team_id)
    );

    CREATE TABLE IF NOT EXISTS tasks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        title TEXT NOT NULL,
        description TEXT,
        team_id INTEGER NOT NULL,
        assigned_to INTEGER,
        created_by INTEGER,
        priority TEXT DEFAULT 'Medium',
        status TEXT DEFAULT 'Pending',
        due_date TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        completed_at TEXT,
        points_awarded INTEGER DEFAULT 0,
        FOREIGN KEY(team_id) REFERENCES teams(id),
        FOREIGN KEY(assigned_to) REFERENCES users(id),
        FOREIGN KEY(created_by) REFERENCES users(id)
    );

    CREATE TABLE IF NOT EXISTS doubts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        question TEXT NOT NULL,
        answer TEXT,
        status TEXT DEFAULT 'Open',
        answered_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        answered_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(team_id) REFERENCES teams(id)
    );

    CREATE TABLE IF NOT EXISTS suggestions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        team_id INTEGER NOT NULL,
        suggestion TEXT NOT NULL,
        status TEXT DEFAULT 'New',
        response TEXT,
        reviewed_by INTEGER,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT,
        FOREIGN KEY(user_id) REFERENCES users(id),
        FOREIGN KEY(team_id) REFERENCES teams(id)
    );

    CREATE TABLE IF NOT EXISTS activities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        activity TEXT NOT NULL,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP
    );
    """)

    # Migrate users table schema if old UNIQUE(email) exists
    try:
        cur.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
        row = cur.fetchone()
        if row:
            raw_sql = row["sql"] or ""
            # Check if UNIQUE(email, team_id) is missing
            if "UNIQUE(email, team_id)" not in raw_sql.replace(" ", "").replace("\n", "").replace("\r", ""):
                cur.execute("PRAGMA foreign_keys = OFF")
                cur.executescript("""
                CREATE TABLE IF NOT EXISTS users_migrated (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL,
                    email TEXT NOT NULL,
                    password TEXT NOT NULL,
                    role TEXT NOT NULL CHECK(role IN ('SUPER_ADMIN','ADMIN','TEAM_MEMBER')),
                    team_id INTEGER,
                    points INTEGER DEFAULT 0,
                    status TEXT DEFAULT 'Active',
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(team_id) REFERENCES teams(id),
                    UNIQUE(email, team_id)
                );
                INSERT INTO users_migrated (id, name, email, password, role, team_id, points, status, created_at)
                SELECT id, name, email, password, role, team_id, points, status, created_at FROM users;
                DROP TABLE users;
                ALTER TABLE users_migrated RENAME TO users;
                """)
                cur.execute("PRAGMA foreign_keys = ON")
                db.commit()
    except Exception as e:
        print("Users table migration note:", e)

    # Seed teams.
    for team_id, name in TEAMS_DEFAULT:
        cur.execute("SELECT id FROM teams WHERE id = ?", (team_id,))
        if cur.fetchone() is None:
            cur.execute(
                "INSERT INTO teams (id, name) VALUES (?, ?)",
                (team_id, name)
            )

    db.commit()

    # Seed users with compatible hashing algorithm
    for admin in ADMINS_DEFAULT:
        email = admin["email"].strip().lower()
        cur.execute(
            "SELECT id, role, team_id FROM users WHERE lower(email) = ? AND team_id = ?",
            (email, admin["team"])
        )
        existing = cur.fetchone()

        role = "SUPER_ADMIN" if admin["super_admin"] else "ADMIN"
        hashed = generate_password_hash(admin["password"], method="pbkdf2:sha256")

        if existing is None:
            cur.execute("""
                INSERT INTO users
                (name, email, password, role, team_id, points, status)
                VALUES (?, ?, ?, ?, ?, 0, 'Active')
            """, (
                admin["name"],
                email,
                hashed,
                role,
                admin["team"]
            ))
            user_id = cur.lastrowid

            cur.execute(
                "UPDATE teams SET admin_id = ? WHERE id = ?",
                (user_id, admin["team"])
            )
        else:
            # Update hash to pbkdf2:sha256 for existing seeded accounts
            cur.execute("UPDATE users SET password = ? WHERE id = ?", (hashed, existing["id"]))

    db.commit()
    db.close()


# ---------------------------------------------------------------------------
# ACTIVITY
# ---------------------------------------------------------------------------

def log_activity(user_id, activity):
    try:
        db = get_db()
        db.execute(
            "INSERT INTO activities (user_id, activity) VALUES (?, ?)",
            (user_id, activity)
        )
        db.commit()
    except Exception:
        # Logging must never break the actual application.
        app.logger.exception("Activity logging failed")


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

def current_user():
    user_id = session.get("user_id")

    if not user_id:
        return None

    db = get_db()
    return db.execute(
        "SELECT * FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()


@app.context_processor
def inject_user():
    user = current_user()
    user_teams = []
    if user and "email" in user.keys() and user["email"]:
        db = get_db()
        user_teams = db.execute("""
            SELECT u.id AS user_id, u.role, u.team_id, t.name AS team_name
            FROM users u
            JOIN teams t ON u.team_id=t.id
            WHERE lower(u.email) = lower(?) AND u.status = 'Active'
            ORDER BY t.name
        """, (user["email"],)).fetchall()
    return {
        "current_user": user,
        "user_teams": user_teams
    }


@app.route("/switch-team/<int:team_id>")
def switch_team(team_id):
    user = current_user()
    if not user:
        session.clear()
        flash("Please log in to continue.", "warning")
        return redirect(url_for("login"))

    db = get_db()
    target_user = db.execute("""
        SELECT u.*, t.name AS team_name
        FROM users u
        LEFT JOIN teams t ON u.team_id=t.id
        WHERE lower(u.email) = lower(?) AND u.team_id = ? AND u.status = 'Active'
    """, (user["email"], team_id)).fetchone()

    if not target_user:
        flash("You are not an active member of this team.", "danger")
        return redirect(url_for("dashboard"))

    session["user_id"] = target_user["id"]
    session["name"] = target_user["name"]
    session["role"] = target_user["role"]
    session["team_id"] = target_user["team_id"]

    log_activity(
        target_user["id"],
        f"{target_user['name']} switched workspace to {target_user['team_name'] or 'Team ' + str(team_id)}"
    )

    flash(f"Switched workspace to {target_user['team_name'] or 'Team ' + str(team_id)}.", "success")
    return redirect(url_for("dashboard"))


def login_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        user = current_user()

        if user is None:
            session.clear()
            flash("Please log in to continue.", "warning")
            return redirect(url_for("login"))

        # Refresh role/team from DB so stale session data cannot break routing.
        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        session["team_id"] = user["team_id"]

        if user["status"] != "Active":
            session.clear()
            flash("This account is inactive. Contact your admin.", "danger")
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return wrapper


def role_required(*roles):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            user = current_user()

            if user is None:
                session.clear()
                flash("Please log in to continue.", "warning")
                return redirect(url_for("login"))

            session["user_id"] = user["id"]
            session["name"] = user["name"]
            session["role"] = user["role"]
            session["team_id"] = user["team_id"]

            if user["status"] != "Active":
                session.clear()
                flash("This account is inactive. Contact your admin.", "danger")
                return redirect(url_for("login"))

            if user["role"] not in roles:
                flash(
                    "You do not have permission to perform this action.",
                    "danger"
                )
                return redirect(url_for("dashboard"))

            return f(*args, **kwargs)

        return wrapper
    return decorator


def team_scope_filter():
    if session.get("role") == "SUPER_ADMIN":
        return "u.team_id IS NOT NULL OR u.team_id IS NULL", []

    return "u.team_id = ?", [session.get("team_id")]


# ---------------------------------------------------------------------------
# AUTH ROUTES
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    if current_user():
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        selected_team_id = request.form.get("team_id")

        app.logger.info("LOGIN ATTEMPT: %s", email)

        if not email or not password:
            flash("Email and password are required.", "danger")
            return render_template("login.html")

        db = get_db()

        users = db.execute("""
            SELECT u.*, t.name AS team_name
            FROM users u
            LEFT JOIN teams t ON u.team_id=t.id
            WHERE lower(u.email) = ?
        """, (email,)).fetchall()

        app.logger.info("USERS FOUND COUNT: %s", len(users))

        if not users:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        valid_users = []
        for user_candidate in users:
            try:
                if check_password_hash(user_candidate["password"], password):
                    valid_users.append(user_candidate)
            except Exception as exc:
                app.logger.warning("Hash check error: %s", exc)

        if not valid_users:
            flash("Invalid email or password.", "danger")
            return render_template("login.html")

        active_users = [u for u in valid_users if u["status"] == "Active"]

        if not active_users:
            flash("This account is inactive. Contact your admin.", "danger")
            return render_template("login.html")

        # If user belongs to multiple teams and team has not been selected yet
        if len(active_users) > 1 and not selected_team_id:
            team_options = [
                {
                    "user_id": u["id"],
                    "team_id": u["team_id"],
                    "team_name": u["team_name"] or f"Team {u['team_id']}",
                    "role": u["role"]
                }
                for u in active_users
            ]
            return render_template(
                "login.html",
                email=email,
                password=password,
                team_options=team_options
            )

        if selected_team_id:
            user = next(
                (u for u in active_users if str(u["team_id"]) == str(selected_team_id)),
                active_users[0]
            )
        else:
            user = active_users[0]

        # Clear old session before creating the new authenticated session.
        session.clear()

        session["user_id"] = user["id"]
        session["name"] = user["name"]
        session["role"] = user["role"]
        session["team_id"] = user["team_id"]

        session.permanent = False

        log_activity(
            user["id"],
            f"{user['name']} logged in"
        )

        app.logger.info(
            "LOGIN SUCCESS: id=%s name=%s role=%s team_id=%s",
            user["id"],
            user["name"],
            user["role"],
            user["team_id"]
        )

        flash(
            f"Welcome, {user['name']}!",
            "success"
        )

        return redirect("/dashboard")

    return render_template("login.html")


@app.route("/logout")
def logout():
    if "user_id" in session:
        log_activity(
            session["user_id"],
            f"{session.get('name')} logged out"
        )

    session.clear()
    flash("You have been logged out.", "info")

    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------------

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    role = session.get("role")

    app.logger.info(
        "DASHBOARD REQUEST: user=%s role=%s team=%s",
        session.get("user_id"),
        role,
        session.get("team_id")
    )

    try:
        # ---------------------------------------------------------------
        # SUPER ADMIN
        # ---------------------------------------------------------------
        if role == "SUPER_ADMIN":
            stats = {
                "total_teams": db.execute(
                    "SELECT COUNT(*) c FROM teams"
                ).fetchone()["c"],

                "total_admins": db.execute("""
                    SELECT COUNT(*) c
                    FROM users
                    WHERE role IN ('SUPER_ADMIN','ADMIN')
                """).fetchone()["c"],

                "total_members": db.execute("""
                    SELECT COUNT(*) c
                    FROM users
                    WHERE role='TEAM_MEMBER'
                """).fetchone()["c"],

                "total_tasks": db.execute(
                    "SELECT COUNT(*) c FROM tasks"
                ).fetchone()["c"],

                "pending_tasks": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE status != 'Completed'
                """).fetchone()["c"],

                "completed_tasks": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE status='Completed'
                """).fetchone()["c"],

                "total_doubts": db.execute(
                    "SELECT COUNT(*) c FROM doubts"
                ).fetchone()["c"],

                "open_doubts": db.execute("""
                    SELECT COUNT(*) c
                    FROM doubts
                    WHERE status='Open'
                """).fetchone()["c"],

                "total_suggestions": db.execute(
                    "SELECT COUNT(*) c FROM suggestions"
                ).fetchone()["c"],
            }

            team_perf_rows = db.execute("""
                SELECT
                    t.id,
                    t.name,
                    COUNT(tk.id) AS total,
                    COALESCE(
                        SUM(
                            CASE
                                WHEN tk.status='Completed' THEN 1
                                ELSE 0
                            END
                        ), 0
                    ) AS done
                FROM teams t
                LEFT JOIN tasks tk
                    ON tk.team_id=t.id
                GROUP BY t.id, t.name
                ORDER BY t.id
            """).fetchall()

            team_perf = []

            for row in team_perf_rows:
                total = row["total"] or 0
                done = row["done"] or 0

                team_perf.append({
                    "id": row["id"],
                    "name": row["name"],
                    "total": total,
                    "done": done,
                    "pct": round(done / total * 100) if total else 0,
                })

            return render_template(
                "dashboard_super.html",
                stats=stats,
                team_perf=team_perf
            )

        # ---------------------------------------------------------------
        # ADMIN
        # ---------------------------------------------------------------
        if role == "ADMIN":
            team_id = session.get("team_id")

            team = db.execute(
                "SELECT * FROM teams WHERE id=?",
                (team_id,)
            ).fetchone()

            # Prevent dashboard crash if the team was deleted.
            if team is None:
                flash(
                    "Your team record was not found. Please contact the super admin.",
                    "danger"
                )
                return render_template(
                    "dashboard_admin.html",
                    team=None,
                    stats={
                        "members": 0,
                        "total_tasks": 0,
                        "completed": 0,
                        "pending": 0,
                        "points": 0,
                    }
                )

            stats = {
                "members": db.execute("""
                    SELECT COUNT(*) c
                    FROM users
                    WHERE team_id=?
                    AND role='TEAM_MEMBER'
                """, (team_id,)).fetchone()["c"],

                "total_tasks": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE team_id=?
                """, (team_id,)).fetchone()["c"],

                "completed": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE team_id=?
                    AND status='Completed'
                """, (team_id,)).fetchone()["c"],

                "pending": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE team_id=?
                    AND status!='Completed'
                """, (team_id,)).fetchone()["c"],

                "points": db.execute("""
                    SELECT COALESCE(SUM(points),0) c
                    FROM users
                    WHERE team_id=?
                """, (team_id,)).fetchone()["c"],
            }

            return render_template(
                "dashboard_admin.html",
                team=team,
                stats=stats
            )

        # ---------------------------------------------------------------
        # TEAM MEMBER
        # ---------------------------------------------------------------
        if role == "TEAM_MEMBER":
            uid = session.get("user_id")
            team_id = session.get("team_id")

            team = db.execute(
                "SELECT * FROM teams WHERE id=?",
                (team_id,)
            ).fetchone()

            stats = {
                "pending": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE assigned_to=?
                    AND status='Pending'
                """, (uid,)).fetchone()["c"],

                "in_progress": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE assigned_to=?
                    AND status='In Progress'
                """, (uid,)).fetchone()["c"],

                "completed": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE assigned_to=?
                    AND status='Completed'
                """, (uid,)).fetchone()["c"],

                "overdue": db.execute("""
                    SELECT COUNT(*) c
                    FROM tasks
                    WHERE assigned_to=?
                    AND status!='Completed'
                    AND due_date IS NOT NULL
                    AND due_date < date('now')
                """, (uid,)).fetchone()["c"],
            }

            point_row = db.execute(
                "SELECT COALESCE(points,0) points FROM users WHERE id=?",
                (uid,)
            ).fetchone()

            my_points = point_row["points"] if point_row else 0

            recent = db.execute("""
                SELECT *
                FROM activities
                WHERE user_id=?
                ORDER BY created_at DESC
                LIMIT 5
            """, (uid,)).fetchall()

            return render_template(
                "dashboard_member.html",
                team=team,
                stats=stats,
                my_points=my_points,
                recent=recent
            )

        # Invalid role safety.
        session.clear()
        flash("Invalid user role. Please log in again.", "danger")
        return redirect(url_for("login"))

    except Exception as exc:
        # IMPORTANT: print the real exception instead of hiding it.
        app.logger.exception("DASHBOARD ERROR: %s", exc)

        return (
            f"""
            <div style="
                font-family:Arial;
                padding:30px;
                max-width:900px;
                margin:auto;
            ">
                <h1>Team Pulse Dashboard Error</h1>
                <p><b>User:</b> {session.get('name')}</p>
                <p><b>Role:</b> {session.get('role')}</p>
                <p><b>Team ID:</b> {session.get('team_id')}</p>
                <hr>
                <h3>Actual error:</h3>
                <pre style="
                    background:#f4f4f4;
                    padding:15px;
                    white-space:pre-wrap;
                ">{exc}</pre>
                <p>Check the terminal where <b>python team_pulse.py</b> is running.</p>
                <a href="/logout">Logout</a>
            </div>
            """,
            500
        )


# ---------------------------------------------------------------------------
# USERS
# ---------------------------------------------------------------------------

@app.route("/users")
@role_required("SUPER_ADMIN", "ADMIN")
def users_list():
    db = get_db()

    q = request.args.get("q", "").strip()
    team_filter = request.args.get("team", "")
    role_filter = request.args.get("role", "")

    if session["role"] == "SUPER_ADMIN":
        sql = """
            SELECT u.*, t.name AS team_name
            FROM users u
            LEFT JOIN teams t ON u.team_id=t.id
            WHERE 1=1
        """
        params = []
    else:
        sql = """
            SELECT u.*, t.name AS team_name
            FROM users u
            LEFT JOIN teams t ON u.team_id=t.id
            WHERE u.team_id=?
        """
        params = [session["team_id"]]

    if q:
        sql += " AND (u.name LIKE ? OR u.email LIKE ?)"
        params.extend([f"%{q}%", f"%{q}%"])

    if team_filter and session["role"] == "SUPER_ADMIN":
        sql += " AND u.team_id=?"
        params.append(team_filter)

    if role_filter:
        sql += " AND u.role=?"
        params.append(role_filter)

    sql += " ORDER BY u.team_id, u.role, u.name"

    users = db.execute(sql, params).fetchall()
    teams = db.execute(
        "SELECT * FROM teams ORDER BY id"
    ).fetchall()

    return render_template(
        "users.html",
        users=users,
        teams=teams,
        q=q,
        team_filter=team_filter,
        role_filter=role_filter
    )


@app.route("/api/user-by-email")
@role_required("SUPER_ADMIN", "ADMIN")
def api_user_by_email():
    email = request.args.get("email", "").strip().lower()
    if not email:
        return {"found": False}
    db = get_db()
    user = db.execute("""
        SELECT u.name, u.email, GROUP_CONCAT(t.name, ', ') AS current_teams
        FROM users u
        LEFT JOIN teams t ON u.team_id=t.id
        WHERE lower(u.email)=?
        GROUP BY lower(u.email)
    """, (email,)).fetchone()

    if user:
        return {
            "found": True,
            "name": user["name"],
            "email": user["email"],
            "current_teams": user["current_teams"] or "None"
        }
    return {"found": False}


@app.route("/users/add", methods=["GET", "POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def user_add():
    db = get_db()

    if session["role"] == "SUPER_ADMIN":
        teams = db.execute(
            "SELECT * FROM teams ORDER BY id"
        ).fetchall()
    else:
        teams = db.execute(
            "SELECT * FROM teams WHERE id=?",
            (session["team_id"],)
        ).fetchall()

    existing_users = db.execute("""
        SELECT u.name, u.email, GROUP_CONCAT(t.name, ', ') AS current_teams
        FROM users u
        LEFT JOIN teams t ON u.team_id=t.id
        GROUP BY lower(u.email)
        ORDER BY u.name
    """).fetchall()

    preset_team_id = request.args.get("team_id", "")
    preset_email = request.args.get("email", "").strip().lower()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        role = request.form.get("role", "TEAM_MEMBER")
        team_id = request.form.get("team_id") or preset_team_id

        if not email:
            flash("Email address is required.", "danger")
            return render_template(
                "user_form.html",
                teams=teams,
                user=None,
                existing_users=existing_users,
                preset_team_id=preset_team_id,
                preset_email=preset_email
            )

        if session["role"] == "ADMIN":
            team_id = session["team_id"]
            if role == "SUPER_ADMIN":
                role = "TEAM_MEMBER"

        if not team_id:
            flash("Assigned team is required.", "danger")
            return render_template(
                "user_form.html",
                teams=teams,
                user=None,
                existing_users=existing_users,
                preset_team_id=preset_team_id,
                preset_email=preset_email
            )

        # Check if this email exists anywhere in the system
        existing_global = db.execute(
            "SELECT * FROM users WHERE lower(email)=? LIMIT 1",
            (email,)
        ).fetchone()

        if existing_global:
            # Re-use name if not provided
            if not name:
                name = existing_global["name"]
            # Re-use existing password hash if not provided
            if not password:
                password_hash = existing_global["password"]
            else:
                password_hash = generate_password_hash(password, method="pbkdf2:sha256")
                db.execute("UPDATE users SET password=? WHERE lower(email)=?", (password_hash, email))
        else:
            # Brand new account requires both name and password
            if not name or not password:
                flash("Full name and password are required when creating a brand new user account.", "danger")
                return render_template(
                    "user_form.html",
                    teams=teams,
                    user=None,
                    existing_users=existing_users,
                    preset_team_id=preset_team_id,
                    preset_email=preset_email
                )
            password_hash = generate_password_hash(password, method="pbkdf2:sha256")

        try:
            existing_in_team = db.execute(
                "SELECT id FROM users WHERE lower(email)=? AND team_id=?",
                (email, int(team_id))
            ).fetchone()

            if existing_in_team:
                flash(
                    "A member with this email is already assigned to the selected team.",
                    "danger"
                )
                return render_template(
                    "user_form.html",
                    teams=teams,
                    user=None,
                    existing_users=existing_users,
                    preset_team_id=preset_team_id,
                    preset_email=preset_email
                )

            db.execute("""
                INSERT INTO users
                (name,email,password,role,team_id,points,status)
                VALUES (?,?,?,?,?,0,'Active')
            """, (
                name,
                email,
                password_hash,
                role,
                int(team_id)
            ))

            db.commit()

            team_row = db.execute("SELECT name FROM teams WHERE id=?", (int(team_id),)).fetchone()
            team_name = team_row["name"] if team_row else f"Team #{team_id}"

            log_activity(
                session["user_id"],
                f"{session['name']} added user {name} ({email}) to {team_name}"
            )

            flash(f"User '{name}' ({email}) assigned to {team_name} successfully.", "success")
            return redirect(url_for("users_list"))

        except sqlite3.IntegrityError as exc:
            db.rollback()
            flash(f"Unable to assign user: {exc}", "danger")

    return render_template(
        "user_form.html",
        teams=teams,
        user=None,
        existing_users=existing_users,
        preset_team_id=preset_team_id,
        preset_email=preset_email
    )


@app.route("/users/edit/<int:user_id>", methods=["GET", "POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def user_edit(user_id):
    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("users_list"))

    if (
        session["role"] == "ADMIN"
        and user["team_id"] != session["team_id"]
    ):
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for("users_list"))

    teams = db.execute(
        "SELECT * FROM teams ORDER BY id"
    ).fetchall()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        role = request.form.get("role", user["role"])
        team_id = request.form.get("team_id", user["team_id"])
        status = request.form.get("status", user["status"])
        new_password = request.form.get("password", "")

        if not name or not email:
            flash("Name and email are required.", "danger")
            return render_template(
                "user_form.html",
                teams=teams,
                user=user
            )

        if session["role"] == "ADMIN":
            team_id = session["team_id"]

            if role == "SUPER_ADMIN":
                role = "TEAM_MEMBER"

        try:
            existing = db.execute(
                "SELECT id FROM users WHERE lower(email)=? AND team_id=? AND id!=?",
                (email, int(team_id), user_id)
            ).fetchone()

            if existing:
                flash(
                    "A user with this email is already assigned to this team.",
                    "danger"
                )
                return render_template(
                    "user_form.html",
                    teams=teams,
                    user=user
                )

            if new_password:
                hashed_pwd = generate_password_hash(new_password, method="pbkdf2:sha256")
                db.execute("""
                    UPDATE users
                    SET name=?, email=?, role=?, team_id=?,
                        status=?, password=?
                    WHERE id=?
                """, (
                    name,
                    email,
                    role,
                    int(team_id),
                    status,
                    hashed_pwd,
                    user_id
                ))
                # Synchronize password for this email across all team accounts
                db.execute("UPDATE users SET password=? WHERE lower(email)=?", (hashed_pwd, email))
            else:
                db.execute("""
                    UPDATE users
                    SET name=?, email=?, role=?, team_id=?, status=?
                    WHERE id=?
                """, (
                    name,
                    email,
                    role,
                    int(team_id),
                    status,
                    user_id
                ))

            db.commit()

            log_activity(
                session["user_id"],
                f"{session['name']} updated user {name}"
            )

            flash("User updated successfully.", "success")
            return redirect(url_for("users_list"))

        except sqlite3.IntegrityError as exc:
            db.rollback()
            flash(f"Unable to update user: {exc}", "danger")

    return render_template(
        "user_form.html",
        teams=teams,
        user=user
    )


@app.route("/users/delete/<int:user_id>", methods=["POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def user_delete(user_id):
    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE id=?",
        (user_id,)
    ).fetchone()

    if not user:
        flash("User not found.", "danger")
        return redirect(url_for("users_list"))

    if (
        session["role"] == "ADMIN"
        and user["team_id"] != session["team_id"]
    ):
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for("users_list"))

    if user_id == session["user_id"]:
        flash("You cannot delete your own account.", "danger")
        return redirect(url_for("users_list"))

    try:
        db.execute(
            "DELETE FROM users WHERE id=?",
            (user_id,)
        )
        db.commit()

        log_activity(
            session["user_id"],
            f"{session['name']} deleted user {user['name']}"
        )

        flash("User deleted successfully.", "success")

    except sqlite3.IntegrityError:
        db.rollback()
        flash(
            "This user cannot be deleted because other records depend on the account.",
            "danger"
        )

    return redirect(url_for("users_list"))


# ---------------------------------------------------------------------------
# TEAMS
# ---------------------------------------------------------------------------

@app.route("/teams")
@role_required("SUPER_ADMIN")
def teams_list():
    db = get_db()

    teams = db.execute("""
        SELECT
            t.*,
            a.name AS admin_name,
            (
                SELECT COUNT(*)
                FROM users u
                WHERE u.team_id=t.id
                AND u.role='TEAM_MEMBER'
            ) AS member_count,
            (
                SELECT COUNT(*)
                FROM tasks tk
                WHERE tk.team_id=t.id
            ) AS total_tasks,
            (
                SELECT COUNT(*)
                FROM tasks tk
                WHERE tk.team_id=t.id
                AND tk.status='Completed'
            ) AS completed_tasks
        FROM teams t
        LEFT JOIN users a ON t.admin_id=a.id
        ORDER BY t.id
    """).fetchall()

    return render_template(
        "teams.html",
        teams=teams
    )


@app.route("/teams/add", methods=["GET", "POST"])
@role_required("SUPER_ADMIN")
def team_add():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Team name is required.", "danger")
            return render_template(
                "team_form.html",
                team=None
            )

        db = get_db()

        db.execute(
            "INSERT INTO teams (name,description) VALUES (?,?)",
            (name, description)
        )
        db.commit()

        log_activity(
            session["user_id"],
            f"{session['name']} created team {name}"
        )

        flash("Team created successfully.", "success")
        return redirect(url_for("teams_list"))

    return render_template(
        "team_form.html",
        team=None
    )


@app.route("/teams/edit/<int:team_id>", methods=["GET", "POST"])
@role_required("SUPER_ADMIN")
def team_edit(team_id):
    db = get_db()

    team = db.execute(
        "SELECT * FROM teams WHERE id=?",
        (team_id,)
    ).fetchone()

    if not team:
        flash("Team not found.", "danger")
        return redirect(url_for("teams_list"))

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        description = request.form.get("description", "").strip()

        if not name:
            flash("Team name is required.", "danger")
            return render_template(
                "team_form.html",
                team=team
            )

        db.execute(
            "UPDATE teams SET name=?,description=? WHERE id=?",
            (name, description, team_id)
        )
        db.commit()

        log_activity(
            session["user_id"],
            f"{session['name']} updated team {name}"
        )

        flash("Team updated successfully.", "success")
        return redirect(url_for("teams_list"))

    return render_template(
        "team_form.html",
        team=team
    )


@app.route("/teams/delete/<int:team_id>", methods=["POST"])
@role_required("SUPER_ADMIN")
def team_delete(team_id):
    db = get_db()

    team = db.execute(
        "SELECT * FROM teams WHERE id=?",
        (team_id,)
    ).fetchone()

    if not team:
        flash("Team not found.", "danger")
        return redirect(url_for("teams_list"))

    try:
        db.execute(
            "DELETE FROM teams WHERE id=?",
            (team_id,)
        )
        db.commit()

        log_activity(
            session["user_id"],
            f"{session['name']} deleted team {team['name']}"
        )

        flash("Team deleted successfully.", "success")

    except sqlite3.IntegrityError:
        db.rollback()
        flash(
            "This team cannot be deleted because users or tasks are still linked to it.",
            "danger"
        )

    return redirect(url_for("teams_list"))


# ---------------------------------------------------------------------------
# TASKS
# ---------------------------------------------------------------------------

@app.route("/tasks")
@login_required
def tasks_list():
    db = get_db()
    role = session["role"]

    q = request.args.get("q", "").strip()
    team_filter = request.args.get("team", "")
    member_filter = request.args.get("member", "")
    status_filter = request.args.get("status", "")
    priority_filter = request.args.get("priority", "")

    base_select = """
        SELECT
            tk.*,
            t.name AS team_name,
            u.name AS assignee
        FROM tasks tk
        LEFT JOIN teams t ON tk.team_id=t.id
        LEFT JOIN users u ON tk.assigned_to=u.id
    """

    if role == "SUPER_ADMIN":
        sql = base_select + " WHERE 1=1"
        params = []

    elif role == "ADMIN":
        sql = base_select + " WHERE tk.team_id=?"
        params = [session["team_id"]]

    else:
        sql = base_select + " WHERE tk.assigned_to=?"
        params = [session["user_id"]]

    if q:
        sql += " AND tk.title LIKE ?"
        params.append(f"%{q}%")

    if team_filter and role == "SUPER_ADMIN":
        sql += " AND tk.team_id=?"
        params.append(team_filter)

    if member_filter and role != "TEAM_MEMBER":
        sql += " AND tk.assigned_to=?"
        params.append(member_filter)

    if status_filter:
        sql += " AND tk.status=?"
        params.append(status_filter)

    if priority_filter:
        sql += " AND tk.priority=?"
        params.append(priority_filter)

    sql += " ORDER BY tk.created_at DESC"

    tasks = db.execute(sql, params).fetchall()

    teams = db.execute(
        "SELECT * FROM teams ORDER BY id"
    ).fetchall()

    return render_template(
        "tasks.html",
        tasks=tasks,
        teams=teams,
        q=q,
        team_filter=team_filter,
        member_filter=member_filter,
        status_filter=status_filter,
        priority_filter=priority_filter
    )


@app.route("/tasks/add", methods=["GET", "POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def task_add():
    db = get_db()

    if session["role"] == "SUPER_ADMIN":
        teams = db.execute(
            "SELECT * FROM teams ORDER BY id"
        ).fetchall()
    else:
        teams = db.execute(
            "SELECT * FROM teams WHERE id=?",
            (session["team_id"],)
        ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        team_id = request.form.get("team_id")
        assigned_to = request.form.get("assigned_to") or None
        priority = request.form.get("priority", "Medium")
        due_date = request.form.get("due_date") or None

        if session["role"] == "ADMIN":
            team_id = session["team_id"]

        if not title or not team_id:
            flash("Task title and team are required.", "danger")
            return render_template(
                "task_form.html",
                teams=teams,
                task=None,
                members=[]
            )

        # Validate assignee belongs to selected team.
        if assigned_to:
            member = db.execute("""
                SELECT id
                FROM users
                WHERE id=?
                AND team_id=?
                AND status='Active'
            """, (assigned_to, team_id)).fetchone()

            if not member:
                assigned_to = None

        db.execute("""
            INSERT INTO tasks
            (title,description,team_id,assigned_to,created_by,
             priority,due_date)
            VALUES (?,?,?,?,?,?,?)
        """, (
            title,
            description,
            team_id,
            assigned_to,
            session["user_id"],
            priority,
            due_date
        ))

        db.commit()

        log_activity(
            session["user_id"],
            f"{session['name']} created task '{title}'"
        )

        flash("Task created successfully.", "success")
        return redirect(url_for("tasks_list"))

    if teams:
        team_ids = [str(t["id"]) for t in teams]
        placeholders = ",".join("?" for _ in team_ids)

        members = db.execute(
            f"""
            SELECT *
            FROM users
            WHERE status='Active'
            AND team_id IN ({placeholders})
            ORDER BY name
            """,
            team_ids
        ).fetchall()
    else:
        members = []

    return render_template(
        "task_form.html",
        teams=teams,
        task=None,
        members=members
    )


@app.route("/tasks/members/<int:team_id>")
@role_required("SUPER_ADMIN", "ADMIN")
def task_members_for_team(team_id):
    db = get_db()

    if (
        session["role"] == "ADMIN"
        and team_id != session["team_id"]
    ):
        return {"members": []}

    members = db.execute("""
        SELECT id, name, role
        FROM users
        WHERE team_id=?
        AND status='Active'
        ORDER BY role DESC, name ASC
    """, (team_id,)).fetchall()

    return {
        "members": [
            {
                "id": m["id"],
                "name": f"{m['name']} ({m['role'].replace('_', ' ')})" if m["role"] != "TEAM_MEMBER" else m["name"]
            }
            for m in members
        ]
    }


@app.route("/tasks/edit/<int:task_id>", methods=["GET", "POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def task_edit(task_id):
    db = get_db()

    task = db.execute(
        "SELECT * FROM tasks WHERE id=?",
        (task_id,)
    ).fetchone()

    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks_list"))

    if (
        session["role"] == "ADMIN"
        and task["team_id"] != session["team_id"]
    ):
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for("tasks_list"))

    if session["role"] == "SUPER_ADMIN":
        teams = db.execute(
            "SELECT * FROM teams ORDER BY id"
        ).fetchall()
    else:
        teams = db.execute(
            "SELECT * FROM teams WHERE id=?",
            (session["team_id"],)
        ).fetchall()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        assigned_to = request.form.get("assigned_to") or None
        priority = request.form.get("priority", "Medium")
        due_date = request.form.get("due_date") or None
        status = request.form.get("status", task["status"])

        if not title:
            flash("Task title is required.", "danger")
            members = db.execute("""
                SELECT *
                FROM users
                WHERE team_id=?
                AND status='Active'
                ORDER BY name
            """, (task["team_id"],)).fetchall()

            return render_template(
                "task_form.html",
                teams=teams,
                task=task,
                members=members
            )

        # Admin must stay inside own team.
        team_id = task["team_id"]

        if assigned_to:
            valid_member = db.execute("""
                SELECT id
                FROM users
                WHERE id=?
                AND team_id=?
                AND status='Active'
            """, (assigned_to, team_id)).fetchone()

            if not valid_member:
                assigned_to = None

        completed_at = task["completed_at"]
        points_awarded = task["points_awarded"]

        if status == "Completed" and task["status"] != "Completed":
            completed_at = datetime.now().isoformat(
                timespec="seconds"
            )

            if not points_awarded and assigned_to:
                db.execute(
                    "UPDATE users SET points=points+? WHERE id=?",
                    (POINTS_PER_TASK, assigned_to)
                )
                points_awarded = 1

        db.execute("""
            UPDATE tasks
            SET title=?,
                description=?,
                assigned_to=?,
                priority=?,
                due_date=?,
                status=?,
                completed_at=?,
                points_awarded=?
            WHERE id=?
        """, (
            title,
            description,
            assigned_to,
            priority,
            due_date,
            status,
            completed_at,
            points_awarded,
            task_id
        ))

        db.commit()

        log_activity(
            session["user_id"],
            f"{session['name']} updated task '{title}'"
        )

        flash("Task updated successfully.", "success")
        return redirect(url_for("tasks_list"))

    members = db.execute("""
        SELECT *
        FROM users
        WHERE team_id=?
        AND role='TEAM_MEMBER'
        ORDER BY name
    """, (task["team_id"],)).fetchall()

    return render_template(
        "task_form.html",
        teams=teams,
        task=task,
        members=members
    )


@app.route("/tasks/status/<int:task_id>", methods=["POST"])
@login_required
def task_update_status(task_id):
    db = get_db()

    task = db.execute(
        "SELECT * FROM tasks WHERE id=?",
        (task_id,)
    ).fetchone()

    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks_list"))

    if session["role"] == "TEAM_MEMBER":
        if task["assigned_to"] != session["user_id"]:
            flash(
                "You do not have permission to perform this action.",
                "danger"
            )
            return redirect(url_for("tasks_list"))

    elif session["role"] == "ADMIN":
        if task["team_id"] != session["team_id"]:
            flash(
                "You do not have permission to perform this action.",
                "danger"
            )
            return redirect(url_for("tasks_list"))

    new_status = request.form.get("status")

    if new_status not in (
        "Pending",
        "In Progress",
        "Completed"
    ):
        flash("Invalid status.", "danger")
        return redirect(url_for("tasks_list"))

    completed_at = task["completed_at"]
    points_awarded = task["points_awarded"]

    if (
        new_status == "Completed"
        and task["status"] != "Completed"
    ):
        completed_at = datetime.now().isoformat(
            timespec="seconds"
        )

        if not points_awarded and task["assigned_to"]:
            db.execute(
                "UPDATE users SET points=points+? WHERE id=?",
                (
                    POINTS_PER_TASK,
                    task["assigned_to"]
                )
            )
            points_awarded = 1

    db.execute("""
        UPDATE tasks
        SET status=?,
            completed_at=?,
            points_awarded=?
        WHERE id=?
    """, (
        new_status,
        completed_at,
        points_awarded,
        task_id
    ))

    db.commit()

    log_activity(
        session["user_id"],
        f"{session['name']} marked task '{task['title']}' as {new_status}"
    )

    flash("Task status updated.", "success")
    return redirect(url_for("tasks_list"))


@app.route("/tasks/delete/<int:task_id>", methods=["POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def task_delete(task_id):
    db = get_db()

    task = db.execute(
        "SELECT * FROM tasks WHERE id=?",
        (task_id,)
    ).fetchone()

    if not task:
        flash("Task not found.", "danger")
        return redirect(url_for("tasks_list"))

    if (
        session["role"] == "ADMIN"
        and task["team_id"] != session["team_id"]
    ):
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for("tasks_list"))

    try:
        db.execute(
            "DELETE FROM tasks WHERE id=?",
            (task_id,)
        )
        db.commit()

        log_activity(
            session["user_id"],
            f"{session['name']} deleted task '{task['title']}'"
        )

        flash("Task deleted successfully.", "success")

    except sqlite3.IntegrityError:
        db.rollback()
        flash(
            "Task cannot be deleted because another record depends on it.",
            "danger"
        )

    return redirect(url_for("tasks_list"))


# ---------------------------------------------------------------------------
# DOUBTS
# ---------------------------------------------------------------------------

@app.route("/doubts", methods=["GET", "POST"])
@login_required
def doubts_list():
    db = get_db()
    role = session["role"]

    if request.method == "POST":
        question = request.form.get("question", "").strip()

        if question:
            db.execute("""
                INSERT INTO doubts
                (user_id,team_id,question)
                VALUES (?,?,?)
            """, (
                session["user_id"],
                session["team_id"],
                question
            ))
            db.commit()

            log_activity(
                session["user_id"],
                f"{session['name']} submitted a doubt"
            )

            flash(
                "Doubt submitted successfully.",
                "success"
            )

        return redirect(url_for("doubts_list"))

    status_filter = request.args.get("status", "")
    q = request.args.get("q", "").strip()

    base = """
        SELECT
            d.*,
            u.name AS asker,
            t.name AS team_name
        FROM doubts d
        JOIN users u ON d.user_id=u.id
        JOIN teams t ON d.team_id=t.id
    """

    if role == "SUPER_ADMIN":
        sql = base + " WHERE 1=1"
        params = []

    elif role == "ADMIN":
        sql = base + " WHERE d.team_id=?"
        params = [session["team_id"]]

    else:
        sql = base + " WHERE d.user_id=?"
        params = [session["user_id"]]

    if status_filter:
        sql += " AND d.status=?"
        params.append(status_filter)

    if q:
        sql += " AND d.question LIKE ?"
        params.append(f"%{q}%")

    sql += " ORDER BY d.created_at DESC"

    doubts = db.execute(sql, params).fetchall()

    return render_template(
        "doubts.html",
        doubts=doubts,
        status_filter=status_filter,
        q=q
    )


@app.route("/doubts/answer/<int:doubt_id>", methods=["POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def doubt_answer(doubt_id):
    db = get_db()

    doubt = db.execute(
        "SELECT * FROM doubts WHERE id=?",
        (doubt_id,)
    ).fetchone()

    if not doubt:
        flash("Doubt not found.", "danger")
        return redirect(url_for("doubts_list"))

    if (
        session["role"] == "ADMIN"
        and doubt["team_id"] != session["team_id"]
    ):
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for("doubts_list"))

    answer = request.form.get("answer", "").strip()

    db.execute("""
        UPDATE doubts
        SET answer=?,
            status='Answered',
            answered_by=?,
            answered_at=?
        WHERE id=?
    """, (
        answer,
        session["user_id"],
        datetime.now().isoformat(timespec="seconds"),
        doubt_id
    ))

    db.commit()

    log_activity(
        session["user_id"],
        f"{session['name']} answered a doubt"
    )

    flash(
        "Doubt answered successfully.",
        "success"
    )

    return redirect(url_for("doubts_list"))


# ---------------------------------------------------------------------------
# SUGGESTIONS
# ---------------------------------------------------------------------------

@app.route("/suggestions", methods=["GET", "POST"])
@login_required
def suggestions_list():
    db = get_db()
    role = session["role"]

    if request.method == "POST":
        text = request.form.get("suggestion", "").strip()

        if text:
            db.execute("""
                INSERT INTO suggestions
                (user_id,team_id,suggestion)
                VALUES (?,?,?)
            """, (
                session["user_id"],
                session["team_id"],
                text
            ))

            db.commit()

            log_activity(
                session["user_id"],
                f"{session['name']} submitted a suggestion"
            )

            flash(
                "Suggestion submitted successfully.",
                "success"
            )

        return redirect(url_for("suggestions_list"))

    status_filter = request.args.get("status", "")
    q = request.args.get("q", "").strip()

    base = """
        SELECT
            s.*,
            u.name AS author,
            t.name AS team_name
        FROM suggestions s
        JOIN users u ON s.user_id=u.id
        JOIN teams t ON s.team_id=t.id
    """

    if role == "SUPER_ADMIN":
        sql = base + " WHERE 1=1"
        params = []

    elif role == "ADMIN":
        sql = base + " WHERE s.team_id=?"
        params = [session["team_id"]]

    else:
        sql = base + " WHERE s.user_id=?"
        params = [session["user_id"]]

    if status_filter:
        sql += " AND s.status=?"
        params.append(status_filter)

    if q:
        sql += " AND s.suggestion LIKE ?"
        params.append(f"%{q}%")

    sql += " ORDER BY s.created_at DESC"

    suggestions = db.execute(
        sql,
        params
    ).fetchall()

    return render_template(
        "suggestions.html",
        suggestions=suggestions,
        status_filter=status_filter,
        q=q
    )


@app.route("/suggestions/review/<int:sug_id>", methods=["POST"])
@role_required("SUPER_ADMIN", "ADMIN")
def suggestion_review(sug_id):
    db = get_db()

    sug = db.execute(
        "SELECT * FROM suggestions WHERE id=?",
        (sug_id,)
    ).fetchone()

    if not sug:
        flash("Suggestion not found.", "danger")
        return redirect(url_for("suggestions_list"))

    if (
        session["role"] == "ADMIN"
        and sug["team_id"] != session["team_id"]
    ):
        flash("You do not have permission to perform this action.", "danger")
        return redirect(url_for("suggestions_list"))

    status = request.form.get(
        "status",
        "Reviewed"
    )

    response = request.form.get(
        "response",
        ""
    ).strip()

    db.execute("""
        UPDATE suggestions
        SET status=?,
            response=?,
            reviewed_by=?,
            updated_at=?
        WHERE id=?
    """, (
        status,
        response,
        session["user_id"],
        datetime.now().isoformat(timespec="seconds"),
        sug_id
    ))

    db.commit()

    log_activity(
        session["user_id"],
        f"{session['name']} reviewed a suggestion"
    )

    flash(
        "Suggestion updated successfully.",
        "success"
    )

    return redirect(url_for("suggestions_list"))


# ---------------------------------------------------------------------------
# LEADERBOARD
# ---------------------------------------------------------------------------

@app.route("/leaderboard")
@login_required
def leaderboard():
    db = get_db()

    if session["role"] == "SUPER_ADMIN":
        rows = db.execute("""
            SELECT
                u.name,
                u.points,
                t.name AS team_name
            FROM users u
            LEFT JOIN teams t ON u.team_id=t.id
            WHERE u.role='TEAM_MEMBER'
            ORDER BY u.points DESC, u.name
        """).fetchall()

    else:
        rows = db.execute("""
            SELECT
                u.name,
                u.points,
                t.name AS team_name
            FROM users u
            LEFT JOIN teams t ON u.team_id=t.id
            WHERE u.role='TEAM_MEMBER'
            AND u.team_id=?
            ORDER BY u.points DESC, u.name
        """, (
            session["team_id"],
        )).fetchall()

    return render_template(
        "leaderboard.html",
        rows=rows
    )


# ---------------------------------------------------------------------------
# ACTIVITIES
# ---------------------------------------------------------------------------

@app.route("/activities")
@role_required("SUPER_ADMIN")
def activities_list():
    db = get_db()

    rows = db.execute("""
        SELECT
            a.*,
            u.name AS user_name
        FROM activities a
        LEFT JOIN users u ON a.user_id=u.id
        ORDER BY a.created_at DESC
        LIMIT 300
    """).fetchall()

    return render_template(
        "activities.html",
        rows=rows
    )


# ---------------------------------------------------------------------------
# PROFILE
# ---------------------------------------------------------------------------

@app.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    db = get_db()

    user = db.execute(
        "SELECT * FROM users WHERE id=?",
        (session["user_id"],)
    ).fetchone()

    if not user:
        session.clear()
        return redirect(url_for("login"))

    team = None

    if user["team_id"]:
        team = db.execute(
            "SELECT * FROM teams WHERE id=?",
            (user["team_id"],)
        ).fetchone()

    if request.method == "POST":
        current_password = request.form.get(
            "current_password",
            ""
        )

        new_password = request.form.get(
            "new_password",
            ""
        )

        confirm_password = request.form.get(
            "confirm_password",
            ""
        )

        if not check_password_hash(
            user["password"],
            current_password
        ):
            flash(
                "Current password is incorrect.",
                "danger"
            )

        elif len(new_password) < 6:
            flash(
                "New password must be at least 6 characters.",
                "danger"
            )

        elif new_password != confirm_password:
            flash(
                "New passwords do not match.",
                "danger"
            )

        else:
            new_hash = generate_password_hash(new_password, method="pbkdf2:sha256")
            db.execute(
                "UPDATE users SET password=? WHERE lower(email)=?",
                (
                    new_hash,
                    user["email"].lower()
                )
            )

            db.commit()

            log_activity(
                user["id"],
                f"{user['name']} changed their password"
            )

            flash(
                "Password updated successfully.",
                "success"
            )

            return redirect(url_for("profile"))

    return render_template(
        "profile.html",
        user=user,
        team=team
    )


# ---------------------------------------------------------------------------
# REPORTS
# ---------------------------------------------------------------------------

@app.route("/reports")
@role_required("SUPER_ADMIN")
def reports():
    db = get_db()

    team_perf = db.execute("""
        SELECT
            t.name,
            COUNT(tk.id) AS total,
            COALESCE(
                SUM(
                    CASE
                        WHEN tk.status='Completed' THEN 1
                        ELSE 0
                    END
                ), 0
            ) AS done
        FROM teams t
        LEFT JOIN tasks tk ON tk.team_id=t.id
        GROUP BY t.id, t.name
        ORDER BY t.id
    """).fetchall()

    member_perf = db.execute("""
        SELECT
            u.name,
            t.name AS team_name,
            u.points,
            (
                SELECT COUNT(*)
                FROM tasks
                WHERE assigned_to=u.id
                AND status='Completed'
            ) AS completed
        FROM users u
        LEFT JOIN teams t ON u.team_id=t.id
        WHERE u.role='TEAM_MEMBER'
        ORDER BY u.points DESC
    """).fetchall()

    return render_template(
        "reports.html",
        team_perf=team_perf,
        member_perf=member_perf
    )


@app.route("/reports/export/<kind>")
@role_required("SUPER_ADMIN")
def reports_export(kind):
    db = get_db()

    output = io.StringIO()
    writer = csv.writer(output)

    if kind == "tasks":
        writer.writerow([
            "Title",
            "Team",
            "Assigned To",
            "Priority",
            "Status",
            "Due Date",
            "Created At"
        ])

        rows = db.execute("""
            SELECT
                tk.title,
                t.name AS team_name,
                u.name AS assignee,
                tk.priority,
                tk.status,
                tk.due_date,
                tk.created_at
            FROM tasks tk
            LEFT JOIN teams t ON tk.team_id=t.id
            LEFT JOIN users u ON tk.assigned_to=u.id
            ORDER BY tk.created_at DESC
        """).fetchall()

        for row in rows:
            writer.writerow(list(row))

        filename = "task_report.csv"

    elif kind == "points":
        writer.writerow([
            "Name",
            "Team",
            "Points"
        ])

        rows = db.execute("""
            SELECT
                u.name,
                t.name AS team_name,
                u.points
            FROM users u
            LEFT JOIN teams t ON u.team_id=t.id
            WHERE u.role='TEAM_MEMBER'
            ORDER BY u.points DESC
        """).fetchall()

        for row in rows:
            writer.writerow(list(row))

        filename = "points_report.csv"

    elif kind == "teams":
        writer.writerow([
            "Team",
            "Admin",
            "Members",
            "Total Tasks",
            "Completed Tasks"
        ])

        rows = db.execute("""
            SELECT
                t.name,
                a.name AS admin_name,
                (
                    SELECT COUNT(*)
                    FROM users u
                    WHERE u.team_id=t.id
                    AND u.role='TEAM_MEMBER'
                ),
                (
                    SELECT COUNT(*)
                    FROM tasks tk
                    WHERE tk.team_id=t.id
                ),
                (
                    SELECT COUNT(*)
                    FROM tasks tk
                    WHERE tk.team_id=t.id
                    AND tk.status='Completed'
                )
            FROM teams t
            LEFT JOIN users a ON t.admin_id=a.id
            ORDER BY t.id
        """).fetchall()

        for row in rows:
            writer.writerow(list(row))

        filename = "team_performance_report.csv"

    else:
        flash(
            "Unknown report type.",
            "danger"
        )
        return redirect(url_for("reports"))

    log_activity(
        session["user_id"],
        f"{session['name']} exported {filename}"
    )

    return Response(
        output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                f"attachment; filename={filename}"
        }
    )


@app.route("/reports/email-excel", methods=["GET", "POST"])
@role_required("SUPER_ADMIN")
def reports_email_excel():
    """
    Generates styled Excel workbook (.xlsx) with openpyxl and emails it to all Super Admins.
    """
    try:
        from email_exporter import send_excel_report_email
        res = send_excel_report_email(db_path=DB_PATH)

        log_activity(
            session["user_id"],
            f"{session['name']} triggered automatic Excel report email to Super Admins"
        )

        if res.get("success"):
            if res.get("simulated"):
                flash(
                    "Excel report generated! (Simulation mode: credentials not configured in .env, file saved locally)",
                    "info"
                )
            else:
                flash(
                    f"Excel report successfully emailed to Super Admin(s): {', '.join(res.get('recipients', []))}",
                    "success"
                )
        else:
            flash(f"Failed to email Excel report: {res.get('message')}", "danger")

    except Exception as exc:
        app.logger.exception("Error sending Excel email report: %s", exc)
        flash(f"Error dispatching Excel report: {exc}", "danger")

    return redirect(url_for("reports"))



# ---------------------------------------------------------------------------
# HEALTH / DEBUG ROUTE
# ---------------------------------------------------------------------------

@app.route("/health")
def health():
    """
    Quick test:
        /health
    If this works, Flask itself is running.
    """
    db = get_db()

    users_count = db.execute(
        "SELECT COUNT(*) c FROM users"
    ).fetchone()["c"]

    teams_count = db.execute(
        "SELECT COUNT(*) c FROM teams"
    ).fetchone()["c"]

    return {
        "status": "ok",
        "database": "connected",
        "users": users_count,
        "teams": teams_count,
        "logged_in": bool(session.get("user_id")),
        "role": session.get("role"),
    }


# ---------------------------------------------------------------------------
# ERROR HANDLERS
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(error):
    try:
        return render_template(
            "error.html",
            code=404,
            message="Page not found."
        ), 404
    except Exception:
        return "<h1>404 - Page not found</h1>", 404


@app.errorhandler(403)
def forbidden(error):
    try:
        return render_template(
            "error.html",
            code=403,
            message="Access forbidden."
        ), 403
    except Exception:
        return "<h1>403 - Access forbidden</h1>", 403


@app.errorhandler(400)
def bad_request(error):
    try:
        return render_template(
            "error.html",
            code=400,
            message="Bad request."
        ), 400
    except Exception:
        return "<h1>400 - Bad request</h1>", 400


@app.errorhandler(500)
def server_error(error):
    # Print the actual traceback in terminal.
    app.logger.error(
        "500 ERROR:\n%s",
        traceback.format_exc()
    )

    return (
        """
        <div style="
            font-family:Arial;
            padding:30px;
            max-width:900px;
            margin:auto;
        ">
            <h1>Team Pulse - Server Error</h1>
            <p>
                The server encountered an error.
                Check the terminal for the full traceback.
            </p>
            <p>
                <a href="/dashboard">Back to Dashboard</a>
            </p>
        </div>
        """,
        500
    )


# ---------------------------------------------------------------------------
# AUTOMATED BACKGROUND CRON SCHEDULER
# ---------------------------------------------------------------------------

def start_automated_report_scheduler():
    import threading
    import time
    from datetime import datetime

    def scheduler_loop():
        print("[Scheduler] Automated Daily 6:00 PM (18:00 IST) Excel Email Scheduler Active.")
        last_sent_day = None
        while True:
            try:
                now = datetime.now()
                # Trigger at 6:00 PM (18:00) every evening
                if now.hour == 18 and now.minute == 0:
                    today_key = now.strftime("%Y-%m-%d")
                    if last_sent_day != today_key:
                        last_sent_day = today_key
                        print(f"[Scheduler] ⏰ 6:00 PM Reached ({today_key})! Automatically emailing Excel report to Super Admins...")
                        from email_exporter import send_excel_report_email
                        res = send_excel_report_email(db_path=DB_PATH)
                        print(f"[Scheduler] Daily 6:00 PM Email dispatch result: {res}")
            except Exception as e:
                print(f"[Scheduler] Error in 6:00 PM automated report email: {e}")

            time.sleep(30)  # Check every 30 seconds

    thread = threading.Thread(target=scheduler_loop, daemon=True)
    thread.start()



# ---------------------------------------------------------------------------
# STARTUP
# ---------------------------------------------------------------------------

init_db()
start_automated_report_scheduler()

if __name__ == "__main__":
    print("=" * 60)
    print("TEAM PULSE STARTING")
    print("=" * 60)
    print(f"Database : {DB_PATH}")
    print("URL      : http://127.0.0.1:5000")
    print("Health   : http://127.0.0.1:5000/health")
    print("=" * 60)

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )

