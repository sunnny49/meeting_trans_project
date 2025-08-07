/* -----------------------------------------------------
   result.html 行內編輯腳本 (繁體中文註解)
   ----------------------------------------------------- */

document.addEventListener("click", async (e) => {
  const row = e.target.closest(".row");     // 找到被點擊元素所在的字幕列
  if (!row) return;

  /* === 進入編輯模式 === */
  if (e.target.matches(".edit-btn")) {
    const txtEl = row.querySelector(".text");       // 原本文字 span
    const textarea = document.createElement("textarea");
    textarea.value = txtEl.textContent.trim();      // 預填現有字幕
    textarea.style.width = "70%";
    txtEl.replaceWith(textarea);

    row.classList.add("editing");
    row.querySelector(".edit-btn").style.display = "none";
    row.querySelector(".save-btn").style.display = "inline";
    textarea.focus();
    return;
  }

  /* === 儲存字幕（Ajax PUT） === */
  if (e.target.matches(".save-btn")) {
    const segId    = row.dataset.id;
    const textarea = row.querySelector("textarea");
    const newTxt   = textarea.value.trim();

    // 呼叫後端 API
    const resp = await fetch(`/api/segment/${segId}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: newTxt })
    });

    if (!resp.ok) {                 // 若儲存失敗
      alert("儲存失敗，請稍後再試");
      return;
    }

    // 用 span 顯示最新文字、退出編輯模式
    const span = document.createElement("span");
    span.className = "text";
    span.textContent = newTxt || "(空白)";
    textarea.replaceWith(span);

    row.classList.remove("editing");
    row.querySelector(".edit-btn").style.display = "inline";
    row.querySelector(".save-btn").style.display = "none";
  }
});
