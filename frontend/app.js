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
    btn.textContent = isFull ? "✕" : "⤢";
    btn.title = isFull ? "Свернуть чат" : "Развернуть на весь экран";
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

function formatCoachRichText(rawText) {
    const lines = String(rawText || "").replace(/\r/g, "").split("\n");
    const htmlParts = [];

    for (let i = 0; i < lines.length; i++) {
        let line = lines[i].trim();
        if (!line) continue;

        // Игнорируем декоративные разделители вроде ****, ---, ===
        if (/^[\*\-_=#]{3,}$/.test(line)) continue;

        // Заголовки ###
        const headingMatch = line.match(/^#{1,4}\s+(.+)$/);
        if (headingMatch) {
            const hText = escapeHtml(headingMatch[1].replace(/\*\*/g, ""));
            htmlParts.push(`<h4>${hText}</h4>`);
            continue;
        }

        // Маркированные пункты (- или • или *)
        const bulletMatch = line.match(/^(?:[-•*])\s+(.+)$/);
        if (bulletMatch) {
            let bContent = escapeHtml(bulletMatch[1]).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
            htmlParts.push(`<div style="display:flex; gap:8px; margin:6px 0;"><span style="color:#a3e635; font-weight:700;">•</span><div>${bContent}</div></div>`);
            continue;
        }

        // Нумерованные пункты (1. ...)
        const numMatch = line.match(/^(\d+[\.\)])\s+(.+)$/);
        if (numMatch) {
            let nContent = escapeHtml(numMatch[2]).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
            htmlParts.push(`<div style="display:flex; gap:8px; margin:6px 0;"><span style="color:#38bdf8; font-weight:700;">${escapeHtml(numMatch[1])}</span><div>${nContent}</div></div>`);
            continue;
        }

        // Обычный абзац или подзаголовок (если вся строка в **...:**)
        let pHtml = escapeHtml(line).replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
        if (/^<strong>[^<]+:<\/strong>$/.test(pHtml)) {
            htmlParts.push(`<h4>${pHtml.replace(/<\/?strong>/g, "")}</h4>`);
        } else {
            htmlParts.push(`<p>${pHtml}</p>`);
        }
    }

    return htmlParts.join("");
}

function appendAiChat(sender, text, color = "#e2e8f0") {
    const box = document.getElementById("aiCoachBox");
    const div = document.createElement("div");

    if (sender === "Ты") {
        const rawUser = String(text || "").replace(/\r/g, "").trim();
        const cleanUser = escapeHtml(rawUser).replace(/\n/g, "<br>");
        const isLong = rawUser.length > 75 || rawUser.includes("\n");

        div.className = "user-msg-wrap" + (isLong ? " collapsed" : "");
        div.innerHTML = `
            <div class="user-msg-text">${cleanUser}</div>
            <button type="button" class="user-msg-toggle" title="Свернуть / развернуть">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="6 9 12 15 18 9"></polyline>
                </svg>
            </button>
        `;

        const toggleBtn = div.querySelector(".user-msg-toggle");
        if (toggleBtn) {
            if (!isLong) {
                toggleBtn.style.opacity = "0.45";
            }
            div.addEventListener("click", () => {
                div.classList.toggle("collapsed");
            });
        }
    } else if (sender === "Система") {
        div.className = "coach-msg coach-msg-sys";
        div.style.cssText = `margin: 10px 0; padding: 8px 12px; border-radius: 10px; background: rgba(15, 23, 42, 0.75); border: 1px solid rgba(56, 189, 248, 0.25); font-size: 13px; color: ${color};`;
        div.textContent = String(text || "").trim();
    } else {
        div.className = "ai-msg-wrap";
        div.innerHTML = formatCoachRichText(text);
    }

    box.appendChild(div);
    if (sender === "Ты" || sender === "Система") {
        box.scrollTop = box.scrollHeight;
    } else {
        box.scrollTop = Math.max(0, div.offsetTop - 10);
    }
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

function speakText(text) {
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
    speakFallbackBrowser(cleanSpeech);
}


let _lastCoachSentText = "";
let _lastCoachSentAt = 0;
async function askAiCoach(customText = null) {
    if (isSendingCoach) return;
    const inp = document.getElementById("aiCoachInput");
    const text = (customText !== null ? String(customText) : (inp ? inp.value : "")).trim();
    if (!text) return;
    const now = Date.now();
    if (text === _lastCoachSentText && (now - _lastCoachSentAt) < 5000) return;
    _lastCoachSentText = text;
    _lastCoachSentAt = now;

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

                } else if (d.mode === "workout_logged" && Array.isArray(d.suggested_plan)) {
            const logDate = d.target_date || document.getElementById("workoutDateInput")?.value || new Date().toLocaleDateString("sv-SE");
            for (const item of d.suggested_plan) {
                await fetch("/workouts/", {
                    method: "POST",
                    headers: authHeaders(),
                    body: JSON.stringify({
                        exercise_name: item.exercise_name || item.name,
                        sets: parseInt(item.sets) || 3,
                        reps: parseInt(item.reps) || 12,
                        weight: parseFloat(item.weight) || 0,
                        workout_date: logDate
                    })
                });
            }
            const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
            if (schedMap[logDate]) {
                delete schedMap[logDate];
                localStorage.setItem("wv_scheduled_plans", JSON.stringify(schedMap));
            }
            selectedDateStr = logDate;
            await Promise.all([loadSupport(), loadNutrition(), loadAnalytics()]);
            appendAiChat("Система", `✓ Тренировка (${d.suggested_plan.length} поз.) сохранена в блокнот и календарь за ${logDate}.`, "#34d399");
            if (navigator.vibrate) navigator.vibrate([40, 40, 40]);

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
let voiceIgnoreResults = false;

function stopVoiceManual(shouldSend = false) {
    isVoiceIntentionalActive = false;
    voiceIgnoreResults = !shouldSend;
    if (voiceSilenceTimer) {
        clearTimeout(voiceSilenceTimer);
        voiceSilenceTimer = null;
    }
    if (activeRecognition) {
        try {
            activeRecognition.onresult = null;
            activeRecognition.onerror = null;
            activeRecognition.onend = null;
            activeRecognition.abort();
        } catch (e) {}
        activeRecognition = null;
    }

    stopVoiceVisualizer();
    const input = document.getElementById("aiCoachInput");
    if (input) {
        input.placeholder = "Спроси тренера или надиктуй подход...";
        if (!shouldSend) {
            input.blur();
            input.value = "";
        }
    }
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
    voiceIgnoreResults = false;
    let committedText = input.value.trim();

    if (capsule) capsule.classList.add("listening");
    if (btn) btn.classList.add("active");
    input.placeholder = "Слушаю... говори спокойно, нажми ↑ для отправки";
    voiceEnergy = 0.45;
    startVoiceVisualizer();

    const resetSilenceTimer = () => {
        if (voiceSilenceTimer) clearTimeout(voiceSilenceTimer);
        voiceSilenceTimer = setTimeout(() => {
            if (!isVoiceIntentionalActive) return;
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
            if (!isVoiceIntentionalActive || voiceIgnoreResults || isSendingCoach) return;
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
            if (isVoiceIntentionalActive && !isSendingCoach && !voiceIgnoreResults) {
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
    const res = await fetch("/coach/support?tired_after_shift=false", { headers: authHeaders() });
    if (res.status === 401) return logout();
    const d = await res.json();
        const nameEl = document.getElementById("profileModalName");
    if (nameEl) nameEl.textContent = d.athlete;
    const initEl = document.getElementById("headerAvatarInitials");
    if (initEl && !localStorage.getItem("wv_avatar_data")) {
        initEl.textContent = (d.athlete || "АС").slice(0, 2).toUpperCase();
    }

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

    const goalEl = document.getElementById("goalLabel");
    if (goalEl) goalEl.textContent = d.goal_ru;

        const targetWeightVal = parseFloat(_wvProfile.targetWeight) || 70.0;
    const mainGoalEl = document.getElementById("mainGoalTitle");
    if (mainGoalEl) mainGoalEl.textContent = d.goal_ru;
    const mainGoalSubEl = document.getElementById("mainGoalSub");
    if (mainGoalSubEl) mainGoalSubEl.textContent = `Цель: ${targetWeightVal.toFixed(1)} кг`;

    const heroBurnEl = document.getElementById("heroDailyBurnVal");
    if (heroBurnEl) heroBurnEl.textContent = d.tdee_maintenance_kcal + " ккал";
    const heroTargetEl = document.getElementById("heroKcalTargetSub");
    if (heroTargetEl) heroTargetEl.textContent = `Цель: ${d.daily_target.calories_kcal} ккал/день`;


    const heroCorrEl = document.getElementById("heroCorridorRange");
    if (heroCorrEl) heroCorrEl.textContent = d.green_corridor.safe_range_kg;
    const heroWeightEl = document.getElementById("heroCurrentWeightInfo");
    if (heroWeightEl) heroWeightEl.textContent = "Сейчас: " + d.green_corridor.current_weight_kg + " кг";

    document.getElementById("macrosInfo").textContent = `${d.daily_target.protein_g}г / ${d.daily_target.fats_g}г / ${d.daily_target.carbs_g}г`;
    document.getElementById("kcalShiftInfo").textContent = `Смена: ${d.schedule_adaptation.work_day_kcal} • Отдых: ${d.schedule_adaptation.rest_day_kcal}`;
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
        const weekAgo = new Date();
        weekAgo.setDate(weekAgo.getDate() - 7);
        const uniqueDays7 = new Set(
            allWorkoutsCache
                .filter(w => w.created_at && new Date(w.created_at) >= weekAgo)
                .map(w => new Date(w.created_at).toLocaleDateString("sv-SE"))
        );
        const streakEl = document.getElementById("weeklyStreakVal");
        if (streakEl) streakEl.textContent = `${uniqueDays7.size} / 4`;

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


function cleanupExpiredScheduledPlans() {
    const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    let changed = false;
    Object.keys(schedMap).forEach(dStr => {
        if (Math.floor((today - new Date(dStr + "T00:00:00")) / 86400000) > 7) { delete schedMap[dStr]; changed = true; }
    });
    if (changed) localStorage.setItem("wv_scheduled_plans", JSON.stringify(schedMap));
    return schedMap;
}

function moveScheduledPlan(fromDateStr, toDateStr) {
    if (!toDateStr || fromDateStr === toDateStr) return;
    const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
    const items = schedMap[fromDateStr];
    if (!Array.isArray(items) || items.length === 0) return;
    delete schedMap[fromDateStr];
    schedMap[toDateStr] = items;
    localStorage.setItem("wv_scheduled_plans", JSON.stringify(schedMap));
    selectedDateStr = toDateStr;
    renderCalendar();
    renderCalDayDetails(toDateStr);
}

function deleteScheduledPlan(dateStr) {
    const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
    delete schedMap[dateStr];
    localStorage.setItem("wv_scheduled_plans", JSON.stringify(schedMap));
    renderCalendar();
    renderCalDayDetails(dateStr);
}

const _origRenderCalendar = renderCalendar;
renderCalendar = function() {
    cleanupExpiredScheduledPlans();
    _origRenderCalendar();
    const todayStr = new Date().toLocaleDateString("sv-SE");
    const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
    const grid = document.getElementById("calendarGrid");
    if (!grid) return;
    grid.querySelectorAll("button").forEach(btn => {
        const m = (btn.getAttribute("onclick") || "").match(/selectCalDay\('(\d{4}-\d{2}-\d{2})'\)/);
        if (!m) return;
        const dStr = m[1];
        const hasWorkout = allWorkoutsCache.some(w => w.created_at && new Date(w.created_at).toLocaleDateString("sv-SE") === dStr);
        if (!hasWorkout && dStr < todayStr && Array.isArray(schedMap[dStr]) && schedMap[dStr].length > 0) {
            btn.style.background = "rgba(148, 163, 184, 0.16)";
            btn.style.border = dStr === selectedDateStr ? "2px solid #cbd5e1" : "1px solid rgba(148, 163, 184, 0.45)";
            btn.style.color = "#cbd5e1";
            const dot = btn.querySelector("div:last-child");
            if (dot) dot.style.background = "#94a3b8";
        }
    });
};

const _origRenderCalDayDetails = renderCalDayDetails;
renderCalDayDetails = function(dateStr) {
    const todayStr = new Date().toLocaleDateString("sv-SE");
    const schedMap = cleanupExpiredScheduledPlans();
    const hasWorkout = allWorkoutsCache.some(w => w.created_at && new Date(w.created_at).toLocaleDateString("sv-SE") === dateStr);
    if (!hasWorkout && dateStr < todayStr && Array.isArray(schedMap[dateStr]) && schedMap[dateStr].length > 0) {
        const box = document.getElementById("calDayDetails");
        if (!box) return;
        const pts = dateStr.split("-");
        const niceDate = pts[2] + "." + pts[1] + "." + pts[0];
        let planHtml = "";
        schedMap[dateStr].forEach((p, idx) => {
            planHtml += `<div style="display:flex; justify-content:space-between; padding:5px 0; border-bottom:1px solid #1e293b; font-size:12px;"><span style="color:#cbd5e1;"><strong>${idx + 1}. ${p.name}</strong></span><span style="color:#94a3b8;">${p.sets || 3}\u00d7${p.reps || 12} \u2022 ${p.weight || 0} \u043a\u0433</span></div>`;
        });
        box.innerHTML = `<div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;"><strong style="color:#cbd5e1;">\u041f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043d\u044b\u0439 \u043f\u043b\u0430\u043d \u043e\u0442 ${niceDate}</strong><span class="badge" style="background:rgba(148,163,184,0.2); color:#cbd5e1;">\u041f\u0440\u043e\u043f\u0443\u0449\u0435\u043d\u043e</span></div>` + planHtml + `<div style="display:flex; flex-wrap:wrap; gap:8px; margin-top:10px; align-items:center;"><input type="date" id="rescheduleDateInp" value="${todayStr}" min="${todayStr}" style="margin:0; padding:7px 10px; font-size:12px; flex:1; min-width:130px;"><button onclick="moveScheduledPlan('${dateStr}', document.getElementById('rescheduleDateInp').value)" class="btn-primary" style="margin:0; padding:8px 12px; font-size:12px; width:auto; background:linear-gradient(135deg,#9333ea,#6366f1);">\u041f\u0435\u0440\u0435\u043d\u0435\u0441\u0442\u0438</button><button onclick="deleteScheduledPlan('${dateStr}')" class="icon-btn" style="padding:8px 12px; font-size:12px; color:#fb7185; border-color:#fb7185;">\u0423\u0434\u0430\u043b\u0438\u0442\u044c</button></div>`;
        return;
    }
    _origRenderCalDayDetails(dateStr);
};

const GIF_EXERCISE_LIBRARY = [
    { name: "\u0416\u0438\u043c \u0448\u0442\u0430\u043d\u0433\u0438 \u043b\u0451\u0436\u0430", group: "\u0413\u0440\u0443\u0434\u044c", met: 6.0, gif: "https://tenor.com", tip: "\u0421\u0432\u0435\u0434\u0438 \u043b\u043e\u043f\u0430\u0442\u043a\u0438, \u043e\u043f\u0443\u0441\u043a\u0430\u0439 \u0433\u0440\u0438\u0444 \u043a \u043d\u0438\u0437\u0443 \u0433\u0440\u0443\u0434\u0438." },
    { name: "\u0416\u0438\u043c \u0433\u0430\u043d\u0442\u0435\u043b\u0435\u0439 \u043d\u0430 \u043d\u0430\u043a\u043b\u043e\u043d\u043d\u043e\u0439 \u0441\u043a\u0430\u043c\u044c\u0435 (30\u00b0)", group: "\u0413\u0440\u0443\u0434\u044c", met: 5.5, gif: "https://tenor.com", tip: "\u041b\u043e\u043a\u0442\u0438 \u043f\u043e\u0434 \u0443\u0433\u043b\u043e\u043c 45\u00b0 \u043a \u043a\u043e\u0440\u043f\u0443\u0441\u0443." },
    { name: "\u041f\u043e\u0434\u0442\u044f\u0433\u0438\u0432\u0430\u043d\u0438\u044f \u0448\u0438\u0440\u043e\u043a\u0438\u043c \u0445\u0432\u0430\u0442\u043e\u043c", group: "\u0421\u043f\u0438\u043d\u0430", met: 6.0, gif: "https://tenor.com", tip: "\u0422\u044f\u043d\u0438\u0441\u044c \u0432\u0435\u0440\u0445\u043e\u043c \u0433\u0440\u0443\u0434\u0438 \u043a \u043f\u0435\u0440\u0435\u043a\u043b\u0430\u0434\u0438\u043d\u0435." },
    { name: "\u0422\u044f\u0433\u0430 \u0432\u0435\u0440\u0445\u043d\u0435\u0433\u043e \u0431\u043b\u043e\u043a\u0430 \u043a \u0433\u0440\u0443\u0434\u0438", group: "\u0421\u043f\u0438\u043d\u0430", met: 5.0, gif: "https://tenor.com", tip: "\u0422\u044f\u043d\u0438 \u043b\u043e\u043a\u0442\u044f\u043c\u0438 \u0432\u043d\u0438\u0437, \u0441\u0432\u043e\u0434\u044f \u043b\u043e\u043f\u0430\u0442\u043a\u0438." },
    { name: "\u041f\u0440\u0438\u0441\u0435\u0434\u0430\u043d\u0438\u044f \u0441\u043e \u0448\u0442\u0430\u043d\u0433\u043e\u0439", group: "\u041d\u043e\u0433\u0438", met: 6.5, gif: "https://tenor.com", tip: "\u041a\u043e\u043b\u0435\u043d\u0438 \u043f\u043e \u043b\u0438\u043d\u0438\u0438 \u043d\u043e\u0441\u043a\u043e\u0432, \u0441\u043f\u0438\u043d\u0430 \u0440\u043e\u0432\u043d\u0430\u044f." },
    { name: "\u041c\u0430\u0445\u0438 \u0433\u0430\u043d\u0442\u0435\u043b\u044f\u043c\u0438 \u0432 \u0441\u0442\u043e\u0440\u043e\u043d\u044b (\u0441\u0440\u0435\u0434\u043d\u044f\u044f \u0434\u0435\u043b\u044c\u0442\u0430)", group: "\u0414\u0435\u043b\u044c\u0442\u044b", met: 4.5, gif: "https://tenor.com", tip: "\u041f\u043e\u0434\u043d\u0438\u043c\u0430\u0439 \u0447\u0435\u0440\u0435\u0437 \u043b\u043e\u043a\u0442\u0438 \u0434\u043e \u0443\u0440\u043e\u0432\u043d\u044f \u043f\u043b\u0435\u0447." },
    { name: "\u0416\u0438\u043c \u0433\u0430\u043d\u0442\u0435\u043b\u0435\u0439 \u0441\u0438\u0434\u044f \u043d\u0430 \u043d\u0430\u043a\u043b\u043e\u043d\u043d\u043e\u0439 \u0441\u043a\u0430\u043c\u044c\u0435 (60\u201375\u00b0)", group: "\u0414\u0435\u043b\u044c\u0442\u044b", met: 5.5, gif: "https://tenor.com", tip: "\u041f\u043e\u044f\u0441\u043d\u0438\u0446\u0430 \u043f\u0440\u0438\u0436\u0430\u0442\u0430, \u0431\u0435\u0437 \u0443\u0434\u0430\u0440\u0430 \u0432\u0432\u0435\u0440\u0445\u0443." },
    { name: "\u041f\u043e\u0434\u044a\u0451\u043c \u0433\u0430\u043d\u0442\u0435\u043b\u0435\u0439 \u043d\u0430 \u0431\u0438\u0446\u0435\u043f\u0441 \u0441\u0442\u043e\u044f", group: "\u0420\u0443\u043a\u0438", met: 4.0, gif: "https://tenor.com", tip: "\u0424\u0438\u043a\u0441\u0438\u0440\u0443\u0439 \u043b\u043e\u043a\u0442\u0438 \u0443 \u043a\u043e\u0440\u043f\u0443\u0441\u0430." },
    { name: "\u0421\u043a\u0440\u0443\u0447\u0438\u0432\u0430\u043d\u0438\u044f \u043d\u0430 \u043f\u0440\u0435\u0441\u0441 \u043d\u0430 \u043f\u043e\u043b\u0443", group: "\u041f\u0440\u0435\u0441\u0441", met: 3.8, gif: "https://tenor.com", tip: "\u041e\u0442\u0440\u044b\u0432\u0430\u0439 \u043b\u043e\u043f\u0430\u0442\u043a\u0438 \u043d\u0430 \u0432\u044b\u0434\u043e\u0445\u0435." }
];

let currentGifGroup = "\u0412\u0441\u0435";
function renderGifLibrary(group) {
    if (group) currentGifGroup = group;
    const tabsEl = document.getElementById("gifCategoryTabs");
    const gridEl = document.getElementById("exerciseGifLibrary");
    if (!tabsEl || !gridEl) return;
    const groups = ["\u0412\u0441\u0435", "\u0413\u0440\u0443\u0434\u044c", "\u0421\u043f\u0438\u043d\u0430", "\u041d\u043e\u0433\u0438", "\u0414\u0435\u043b\u044c\u0442\u044b", "\u0420\u0443\u043a\u0438", "\u041f\u0440\u0435\u0441\u0441"];
    tabsEl.innerHTML = groups.map(g => `<button class="chip-btn" style="${g === currentGifGroup ? 'border-color:#38bdf8; color:#38bdf8; background:rgba(56,189,248,0.15);' : ''}" onclick="renderGifLibrary('${g}')">${g}</button>`).join("");
    const list = currentGifGroup === "\u0412\u0441\u0435" ? GIF_EXERCISE_LIBRARY : GIF_EXERCISE_LIBRARY.filter(item => item.group === currentGifGroup);
    gridEl.innerHTML = "";
    list.forEach(item => {
        const safeName = item.name.replace(/'/g, "\\'");
        const card = document.createElement("div");
        card.style.cssText = "background:#0f172a; border:1px solid #1e293b; border-radius:12px; padding:10px; display:flex; flex-direction:column; justify-content:space-between; gap:8px;";
        card.innerHTML = `<div><div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;"><span class="badge" style="font-size:10px; background:rgba(56,189,248,0.15); color:#38bdf8;">${item.group}</span><span style="font-size:10px; color:#fbbf24;">MET ${item.met}</span></div><img src="${item.gif}" alt="${item.name}" loading="lazy" onerror="this.style.display='none'" style="width:100%; height:110px; object-fit:cover; border-radius:8px; background:#1e293b; margin-bottom:6px;"><div style="font-size:13px; font-weight:700; color:#e2e8f0; margin-bottom:4px;">${item.name}</div><div style="font-size:11px; color:#94a3b8; line-height:1.35;">${item.tip}</div></div><button class="btn-primary" style="margin:0; padding:7px; font-size:12px;" onclick="addToPlan('${safeName}')">\uff0b \u0412 \u043f\u043b\u0430\u043d</button>`;
        gridEl.appendChild(card);
    });
}
if (typeof renderGifLibrary === "function") renderGifLibrary();


// === SHARP ATHLETIC EMBLEM & STRICT MISSED-DAY GRAY ===
(function() {
          const sharpSvg = `<svg width="280" height="310" viewBox="0 0 280 310" fill="none" xmlns="http://w3.org" style="opacity:0.26; filter:drop-shadow(0 0 32px rgba(168,85,247,0.45));">
      <defs>
        <linearGradient id="wvShieldGrad" x1="25" y1="15" x2="255" y2="295" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#c084fc"/>
          <stop offset="52%" stop-color="#8b5cf6"/>
          <stop offset="100%" stop-color="#a3e635"/>
        </linearGradient>
        <linearGradient id="wvCoreFill" x1="140" y1="20" x2="140" y2="290" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#a855f7" stop-opacity="0.24"/>
          <stop offset="65%" stop-color="#0f172a" stop-opacity="0.12"/>
          <stop offset="100%" stop-color="#a3e635" stop-opacity="0.18"/>
        </linearGradient>
        <linearGradient id="wvBladeGrad" x1="55" y1="85" x2="225" y2="215" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stop-color="#f8fafc"/>
          <stop offset="45%" stop-color="#c084fc"/>
          <stop offset="100%" stop-color="#a3e635"/>
        </linearGradient>
      </defs>

      <!-- Внешний рубленый титановый шестиугольный щит -->
      <path d="M140 14 L250 58 L236 196 L140 294 L44 196 L30 58 Z"
            fill="url(#wvCoreFill)" stroke="url(#wvShieldGrad)" stroke-width="3.5" stroke-linejoin="miter"/>

      <!-- Внутренняя броневая грань щита -->
      <path d="M140 28 L236 67 L224 189 L140 276 L56 189 L44 67 Z"
            stroke="url(#wvShieldGrad)" stroke-width="1.4" stroke-opacity="0.65"/>

      <!-- Верхняя корона-клинок -->
      <path d="M108 46 L140 34 L172 46 L158 54 L140 47 L122 54 Z" fill="url(#wvBladeGrad)" fill-opacity="0.85"/>

      <!-- Стилизованный силовой гриф с дисками на заднем плане -->
      <rect x="56" y="136" width="168" height="4" rx="2" fill="url(#wvShieldGrad)" fill-opacity="0.55"/>
      <rect x="64" y="122" width="6" height="32" rx="1.5" fill="url(#wvShieldGrad)" fill-opacity="0.7"/>
      <rect x="73" y="127" width="5" height="22" rx="1.5" fill="url(#wvShieldGrad)" fill-opacity="0.55"/>
      <rect x="210" y="122" width="6" height="32" rx="1.5" fill="url(#wvShieldGrad)" fill-opacity="0.7"/>
      <rect x="202" y="127" width="5" height="22" rx="1.5" fill="url(#wvShieldGrad)" fill-opacity="0.55"/>

      <!-- Агрессивная остроугольная монограмма W (крылья/клинки) -->
      <path d="M68 88 L92 88 L112 146 L140 102 L168 146 L188 88 L212 88 L176 176 L158 176 L140 142 L122 176 L104 176 Z"
            fill="url(#wvBladeGrad)" stroke="#0b0f19" stroke-width="1.5" stroke-linejoin="miter"/>

      <!-- Нижнее остриё монограммы V (наконечник копья) -->
      <path d="M104 184 L126 184 L140 222 L154 184 L176 184 L140 258 Z"
            fill="url(#wvShieldGrad)" stroke="#0b0f19" stroke-width="1.5" stroke-linejoin="miter"/>

      <!-- Клубная надпись WORKOUT VAULT -->
      <text x="140" y="271" text-anchor="middle" fill="#e2e8f0" fill-opacity="0.8"
            font-family="system-ui, -apple-system, sans-serif" font-size="9.5" font-weight="800" letter-spacing="3.2">
        WORKOUT VAULT
      </text>
    </svg>`;



    const origToggleFs = window.toggleCoachFullscreen;
    window.toggleCoachFullscreen = function() {
        if (typeof origToggleFs === "function") origToggleFs();
        const card = document.getElementById("coachCard");
        const box = document.getElementById("aiCoachBox");
        if (!card || !box) return;
        let wm = document.getElementById("coachBgWatermark");
        if (!wm) {
            wm = document.createElement("div");
            wm.id = "coachBgWatermark";
            wm.style.cssText = "position:absolute; inset:0; display:none; align-items:center; justify-content:center; pointer-events:none; z-index:0;";
            wm.innerHTML = sharpSvg;
            card.style.position = "relative";
            card.appendChild(wm);
        }
        const isFull = card.classList.contains("coach-fullscreen");
        wm.style.display = isFull ? "flex" : "none";
        box.style.background = isFull ? "rgba(15, 23, 42, 0.62)" : "#0f172a";
        box.style.position = "relative";
        box.style.zIndex = "1";
    };

    const prevRenderCal = window.renderCalendar;
    window.renderCalendar = function() {
        if (typeof prevRenderCal === "function") prevRenderCal();
        const todayStr = new Date().toLocaleDateString("sv-SE");
        const schedMap = JSON.parse(localStorage.getItem("wv_scheduled_plans") || "{}");
        const grid = document.getElementById("calendarGrid");
        if (!grid) return;
        grid.querySelectorAll("button").forEach(btn => {
            const m = (btn.getAttribute("onclick") || "").match(/selectCalDay\('(\d{4}-\d{2}-\d{2})'\)/);
            if (!m) return;
            const dStr = m[1];
            const hasWorkout = Array.isArray(allWorkoutsCache) && allWorkoutsCache.some(w => w.created_at && new Date(w.created_at).toLocaleDateString("sv-SE") === dStr);
            if (!hasWorkout && dStr < todayStr && Array.isArray(schedMap[dStr]) && schedMap[dStr].length > 0) {
                btn.style.setProperty("background", "rgba(148, 163, 184, 0.16)", "important");
                btn.style.setProperty("border", dStr === selectedDateStr ? "2px solid #cbd5e1" : "1px solid rgba(148, 163, 184, 0.45)", "important");
                btn.style.setProperty("color", "#cbd5e1", "important");
                const dot = btn.querySelector("div:last-child");
                if (dot) dot.style.setProperty("background", "#94a3b8", "important");
            }
        });
    };
})();
// === УПРАВЛЕНИЕ ЦЕЛЬЮ, АНКЕТОЙ И ПРОФИЛЕМ (v50) ===
let _wvProfile = JSON.parse(localStorage.getItem("wv_profile_v49") || '{"age":41,"height":176,"weight":67.0,"targetWeight":70.0,"activity":1.55}');
let _wvGoalState = JSON.parse(localStorage.getItem("wv_goal_state") || '{"direction":"bulk","intensity":1,"prevDirection":"bulk","targetKcal":2541}');

function _getLatestWeightValue() {
    if (typeof weightHistory !== "undefined" && Array.isArray(weightHistory) && weightHistory.length > 0) {
        const last = weightHistory[weightHistory.length - 1];
        if (last && last.weight) return parseFloat(last.weight);
    }
    return parseFloat(_wvProfile.weight) || (currentNutritionPlan?.green_corridor?.current_weight_kg) || 67.0;
}

function _calcMaintenanceTdee() {
    const w = _getLatestWeightValue();
    const h = parseFloat(_wvProfile.height) || 176;
    const age = parseInt(_wvProfile.age) || 41;
    const act = parseFloat(_wvProfile.activity) || 1.55;
    const bmr = 10 * w + 6.25 * h - 5 * age + 5;
    return Math.round(bmr * act);
}

function openProfileModal() {
    const m = document.getElementById("profileCenterModal");
    if (!m) return;
    document.getElementById("profAgeInput").value = _wvProfile.age || 41;
    document.getElementById("profHeightInput").value = _wvProfile.height || 176;
    document.getElementById("profTargetWeightInput").value = _wvProfile.targetWeight || 70.0;
    document.getElementById("profActivitySelect").value = String(_wvProfile.activity || 1.55);
    m.classList.remove("hidden");
    m.style.display = "flex";
}

function closeProfileModal() {
    const m = document.getElementById("profileCenterModal");
    if (!m) return;
    m.classList.add("hidden");
    m.style.display = "none";
}
function _syncAvatarUI() {
    const savedImg = localStorage.getItem("wv_avatar_data");
    const hdrImg = document.getElementById("headerAvatarImg");
    const hdrInit = document.getElementById("headerAvatarInitials");
    const modPrev = document.getElementById("modalAvatarPreview");
    if (savedImg) {
        if (hdrImg) { hdrImg.src = savedImg; hdrImg.classList.remove("hidden"); }
        if (hdrInit) hdrInit.classList.add("hidden");
        if (modPrev) modPrev.innerHTML = `<img src="${savedImg}" style="width:100%;height:100%;object-fit:cover;">`;
    }
}

function handleAvatarUpload(input) {
    const file = input && input.files ? input.files[0] : null;
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        localStorage.setItem("wv_avatar_data", e.target.result);
        _syncAvatarUI();
    };
    reader.readAsDataURL(file);
}

function saveProfileCenter() {
    _wvProfile.age = parseInt(document.getElementById("profAgeInput")?.value) || 41;
    _wvProfile.height = parseFloat(document.getElementById("profHeightInput")?.value) || 176;
    _wvProfile.targetWeight = parseFloat(document.getElementById("profTargetWeightInput")?.value) || 70.0;
    _wvProfile.activity = parseFloat(document.getElementById("profActivitySelect")?.value) || 1.55;
    localStorage.setItem("wv_profile_v49", JSON.stringify(_wvProfile));
    _syncGoalCardsUI();
    closeProfileModal();
}

function changeAppLanguage(lang) {
    localStorage.setItem("wv_lang", lang);
}

function openGoalModal() {
    const m = document.getElementById("goalSelectorModal");
    if (!m) return;
    const slider = document.getElementById("goalIntensitySlider");
    if (slider) slider.value = _wvGoalState.intensity || 1;
    selectGoalDirection(_wvGoalState.direction || "bulk");
    m.classList.remove("hidden");
    m.style.display = "flex";
}

function closeGoalModal() {
    const m = document.getElementById("goalSelectorModal");
    if (!m) return;
    m.classList.add("hidden");
    m.style.display = "none";
}

function selectGoalDirection(dir) {
    _wvGoalState.direction = dir;
    const map = { cut: "goalDirCutBtn", hold: "goalDirHoldBtn", bulk: "goalDirBulkBtn" };
    Object.entries(map).forEach(([k, id]) => {
        const btn = document.getElementById(id);
        if (!btn) return;
        const active = k === dir;
        btn.style.borderColor = active ? "#a855f7" : "#334155";
        btn.style.background = active ? "rgba(168,85,247,0.2)" : "#0f172a";
        btn.style.color = active ? "#f3e8ff" : "#cbd5e1";
    });
    const sliderSec = document.getElementById("goalSliderSection");
    if (sliderSec) sliderSec.style.display = dir === "hold" ? "none" : "block";
    updateGoalPreview();
}


function _computeGoalMetrics(dir, step) {
    const tdee = _calcMaintenanceTdee();
    const curW = _getLatestWeightValue();
    let kcal = tdee;
    let title = "Удержание формы";
    let badge = "Баланс (0%)";
    let note = "Стабильная энергия, восстановление и контроль качества тела.";

    if (dir === "cut") {
        const cutSteps = [
            { mult: 0.90, min: 1900, t: "Бережное похудение", b: "1. Лёгкий дефицит (-10%)", n: "Комфортное снижение веса без чувства голода и стресса для ЦНС." },
            { mult: 0.85, min: 1800, t: "Мягкая сушка", b: "2. Мягкая сушка (-15%)", n: "Оптимальный темп сжигания жира с сохранением силовых показателей." },
            { mult: 0.80, min: 1700, t: "Средняя сушка", b: "3. Средняя сушка (-20%)", n: "Выраженный рельеф. Держи 2.1 г белка/кг, клетчатку и электролиты." },
            { mult: 0.75, min: 1600, t: "Интенсивная сушка", b: "4. Интенсивная (-25%)", n: "⚠️ Повышенный дефицит. Следи за сном и самочувствием, не затягивай цикл." },
            { mult: 0.70, min: 1550, t: "Жёсткая сушка (Профи)", b: "5. Спорт-сушка (-30%)", n: "⚠️ Предельный безопасный дефицит (порог ≥ 1550 ккал/день). Только для опытных." }
        ];
        const s = cutSteps[Math.min(4, Math.max(0, step - 1))];
        kcal = Math.max(s.min, Math.round(tdee * s.mult));
        title = s.t; badge = s.b; note = s.n;
    } else if (dir === "bulk") {
        const bulkSteps = [
            { mult: 1.08, t: "Плавный набор массы", b: "1. Плавный (+8%)", n: "Качественный рост сухой мышечной массы с минимальным процентом жира." },
            { mult: 1.15, t: "Уверенный набор массы", b: "2. Средний (+15%)", n: "Активный прогресс рабочих весов и объёмов при регулярных тренировках." },
            { mult: 1.24, t: "Форсированный набор", b: "3. Сильный (+24%)", n: "Увеличенный энергетический резерв для тяжёлых базовых циклов и сменного графика." },
            { mult: 1.35, t: "Спортивный профицит", b: "4. Атлет (+35% · 3500+)", n: "Высокий калораж для атлетов с быстрым обменом веществ и большим расходом энергии." },
            { mult: 1.50, t: "Максимум (Хардгейнер)", b: "5. Профи (+50% · 4000–5500+)", n: "Экстремальный профицит для тяжёлых силовых циклов. Контролируй качество пищи и ЖКТ." }
        ];
        const s = bulkSteps[Math.min(4, Math.max(0, step - 1))];
        kcal = Math.round(tdee * s.mult);
        title = s.t; badge = s.b; note = s.n;
    }

    const prot = Math.round(curW * (dir === "cut" ? 2.15 : 2.0));
    const fat = Math.round(curW * (dir === "cut" ? 0.85 : 1.05));
    const carbs = Math.max(90, Math.round((kcal - prot * 4 - fat * 9) / 4));
    return { tdee, kcal, title, badge, note, prot, fat, carbs };
}

function updateGoalPreview() {
    const dir = _wvGoalState.direction || "bulk";
    const step = parseInt(document.getElementById("goalIntensitySlider")?.value) || 1;
    const labels = dir === "cut"
        ? ["1. Лёгкая", "2. Мягкая", "3. Средняя", "4. Сильная", "5. Профи"]
        : ["1. Плавный", "2. Средний", "3. Сильный", "4. Атлет", "5. Профи"];
    labels.forEach((txt, idx) => {
        const el = document.getElementById(`goalStep${idx + 1}Text`);
        if (el) el.textContent = txt;
    });

    const m = _computeGoalMetrics(dir, step);
    const lbl = document.getElementById("goalIntensityLabel");
    const kEl = document.getElementById("goalCalcKcalVal");
    const mEl = document.getElementById("goalCalcMacrosVal");
    const nEl = document.getElementById("goalSafetyNote");
    if (lbl) lbl.textContent = m.badge;
    if (kEl) kEl.textContent = `${m.kcal} ккал`;
    if (mEl) mEl.textContent = `Белки: ${m.prot} г · Жиры: ${m.fat} г · Углеводы: ${m.carbs} г`;
    if (nEl) nEl.textContent = m.note;

    const hint = document.getElementById("goalTransitionHint");
    if (hint) {
        if (dir === "cut" && step >= 3) {
            hint.innerHTML = "🧬 <strong>Научный совет:</strong> если вы ранее не проходили жёсткую сушку, лучше выбрать <strong>1–2 мягкую ступень (-10…-15%)</strong> и растянуть путь на дольше. При резком дефиците подскакивает гормон голода <strong>грелин</strong> и падает <strong>лептин</strong> — плавный темп защищает от срывов и сохраняет мышцы.";
            hint.classList.remove("hidden");
        } else if (dir === "bulk" && step >= 4) {
            hint.innerHTML = "⚡ <strong>Совет по профициту:</strong> режимы <strong>4–5 (3500–5500+ ккал)</strong> рассчитаны на высокий расход энергии и тяжёлые тренировки. Если прирост веса превышает +0.5 кг в неделю, снизь ступень на 1 шаг, чтобы не набирать лишний жир.";
            hint.classList.remove("hidden");
        } else if (_wvGoalState.prevDirection === "cut" && dir === "bulk") {
            hint.textContent = "💡 Переход после сушки: начни с 1-й ступени (+8%) на 10–14 дней, чтобы избежать резкого отката воды.";
            hint.classList.remove("hidden");
        } else {
            hint.classList.add("hidden");
        }
    }
}


function saveGoalSettings() {
    const dir = _wvGoalState.direction || "bulk";
    const step = parseInt(document.getElementById("goalIntensitySlider")?.value) || 1;
    const m = _computeGoalMetrics(dir, step);
    _wvGoalState = { direction: dir, intensity: step, prevDirection: dir, targetKcal: m.kcal };
    localStorage.setItem("wv_goal_state", JSON.stringify(_wvGoalState));
    _syncGoalCardsUI();
    closeGoalModal();
    renderWeightTerminal();
}

function _syncGoalCardsUI() {
    const dir = _wvGoalState.direction || "bulk";
    const step = _wvGoalState.intensity || 1;
    const m = _computeGoalMetrics(dir, step);
    const curW = _getLatestWeightValue();
    const targetW = parseFloat(_wvProfile.targetWeight) || 70.0;
    const fc = _calcPhysiologyForecast(curW, targetW, dir, m.kcal, m.tdee);

    const tEl = document.getElementById("mainGoalTitle");
    const sEl = document.getElementById("mainGoalSub");
    const bEl = document.getElementById("heroDailyBurnVal");
    const ktEl = document.getElementById("heroKcalTargetSub");
    const rateEl = document.getElementById("heroWeeklyRateSub");
    const macEl = document.getElementById("macrosInfo");
    const gLbl = document.getElementById("goalLabel");
    if (tEl) tEl.textContent = m.title;
    if (sEl) sEl.textContent = `Цель: ${targetW.toFixed(1)} кг`;
    if (bEl) bEl.textContent = `${m.tdee} ккал`;
    if (ktEl) ktEl.textContent = `Цель: ${m.kcal} ккал/день`;
    if (rateEl) {
        rateEl.textContent = fc.weeklyRate !== 0
            ? `Темп: ${fc.weeklyRate > 0 ? "+" : ""}${fc.weeklyRate} кг/нед`
            : "Темп: 0.0 кг/нед (баланс)";
    }
    if (macEl) macEl.textContent = `${m.prot}г / ${m.fat}г / ${m.carbs}г`;
    if (gLbl) gLbl.textContent = m.title;
}



// === БИРЖЕВОЙ ТЕРМИНАЛ «ЗЕЛЁНЫЙ КОРИДОР» (НЕОН WORKOUT VAULT + МОДЕЛЬ ХОЛЛА) ===
let _wtDays = 14;
let _wtChartType = "candles";
let _wtViewMode = "stage";

function openWeightModal() {
    const m = document.getElementById("weightTerminalModal");
    if (!m) return;
    m.classList.remove("hidden");
    m.style.display = "flex";
    setTimeout(renderWeightTerminal, 50);
}

function closeWeightModal() {
    const m = document.getElementById("weightTerminalModal");
    if (!m) return;
    m.classList.add("hidden");
    m.style.display = "none";
}

function toggleWeightChartType() {
    _wtChartType = _wtChartType === "candles" ? "line" : "candles";
    const btn = document.getElementById("wtChartTypeBtn");
    if (btn) btn.textContent = _wtChartType === "candles" ? "🕯 Свечи" : "📈 Линия";
    renderWeightTerminal();
}

function setWeightViewMode(mode) {
    _wtViewMode = mode;
    const sBtn = document.getElementById("wtModeStageBtn");
    const gBtn = document.getElementById("wtModeGoalBtn");
    if (sBtn && gBtn) {
        sBtn.style.background = mode === "stage" ? "#1e293b" : "transparent";
        sBtn.style.color = mode === "stage" ? "#00ff88" : "#94a3b8";
        sBtn.style.border = mode === "stage" ? "1px solid rgba(0,255,136,0.45)" : "none";
        gBtn.style.background = mode === "goal" ? "#1e293b" : "transparent";
        gBtn.style.color = mode === "goal" ? "#e879f9" : "#94a3b8";
        gBtn.style.border = mode === "goal" ? "1px solid rgba(217,70,239,0.5)" : "none";
    }
    if (mode === "goal" && _wtDays < 90) setWeightTimeframe(180);
    else renderWeightTerminal();
}

function setWeightTimeframe(days) {
    _wtDays = days;
    document.querySelectorAll(".wt-tf-btn").forEach(b => {
        const active = parseInt(b.dataset.days) === days;
        b.style.borderColor = active ? "#00ff88" : "#334155";
        b.style.color = active ? "#00ff88" : "#94a3b8";
    });
    renderWeightTerminal();
}

function _calcPhysiologyForecast(curW, targetW, dir, targetKcal, tdee) {
    const deltaW = targetW - curW;
    const dailyBalance = targetKcal - tdee;
    // Научная плотность ткани: ~6000 ккал/кг для качественной мышечной массы, ~7700 ккал/кг для жировой
    const kcalPerKg = deltaW >= 0 ? 6000 : 7700;
    const safeWeeklyMax = deltaW >= 0 ? curW * 0.0045 : curW * 0.0075;
    let rawWeekly = Math.abs(dailyBalance * 7) / kcalPerKg;
    if (Math.abs(deltaW) < 0.1 || dir === "hold") return { days: 0, weeks: 0, etaDate: "Цель достигнута", weeklyRate: 0 };
    if (rawWeekly < 0.08) rawWeekly = Math.min(safeWeeklyMax, 0.22);
    const effectiveWeekly = Math.min(rawWeekly, safeWeeklyMax);
    // Учёт метаболической адаптации (коэффициент замедления 1.12 по модели Холла)
    const weeks = Math.max(1, Math.round((Math.abs(deltaW) / effectiveWeekly) * 1.12));
    const days = weeks * 7;
    const eta = new Date();
    eta.setDate(eta.getDate() + days);
    const etaStr = eta.toLocaleDateString("ru-RU", { day: "numeric", month: "short", year: "numeric" });
    return { days, weeks, etaDate: etaStr, weeklyRate: Number((effectiveWeekly * Math.sign(deltaW)).toFixed(2)) };
}
function _getWeightLogSeries() {
    let logs = JSON.parse(localStorage.getItem("wv_weight_logs_v1") || "[]");
    if (!Array.isArray(logs)) logs = [];
    if (logs.length === 0) {
        const curW = _getLatestWeightValue();
        const seed = [
            { date: new Date(Date.now() - 6 * 86400000).toLocaleDateString("sv-SE"), open: 66.8, high: 67.2, low: 66.7, close: 67.0 },
            { date: new Date(Date.now() - 4 * 86400000).toLocaleDateString("sv-SE"), open: 67.0, high: 67.5, low: 66.9, close: 67.3 },
            { date: new Date(Date.now() - 2 * 86400000).toLocaleDateString("sv-SE"), open: 67.3, high: 67.6, low: 67.1, close: 67.2 },
            { date: new Date().toLocaleDateString("sv-SE"), open: 67.2, high: Math.max(67.2, curW), low: curW, close: curW }
        ];
        localStorage.setItem("wv_weight_logs_v1", JSON.stringify(seed));
        return seed;
    }
    return logs;
}

function _recordWeightBar(newW) {
    const todayIso = new Date().toLocaleDateString("sv-SE");
    const logs = _getWeightLogSeries();
    const last = logs[logs.length - 1];
    if (last && last.date === todayIso) {
        last.high = Number(Math.max(last.high, newW).toFixed(2));
        last.low = Number(Math.min(last.low, newW).toFixed(2));
        last.close = Number(newW.toFixed(2));
    } else {
        const prevClose = last ? last.close : newW;
        logs.push({
            date: todayIso,
            open: Number(prevClose.toFixed(2)),
            high: Number(Math.max(prevClose, newW).toFixed(2)),
            low: Number(Math.min(prevClose, newW).toFixed(2)),
            close: Number(newW.toFixed(2))
        });
    }
    localStorage.setItem("wv_weight_logs_v1", JSON.stringify(logs));
    return logs;
}

function _generateMarketCandles(curW, targetW, dir, forecast) {
    const isGoal = _wtViewMode === "goal";
    const logs = _getWeightLogSeries();
    const workoutDays = new Set((allWorkoutsCache || []).map(w => w.created_at ? new Date(w.created_at).toLocaleDateString("sv-SE") : ""));
    const candles = [];

    // 1. Замороженная история реальных свечей (прошлое не перерисовывается!)
    logs.forEach(item => {
        const vol = Number((0.4 + Math.abs(item.close - item.open) * 2.4 + (workoutDays.has(item.date) ? 0.45 : 0)).toFixed(2));
        candles.push({
            open: item.open,
            high: item.high,
            low: item.low,
            close: item.close,
            isFuture: false,
            date: new Date(item.date + "T12:00:00"),
            hasTrain: workoutDays.has(item.date),
            vol
        });
    });

    // 2. Будущая траектория к цели (только в режиме «Путь до цели»)
    if (isGoal) {
        const futureBars = 24;
        let price = curW;
        for (let i = 0; i < futureBars; i++) {
            const fwdRatio = (i + 1) / futureBars;
            const barDate = new Date();
            barDate.setDate(barDate.getDate() + Math.round(fwdRatio * Math.max(30, forecast.days)));
            const open = price;
            const wave = Math.sin(i * 0.65) * 0.09;
            const drift = ((targetW - curW) / futureBars) * (1 - 0.15 * fwdRatio);
            const close = Number((open + drift + wave).toFixed(2));
            const high = Number((Math.max(open, close) + 0.08).toFixed(2));
            const low = Number((Math.min(open, close) - 0.08).toFixed(2));
            candles.push({ open, high, low, close, isFuture: true, date: barDate, hasTrain: false, vol: 0.45 });
            price = close;
        }
    }
    return candles;
}

function renderWeightTerminal() {
    const canvas = document.getElementById("weightTerminalCanvas");
    const wrap = document.getElementById("wtCanvasWrap");
    if (!canvas || !wrap) return;
    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    const W = Math.max(320, wrap.clientWidth || window.innerWidth);
    const H = Math.max(280, wrap.clientHeight || 380);
    canvas.width = W * dpr;
    canvas.height = H * dpr;
    ctx.scale(dpr, dpr);

    const curW = _getLatestWeightValue();
    const targetW = parseFloat(_wvProfile.targetWeight) || 70.0;
    const dir = _wvGoalState.direction || "bulk";
    const metrics = _computeGoalMetrics(dir, _wvGoalState.intensity || 1);
    const forecast = _calcPhysiologyForecast(curW, targetW, dir, metrics.kcal, metrics.tdee);
    const logs = _getWeightLogSeries();

    // Динамический коридор от точки пробоя (+0.4..0.5 кг для набора, -0.5 кг для сушки)
    const bandWidth = (_wvProfile.knownMaxW && _wvProfile.knownMinW && _wvProfile.knownMaxW > _wvProfile.knownMinW)
        ? Math.min(1.2, Math.max(0.4, Number((_wvProfile.knownMaxW - _wvProfile.knownMinW).toFixed(2))))
        : 0.5;
    const support = dir === "cut" ? Number((curW - bandWidth).toFixed(1)) : Number(curW.toFixed(1));
    const resistance = Number((support + bandWidth).toFixed(1));

    const prevClose = logs.length >= 2 ? logs[logs.length - 2].close : curW;
    const isBreakoutDown = curW < prevClose - 0.25;
    const isBreakoutUp = curW > prevClose + 0.25;
    const isCalibrating = logs.length < 7 && !(_wvProfile.knownMinW && _wvProfile.knownMaxW);

    const badgeEl = document.getElementById("wtBreakoutBadge");
    if (badgeEl) {
        if (isBreakoutDown) {
            badgeEl.textContent = `ПРОБОЙ ВНИЗ · ПОДДЕРЖКА ${support.toFixed(1)}`;
            badgeEl.style.background = "rgba(217,70,239,0.24)";
            badgeEl.style.color = "#f5d0fe";
        } else if (isBreakoutUp) {
            badgeEl.textContent = `ПРОБОЙ ВВЕРХ ⚡`;
            badgeEl.style.background = "rgba(0,255,136,0.22)";
            badgeEl.style.color = "#00ff88";
        } else if (isCalibrating) {
            badgeEl.textContent = `КАЛИБРОВКА ${logs.length}/7 ДН.`;
            badgeEl.style.background = "rgba(56,189,248,0.18)";
            badgeEl.style.color = "#7dd3fc";
        } else {
            badgeEl.textContent = `КОРИДОР ${support.toFixed(1)}–${resistance.toFixed(1)}`;
            badgeEl.style.background = "rgba(0,255,136,0.14)";
            badgeEl.style.color = "#00ff88";
        }
    }
    const tickerEl = document.getElementById("wtTickerLine");
    const deltaKg = (curW - prevClose).toFixed(2);
    if (tickerEl) tickerEl.textContent = `${curW.toFixed(2)} кг (${deltaKg >= 0 ? "+" : ""}${deltaKg} кг) · Коридор: ${support.toFixed(1)}–${resistance.toFixed(1)} кг`;

    const candles = _generateMarketCandles(curW, targetW, dir, forecast);
    const allLows = candles.map(c => c.low);
    const allHighs = candles.map(c => c.high);
    const minVal = Math.min(...allLows, support - 0.4, _wtViewMode === "goal" ? targetW - 0.4 : support) - 0.25;
    const maxVal = Math.max(...allHighs, resistance + 0.4, targetW + 0.4) + 0.35;

    const padL = 6, padR = 52, padT = 16, padB = 26;
    const plotW = W - padL - padR;
    const plotH = H - padT - padB;
    const volH = Math.round(plotH * 0.16);
    const priceH = plotH - volH - 6;
    const toY = v => padT + ((maxVal - v) / Math.max(0.2, maxVal - minVal)) * priceH;

    ctx.fillStyle = "#07090f";
    ctx.fillRect(0, 0, W, H);


    // Сетка уровней цены справа
    const gridSteps = 6;
    ctx.font = "600 10px system-ui, sans-serif";
    for (let g = 0; g <= gridSteps; g++) {
        const val = minVal + ((maxVal - minVal) * g) / gridSteps;
        const y = toY(val);
        ctx.strokeStyle = "rgba(255, 255, 255, 0.05)";
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(padL, y);
        ctx.lineTo(W - padR, y);
        ctx.stroke();
        ctx.fillStyle = "#64748b";
        ctx.fillText(val.toFixed(1), W - padR + 6, y + 3);
    }

    // Световая зона 1: Зелёный коридор (текущая база)
    const yRes = toY(resistance), ySup = toY(support);
    ctx.fillStyle = "rgba(0, 255, 136, 0.08)";
    ctx.fillRect(padL, yRes, plotW, Math.max(4, ySup - yRes));

    // Световая зона 2: Целевой коридор (куда идём)
    const yTgtTop = toY(targetW + 0.4), yTgtBot = toY(targetW - 0.4);
    ctx.fillStyle = "rgba(217, 70, 239, 0.09)";
    ctx.fillRect(padL, yTgtTop, plotW, Math.max(4, yTgtBot - yTgtTop));

    // Пунктирные границы и шкала дат снизу
    const stepX = plotW / candles.length;
    const labelEvery = Math.max(8, Math.floor(candles.length / 5));
    candles.forEach((c, i) => {
        const x = padL + i * stepX + stepX / 2;
        if (i > 0 && i % labelEvery === 0) {
            ctx.strokeStyle = "rgba(255, 255, 255, 0.04)";
            ctx.beginPath();
            ctx.moveTo(x, padT);
            ctx.lineTo(x, H - padB);
            ctx.stroke();
            const lbl = _wtDays <= 30 && _wtViewMode === "stage"
                ? c.date.toLocaleDateString("ru-RU", { day: "2-digit", month: "short" })
                : c.date.toLocaleDateString("ru-RU", { month: "short", year: "2-digit" });
            ctx.fillStyle = "#64748b";
            ctx.fillText(lbl, x - 16, H - 8);
        }
    });

    // Гистограмма объёмов по низу и свечи
    const maxVol = Math.max(...candles.map(c => c.vol), 1);
    const bodyW = Math.max(2.5, Math.min(6.5, stepX * 0.62));
    candles.forEach((c, i) => {
        const x = padL + i * stepX + stepX / 2;
        const isUp = c.close >= c.open;
        const col = isUp ? "#00ff88" : "#d946ef";
        ctx.save();
        if (c.isFuture) ctx.globalAlpha = 0.48;

        // Объём снизу
        const vh = Math.max(3, (c.vol / maxVol) * volH);
        ctx.fillStyle = isUp ? "rgba(0, 255, 136, 0.26)" : "rgba(217, 70, 239, 0.26)";
        ctx.fillRect(x - bodyW / 2, H - padB - vh, bodyW, vh);

        if (_wtChartType === "candles") {
            ctx.strokeStyle = col;
            ctx.lineWidth = 1.1;
            ctx.beginPath();
            ctx.moveTo(x, toY(c.high));
            ctx.lineTo(x, toY(c.low));
            ctx.stroke();

            const yTop = toY(Math.max(c.open, c.close));
            const yBot = toY(Math.min(c.open, c.close));
            ctx.fillStyle = col;
            ctx.fillRect(x - bodyW / 2, yTop, bodyW, Math.max(2, yBot - yTop));
        }


        ctx.restore();
    });

    if (_wtChartType === "line") {
        ctx.strokeStyle = "#00ff88";
        ctx.lineWidth = 2;
        ctx.beginPath();
        candles.forEach((c, i) => {
            const x = padL + i * stepX + stepX / 2;
            const y = toY(c.close);
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        });
        ctx.stroke();
    }

    // Пунктирная линия текущего веса и яркая плашка справа
    const yCur = toY(curW);
    ctx.save();
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = "#00ff88";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(padL, yCur);
    ctx.lineTo(W - padR, yCur);
    ctx.stroke();
    ctx.restore();

    ctx.fillStyle = "#00ff88";
    ctx.beginPath();
    ctx.roundRect(W - padR + 3, yCur - 9, 45, 18, 5);
    ctx.fill();
    ctx.fillStyle = "#04100a";
    ctx.font = "bold 10px sans-serif";
    ctx.fillText(curW.toFixed(1), W - padR + 9, yCur + 3.5);

    // Научный расчёт пути до цели внизу
    const progEl = document.getElementById("wtEnergyProgressBox");
    if (progEl) {
        progEl.innerHTML = forecast.days === 0
            ? `⚡ <strong style="color:#00ff88;">Целевой вес ${targetW.toFixed(1)} кг достигнут!</strong> Удерживаем форму на <strong>${metrics.kcal} ккал/день</strong>.`
            : `🎯 <strong style="color:#e879f9;">Путь до ${targetW.toFixed(1)} кг:</strong> ~<strong>${forecast.weeks} нед.</strong> (ориентир <strong>${forecast.etaDate}</strong>, темп ${forecast.weeklyRate > 0 ? "+" : ""}${forecast.weeklyRate} кг/нед.) при соблюдении нормы <strong>${metrics.kcal} ккал/день</strong>.`;
    }
}


async function submitNewWeightPoint() {
    const inp = document.getElementById("wtNewWeightInput");
    const val = parseFloat(inp?.value);
    if (!val || val < 35 || val > 250) return;
    _wvProfile.weight = val;
    localStorage.setItem("wv_profile_v49", JSON.stringify(_wvProfile));
    _recordWeightBar(val);
    if (typeof weightHistory !== "undefined" && Array.isArray(weightHistory)) {
        weightHistory.push({ date: new Date().toISOString(), weight: val });
    }
    inp.value = "";
    _syncGoalCardsUI();
    renderWeightTerminal();
    try {
        await fetch("/coach/ask", {
            method: "POST",
            headers: authHeaders(),
            body: JSON.stringify({ message: `Мой вес ${val}` })
        });
        await Promise.all([loadSupport(), loadNutrition()]);
    } catch (e) {}
}

async function checkAndOpenOnboarding() {
    if (!token) return;
    try {
        const res = await fetch("/auth/me", { headers: authHeaders() });
        if (!res.ok) return;
        const prof = await res.json();
        if (prof.weight_kg) _wvProfile.weight = prof.weight_kg;
        if (prof.target_weight_kg) _wvProfile.targetWeight = prof.target_weight_kg;
        if (prof.height_cm) _wvProfile.height = prof.height_cm;
        if (prof.age) _wvProfile.age = prof.age;
        localStorage.setItem("wv_profile_v49", JSON.stringify(_wvProfile));
        _syncGoalCardsUI();

        if (prof.is_onboarded === false) {
            const m = document.getElementById("onboardingWelcomeModal");
            if (m) {
                const nameInp = document.getElementById("obNameInput");
                if (nameInp && prof.username) nameInp.value = prof.username;
                m.classList.remove("hidden");
                m.style.display = "flex";
            }
        }
    } catch (e) {}
}

async function submitOnboardingWizard() {
    const minW = parseFloat(document.getElementById("obMinWeightInput")?.value) || null;
    const maxW = parseFloat(document.getElementById("obMaxWeightInput")?.value) || null;
    const payload = {
        full_name: (document.getElementById("obNameInput")?.value || "").trim() || "Атлет",
        gender: document.getElementById("obGenderSelect")?.value || "male",
        age: parseInt(document.getElementById("obAgeInput")?.value) || 35,
        height_cm: parseFloat(document.getElementById("obHeightInput")?.value) || 176,
        weight_kg: parseFloat(document.getElementById("obWeightInput")?.value) || 70.0,
        target_weight_kg: parseFloat(document.getElementById("obTargetInput")?.value) || 72.0,
        work_type: document.getElementById("obWorkTypeSelect")?.value || "mixed",
        work_schedule: document.getElementById("obScheduleSelect")?.value || "2/2",
        goal: document.getElementById("obGoalSelect")?.value || "recomp",
        workouts_per_week: 3
    };
    const res = await fetch("/auth/onboarding", {
        method: "POST",
        headers: authHeaders(),
        body: JSON.stringify(payload)
    });
    if (res.ok) {
        const actMap = { sedentary: 1.375, mixed: 1.55, physical: 1.725, sport: 1.95 };
        _wvProfile = {
            age: payload.age,
            height: payload.height_cm,
            weight: payload.weight_kg,
            targetWeight: payload.target_weight_kg,
            activity: actMap[payload.work_type] || 1.55,
            knownMinW: minW,
            knownMaxW: maxW
        };
        localStorage.setItem("wv_profile_v49", JSON.stringify(_wvProfile));
        localStorage.removeItem("wv_weight_logs_v1");
        _recordWeightBar(payload.weight_kg);
        const m = document.getElementById("onboardingWelcomeModal");
        if (m) { m.classList.add("hidden"); m.style.display = "none"; }
        _syncGoalCardsUI();
        renderWeightTerminal();
        await Promise.all([loadSupport(), loadNutrition()]);
    }
}


function initV49Modules() {
    _syncAvatarUI();
    _syncGoalCardsUI();
    renderWeightTerminal();
    checkAndOpenOnboarding();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initV49Modules);
} else {
    initV49Modules();
}


