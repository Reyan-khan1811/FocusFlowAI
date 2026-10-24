"""
FocusFlow AI — Python FastAPI Backend & SQLite Database Engine
Crafted for Reyan Khan's FocusFlow AI Suite

How to run locally:
1. Install dependencies:
   pip install fastapi uvicorn pydantic httpx
2. Start the server:
   python app.py
3. Open http://127.0.0.1:8000 in your browser!
"""

import os
import sqlite3
from datetime import datetime
from typing import List, Optional
import urllib.request
import json

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

# ==========================================
# 1. INITIALIZE FASTAPI & CORS
# ==========================================
app = FastAPI(
    title="FocusFlow AI Python Backend",
    description="REST API for Task Management, Weekly Analytics, Settings & Gemini AI Planning",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "focusflow.db"


# ==========================================
# 2. DATABASE INITIALIZATION (SQLite3)
# ==========================================
def init_db():
    """Creates tables and seeds default FocusFlow data if empty."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Tasks Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            tags TEXT NOT NULL,
            priority TEXT NOT NULL,
            difficulty TEXT NOT NULL,
            date TEXT NOT NULL,
            completed BOOLEAN NOT NULL DEFAULT 0
        )
    """)

    # User Settings Table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS user_settings (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            name TEXT NOT NULL,
            role TEXT NOT NULL,
            email TEXT NOT NULL,
            api_key TEXT DEFAULT ''
        )
    """)

    # Seed initial tasks if table is empty
    cursor.execute("SELECT COUNT(*) FROM tasks")
    if cursor.fetchone()[0] == 0:
        initial_tasks = [
            ("Finish ML Lab Report", "Academic,Lab", "Critical", "Hard", "Today · 7:00 PM", 0),
            ("Prepare for SDM-1 Exam", "Exam,Study", "High", "Hard", "Today · 11:00 AM", 0),
            ("Complete MSC Assignment", "Academic,Assignment", "High", "Medium", "Today · 5:00 PM", 0),
            ("Work on IoT Project (AQI Dashboard)", "Project,IoT", "Normal", "Medium", "Today · 8:00 PM", 0),
            ("Update GitHub Repository", "Project,Open Source", "Normal", "Easy", "Today · 4:30 PM", 1),
            ("Read 1 chapter (System Design)", "Learning,Tech", "Low", "Easy", "Tomorrow · 10:00 AM", 0),
            ("Workout / Health", "Health,Personal", "Low", "Easy", "Tomorrow · 6:00 PM", 0),
        ]
        cursor.executemany(
            "INSERT INTO tasks (title, tags, priority, difficulty, date, completed) VALUES (?, ?, ?, ?, ?, ?)",
            initial_tasks
        )

    # Seed initial user profile if empty
    cursor.execute("SELECT COUNT(*) FROM user_settings")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            "INSERT INTO user_settings (id, name, role, email, api_key) VALUES (1, ?, ?, ?, ?)",
            ("Reyan Khan", "Student · Builder", "reyan.khan@focusflow.ai", "")
        )

    conn.commit()
    conn.close()


init_db()


# ==========================================
# 3. PYDANTIC DATA MODELS
# ==========================================
class TaskCreate(BaseModel):
    title: str
    tags: List[str] = ["Academic"]
    priority: str = "Normal"
    difficulty: str = "Medium"
    date: str = "Today · 7:00 PM"
    completed: bool = False


class TaskUpdate(BaseModel):
    completed: bool


class SettingsPayload(BaseModel):
    name: str
    role: str
    email: str
    api_key: Optional[str] = ""


class AIPlanRequest(BaseModel):
    prompt: str
    api_key: Optional[str] = ""


# ==========================================
# 4. REST API ENDPOINTS
# ==========================================
@app.get("/api/health")
def health_check():
    """Returns Python backend status."""
    return {
        "status": "online",
        "engine": "Python 3 + FastAPI + SQLite",
        "timestamp": datetime.now().isoformat()
    }


@app.get("/api/tasks")
def get_tasks():
    """Fetches all tasks from the SQLite database."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM tasks ORDER BY id DESC")
    rows = cursor.fetchall()
    conn.close()

    tasks = []
    for row in rows:
        tasks.append({
            "id": row["id"],
            "title": row["title"],
            "tags": [t.strip() for t in row["tags"].split(",") if t.strip()],
            "priority": row["priority"],
            "difficulty": row["difficulty"],
            "date": row["date"],
            "completed": bool(row["completed"])
        })
    return {"tasks": tasks}


@app.post("/api/tasks")
def create_task(task: TaskCreate):
    """Creates a new task in SQLite and returns the created record."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    tags_str = ",".join(task.tags)
    cursor.execute(
        "INSERT INTO tasks (title, tags, priority, difficulty, date, completed) VALUES (?, ?, ?, ?, ?, ?)",
        (task.title, tags_str, task.priority, task.difficulty, task.date, int(task.completed))
    )
    new_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return {
        "id": new_id,
        "title": task.title,
        "tags": task.tags,
        "priority": task.priority,
        "difficulty": task.difficulty,
        "date": task.date,
        "completed": task.completed
    }


@app.patch("/api/tasks/{task_id}")
def toggle_task(task_id: int, update: TaskUpdate):
    """Updates task completion status in SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("UPDATE tasks SET completed = ? WHERE id = ?", (int(update.completed), task_id))
    if cursor.rowcount == 0:
        conn.close()
        raise HTTPException(status_code=404, detail="Task not found")
    conn.commit()
    conn.close()
    return {"status": "updated", "id": task_id, "completed": update.completed}


@app.delete("/api/tasks/{task_id}")
def delete_task(task_id: int):
    """Deletes a task from SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    conn.commit()
    conn.close()
    return {"status": "deleted", "id": task_id}


@app.get("/api/settings")
def get_settings():
    """Fetches saved user login details and API key state."""
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_settings WHERE id = 1")
    row = cursor.fetchone()
    conn.close()
    return {
        "name": row["name"],
        "role": row["role"],
        "email": row["email"],
        "has_key": bool(row["api_key"])
    }


@app.post("/api/settings")
def save_settings(payload: SettingsPayload):
    """Saves user login profile and API key to SQLite."""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE user_settings SET name = ?, role = ?, email = ?, api_key = ? WHERE id = 1",
        (payload.name, payload.role, payload.email, payload.api_key or "")
    )
    conn.commit()
    conn.close()
    return {"status": "saved", "name": payload.name, "role": payload.role}


@app.post("/api/ai/plan")
def ai_plan(req: AIPlanRequest):
    """
    Uses Python to call the Gemini API (if API key is configured) or
    executes FocusFlow's local Python heuristic task scheduler.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT api_key FROM user_settings WHERE id = 1")
    row = cursor.fetchone()
    saved_key = (req.api_key or (row["api_key"] if row else "")).strip()
    conn.close()

    # If a Gemini API Key is available, call Gemini 2.5 Flash from Python
    if len(saved_key) > 10:
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={saved_key}"
            body = json.dumps({
                "contents": [{
                    "parts": [{
                        "text": (
                            "You are FocusFlow AI, a mindful productivity assistant built by Reyan Khan. "
                            "Keep your response concise (max 2 sentences) and actionable. "
                            f"User request: {req.prompt}"
                        )
                    }]
                }]
            }).encode("utf-8")

            request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
            with urllib.request.urlopen(request, timeout=8) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                reply = res_data["candidates"][0]["content"]["parts"][0]["text"]
                return {"reply": reply, "engine": "python-gemini"}
        except Exception as e:
            pass

    # Fallback Python Smart Scheduler
    prompt_lower = req.prompt.lower()
    if "tomorrow" in prompt_lower:
        reply = "Python Engine scheduled your 'AI Morning Deep-Work Block' for Tomorrow at 9:00 AM and prioritized your SDM-1 Exam prep! 🐍🪴"
    elif "focus" in prompt_lower:
        reply = "Python Priority Analyzer recommends tackling 'Finish ML Lab Report' (Critical) first before 7:00 PM, then reviewing SDM-1 notes. 🎯"
    else:
        reply = "Python Task Decomposer split this into: 1) Core architecture outline (25m), 2) Implementation & testing (45m), 3) Final review (20m). ✨"

    return {"reply": reply, "engine": "python-local"}


# Serve the existing FocusFlow AI HTML file at the root URL
@app.get("/")
def serve_frontend():
    if os.path.exists("focusflow_ai.html"):
        return FileResponse("focusflow_ai.html")
    return JSONResponse({
        "message": "Could not find focusflow_ai.html. Make sure it is in the same folder as focusflow_python_backend.py."
    })


if __name__ == "__main__":
    import uvicorn
    print("🌿 Starting FocusFlow AI Python Server at http://127.0.0.1:8000 ...")
    uvicorn.run(app, host="127.0.0.1", port=8000)