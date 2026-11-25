
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
