let token = localStorage.getItem("wv_token") || "";
let currentMuscle = "";
let currentLocation = "";

if (token) { showDashboard(); }

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
    document.getElementById("kcalTarget").textContent = d.daily_target.calories_kcal + " ккал";
    document.getElementById("kcalShiftInfo").textContent = "Смена: " + d.schedule_adaptation.work_day_kcal + " | Вых: " + d.schedule_adaptation.rest_day_kcal;
    document.getElementById("macrosInfo").textContent = d.daily_target.protein_g + "Б / " + d.daily_target.fats_g + "Ж / " + d.daily_target.carbs_g + "У";
    document.getElementById("corridorRange").textContent = d.green_corridor.safe_range_kg;
    document.getElementById("currentWeightInfo").textContent = "Сейчас: " + d.green_corridor.current_weight_kg + " кг";
    document.getElementById("waterInfo").textContent = d.hydration_and_electrolytes.water_ml_per_day + " мл";
    document.getElementById("saltInfo").textContent = d.hydration_and_electrolytes.salt_g_per_day + " г";
    document.getElementById("scheduleCoachTip").textContent = d.schedule_adaptation.coach_tip;
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
        div.onclick = () => { document.getElementById("exName").value = ex.name; };
        div.innerHTML =
            '<div class="ex-head"><strong style="font-size:14px;">' + ex.name + '</strong><span class="ex-tag">' + ex.equipment + '</span></div>' +
            '<p style="font-size:12px; color:#cbd5e1; margin-top:6px;"><span style="color:#34d399; font-weight:600;">Техника:</span> ' + ex.technique_tips + '</p>' +
            (ex.common_mistakes ? '<p style="font-size:12px; color:#94a3b8; margin-top:4px;"><span style="color:#fb7185; font-weight:600;">Ошибки:</span> ' + ex.common_mistakes + '</p>' : '');
        list.appendChild(div);
    });
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
        loadSupport();
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
        if (autoCommit) {
            return confirmTx();
        }
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
    await loadSupport();
}

function cancelTx() {
    pendingTx = null;
    document.getElementById("txCard").classList.add("hidden");
    appendChat("Наставник", "Запись отменена. Можешь продиктовать заново!", "#fb7185");
}

function startVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        appendChat("Система", "Голосовой ввод не поддерживается этим браузером — используй клавиатуру или микрофон на клавиатуре телефона.", "#fbbf24");
        return;
    }
    const btn = document.querySelector("button[onclick='startVoice()']");
    const recog = new SpeechRecognition();
    recog.lang = "ru-RU";
    recog.interimResults = false;

    recog.onstart = () => {
        if (btn) { btn.style.borderColor = "#fb7185"; btn.textContent = "🔴"; }
        appendChat("Микрофон", "Слушаю... Говори фразу целиком (например: «Гоблет-приседания 25 кг 4 по 15»).", "#fbbf24");
    };

    recog.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        document.getElementById("chatInput").value = transcript;
        sendChat();
    };

    recog.onerror = (e) => {
        if (e.error === "not-allowed") {
            appendChat("Микрофон", "Доступ к микрофону запрещён браузером. Нажми на значок слева от localhost:8000 в адресной строке и разреши микрофон.", "#fb7185");
        } else if (e.error === "no-speech") {
            appendChat("Микрофон", "Речь не распознана — попробуй сказать чуть громче или проверь, подключён ли микрофон к ПК.", "#fbbf24");
        } else {
            appendChat("Микрофон", "Ошибка распознавания (" + e.error + "). На стационарном ПК без гарнитуры удобнее вводить текстом.", "#fbbf24");
        }
    };

    recog.onend = () => {
        if (btn) { btn.style.borderColor = "#334155"; btn.textContent = "🎤"; }
    };

    recog.start();
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
