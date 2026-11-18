let token = localStorage.getItem("wv_token") || "";
let currentMuscle = "";
let currentLocation = "";
let workoutPlan = JSON.parse(localStorage.getItem("wv_plan") || "[]");
let restInterval = null;
let restSecondsLeft = 0;

if (token) { showDashboard(); }

function switchTab(tabName) {
    ["home", "workout", "analytics"].forEach(name => {
        document.getElementById("tab-" + name).classList.toggle("hidden", name !== tabName);
        document.getElementById("nav-" + name).classList.toggle("active", name === tabName);
    });
    if (tabName === "analytics") loadAnalytics();
}

async function login() {
    const form = new URLSearchParams();
    form.append("username", document.getElementById("loginUser").value);
    form.append("password", document.getElementById("loginPass").value);
    const res = await fetch("/auth/login", { method: "POST", body: form });
    if (!res.ok) {
        const err = document.getElementById("loginError");
        err.textContent = "Неверный логин или пароль";
        err.classList.remove("hidden");
        return;
    }
    const data = await res.json();
    token = data.access_token;
    localStorage.setItem("wv_token", token);
    showDashboard();
}

function logout() {
    localStorage.removeItem("wv_token");
    token = "";
    location.reload();
}

function authHeaders() {
    return { "Authorization": "Bearer " + token, "Content-Type": "application/json" };
}

async function showDashboard() {
    document.getElementById("loginSection").classList.add("hidden");
    document.getElementById("dashboardSection").classList.remove("hidden");
    document.getElementById("userBadge").classList.remove("hidden");
    renderPlan();
    await fetch("/workouts/claim-legacy", { method: "POST", headers: authHeaders() });
    await Promise.all([loadSupport(), loadNutrition(), loadRecommendation(), loadAnalytics()]);
}

function setLocation(loc) {
    currentLocation = loc;
    document.querySelectorAll("#tab-workout .tiles:nth-of-type(1) .tile-btn").forEach(btn => {
        const isMatch = btn.getAttribute("onclick") === `setLocation('${loc}')`;
        btn.style.borderColor = isMatch ? "#38bdf8" : "";
        btn.style.background = isMatch ? "rgba(56,189,248,0.18)" : "";
    });
    loadRecommendation(currentMuscle);
}

function openVideoTech(name) {
    const query = encodeURIComponent(name + " правильная техника выполнения упражнение");
    window.open("https://youtube.com" + query, "_blank", "noopener");
}


async function loadSupport() {
    const tired = document.getElementById("tiredCheckbox").checked;
    const res = await fetch("/coach/support?tired_after_shift=" + tired, { headers: authHeaders() });
    if (res.status === 401) return logout();
    const d = await res.json();
    document.getElementById("athleteName").textContent = "Атлет: " + d.athlete;
    document.getElementById("protocolTitle").textContent = d.protocol_title;
    document.getElementById("mentorMessage").textContent = d.mentor_message;
    document.getElementById("personalizedTone").textContent = d.personalized_tone;
    document.getElementById("microStep").textContent = d.today_micro_step;
    document.getElementById("totalRecords").textContent = d.training_progress.total_workout_records;
    document.getElementById("totalTonnage").textContent = d.training_progress.total_tonnage_kg + " кг";
    document.getElementById("totalReps").textContent = d.training_progress.total_reps_completed;
}

async function loadRecommendation(muscle) {
    if (muscle !== undefined) {
        currentMuscle = (currentMuscle === muscle && muscle !== "") ? "" : muscle;
    }
    document.querySelectorAll("#tab-workout .tiles:nth-of-type(2) .tile-btn").forEach(btn => {
        const isMatch = currentMuscle && btn.getAttribute("onclick") === `loadRecommendation('${currentMuscle}')`;
        btn.style.borderColor = isMatch ? "#38bdf8" : "";
        btn.style.background = isMatch ? "rgba(56,189,248,0.18)" : "";
    });

    const back = document.getElementById("safeBack").checked;
    const knees = document.getElementById("safeKnees").checked;
    const elbows = document.getElementById("safeElbows").checked;
    let url = "/workouts/recommend?protect_lower_back=" + back + "&protect_knees=" + knees + "&protect_elbows=" + elbows;
    if (currentMuscle) url += "&target_muscle=" + currentMuscle;
    if (currentLocation) url += "&location=" + currentLocation;

    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) return;
    const d = await res.json();
    document.getElementById("coachWorkoutAdvice").textContent = d.coach_advice;

    const list = document.getElementById("exercisesList");
    list.innerHTML = "";
    d.suggested_exercises.forEach(ex => {
        const safeName = ex.name.replace(/'/g, "\\'");
        const div = document.createElement("div");
        div.className = "ex-item";
        div.innerHTML =
            `<div class="ex-head">` +
            `<strong style="font-size:14px; cursor:pointer;" onclick="selectExerciseForForm('${safeName}')">${ex.name}</strong>` +
            `<div style="display:flex; gap:6px; align-items:center; flex-wrap:wrap;">` +
            `<span class="ex-tag">${ex.equipment}</span>` +
            `<button class="icon-btn" style="width:auto; padding:0 8px; font-size:11px; color:#38bdf8;" title="Смотреть технику" onclick="openVideoTech('${safeName}')">▶ Видео</button>` +
            `<button class="icon-btn" style="background:rgba(52,211,153,0.15); border-color:#34d399; color:#34d399;" title="Добавить в тренировку" onclick="addToPlan('${safeName}')">＋</button>` +
            `</div></div>` +
            `<p style="font-size:12px; color:#cbd5e1; margin-top:6px;"><span style="color:#34d399; font-weight:600;">Техника:</span> ${ex.technique_tips}</p>` +
            (ex.common_mistakes ? `<p style="font-size:12px; color:#94a3b8; margin-top:4px;"><span style="color:#fb7185; font-weight:600;">Ошибки:</span> ${ex.common_mistakes}</p>` : "");
        list.appendChild(div);
    });
}

function selectExerciseForForm(name) {
    document.getElementById("exName").value = name;
}

function savePlanStorage() {
    localStorage.setItem("wv_plan", JSON.stringify(workoutPlan));
}

function addToPlan(name) {
    workoutPlan.push({ name: name, done: false, sets: 3, reps: 15, weight: 0 });
    savePlanStorage();
    renderPlan();
    if (navigator.vibrate) navigator.vibrate(30);
}

function updatePlanField(idx, field, val) {
    workoutPlan[idx][field] = field === "weight" ? (parseFloat(val) || 0) : (parseInt(val) || 0);
    savePlanStorage();
}

function togglePlanDone(idx) {
    workoutPlan[idx].done = !workoutPlan[idx].done;
    savePlanStorage();
    renderPlan();
    if (workoutPlan[idx].done && navigator.vibrate) navigator.vibrate(40);
}

function movePlanItem(idx, dir) {
    const newIdx = idx + dir;
    if (newIdx < 0 || newIdx >= workoutPlan.length) return;
    const temp = workoutPlan[idx];
    workoutPlan[idx] = workoutPlan[newIdx];
    workoutPlan[newIdx] = temp;
    savePlanStorage();
    renderPlan();
}

function removePlanItem(idx) {
    workoutPlan.splice(idx, 1);
    savePlanStorage();
    renderPlan();
}

function clearPlan() {
    workoutPlan = [];
    savePlanStorage();
    renderPlan();
}

function renderPlan() {
    const box = document.getElementById("workoutPlanList");
    const saveBox = document.getElementById("savePlanBtnBox");
    if (!box) return;
    if (workoutPlan.length === 0) {
        box.innerHTML = `<div style="font-size:12px; color:#94a3b8;">Корзина пуста. Выбери группу мышц ниже и нажми <strong>«＋»</strong>, чтобы собрать тренировку.</div>`;
        if (saveBox) saveBox.classList.add("hidden");
        return;
    }
    if (saveBox) saveBox.classList.remove("hidden");
    box.innerHTML = "";
    workoutPlan.forEach((item, idx) => {
        const safeName = item.name.replace(/'/g, "\\'");
        const sets = item.sets || 3;
        const reps = item.reps || 15;
        const weight = item.weight ?? 0;
        const row = document.createElement("div");
        row.className = "plan-row" + (item.done ? " done" : "");
        row.style.flexDirection = "column";
        row.style.alignItems = "stretch";
        row.style.gap = "8px";
        row.innerHTML =
            `<div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">` +
            `<label style="display:flex; align-items:center; gap:10px; margin:0; cursor:pointer; flex:1; color:#e2e8f0; font-size:14px;">` +
            `<input type="checkbox" ${item.done ? "checked" : ""} style="width:20px; height:20px;" onchange="togglePlanDone(${idx})">` +
            `<strong onclick="selectExerciseForForm('${safeName}')">${idx + 1}. ${item.name}</strong>` +
            `</label>` +
            `<div style="display:flex; gap:4px;">` +
            `<button class="icon-btn" style="width:auto; padding:0 6px; font-size:11px; color:#38bdf8;" onclick="openVideoTech('${safeName}')" title="Видео техники">▶</button>` +
            `<button class="icon-btn" onclick="movePlanItem(${idx}, -1)" title="Выше">↑</button>` +
            `<button class="icon-btn" onclick="movePlanItem(${idx}, 1)" title="Ниже">↓</button>` +
            `<button class="icon-btn" style="color:#fb7185;" onclick="removePlanItem(${idx})" title="Убрать">✕</button>` +
            `</div></div>` +
            `<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; padding-left:30px;">` +
            `<div><span style="font-size:10px; color:#94a3b8;">Подходы</span><input type="number" value="${sets}" min="1" style="margin:0; padding:6px; font-size:13px;" onchange="updatePlanField(${idx}, 'sets', this.value)"></div>` +
            `<div><span style="font-size:10px; color:#94a3b8;">Повторы</span><input type="number" value="${reps}" min="1" style="margin:0; padding:6px; font-size:13px;" onchange="updatePlanField(${idx}, 'reps', this.value)"></div>` +
            `<div><span style="font-size:10px; color:#94a3b8;">Вес (кг)</span><input type="number" step="0.5" value="${weight}" style="margin:0; padding:6px; font-size:13px;" onchange="updatePlanField(${idx}, 'weight', this.value)"></div>` +
            `</div>`;
        box.appendChild(row);
    });
}

async function saveWholePlan() {
    if (workoutPlan.length === 0) return;
    const st = document.getElementById("planSaveStatus");
    for (const item of workoutPlan) {
        const payload = {
            exercise_name: item.name,
            sets: parseInt(item.sets) || 3,
            reps: parseInt(item.reps) || 15,
            weight: parseFloat(item.weight) || 0
        };
        await fetch("/workouts/", { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) });
    }
    if (st) {
        st.textContent = `Вся тренировка (${workoutPlan.length} упр.) записана в базу!`;
        st.classList.remove("hidden");
        setTimeout(() => st.classList.add("hidden"), 3500);
    }
    await Promise.all([loadSupport(), loadNutrition(), loadAnalytics()]);
}


/* Таймер отдыха между подходами */
function startRestTimer(seconds) {
    stopRestTimer();
    restSecondsLeft = seconds;
    updateRestDisplay();
    restInterval = setInterval(() => {
        restSecondsLeft--;
        updateRestDisplay();
        if (restSecondsLeft <= 0) {
            stopRestTimer();
            document.getElementById("restTimerDisplay").textContent = "В ПОДХОД!";
            if (navigator.vibrate) navigator.vibrate();
        }
    }, 1000);
}

function stopRestTimer() {
    if (restInterval) clearInterval(restInterval);
    restInterval = null;
}

function updateRestDisplay() {
    const mins = Math.floor(restSecondsLeft / 60);
    const secs = restSecondsLeft % 60;
    document.getElementById("restTimerDisplay").textContent =
        String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
}

async function saveWorkout() {
    const payload = {
        exercise_name: document.getElementById("exName").value,
        sets: parseInt(document.getElementById("exSets").value),
        reps: parseInt(document.getElementById("exReps").value),
        weight: parseFloat(document.getElementById("exWeight").value) || 0
    };
    const res = await fetch("/workouts/", { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) });
    if (res.ok) {
        const st = document.getElementById("saveStatus");
        st.textContent = "Подход сохранён в PostgreSQL 17!";
        st.classList.remove("hidden");
        setTimeout(() => st.classList.add("hidden"), 3000);
        await Promise.all([loadSupport(), loadNutrition()]);
    }
}

let pendingTx = null;
let autoCommit = localStorage.getItem("wv_autocommit") === "true";
document.getElementById("autoCommitToggle").checked = autoCommit;

function toggleAutoCommit() {
    autoCommit = document.getElementById("autoCommitToggle").checked;
    localStorage.setItem("wv_autocommit", autoCommit);
}

function appendChat(sender, text, color = "#e2e8f0") {
    const box = document.getElementById("chatBox");
    const div = document.createElement("div");
    div.style.marginTop = "8px";
    div.style.color = color;
    div.innerHTML = "<strong>" + sender + ":</strong> " + text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

async function sendChat() {
    const inp = document.getElementById("chatInput");
    const text = inp.value.trim();
    if (!text) return;
    inp.value = "";
    appendChat("Ты", text, "#38bdf8");

    if (pendingTx && ["да", "ок", "записывай", "верно", "всё отлично", "все отлично"].includes(text.toLowerCase())) {
        return confirmTx();
    }
    if (pendingTx && ["нет", "отмена", "отмени"].includes(text.toLowerCase())) {
        return cancelTx();
    }

    const res = await fetch("/coach/chat", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: text })
    });
    const d = await res.json();

    if (d.action === "confirm_workout" && d.transaction) {
        pendingTx = d.transaction;
        if (autoCommit) return confirmTx();
        const rows = d.transaction.entries.map(e => `${e.sets} подх. × ${e.reps} повт. (${e.weight} кг)`).join("<br>");
        document.getElementById("txDetails").innerHTML =
            `<strong>${d.transaction.exercise_name}</strong><br>${rows}<br>` +
            `<span style="color:#fbbf24;">Итого: ${d.transaction.summary.total_sets} подх., ${d.transaction.summary.total_reps} повт., тоннаж ${d.transaction.summary.tonnage_kg} кг</span>`;
        document.getElementById("txCard").classList.remove("hidden");
        appendChat("Наставник", d.reply, "#34d399");
    } else {
        appendChat("Наставник", d.reply, "#e2e8f0");
        if (d.action === "deleted" || d.action === "weight_updated") {
            await Promise.all([loadSupport(), loadNutrition()]);
        }
    }
}

async function confirmTx() {
    if (!pendingTx) return;
    if (document.getElementById("dontAskAgain").checked) {
        autoCommit = true;
        localStorage.setItem("wv_autocommit", "true");
        document.getElementById("autoCommitToggle").checked = true;
    }
    const txToSend = pendingTx;
    pendingTx = null;
    document.getElementById("txCard").classList.add("hidden");

    const res = await fetch("/coach/chat/commit", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ exercise_name: txToSend.exercise_name, entries: txToSend.entries })
    });
    const d = await res.json();
    appendChat("Наставник", d.reply, "#34d399");
    await Promise.all([loadSupport(), loadNutrition()]);
}

function cancelTx() {
    pendingTx = null;
    document.getElementById("txCard").classList.add("hidden");
    appendChat("Наставник", "Запись отменена. Можешь продиктовать заново!", "#fb7185");
}

function startVoice() {
    _runSpeechToText("chatInput", "button[onclick='startVoice()']", appendChat, sendChat);
}

function startAiVoice() {
    _runSpeechToText("aiCoachInput", "button[onclick='startAiVoice()']", appendAiChat, askAiCoach);
}

function _runSpeechToText(inputId, btnSelector, logFn, submitFn) {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        logFn("Система", "Браузер не поддерживает голосовой ввод — используй клавиатуру или микрофон на телефоне.", "#fbbf24");
        return;
    }
    const btn = document.querySelector(btnSelector);
    const input = document.getElementById(inputId);
    const oldPlaceholder = input.placeholder;

    if (btn) {
        btn.style.borderColor = "#fb7185";
        btn.style.background = "rgba(251,113,133,0.25)";
        btn.textContent = "〰️🔴";
    }
    input.placeholder = "〰️〰️ Слушаю голос... Говори...";

    const recog = new SpeechRecognition();
    recog.lang = "ru-RU";
    recog.interimResults = true;

    recog.onresult = (e) => {
        let liveText = "";
        for (let i = e.resultIndex; i < e.results.length; i++) {
            liveText += e.results[i][0].transcript;
        }
        input.value = liveText;
        if (e.results[e.results.length - 1].isFinal) submitFn();
    };

    recog.onerror = (e) => {
        logFn("Микрофон", "Статус записи: " + e.error, "#fbbf24");
    };

    recog.onend = () => {
        if (btn) {
            btn.style.borderColor = "#334155";
            btn.style.background = "";
            btn.textContent = "🎙️";
        }
        input.placeholder = oldPlaceholder;
    };

    try { recog.start(); } catch (err) { logFn("Микрофон", "Ошибка запуска: " + err.message, "#fb7185"); }
}

function appendAiChat(sender, text, color = "#e2e8f0") {
    const box = document.getElementById("aiCoachBox");
    const div = document.createElement("div");
    div.style.marginTop = "8px";
    div.style.color = color;
    div.innerHTML = "<strong>" + sender + ":</strong> " + text;
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}

function speakText(text) {
    if (!document.getElementById("ttsToggle")?.checked) return;
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.lang = "ru-RU";
    utter.rate = 1.03;
    window.speechSynthesis.speak(utter);
}

async function askAiCoach() {
    const inp = document.getElementById("aiCoachInput");
    const text = inp.value.trim();
    if (!text) return;
    inp.value = "";
    appendAiChat("Ты", text, "#c084fc");

    const res = await fetch("/coach/ask", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({ message: text })
    });
    if (res.ok) {
        const d = await res.json();
        appendAiChat("ИИ-тренер", d.reply, "#e2e8f0");
        speakText(d.reply);
    }
}
let allWorkoutsCache = [];
let calYear = new Date().getFullYear();
let calMonth = new Date().getMonth();
let selectedDateStr = new Date().toISOString().slice(0, 10);

function changeCalMonth(delta) {
    calMonth += delta;
    if (calMonth < 0) {
        calMonth = 11;
        calYear--;
    } else if (calMonth > 11) {
        calMonth = 0;
        calYear++;
    }
    renderCalendar();
}

function selectCalDay(dateStr) {
    selectedDateStr = dateStr;
    renderCalendar();
    renderCalDayDetails(dateStr);
}

function renderCalendar() {
    const grid = document.getElementById("calendarGrid");
    const title = document.getElementById("calMonthTitle");
    if (!grid || !title) return;

    const monthsRu = ["Январь", "Февраль", "Март", "Апрель", "Май", "Июнь", "Июль", "Август", "Сентябрь", "Октябрь", "Ноябрь", "Декабрь"];
    title.textContent = `${monthsRu[calMonth]} ${calYear}`;

    const workoutsByDate = {};
    allWorkoutsCache.forEach(w => {
        if (!w.created_at) return;
        const dKey = new Date(w.created_at).toLocaleDateString("sv-SE");
        if (!workoutsByDate[dKey]) workoutsByDate[dKey] = [];
        workoutsByDate[dKey].push(w);
    });

    const firstDay = new Date(calYear, calMonth, 1).getDay();
    const startOffset = firstDay === 0 ? 6 : firstDay - 1;
    const daysInMonth = new Date(calYear, calMonth + 1, 0).getDate();
    const todayStr = new Date().toLocaleDateString("sv-SE");

    grid.innerHTML = "";
    for (let i = 0; i < startOffset; i++) {
        grid.innerHTML += `<div></div>`;
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const dStr = `${calYear}-${String(calMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
        const hasWorkout = Boolean(workoutsByDate[dStr]);
        const isSelected = dStr === selectedDateStr;
        const isToday = dStr === todayStr;

        let bg = "#0f172a";
        let border = isToday ? "1px solid #38bdf8" : "1px solid #1e293b";
        let color = "#cbd5e1";

        if (hasWorkout) {
            bg = "rgba(52, 211, 153, 0.16)";
            border = isSelected ? "2px solid #34d399" : "1px solid rgba(52, 211, 153, 0.5)";
            color = "#34d399";
        } else if (isSelected) {
            bg = "rgba(56, 189, 248, 0.18)";
            border = "2px solid #38bdf8";
            color = "#fff";
        }

        const dot = hasWorkout ? `<div style="width:5px; height:5px; border-radius:50%; background:#34d399; margin:2px auto 0;"></div>` : `<div style="height:7px;"></div>`;

        grid.innerHTML +=
            `<button onclick="selectCalDay('${dStr}')" style="background:${bg}; border:${border}; border-radius:10px; padding:6px 2px; cursor:pointer; text-align:center; color:${color}; font-weight:${hasWorkout || isSelected ? '700' : '500'}; font-size:13px;">` +
            `<div>${day}</div>${dot}` +
            `</button>`;
    }
}

function renderCalDayDetails(dateStr) {
    const box = document.getElementById("calDayDetails");
    if (!box) return;

    const parts = dateStr.split("-");
    const niceDate = `${parts[2]}.${parts[1]}.${parts[0]}`;
    const dayItems = allWorkoutsCache.filter(w => w.created_at && new Date(w.created_at).toLocaleDateString("sv-SE") === dateStr);

    if (dayItems.length === 0) {
        box.innerHTML =
            `<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">` +
            `<strong style="color:#38bdf8;">${niceDate}</strong>` +
            `<span class="badge" style="background:rgba(148,163,184,0.15); color:#cbd5e1;">День отдыха и восстановления</span>` +
            `</div>` +
            `<div style="color:#94a3b8; font-size:12px;">В этот день силовых записей нет — организм восстанавливал мышцы, связки и ЦНС (протокол Zero-Shame).</div>`;
        return;
    }

    let totalTon = 0;
    let rowsHtml = "";
    dayItems.forEach(w => {
        const wt = w.weight || 0;
        const ton = Math.round(w.sets * w.reps * wt * 10) / 10;
        totalTon += ton;
        rowsHtml +=
            `<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #1e293b; font-size:12px;">` +
            `<span style="color:#e2e8f0;"><strong>${w.exercise_name}</strong></span>` +
            `<span style="color:#34d399;">${w.sets}×${w.reps} • ${wt} кг (${ton} кг)</span>` +
            `</div>`;
    });

    box.innerHTML =
        `<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">` +
        `<strong style="color:#34d399;">Тренировка за ${niceDate}</strong>` +
        `<span class="badge" style="background:rgba(52,211,153,0.18); color:#34d399;">Тоннаж: ${Math.round(totalTon * 10) / 10} кг</span>` +
        `</div>` +
        rowsHtml;
}

async function loadAnalytics() {
    const [recRes, histRes] = await Promise.all([
        fetch("/workouts/records", { headers: authHeaders() }),
        fetch("/workouts/", { headers: authHeaders() })
    ]);

    if (recRes.ok) {
        const recData = await recRes.json();
        const recBody = document.getElementById("recordsTableBody");
        if (recBody) {
            recBody.innerHTML = "";
            const sorted = (recData.records || []).sort((a, b) => (b.max_weight_kg - a.max_weight_kg) || (b.max_reps - a.max_reps));
            if (sorted.length === 0) {
                recBody.innerHTML = '<tr><td colspan="4" style="color:#64748b;">Пока нет записей</td></tr>';
            } else {
                sorted.forEach(r => {
                    recBody.innerHTML +=
                        `<tr>` +
                        `<td><strong>${r.exercise_name}</strong></td>` +
                        `<td class="num-accent">${r.max_weight_kg} кг</td>` +
                        `<td class="num-green">${r.max_reps}</td>` +
                        `<td>${r.total_sessions}</td>` +
                        `</tr>`;
                });
            }
        }
    }

    if (histRes.ok) {
        const histData = await histRes.json();
        allWorkoutsCache = histData.workouts || [];
        renderCalendar();
        renderCalDayDetails(selectedDateStr);

        const histBody = document.getElementById("historyTableBody");
        if (histBody) {
            histBody.innerHTML = "";
            const recent = allWorkoutsCache.slice(0, 15);
            if (recent.length === 0) {
                histBody.innerHTML = '<tr><td colspan="5" style="color:#64748b;">Журнал пуст</td></tr>';
            } else {
                recent.forEach(w => {
                    const dt = w.created_at ? new Date(w.created_at).toLocaleDateString("ru-RU", { day: "2-digit", month: "2-digit" }) : "—";
                    const wt = w.weight || 0;
                    const ton = Math.round(w.sets * w.reps * wt * 10) / 10;
                    histBody.innerHTML +=
                        `<tr>` +
                        `<td style="color:#94a3b8;">${dt}</td>` +
                        `<td>${w.exercise_name}</td>` +
                        `<td>${w.sets} × ${w.reps}</td>` +
                        `<td class="num-accent">${wt} кг</td>` +
                        `<td class="num-green">${ton} кг</td>` +
                        `</tr>`;
                });
            }
        }
    }
}
