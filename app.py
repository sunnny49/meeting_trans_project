from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, flash,send_from_directory
from sqlalchemy import text
from asr_core import transcribe_and_store, get_segments,ENGINE
from werkzeug.utils import secure_filename
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import text

app = Flask(__name__)
app.config["SECRET_KEY"] = "super-secret"

UPLOAD_DIR = Path("./uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

login_mgr = LoginManager(app)
login_mgr.login_view = "login"  

# --- 新增首頁顯示所有音檔 ---
@app.route("/")
def home():
    with ENGINE.begin() as conn:
        rows = conn.execute(
            text("SELECT AudioID, OriginalName, CreatedAt "
                 "FROM dbo.AudioFiles ORDER BY AudioID DESC")
        )
        files = [dict(r._mapping) for r in rows]
    return render_template("home.html", files=files)


@app.route("/result/<int:audio_id>")
def result(audio_id):
    segments = get_segments(audio_id)
    
    with ENGINE.begin() as conn:
        audio_file = conn.execute(
            text("SELECT OriginalName FROM dbo.AudioFiles WHERE AudioID=:id"),
            {"id": audio_id}
        ).scalar()


    return render_template("result.html",
                       audio_id=audio_id,
                       segments=segments,
                       audio_file=audio_file)

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files["audio"]
    save_path = UPLOAD_DIR / secure_filename(f.filename)
    f.save(save_path)

    # 直接同步轉錄 + 落DB
    audio_id = transcribe_and_store(Path(save_path))

    # 上傳完 → 立刻跳結果頁
    return redirect(url_for("result", audio_id=audio_id))

@app.route("/uploads/<path:fname>")
def download_file(fname):
    # UPLOAD_DIR 是 pathlib.Path，轉成字串給 send_from_directory
    return send_from_directory(str(UPLOAD_DIR), fname)

# --- 新增登入功能 ---
class Admin(UserMixin):
    def __init__(self, id_, username):
        self.id = id_
        self.username = username

@login_mgr.user_loader
def load_user(user_id):
    with ENGINE.begin() as conn:
        row = conn.execute(text("SELECT UserID, Username FROM dbo.AdminUsers WHERE UserID=:id"),
                           {"id": user_id}).first()
        if row:
            return Admin(row.UserID, row.Username)
    return None

# --- 新增登入頁面 ---
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        u = request.form["username"]
        p = request.form["password"]
        with ENGINE.begin() as conn:
            row = conn.execute(text("SELECT UserID, Username, PasswordHash FROM dbo.AdminUsers WHERE Username=:u"),
                               {"u": u}).first()
            if row and check_password_hash(row.PasswordHash, p):
                login_user(Admin(row.UserID, row.Username))
                return redirect(url_for("home"))
        flash("帳號或密碼錯誤")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("login"))

# ── 改名 ──────────────────────────────────────────
@app.route("/rename/<int:audio_id>", methods=["POST"])
@login_required
def rename_audio(audio_id):
    new_name = request.form.get("new_name", "").strip()
    if new_name:
        with ENGINE.begin() as conn:
            conn.execute(
                text("UPDATE dbo.AudioFiles SET OriginalName=:n WHERE AudioID=:id"),
                {"n": new_name, "id": audio_id}
            )
        flash("檔名已更新")
    else:
        flash("新檔名不可為空")
    return redirect(url_for("home"))

# ── 刪除 ──────────────────────────────────────────
@app.route("/delete/<int:audio_id>", methods=["POST"])
@login_required
def delete_audio(audio_id):
    with ENGINE.begin() as conn:
        conn.execute(text("DELETE FROM dbo.TranscriptSeg WHERE AudioID=:id"), {"id": audio_id})
        conn.execute(text("DELETE FROM dbo.AudioFiles    WHERE AudioID=:id"), {"id": audio_id})
    flash("已刪除")
    return redirect(url_for("home"))

# --- 前端更改字幕結果回傳給資料庫儲存 ---

@app.route("/api/segment/<int:seg_id>", methods=["PUT"])
@login_required
def api_update_segment(seg_id):
    data = request.get_json()
    new_txt = (data.get("text") or "").strip()

    if not new_txt:
        return {"ok": False, "msg": "字幕不得為空"}, 400

    with ENGINE.begin() as conn:
        affected = conn.execute(
            text("UPDATE dbo.TranscriptSeg SET Text=:t WHERE SegID=:id"),
            {"t": new_txt, "id": seg_id}
        ).rowcount

    if not affected:                        # 找不到該 SegID
        return {"ok": False, "msg": "SegID 不存在"}, 404

    return {"ok": True}

@app.after_request
def add_no_cache(resp):
    """讓所有回應都不要被瀏覽器快取，避免登出後返回仍顯示舊畫面。"""
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    return resp

if __name__ == "__main__":
    app.run(debug=True)
