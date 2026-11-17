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
    loadRecommendation(currentMuscle);
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

async function loadNutrition() {
    const res = await fetch("/nutrition/plan", { headers: authHeaders() });
    if (!res.ok) return;
    const d = await res.json();

    document.getElementById("goalLabel").textContent = d.goal_ru;
    document.getElementById("dailyBurnVal").textContent = d.tdee_maintenance_kcal + " ккал";
    document.getElementById("kcalTargetSub").textContent =
        "Целевое значение: " + d.daily_target.calories_kcal + " ккал" +
        (d.is_manual_burn ? " (ручной ввод)" : " (тренировки: +" + (d.daily_workout_bonus_kcal || 0) + " ккал)");

    document.getElementById("macrosInfo").textContent =
        d.daily_target.protein_g + "Б / " + d.daily_target.fats_g + "Ж / " + d.daily_target.carbs_g + "У";
    document.getElementById("kcalShiftInfo").textContent =
        "Смена: " + d.schedule_adaptation.work_day_kcal + " | Вых: " + d.schedule_adaptation.rest_day_kcal;

    document.getElementById("corridorRange").textContent = d.green_corridor.safe_range_kg;
    document.getElementById("currentWeightInfo").textContent = "Сейчас: " + d.green_corridor.current_weight_kg + " кг";
    document.getElementById("waterInfo").textContent = d.hydration_and_electrolytes.water_ml_per_day + " мл";
    document.getElementById("saltInfo").textContent = "Соль: " + d.hydration_and_electrolytes.salt_g_per_day + " г/сут";
    document.getElementById("scheduleCoachTip").textContent = d.schedule_adaptation.coach_tip;

    const menuBox = document.getElementById("sampleMenuList");
    if (menuBox && d.sample_daily_menu) {
        menuBox.innerHTML = "";
        d.sample_daily_menu.forEach(m => {
            const row = document.createElement("div");
            row.className = "meal-row";
            row.innerHTML =
                `<label style="display:flex; align-items:flex-start; gap:10px; margin:0; cursor:pointer; flex:1; color:#e2e8f0;">` +
                `<input type="checkbox" style="margin-top:4px; width:18px; height:18px;" onchange="this.closest('.meal-row').classList.toggle('done', this.checked)">` +
                `<div><strong style="color:#fbbf24;">${m.meal}</strong> <span style="color:#38bdf8; font-size:12px;">(~${m.kcal} ккал • ${m.protein_g} г белка)</span>` +
                `<div style="font-size:12px; color:#cbd5e1; margin-top:2px;">${m.items}</div></div>` +
                `</label>`;
            menuBox.appendChild(row);
        });
    }
}

async function loadRecommendation(muscle) {
    if (muscle !== undefined) currentMuscle = muscle;
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
        const div = document.createElement("div");
        div.className = "ex-item";
        div.innerHTML =
            `<div class="ex-head">` +
            `<strong style="font-size:14px; cursor:pointer;" onclick="selectExerciseForForm('${ex.name.replace(/'/g, "\\'")}')">${ex.name}</strong>` +
            `<div style="display:flex; gap:6px; align-items:center;">` +
            `<span class="ex-tag">${ex.equipment}</span>` +
            `<button class="icon-btn" title="Добавить в план тренировки" onclick="addToPlan('${ex.name.replace(/'/g, "\\'")}')">＋</button>` +
            `</div></div>` +
            `<p style="font-size:12px; color:#cbd5e1; margin-top:6px;"><span style="color:#34d399; font-weight:600;">Техника:</span> ${ex.technique_tips}</p>` +
            (ex.common_mistakes ? `<p style="font-size:12px; color:#94a3b8; margin-top:4px;"><span style="color:#fb7185; font-weight:600;">Ошибки:</span> ${ex.common_mistakes}</p>` : "");
        list.appendChild(div);
    });
}

function selectExerciseForForm(name) {
    document.getElementById("exName").value = name;
}
/* Конструктор тренировки на сегодня: галочки, перестановка, выбор */
function savePlanStorage() {
    localStorage.setItem("wv_plan", JSON.stringify(workoutPlan));
}

function addToPlan(name) {
    workoutPlan.push({ name: name, done: false });
    savePlanStorage();
    renderPlan();
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
    if (!box) return;
    if (workoutPlan.length === 0) {
        box.innerHTML = `<div style="font-size:12px; color:#94a3b8;">План пуст. Нажми <strong>«＋»</strong> на любом упражнении ниже, чтобы собрать тренировку и отмечать подходы галочками.</div>`;
        return;
    }
    box.innerHTML = "";
    workoutPlan.forEach((item, idx) => {
        const row = document.createElement("div");
        row.className = "plan-row" + (item.done ? " done" : "");
        row.innerHTML =
            `<label style="display:flex; align-items:center; gap:10px; margin:0; cursor:pointer; flex:1; color:#e2e8f0; font-size:14px;">` +
            `<input type="checkbox" ${item.done ? "checked" : ""} style="width:20px; height:20px;" onchange="togglePlanDone(${idx})">` +
            `<span onclick="selectExerciseForForm('${item.name.replace(/'/g, "\\'")}')">${idx + 1}. ${item.name}</span>` +
            `</label>` +
            `<div style="display:flex; gap:4px;">` +
            `<button class="icon-btn" onclick="movePlanItem(${idx}, -1)" title="Выше">↑</button>` +
            `<button class="icon-btn" onclick="movePlanItem(${idx}, 1)" title="Ниже">↓</button>` +
            `<button class="icon-btn" style="color:#fb7185;" onclick="removePlanItem(${idx})" title="Убрать">✕</button>` +
            `</div>`;
        box.appendChild(row);
    });
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
        const histBody = document.getElementById("historyTableBody");
        if (histBody) {
            histBody.innerHTML = "";
            const recent = (histData.workouts || []).slice(0, 15);
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
