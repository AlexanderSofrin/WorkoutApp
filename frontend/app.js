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
    await Promise.all([loadSupport(), loadNutrition(), loadRecommendation()]);
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
