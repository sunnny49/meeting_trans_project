"""
asr_core.py
把 whisper_to_sql.py 的核心邏輯抽成 2 個函式：
1. transcribe_and_store(audio_path) → AudioID, segments
2. get_segments(audio_id)           → list[dict]
"""

import os
from urllib.parse import quote_plus
from pathlib import Path
from opencc import OpenCC
import whisper
from sqlalchemy import create_engine, text
tc = OpenCC('s2t')                 # ← 建立轉換器，放在檔案最上方即可 (載一次全局重用)
# ---------- 資料庫連線 ----------
RAW_CONN = os.getenv(
    "MSSQL_CONN_STR",
    "Driver={ODBC Driver 18 for SQL Server};"
    "Server=localhost,1433;"
    "Database=SpeechDB;"
    "UID=sa;PWD=josh0207!;"
    "Encrypt=yes;TrustServerCertificate=yes;"
)
ENGINE = create_engine(f"mssql+pyodbc:///?odbc_connect={quote_plus(RAW_CONN)}",
                       fast_executemany=True, future=True)

# ---------- Whisper 模型（載入一次即可重用） ----------
MODEL = whisper.load_model("base")   # 需要 GPU 可改 faster-whisper

# ---------- 主要函式 ----------
def transcribe_and_store(audio_path: Path) -> int:
    """執行 ASR、寫入 DB，回傳 AudioID"""
    result = MODEL.transcribe(str(audio_path), language=None, verbose=False)
    lang = result["language"]
    segments = result["segments"]
# ---------- ★ 把每句文字轉繁體 ----------

    for s in segments:                            # ① 迭代段落
        s["text"] = tc.convert(s["text"])         # ② 就地覆寫為繁體

# ---------- ★ 轉換完畢 --------------------

    # 寫入 AudioFiles
    with ENGINE.begin() as conn:
        audio_id = conn.execute(
            text("""
                INSERT INTO dbo.AudioFiles (FilePath, OriginalName, Lang, DurationSec)
                OUTPUT INSERTED.AudioID
                VALUES (:fp, :orig, :lang, :dur)
            """),
            {"fp": str(audio_path),
            "orig": audio_path.name,
            "lang": lang,
            "dur": segments[-1]["end"]}
        ).scalar()

        # 批次寫入 TranscriptSeg
        rows = [
            {"aid": audio_id,
             "st": round(s["start"], 2),
             "ed": round(s["end"], 2),
             "txt": s["text"].strip()}
            for s in segments
        ]
        conn.execute(text("""
            INSERT INTO dbo.TranscriptSeg (AudioID, StartSec, EndSec, Text)
            VALUES (:aid, :st, :ed, :txt)
        """), rows)

    return audio_id


def get_segments(audio_id: int):
    with ENGINE.begin() as conn:
        rs = conn.execute(
            text("""
                SELECT SegID,StartSec, EndSec, Text
                FROM dbo.TranscriptSeg
                WHERE AudioID = :aid
                ORDER BY StartSec
            """),
            {"aid": audio_id}
        )
        return [dict(r._mapping) for r in rs]
