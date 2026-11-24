let token = localStorage.getItem("wv_token") || "";
let currentMuscle = "";
let currentLocation = "";
let workoutPlan = JSON.parse(localStorage.getItem("wv_plan") || "[]");
let allExercisesCatalog = [];
let restInterval = null;
let restSecondsLeft = 0;

if (token) { showDashboard(); }

function switchTab(tabName) {
    ["home", "workout", "analytics"].forEach(name => {
        document.getElementById("tab-" + name)?.classList.toggle("hidden", name !== tabName);
        document.getElementById("nav-" + name)?.classList.toggle("active", name === tabName);
    });
    localStorage.setItem("wv_active_tab", tabName);
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

    const dateInp = document.getElementById("workoutDateInput");
    if (dateInp && !dateInp.value) {
        dateInp.value = new Date().toLocaleDateString("sv-SE");
    }

    const savedTab = localStorage.getItem("wv_active_tab") || "home";
    switchTab(savedTab);
    renderPlan();

    await fetch("/workouts/claim-legacy", { method: "POST", headers: authHeaders() });
    await Promise.all([loadSupport(), loadNutrition(), loadExercisesCatalog(), loadRecommendation(), loadAnalytics()]);
}

function toggleCoachFullscreen() {
    const card = document.getElementById("coachCard");
    const btn = document.getElementById("fullscreenCoachBtn");
    const isFull = card.classList.toggle("coach-fullscreen");
    btn.textContent = isFull ? "✕ Свернуть" : "⤢ Весь экран";
    const box = document.getElementById("aiCoachBox");
    if (box) box.scrollTop = box.scrollHeight;
}

let isSendingCoach = false;
let lastCoachText = "";
let lastCoachTime = 0;

function escapeHtml(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;");
}

function appendAiChat(sender, text, color = "#e2e8f0") {
    const box = document.getElementById("aiCoachBox");
    const div = document.createElement("div");
    const cleanText = escapeHtml(String(text || "").replace(/\r/g, "").replace(/\n{2,}/g, "\n").trim());
    const formatted = cleanText.replace(/\n/g, "<br>");

    if (sender === "Ты") {
        div.className = "coach-msg coach-msg-user";
        const preview = String(text || "").replace(/\s+/g, " ").trim();
        div.innerHTML = `
            <div class="coach-user-toggle" style="display:flex;align-items:center;justify-content:space-between;gap:8px;cursor:pointer;padding:6px 10px;border-radius:10px;background:rgba(192,132,252,0.12);border:1px solid rgba(192,132,252,0.25);color:#d8b4fe;font-size:13px;">
                <span class="coach-user-preview" style="white-space:nowrap;overflow:hidden;text-overflow:ellipsis;"><strong>Ты:</strong> ${escapeHtml(preview)}</span>
                <span class="coach-user-arrow" style="flex-shrink:0;font-size:12px;">▸</span>
            </div>
            <div class="coach-user-full" style="display:none;padding:8px 10px 4px;color:#e9d5ff;font-size:14px;line-height:1.45;">${formatted}</div>
        `;
        const toggle = div.querySelector(".coach-user-toggle");
        const full = div.querySelector(".coach-user-full");
        const arrow = div.querySelector(".coach-user-arrow");
        const prevEl = div.querySelector(".coach-user-preview");
        toggle.addEventListener("click", () => {
            const isOpen = full.style.display === "block";
            full.style.display = isOpen ? "none" : "block";
            prevEl.style.display = isOpen ? "block" : "none";
            if (isOpen) {
                toggle.firstElementChild.innerHTML = `<strong>Ты:</strong> ${escapeHtml(preview)}`;
            } else {
                toggle.firstElementChild.innerHTML = `<strong>Ты</strong>`;
            }
            arrow.textContent = isOpen ? "▸" : "▾";
        });
    } else {
        div.className = "coach-msg coach-msg-ai";
        div.style.marginTop = "12px";
        div.style.padding = "10px 12px";
        div.style.borderRadius = "12px";
        div.style.background = "rgba(30, 41, 59, 0.55)";
        div.style.fontSize = "16px";
        div.style.lineHeight = "1.55";
        div.style.color = color;
        div.innerHTML = `<div style="font-size:12px;text-transform:uppercase;letter-spacing:0.04em;color:#38bdf8;margin-bottom:4px;font-weight:600;">${escapeHtml(sender)}</div><div>${formatted}</div>`;
    }

    div.style.marginTop = "10px";
    box.appendChild(div);
    box.scrollTop = box.scrollHeight;
}


let preferredRuVoice = null;

function pickBestRussianVoice() {
    if (!("speechSynthesis" in window)) return null;
    const voices = window.speechSynthesis.getVoices() || [];
    const ruVoices = voices.filter(v => (v.lang || "").toLowerCase().startsWith("ru"));
    if (ruVoices.length === 0) return null;

    const priorities = [
        v => /dmitry.*online|natural|neural/i.test(v.name),
        v => /svetlana.*online|irina.*online/i.test(v.name),
        v => /google\s*русский/i.test(v.name),
        v => /dmitry|yuri|maxim|pavel|milena|katya/i.test(v.name),
        v => !v.localService
    ];
    for (const rule of priorities) {
        const found = ruVoices.find(rule);
        if (found) return found;
    }
    return ruVoices[0];
}

if ("speechSynthesis" in window) {
    window.speechSynthesis.getVoices();
    window.speechSynthesis.onvoiceschanged = () => {
        preferredRuVoice = pickBestRussianVoice();
    };
}

const sharedTtsAudio = new Audio(); let currentTtsAudio = sharedTtsAudio;

function speakFallbackBrowser(cleanSpeech) {
    if (!("speechSynthesis" in window)) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(cleanSpeech);
    const voice = preferredRuVoice || pickBestRussianVoice();
    if (voice) utter.voice = voice;
    utter.lang = "ru-RU";
    utter.rate = 1.02;
    utter.pitch = 0.94;
    window.speechSynthesis.speak(utter);
}

function stopAllSpeech() {
    if (currentTtsAudio) {
        try {
            currentTtsAudio.pause();
            currentTtsAudio.src = "";
        } catch (e) {}
    }
    if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
    }
}

function toggleCoachVoice(isEnabled) {
    localStorage.setItem("wv_tts_enabled", isEnabled ? "1" : "0");
    if (!isEnabled) {
        stopAllSpeech();
    } else {
        try { sharedTtsAudio.play().then(() => sharedTtsAudio.pause()).catch(() => {}); } catch (e) {}
    }
}

async function speakText(text) {
    if (!document.getElementById("ttsToggle")?.checked) return;

    let cleanSpeech = String(text || "")
        .replace(/[*#_`~]/g, "")
        .replace(/×/g, " на ")
        .replace(/\|/g, ", ")
        .replace(/•/g, ", ")
        .replace(/\s+/g, " ")
        .trim();

    if (!cleanSpeech) return;
    if (cleanSpeech.length > 220) {
        const cut = cleanSpeech.slice(0, 220);
        const lastDot = Math.max(cut.lastIndexOf("."), cut.lastIndexOf("!"), cut.lastIndexOf("?"));
        cleanSpeech = lastDot > 60 ? cut.slice(0, lastDot + 1) : (cut + "...");
    }

    stopAllSpeech();

    try {
        const res = await fetch("/api/tts", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: cleanSpeech })
        });
        if (!res.ok) throw new Error("TTS API error");

        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const audio = sharedTtsAudio; audio.src = url;
        currentTtsAudio = audio;
        audio.onended = () => URL.revokeObjectURL(url);
        audio.onerror = () => {
            URL.revokeObjectURL(url);
            speakFallbackBrowser(cleanSpeech);
        };
        await audio.play();
    } catch (err) {
        speakFallbackBrowser(cleanSpeech);
    }
}

async function askAiCoach() {
    const inp = document.getElementById("aiCoachInput");
    const text = (inp ? inp.value : "").trim();
    if (!text) return; try { sharedTtsAudio.play().then(()=>sharedTtsAudio.pause()).catch(()=>{}); } catch(e){}

    const now = Date.now();
    if (isSendingCoach || (text === lastCoachText && now - lastCoachTime < 3000)) {
        return;
    }

    isSendingCoach = true;
    lastCoachText = text;
    lastCoachTime = now;
    if (inp) inp.value = "";

    if (typeof stopVoiceManual === "function") {
        stopVoiceManual(false);


    }
        appendAiChat("Ты", text);

    try {
        const res = await fetch("/coach/ask", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ message: text, current_plan: workoutPlan, scheduled_plans: JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}") })
        });
        if (!res.ok) { const errTxt = await res.text().catch(() => ""); appendAiChat("Система", `Ошибка (${res.status}): ${errTxt.slice(0, 120)}`, "#fb7185"); return; }
        const d = await res.json();

        appendAiChat("ИИ-тренер", d.reply, "#e2e8f0");
        speakText(d.reply);

        if (d.mode === "plan_moved" && d.from_date && d.target_date && Array.isArray(d.suggested_plan)) {
            const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
            delete schedMap[d.from_date];
            schedMap[d.target_date] = d.suggested_plan.map(item => ({
                name: item.name || item.exercise_name,
                done: false,
                sets: item.sets || 3,
                reps: item.reps || 12,
                weight: item.weight || 0
            }));
            localStorage.setItem("wv_scheduled_plans", JSON.stringify(schedMap));
            selectedDateStr = d.target_date;
            renderCalendar();
            renderCalDayDetails(d.target_date);
        } else if (d.mode === "plan_cancelled" && d.target_date) {
            const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
            delete schedMap[d.target_date];
            localStorage.setItem("wv_scheduled_plans", JSON.stringify(schedMap));
            renderCalendar();
            renderCalDayDetails(d.target_date);
        } else if (d.mode === "plan_scheduled" && Array.isArray(d.suggested_plan) && d.target_date) {
            const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
            schedMap[d.target_date] = d.suggested_plan.map(item => ({
                name: item.exercise_name,
                done: false,
                sets: item.sets || 3,
                reps: item.reps || 12,
                weight: item.weight || 0
            }));
            localStorage.setItem("wv_scheduled_plans", JSON.stringify(schedMap));
            workoutPlan = [];
            savePlanStorage();
            renderPlan();
            selectedDateStr = d.target_date;
            renderCalendar();
            renderCalDayDetails(d.target_date);
            appendAiChat("Система", `✓ Тренировка сохранена в календарь на ${d.target_date} и убрана из текущего списка.`, "#c084fc");
        } else if (d.mode === "plan_approved" && Array.isArray(d.suggested_plan)) {
            if (d.target_date) {
                const dateInp = document.getElementById("workoutDateInput");
                if (dateInp) dateInp.value = d.target_date;
            }
            workoutPlan = [];

            d.suggested_plan.forEach(item => {
                workoutPlan.push({
                    name: item.exercise_name,
                    done: Boolean(item.done),
                    sets: item.sets || 3,
                    reps: item.reps || 12,
                    weight: item.weight || 0
                });
            });
            savePlanStorage();
            renderPlan();
            appendAiChat("Система", `✓ План (${d.suggested_plan.length} поз.) перенесён в «План тренировки» ниже.`, "#34d399");
            if (navigator.vibrate) navigator.vibrate([40, 40, 40]);

            const card = document.getElementById("coachCard");
            if (card && card.classList.contains("coach-fullscreen")) {
                toggleCoachFullscreen();
            }
            const planEl = document.getElementById("workoutPlanList");
            if (planEl) {
                planEl.scrollIntoView({ behavior: "smooth", block: "center" });
            }

        } else if (d.mode === "live_set" && d.workout_entry) {
            const entry = d.workout_entry;
            entry.entries.forEach(item => {
                workoutPlan.push({
                    name: entry.exercise_name,
                    done: true,
                    sets: item.sets || 1,
                    reps: item.reps || 1,
                    weight: item.weight || 0
                });
            });
            savePlanStorage();
            renderPlan();
            appendAiChat("Система", `✓ Подход (${entry.exercise_name}) добавлен в текущий план.`, "#34d399");

        } else if (d.mode === "weight_updated") {
            await Promise.all([loadSupport(), loadNutrition()]);
        }

    } finally {
        isSendingCoach = false;
    }
}

let activeRecognition = null;
let voiceAnimFrame = null;
let voiceEnergy = 0;

function stopVoiceVisualizer() {
    if (voiceAnimFrame) cancelAnimationFrame(voiceAnimFrame);
    voiceAnimFrame = null;
    voiceEnergy = 0;
    const capsule = document.getElementById("coachInputCapsule");
    const btn = document.getElementById("aiVoiceBtn");
    if (capsule) capsule.classList.remove("listening");
    if (btn) btn.classList.remove("active");
    document.querySelectorAll("#aiVoiceWave span").forEach(bar => { bar.style.height = "5px"; });
}

function startVoiceVisualizer() {
    const bars = document.querySelectorAll("#aiVoiceWave span");
    const phases = [0, 1.1, 2.2, 1.1, 0];
    let t = 0;
    const tick = () => {
        if (!activeRecognition) return;
        t += 0.18;
        voiceEnergy = Math.max(0.18, voiceEnergy * 0.92);
        bars.forEach((bar, idx) => {
            const wave = (Math.sin(t + phases[idx]) + 1) / 2;
            const h = Math.round(5 + wave * 16 * voiceEnergy);
            bar.style.height = h + "px";
        });
        voiceAnimFrame = requestAnimationFrame(tick);
    };
    tick();
}

let isVoiceIntentionalActive = false;
let voiceSilenceTimer = null;

function stopVoiceManual(shouldSend = false) {
    isVoiceIntentionalActive = false;
    if (voiceSilenceTimer) {
        clearTimeout(voiceSilenceTimer);
        voiceSilenceTimer = null;
    }
        if (activeRecognition) {
        try {
            activeRecognition.onend = null;
            activeRecognition.stop();
        } catch (e) {}
        activeRecognition = null;
    }

    stopVoiceVisualizer();
    const input = document.getElementById("aiCoachInput");
    if (input) input.placeholder = "Спроси тренера или надиктуй подход...";
    if (shouldSend && input && input.value.trim()) {
        askAiCoach();
    }
}

function isFillerPhrase(txt) {
    const clean = txt.toLowerCase().replace(/[^\wа-яё\s]/g, "").trim();
    const fillers = new Set([
        "привет", "здравствуй", "слушай", "посмотри", "скажи",
        "так", "ну", "короче", "тренер", "братан", "эй"
    ]);
    return clean.length < 3 || fillers.has(clean);
}

function startAiVoice() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!SpeechRecognition) {
        appendAiChat("Система", "Используй микрофон на клавиатуре телефона для голосового ввода.", "#fbbf24");
        return;
    }

    if (isVoiceIntentionalActive || activeRecognition) {
        stopVoiceManual(true);
        return;
    }

    const capsule = document.getElementById("coachInputCapsule");
    const btn = document.getElementById("aiVoiceBtn");
    const input = document.getElementById("aiCoachInput");

    isVoiceIntentionalActive = true;
    let committedText = input.value.trim();

    if (capsule) capsule.classList.add("listening");
    if (btn) btn.classList.add("active");
    input.placeholder = "Слушаю... говори спокойно, нажми ↑ для отправки";
    voiceEnergy = 0.45;
    startVoiceVisualizer();

    const resetSilenceTimer = () => {
        if (voiceSilenceTimer) clearTimeout(voiceSilenceTimer);
        voiceSilenceTimer = setTimeout(() => {
            const currentVal = input.value.trim();
            if (!currentVal || isFillerPhrase(currentVal)) {
                resetSilenceTimer();
                return;
            }
            stopVoiceManual(true);
        }, 4200);
    };

    const launchSession = () => {
        if (!isVoiceIntentionalActive) return;
        const recog = new SpeechRecognition();
        activeRecognition = recog;
        recog.lang = "ru-RU";
        recog.interimResults = true;
        recog.continuous = true;

        recog.onresult = (e) => {
            voiceEnergy = 1.0;
            let interim = "";
            let sessionFinal = "";
            for (let i = 0; i < e.results.length; i++) {
                const part = e.results[i][0].transcript.trim();
                if (!part) continue;
                if (e.results[i].isFinal) {
                    sessionFinal += (sessionFinal ? " " : "") + part;
                } else {
                    interim += (interim ? " " : "") + part;
                }
            }
            const nextChunk = [sessionFinal, interim].filter(Boolean).join(" ").trim();
            const combined = committedText && nextChunk.toLowerCase().startsWith(committedText.toLowerCase())
                ? nextChunk
                : [committedText, nextChunk].filter(Boolean).join(" ").replace(/\s+/g, " ").trim();

            input.value = combined;
            resetSilenceTimer();
        };

        recog.onerror = (e) => {
            if (e.error === "not-allowed" || e.error === "service-not-allowed") {
                isVoiceIntentionalActive = false;
                stopVoiceVisualizer();
                appendAiChat("Система", "Разреши доступ к микрофону в настройках браузера.", "#fb7185");
            }
        };

        recog.onend = () => {
            activeRecognition = null;
            if (isVoiceIntentionalActive && !isSendingCoach) {
                committedText = input.value.trim();
                setTimeout(launchSession, 150);
            } else {
                stopVoiceVisualizer();
            }
        };

        try {
            recog.start();
            resetSilenceTimer();
        } catch (err) {
            isVoiceIntentionalActive = false;
            stopVoiceVisualizer();
        }
    };

    launchSession();
}








function startRestTimer(seconds) {
    stopRestTimer();
    restSecondsLeft = seconds;
    updateRestDisplay();
    restInterval = setInterval(() => {
        restSecondsLeft--;
        updateRestDisplay();
        if (restSecondsLeft <= 0) {
            stopRestTimer();
            const badge = document.getElementById("coachMiniTimer");
            if (badge) badge.textContent = "🔥 В ПОДХОД!";
            if (navigator.vibrate) navigator.vibrate([200, 100, 200]);
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
    const formatted = String(mins).padStart(2, "0") + ":" + String(secs).padStart(2, "0");
    const badge = document.getElementById("coachMiniTimer");
    if (badge) badge.textContent = "⏱ " + formatted;
}
function isBaseExercise(name) {
    const low = name.toLowerCase();
    return ["присед", "тяга", "жим", "подтягив", "брусь", "отжиман", "выпад"].some(k => low.includes(k));
}

async function loadExercisesCatalog() {
    const res = await fetch("/exercises/", { headers: authHeaders() });
    if (!res.ok) return;
    const d = await res.json();
    allExercisesCatalog = d.exercises || [];
    renderQuickChips();
}

function renderQuickChips() {
    const row = document.getElementById("quickChipsRow");
    if (!row) return;
    const topItems = allExercisesCatalog.slice(0, 6);
    row.innerHTML = "";
    topItems.forEach(ex => {
        const shortName = ex.name.split("(")[0].trim();
        const safeName = ex.name.replace(/'/g, "\\'");
        row.innerHTML += `<button class="chip-btn" onclick="addToPlan('${safeName}')">＋ ${shortName}</button>`;
    });
}

function handleQuickSearch(query) {
    const box = document.getElementById("quickAutocompleteList");
    if (!box) return;
    const q = query.trim().toLowerCase();
    if (q.length < 2) {
        box.classList.add("hidden");
        box.innerHTML = "";
        return;
    }

    const matches = allExercisesCatalog
        .filter(ex => ex.name.toLowerCase().includes(q))
        .slice(0, 5);

    if (matches.length === 0) {
        box.classList.add("hidden");
        return;
    }

    box.innerHTML = "";
    matches.forEach(ex => {
        const safeName = ex.name.replace(/'/g, "\\'");
        const tag = isBaseExercise(ex.name) ? "База" : "Изоляция";
        const tagColor = tag === "База" ? "#fbbf24" : "#38bdf8";
        box.innerHTML +=
            `<div class="ac-item" onclick="pickAutocomplete('${safeName}')">` +
            `<span>${ex.name}</span>` +
            `<span style="font-size:11px; color:${tagColor}; font-weight:700;">${tag} ＋</span>` +
            `</div>`;
    });
    box.classList.remove("hidden");
}

function pickAutocomplete(name) {
    addToPlan(name);
    document.getElementById("exName").value = name;
    document.getElementById("quickSearchInput").value = "";
    document.getElementById("quickAutocompleteList").classList.add("hidden");
}

function toggleCatalogPanel() {
    const panel = document.getElementById("fullCatalogPanel");
    const btn = document.getElementById("toggleCatalogBtn");
    const isHidden = panel.classList.toggle("hidden");
    btn.textContent = isHidden ? "📂 Каталог" : "✕ Скрыть";
}

function setLocation(loc) {
    currentLocation = loc;
    loadRecommendation(currentMuscle);
}

async function loadRecommendation(muscle) {
    if (muscle !== undefined) {
        currentMuscle = (currentMuscle === muscle && muscle !== "") ? "" : muscle;
    }
    const back = document.getElementById("safeBack")?.checked ?? true;
    const knees = document.getElementById("safeKnees")?.checked ?? true;
    const elbows = document.getElementById("safeElbows")?.checked ?? true;
    let url = "/workouts/recommend?protect_lower_back=" + back + "&protect_knees=" + knees + "&protect_elbows=" + elbows;
    if (currentMuscle) url += "&target_muscle=" + currentMuscle;
    if (currentLocation) url += "&location=" + currentLocation;

    const res = await fetch(url, { headers: authHeaders() });
    if (!res.ok) return;
    const d = await res.json();
    const adviceEl = document.getElementById("coachWorkoutAdvice");
    if (adviceEl) adviceEl.textContent = d.coach_advice;

    const list = document.getElementById("exercisesList");
    if (!list) return;
    list.innerHTML = "";
    d.suggested_exercises.forEach(ex => {
        const safeName = ex.name.replace(/'/g, "\\'");
        const tag = isBaseExercise(ex.name) ? "База" : "Изоляция";
        const div = document.createElement("div");
        div.className = "ex-item";
        div.innerHTML =
            `<div class="ex-head">` +
            `<strong style="font-size:13px; cursor:pointer;" onclick="selectExerciseForForm('${safeName}')">${ex.name}</strong>` +
            `<div style="display:flex; gap:6px; align-items:center;">` +
            `<span class="ex-tag">${tag}</span>` +
            `<button class="icon-btn" style="background:rgba(52,211,153,0.15); border-color:#34d399; color:#34d399;" onclick="addToPlan('${safeName}')">＋</button>` +
            `</div></div>` +
            `<details style="margin-top:6px; font-size:12px; color:#94a3b8;">` +
            `<summary style="cursor:pointer; color:#38bdf8;">Показать технику и ошибки</summary>` +
            `<p style="color:#cbd5e1; margin-top:4px;"><strong style="color:#34d399;">Техника:</strong> ${ex.technique_tips}</p>` +
            (ex.common_mistakes ? `<p style="margin-top:3px;"><strong style="color:#fb7185;">Ошибки:</strong> ${ex.common_mistakes}</p>` : "") +
            `</details>`;
        list.appendChild(div);
    });
}

function selectExerciseForForm(name) {
    document.getElementById("exName").value = name;
}

function savePlanStorage() {
    localStorage.setItem("wv_plan", JSON.stringify(workoutPlan));
    const dateVal = document.getElementById("workoutDateInput")?.value || new Date().toLocaleDateString("sv-SE");
    localStorage.setItem("wv_plan_date", dateVal);
    renderCalendar();
    renderCalDayDetails(selectedDateStr);
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

let draggedPlanIdx = null;

function reorderPlanItems(fromIdx, toIdx) {
    if (fromIdx === null || toIdx === null || fromIdx === toIdx) return;
    const [moved] = workoutPlan.splice(fromIdx, 1);
    workoutPlan.splice(toIdx, 0, moved);
    savePlanStorage();
    renderPlan();
    if (navigator.vibrate) navigator.vibrate(25);
}

function renderPlan() {
    const box = document.getElementById("workoutPlanList");
    const saveBox = document.getElementById("savePlanBtnBox");
    if (!box) return;
    if (workoutPlan.length === 0) {
        box.innerHTML = `<div style="font-size:12px; color:#94a3b8;">План пуст. Надиктуй подход ИИ-тренеру или выбери упражнение ниже.</div>`;
        if (saveBox) saveBox.classList.add("hidden");
        return;
    }
    if (saveBox) saveBox.classList.remove("hidden");
    box.innerHTML = "";
    workoutPlan.forEach((item, idx) => {
        const safeName = item.name.replace(/'/g, "\\'");
        const row = document.createElement("div");
        row.className = "plan-row" + (item.done ? " done" : "");
        row.dataset.planIdx = idx;
        row.draggable = true;
        row.style.flexDirection = "column";
        row.style.alignItems = "stretch";
        row.style.gap = "8px";
        row.style.transition = "transform 0.15s ease, border-color 0.15s ease";

        row.addEventListener("dragstart", () => {
            draggedPlanIdx = idx;
            row.style.opacity = "0.55";
        });
        row.addEventListener("dragend", () => {
            row.style.opacity = "1";
            draggedPlanIdx = null;
        });
        row.addEventListener("dragover", (e) => {
            e.preventDefault();
            row.style.borderColor = "#38bdf8";
        });
        row.addEventListener("dragleave", () => {
            row.style.borderColor = "";
        });
        row.addEventListener("drop", (e) => {
            e.preventDefault();
            row.style.borderColor = "";
            reorderPlanItems(draggedPlanIdx, idx);
        });

        row.innerHTML =
            `<div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">` +
            `<div style="display:flex; align-items:center; gap:8px; flex:1;">` +
            `<span class="drag-handle" title="Потяни, чтобы поменять местами" style="cursor:grab; touch-action:none; color:#64748b; font-size:18px; padding:2px 4px; user-select:none;">⠿</span>` +
            `<input type="checkbox" ${item.done ? "checked" : ""} style="width:18px; height:18px; cursor:pointer;" onchange="togglePlanDone(${idx})">` +
            `<strong style="color:#e2e8f0; font-size:14px; cursor:pointer;" onclick="selectExerciseForForm('${safeName}')">${idx + 1}. ${item.name}</strong>` +
            `</div>` +
            `<button class="icon-btn" style="color:#fb7185; min-width:32px; min-height:32px;" onclick="removePlanItem(${idx})">✕</button>` +
            `</div>` +
            `<div style="display:grid; grid-template-columns:1fr 1fr 1fr; gap:6px; padding-left:34px;">` +
            `<div><span style="font-size:10px; color:#94a3b8;">Подходы</span><input type="number" value="${item.sets || 3}" min="1" style="margin:0; padding:6px; font-size:13px;" onchange="updatePlanField(${idx}, 'sets', this.value)"></div>` +
            `<div><span style="font-size:10px; color:#94a3b8;">Повторы</span><input type="number" value="${item.reps || 15}" min="1" style="margin:0; padding:6px; font-size:13px;" onchange="updatePlanField(${idx}, 'reps', this.value)"></div>` +
            `<div><span style="font-size:10px; color:#94a3b8;">Вес (кг)</span><input type="number" step="0.5" value="${item.weight ?? 0}" style="margin:0; padding:6px; font-size:13px;" onchange="updatePlanField(${idx}, 'weight', this.value)"></div>` +
            `</div>`;

        const handle = row.querySelector(".drag-handle");
        handle.addEventListener("touchstart", () => {
            draggedPlanIdx = idx;
            row.style.opacity = "0.65";
            row.style.borderColor = "#38bdf8";
            if (navigator.vibrate) navigator.vibrate(20);
        }, { passive: true });

        handle.addEventListener("touchmove", (e) => {
            if (draggedPlanIdx === null) return;
            const touch = e.touches[0];
            const targetEl = document.elementFromPoint(touch.clientX, touch.clientY)?.closest(".plan-row");
            document.querySelectorAll(".plan-row").forEach(el => {
                if (el !== row) el.style.borderColor = "";
            });
            if (targetEl && targetEl !== row) {
                targetEl.style.borderColor = "#34d399";
            }
        }, { passive: true });

        handle.addEventListener("touchend", (e) => {
            row.style.opacity = "1";
            row.style.borderColor = "";
            if (draggedPlanIdx === null) return;
            const touch = e.changedTouches[0];
            const targetEl = document.elementFromPoint(touch.clientX, touch.clientY)?.closest(".plan-row");
            document.querySelectorAll(".plan-row").forEach(el => { el.style.borderColor = ""; });
            const targetIdx = targetEl ? parseInt(targetEl.dataset.planIdx, 10) : null;
            const from = draggedPlanIdx;
            draggedPlanIdx = null;
            if (targetIdx !== null && !Number.isNaN(targetIdx)) {
                reorderPlanItems(from, targetIdx);
            }
        });

        box.appendChild(row);
    });
}

async function saveWholePlan() {
    if (workoutPlan.length === 0) return;
    const st = document.getElementById("planSaveStatus");
    const chosenDate = document.getElementById("workoutDateInput")?.value || null;
    for (const item of workoutPlan) {
        const payload = {
            exercise_name: item.name,
            sets: parseInt(item.sets) || 3,
            reps: parseInt(item.reps) || 15,
            weight: parseFloat(item.weight) || 0,
            workout_date: chosenDate
        };
        await fetch("/workouts/", { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) });
    }
    if (st) {
        st.textContent = `Вся тренировка (${workoutPlan.length} поз.) записана в PostgreSQL!`;
        st.classList.remove("hidden");
        setTimeout(() => st.classList.add("hidden"), 3500);
    }
    await Promise.all([loadSupport(), loadNutrition(), loadAnalytics()]);
}

async function saveWorkout() {
    const chosenDate = document.getElementById("workoutDateInput")?.value || null;
    const payload = {
        exercise_name: document.getElementById("exName").value,
        sets: parseInt(document.getElementById("exSets").value),
        reps: parseInt(document.getElementById("exReps").value),
        weight: parseFloat(document.getElementById("exWeight").value) || 0,
        workout_date: chosenDate
    };
    const res = await fetch("/workouts/", { method: "POST", headers: authHeaders(), body: JSON.stringify(payload) });
    if (res.ok) {
        const st = document.getElementById("saveStatus");
        st.textContent = "Подход сохранён в PostgreSQL 17!";
        st.classList.remove("hidden");
        setTimeout(() => st.classList.add("hidden"), 3000);
        await Promise.all([loadSupport(), loadNutrition(), loadAnalytics()]);
    }
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

let currentNutritionPlan = null;
let checkedMealsSet = new Set();

async function loadNutrition() {
    const todayIso = new Date().toLocaleDateString("sv-SE");
    const [planRes, logRes] = await Promise.all([
        fetch("/nutrition/plan", { headers: authHeaders() }),
        fetch("/nutrition/logs/" + todayIso, { headers: authHeaders() })
    ]);
    if (!planRes.ok) return;
    const d = await planRes.json();
    currentNutritionPlan = d;

    if (logRes.ok) {
        const logData = await logRes.json();
        try {
            checkedMealsSet = new Set(JSON.parse(logData.checked_meals_json || "[]"));
        } catch (e) {
            checkedMealsSet = new Set();
        }
    }

    document.getElementById("goalLabel").textContent = d.goal_ru;
    document.getElementById("dailyBurnVal").textContent = d.tdee_maintenance_kcal + " ккал";
    document.getElementById("kcalTargetSub").textContent = "Цель на день: " + d.daily_target.calories_kcal + " ккал";
    document.getElementById("macrosInfo").textContent = `${d.daily_target.protein_g}г / ${d.daily_target.fats_g}г / ${d.daily_target.carbs_g}г`;
    document.getElementById("kcalShiftInfo").textContent = `Смена: ${d.schedule_adaptation.work_day_kcal} • Отдых: ${d.schedule_adaptation.rest_day_kcal}`;
    document.getElementById("corridorRange").textContent = d.green_corridor.safe_range_kg;
    document.getElementById("currentWeightInfo").textContent = "Сейчас: " + d.green_corridor.current_weight_kg + " кг";
    document.getElementById("waterInfo").textContent = d.hydration_and_electrolytes.water_ml_per_day + " мл";
    document.getElementById("saltInfo").textContent = "Соль: ~" + d.hydration_and_electrolytes.salt_g_per_day + " г/день";
    document.getElementById("scheduleCoachTip").textContent = d.schedule_adaptation.coach_tip;

    renderSampleMenu();
}

function renderSampleMenu() {
    const list = document.getElementById("sampleMenuList");
    if (!list || !currentNutritionPlan) return;
    list.innerHTML = "";
    currentNutritionPlan.sample_daily_menu.forEach((m, idx) => {
        const isDone = checkedMealsSet.has(idx);
        const row = document.createElement("div");
        row.className = "meal-row" + (isDone ? " done" : "");
        row.style.cursor = "pointer";
        row.onclick = () => toggleMealDone(idx);
        row.innerHTML =
            `<div style="display:flex; align-items:center; gap:10px;">` +
            `<input type="checkbox" ${isDone ? "checked" : ""} style="width:18px; height:18px; pointer-events:none;">` +
            `<div><strong style="color:#e2e8f0; font-size:13px;">${m.meal}</strong><div style="font-size:12px; color:#94a3b8;">${m.items}</div></div>` +
            `</div>` +
            `<span class="badge" style="white-space:nowrap;">${m.kcal} ккал</span>`;
        list.appendChild(row);
    });
}

async function toggleMealDone(idx) {
    if (checkedMealsSet.has(idx)) checkedMealsSet.delete(idx);
    else checkedMealsSet.add(idx);
    renderSampleMenu();

    if (!currentNutritionPlan) return;
    const todayIso = new Date().toLocaleDateString("sv-SE");
    let consumed = 0;
    currentNutritionPlan.sample_daily_menu.forEach((m, i) => {
        if (checkedMealsSet.has(i)) consumed += m.kcal;
    });

    await fetch("/nutrition/logs", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify({
            log_date: todayIso,
            target_kcal: currentNutritionPlan.daily_target.calories_kcal,
            consumed_kcal: consumed,
            protein_g: currentNutritionPlan.daily_target.protein_g,
            fats_g: currentNutritionPlan.daily_target.fats_g,
            carbs_g: currentNutritionPlan.daily_target.carbs_g,
            weight_kg: currentNutritionPlan.green_corridor.current_weight_kg,
            checked_meals_json: JSON.stringify(Array.from(checkedMealsSet))
        })
    });
    const badge = document.getElementById("nutritionSyncBadge");
    if (badge) {
        badge.textContent = "✓ Сохранено в БД";
        setTimeout(() => { badge.textContent = ""; }, 2000);
    }
}

let allWorkoutsCache = [];
let calYear = new Date().getFullYear();
let calMonth = new Date().getMonth();
let selectedDateStr = new Date().toLocaleDateString("sv-SE");

function changeCalMonth(delta) {
    calMonth += delta;
    if (calMonth < 0) { calMonth = 11; calYear--; }
    else if (calMonth > 11) { calMonth = 0; calYear++; }
    renderCalendar();
}

function selectCalDay(dateStr) {
    selectedDateStr = dateStr;
    renderCalendar();
    renderCalDayDetails(dateStr);
}

function estimateWorkoutKcal(items) {
    if (!items || items.length === 0) return 0;
    let totalSets = 0;
    let totalReps = 0;
    let weightedTonnage = 0;
    items.forEach(w => {
        const s = w.sets || 1;
        const r = w.reps || 1;
        const wt = w.weight || 0;
        const low = (w.exercise_name || "").toLowerCase();
        const isBodyweight = low.includes("подтягив") || low.includes("брусь") || low.includes("отжиман");
        totalSets += s;
        totalReps += s * r;
        weightedTonnage += (s * r * wt) * (isBodyweight ? 0.45 : 1.0);
    });
    const kcal = 45 + (weightedTonnage * 0.042) + (totalReps * 0.55) + (totalSets * 3.5);
    return Math.round(kcal);
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

    let monthWorkoutsCount = 0;
    let monthTotalKcal = 0;

    grid.innerHTML = "";
    for (let i = 0; i < startOffset; i++) {
        grid.innerHTML += `<div></div>`;
    }

    for (let day = 1; day <= daysInMonth; day++) {
        const dStr = `${calYear}-${String(calMonth + 1).padStart(2, "0")}-${String(day).padStart(2, "0")}`;
        const dayItems = workoutsByDate[dStr];
        const hasWorkout = Boolean(dayItems);
        const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
        const plannedDate = localStorage.getItem("wv_plan_date") || "";
        const isPlanned = !hasWorkout && ((Array.isArray(schedMap[dStr]) && schedMap[dStr].length > 0) || (workoutPlan.length > 0 && dStr === plannedDate));

        const isSelected = dStr === selectedDateStr;
                const isToday = dStr === todayStr;

        if (hasWorkout) {
            monthWorkoutsCount++;
            monthTotalKcal += estimateWorkoutKcal(dayItems);
        }

        let bg = "#0f172a";
        let border = isToday ? "1px solid #38bdf8" : "1px solid #1e293b";
        let color = "#94a3b8";

        if (hasWorkout) {
            bg = "rgba(52, 211, 153, 0.16)";
            border = isSelected ? "2px solid #34d399" : "1px solid rgba(52, 211, 153, 0.5)";
            color = "#34d399";
        } else if (isPlanned) {
            bg = "rgba(168, 85, 247, 0.20)";
            border = isSelected ? "2px solid #c084fc" : "1px solid rgba(168, 85, 247, 0.55)";
            color = "#d8b4fe";
        } else if (isSelected) {
            bg = "rgba(56, 189, 248, 0.18)";
            border = "2px solid #38bdf8";
            color = "#fff";
        }

        const dot = hasWorkout
            ? `<div style="width:5px; height:5px; border-radius:50%; background:#34d399; margin:2px auto 0;"></div>`
            : (isPlanned
                ? `<div style="width:5px; height:5px; border-radius:50%; background:#c084fc; margin:2px auto 0;"></div>`
                : `<div style="height:7px;"></div>`);

        grid.innerHTML +=
            `<button onclick="selectCalDay('${dStr}')" style="background:${bg}; border:${border}; border-radius:10px; padding:6px 2px; cursor:pointer; text-align:center; color:${color}; font-weight:${hasWorkout || isPlanned || isSelected ? '700' : '500'}; font-size:13px;">` +
            `<div>${day}</div>${dot}` +
            `</button>`;
    }




    let summaryEl = document.getElementById("calMonthSummary");
    if (!summaryEl) {
        summaryEl = document.createElement("div");
        summaryEl.id = "calMonthSummary";
        summaryEl.style.cssText = "margin-bottom:10px; padding:8px 10px; background:#0f172a; border:1px solid #1e293b; border-radius:10px; font-size:12px; color:#cbd5e1; display:flex; flex-wrap:wrap; justify-content:space-between; gap:6px;";
        grid.parentNode.insertBefore(summaryEl, grid.previousElementSibling);
    }
    const avgKcal = monthWorkoutsCount > 0 ? Math.round(monthTotalKcal / monthWorkoutsCount) : 0;
    summaryEl.innerHTML =
        `<span>Тренировок в месяце: <strong style="color:#34d399;">${monthWorkoutsCount}</strong></span>` +
        `<span>Расход: <strong style="color:#fbbf24;">~${monthTotalKcal} ккал</strong> (ср. <strong>~${avgKcal} ккал</strong>/трен.)</span>`;
}

function renderCalDayDetails(dateStr) {
    const box = document.getElementById("calDayDetails");
    if (!box) return;

    const parts = dateStr.split("-");
    const niceDate = `${parts[2]}.${parts[1]}.${parts[0]}`;
    const dayItems = allWorkoutsCache.filter(w => w.created_at && new Date(w.created_at).toLocaleDateString("sv-SE") === dateStr);

    if (dayItems.length === 0) {
        const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
        const plannedDate = localStorage.getItem("wv_plan_date") || "";
        const schedItems = (Array.isArray(schedMap[dateStr]) && schedMap[dateStr].length > 0)
            ? schedMap[dateStr]
            : ((workoutPlan.length > 0 && dateStr === plannedDate) ? workoutPlan : []);
        if (schedItems.length > 0) {
            let planHtml = "";
            schedItems.forEach((p, idx) => {
                planHtml +=
                    `<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #1e293b; font-size:12px;">` +
                    `<span style="color:#e2e8f0;"><strong>${idx + 1}. ${p.name}</strong></span>` +
                    `<span style="color:#c084fc;">${p.sets || 3}×${p.reps || 12} • ${p.weight || 0} кг</span>` +
                    `</div>`;
            });
            box.innerHTML =
                `<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">` +
                `<strong style="color:#c084fc;">Запланировано на ${niceDate}</strong>` +
                `<span class="badge" style="background:rgba(168,85,247,0.18); color:#d8b4fe;">План (${schedItems.length} поз.)</span>` +
                `</div>` +
                planHtml +
                `<button onclick="loadScheduledToToday('${dateStr}')" class="btn-primary" style="margin-top:10px; padding:8px; font-size:12px; background:linear-gradient(135deg,#9333ea,#6366f1);">Загрузить в «План тренировки» на сегодня</button>`;
            return;
        }

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
            `<div style="display:flex; justify-content:space-between; align-items:center; gap:6px; padding:5px 0; border-bottom:1px solid #1e293b; font-size:12px;">` +
            `<span style="color:#e2e8f0; flex:1;"><strong>${w.exercise_name}</strong></span>` +
            `<span style="color:#34d399;">${w.sets}×${w.reps} • ${wt} кг</span>` +
            `<button onclick="deleteCalWorkout(${w.id})" title="Удалить запись" style="background:none; border:none; color:#fb7185; cursor:pointer; font-size:13px; padding:2px 4px;">✕</button>` +
            `</div>`;
    });

    const burnedKcal = estimateWorkoutKcal(dayItems);

    box.innerHTML =
        `<div style="display:flex; flex-wrap:wrap; justify-content:space-between; align-items:center; gap:6px; margin-bottom:8px;">` +
        `<strong style="color:#34d399;">Тренировка за ${niceDate}</strong>` +
        `<div style="display:flex; gap:6px; flex-wrap:wrap;">` +
        `<span class="badge" style="background:rgba(251,191,36,0.16); color:#fbbf24;">🔥 ~${burnedKcal} ккал</span>` +
        `<span class="badge" style="background:rgba(52,211,153,0.18); color:#34d399;">Тоннаж: ${Math.round(totalTon * 10) / 10} кг</span>` +
        `</div>` +
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

function loadScheduledToToday(dateStr) {
    const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
    const items = schedMap[dateStr];
    if (!Array.isArray(items) || items.length === 0) return;
    workoutPlan = items.map(it => ({ ...it }));
    const dateInp = document.getElementById("workoutDateInput");
    if (dateInp) dateInp.value = dateStr;
    savePlanStorage();
    renderPlan();
    switchTab("workout");
}

async function deleteCalWorkout(workoutId) {
    const res = await fetch("/workouts/" + workoutId, { method: "DELETE", headers: authHeaders() });
    if (res.ok) {
        await Promise.all([loadSupport(), loadNutrition(), loadAnalytics()]);
    }
}
