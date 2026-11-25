const CACHE_NAME = 'workout-vault-v4';

self.addEventListener('install', (event) => {
    self.skipWaiting();
});

self.addEventListener('activate', (event) => {
    event.waitUntil(
        caches.keys().then((keys) =>
            Promise.all(keys.map((k) => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

self.addEventListener('fetch', (event) => {
    const url = new URL(event.request.url);
    if (
        event.request.method !== 'GET' ||
        url.pathname.startsWith('/workouts') ||
        url.pathname.startsWith('/coach') ||
        url.pathname.startsWith('/nutrition') ||
        url.pathname.startsWith('/exercises') ||
        url.pathname.startsWith('/auth') ||
        url.pathname.startsWith('/api')
    ) {
        return;
    }

    event.respondWith(
        fetch(event.request, { cache: 'no-store' })
            .then((response) => {
                const clone = response.clone();
                caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
                return response;
            })
            .catch(() => caches.match(event.request))
    );
});
// === БИРЖЕВОЙ ТЕРМИНАЛ ВЕСА ТЕЛА (SUPPORT / RESISTANCE / BREAKOUT) ===
let _wtTimeframeDays = 30;

function _getWeightHistoryList(currentW) {
    const raw = localStorage.getItem("wv_weight_history");
    let list = [];
    try { list = raw ? JSON.parse(raw) : []; } catch (_) { list = []; }
    if (!Array.isArray(list)) list = [];
    const todayIso = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Moscow" });
    if (currentW && currentW > 0) {
        if (!list.length) {
            list.push({ date: todayIso, weight: Number(currentW) });
        } else if (list[list.length - 1].date === todayIso) {
            list[list.length - 1].weight = Number(currentW);
        } else {
            list.push({ date: todayIso, weight: Number(currentW) });
        }
        localStorage.setItem("wv_weight_history", JSON.stringify(list.slice(-180)));
    }
    return list;
}

function setWeightTimeframe(days) {
    _wtTimeframeDays = days;
    document.querySelectorAll(".wt-tf-btn").forEach(btn => {
        const active = Number(btn.dataset.days) === days;
        btn.style.borderColor = active ? "#34d399" : "";
        btn.style.color = active ? "#34d399" : "";
    });
    renderWeightTerminal();
}

function quickPromptWeight() {
    const val = prompt("Введи актуальный вес тела (кг), например 67.2:");
    if (!val) return;
    const num = parseFloat(val.replace(",", "."));
    if (!isNaN(num) && num >= 35 && num <= 250) {
        _saveWeightToSystem(num);
    }
}

function submitNewWeightPoint() {
    const inp = document.getElementById("wtNewWeightInput");
    if (!inp || !inp.value) return;
    const num = parseFloat(inp.value.replace(",", "."));
    if (isNaN(num) || num < 35 || num > 250) return;
    inp.value = "";
    _saveWeightToSystem(num);
}

async function _saveWeightToSystem(newWeight) {
    const todayIso = new Date().toLocaleDateString("sv-SE", { timeZone: "Europe/Moscow" });
    const list = _getWeightHistoryList(null);
    if (list.length && list[list.length - 1].date === todayIso) {
        list[list.length - 1].weight = newWeight;
    } else {
        list.push({ date: todayIso, weight: newWeight });
    }
    localStorage.setItem("wv_weight_history", JSON.stringify(list.slice(-180)));
    if (window._currentUserProfile) window._currentUserProfile.weight_kg = newWeight;
    renderWeightTerminal();
    try {
        await apiFetch("/coach/ask", {
            method: "POST",
            body: JSON.stringify({ message: `мой вес ${newWeight}` })
        });
    } catch (_) {}
}
function renderWeightTerminal() {
    const prof = window._currentUserProfile || {};
    const curW = Number(prof.weight_kg || 67.0);
    const targetW = Number(prof.target_weight_kg || 67.0);
    const allPts = _getWeightHistoryList(curW);
    const pts = allPts.slice(-Math.max(2, _wtTimeframeDays));

    const isCut = targetW < curW - 0.2;
    const isBulk = targetW > curW + 0.2;

    let baseLevel = Math.round(curW * 2) / 2;
    let support = Number((baseLevel - 0.5).toFixed(1));
    let resistance = Number((baseLevel + 0.5).toFixed(1));
    let breakoutState = "В КОРИДОРЕ";

    if (pts.length >= 2) {
        const p1 = pts[pts.length - 2].weight;
        const p2 = pts[pts.length - 1].weight;
        if (isBulk && p1 >= resistance && p2 >= resistance) {
            support = resistance;
            resistance = Number((resistance + 0.5).toFixed(1));
            breakoutState = "ПРОБОЙ ВВЕРХ ↗";
        } else if (isCut && p1 <= support && p2 <= support) {
            resistance = support;
            support = Number((support - 0.5).toFixed(1));
            breakoutState = "ПРОБОЙ ВНИЗ ↘";
        }
    }

    const prevW = pts.length >= 2 ? pts[pts.length - 2].weight : curW;
    const delta = Number((curW - prevW).toFixed(2));
    const arrow = delta > 0.02 ? "↗" : (delta < -0.02 ? "↘" : "→");
    const goodTrend = (isBulk && delta >= 0) || (isCut && delta <= 0) || (!isBulk && !isCut && Math.abs(delta) <= 0.3);
    const trendColor = goodTrend ? "#34d399" : "#fbbf24";

    let distKg = 0;
    let hintText = "";
    if (isCut) {
        distKg = Math.max(0, Number((curW - support).toFixed(2)));
        const kcalLeft = Math.round(distKg * 7700);
        hintText = distKg > 0
            ? `До пробоя поддержки ${support.toFixed(1)} кг осталось ${distKg.toFixed(1)} кг (≈ ${kcalLeft.toLocaleString("ru-RU")} ккал дефицита)`
            : `Уровень ${support.toFixed(1)} кг пробит! Закрепись ещё 1 замером для сдвига коридора вниз.`;
    } else if (isBulk) {
        distKg = Math.max(0, Number((resistance - curW).toFixed(2)));
        const kcalLeft = Math.round(distKg * 7700);
        hintText = distKg > 0
            ? `До пробоя сопротивления ${resistance.toFixed(1)} кг осталось ${distKg.toFixed(1)} кг (≈ ${kcalLeft.toLocaleString("ru-RU")} ккал профицита)`
            : `Уровень ${resistance.toFixed(1)} кг пробит! Закрепись ещё 1 замером — он станет новой поддержкой.`;
    } else {
        hintText = `Идеальное удержание в зелёном канале ${support.toFixed(1)} – ${resistance.toFixed(1)} кг (цель ${targetW.toFixed(1)} кг).`;
    }

    const elCorridor = document.getElementById("heroCorridorRange");
    const elCurInfo = document.getElementById("heroCurrentWeightInfo");
    const elHint = document.getElementById("heroBreakoutHint");
    if (elCorridor) {
        elCorridor.textContent = `${support.toFixed(1)} – ${resistance.toFixed(1)} кг`;
        elCorridor.style.color = trendColor;
    }
    if (elCurInfo) {
        elCurInfo.innerHTML = `Сейчас: <strong style="color:${trendColor}">${curW.toFixed(1)} кг ${arrow}</strong> (цель ${targetW.toFixed(1)} кг)`;
    }
    if (elHint) elHint.textContent = hintText;

    const elBadge = document.getElementById("wtBreakoutBadge");
    const elTicker = document.getElementById("wtTickerLine");
    const elRes = document.getElementById("wtResistanceVal");
    const elSup = document.getElementById("wtSupportVal");
    const elCor = document.getElementById("wtCorridorVal");
    const elProg = document.getElementById("wtEnergyProgressBox");
    if (elBadge) { elBadge.textContent = breakoutState; elBadge.style.color = trendColor; }
    if (elTicker) {
        const sign = delta > 0 ? "+" : "";
        elTicker.innerHTML = `${curW.toFixed(2)} кг <span style="color:${trendColor}">${arrow} ${sign}${delta.toFixed(2)}</span> · Цель: ${targetW.toFixed(1)} кг`;
    }
    if (elRes) elRes.textContent = `${resistance.toFixed(1)} кг`;
    if (elSup) elSup.textContent = `${support.toFixed(1)} кг`;
    if (elCor) elCor.textContent = `${support.toFixed(1)} ↔ ${resistance.toFixed(1)}`;
    if (elProg) elProg.innerHTML = `<strong style="color:${trendColor}">${arrow} Статус уровня:</strong> ${hintText}`;

    const canvas = document.getElementById("weightTerminalCanvas");
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    const rect = canvas.getBoundingClientRect();
    const w = Math.max(280, rect.width || 320);
    const h = 190;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    const ctx = canvas.getContext("2d");
    ctx.scale(dpr, dpr);
    ctx.clearRect(0, 0, w, h);

    const drawPts = pts.length >= 2 ? pts : [{ date: "Старт", weight: curW }, { date: "Сегодня", weight: curW }];
    const vals = drawPts.map(p => p.weight).concat([support - 0.3, resistance + 0.3]);
    const minV = Math.min(...vals);
    const maxV = Math.max(...vals);
    const padL = 10, padR = 46, padT = 16, padB = 22;
    const plotW = w - padL - padR;
    const plotH = h - padT - padB;
    const yOf = v => padT + plotH - ((v - minV) / Math.max(0.2, maxV - minV)) * plotH;

    const yRes = yOf(resistance);
    const ySup = yOf(support);
    ctx.fillStyle = "rgba(52, 211, 153, 0.11)";
    ctx.fillRect(padL, Math.min(yRes, ySup), plotW, Math.abs(ySup - yRes));

    ctx.save();
    ctx.setLineDash([5, 4]);
    ctx.strokeStyle = "#38bdf8";
    ctx.lineWidth = 1.2;
    ctx.beginPath(); ctx.moveTo(padL, yRes); ctx.lineTo(padL + plotW, yRes); ctx.stroke();
    ctx.fillStyle = "#38bdf8"; ctx.font = "bold 10px sans-serif";
    ctx.fillText(resistance.toFixed(1), padL + plotW + 5, yRes + 3);

    ctx.strokeStyle = "#fbbf24";
    ctx.beginPath(); ctx.moveTo(padL, ySup); ctx.lineTo(padL + plotW, ySup); ctx.stroke();
    ctx.fillStyle = "#fbbf24";
    ctx.fillText(support.toFixed(1), padL + plotW + 5, ySup + 3);
    ctx.restore();

    const stepX = plotW / Math.max(1, drawPts.length - 1);
    const grad = ctx.createLinearGradient(0, padT, 0, padT + plotH);
    grad.addColorStop(0, "rgba(163, 230, 53, 0.35)");
    grad.addColorStop(1, "rgba(163, 230, 53, 0.0)");

    ctx.beginPath();
    drawPts.forEach((p, i) => {
        const x = padL + i * stepX;
        const y = yOf(p.weight);
        if (i === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    });
    ctx.strokeStyle = "#a3e635";
    ctx.lineWidth = 2.4;
    ctx.stroke();

    ctx.lineTo(padL + (drawPts.length - 1) * stepX, padT + plotH);
    ctx.lineTo(padL, padT + plotH);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    drawPts.forEach((p, i) => {
        const x = padL + i * stepX;
        const y = yOf(p.weight);
        ctx.beginPath();
        ctx.arc(x, y, i === drawPts.length - 1 ? 4.5 : 2.8, 0, Math.PI * 2);
        ctx.fillStyle = i === drawPts.length - 1 ? "#f8fafc" : "#a3e635";
        ctx.fill();
        if (i === drawPts.length - 1) {
            ctx.fillStyle = "#a3e635";
            ctx.fillRect(padL + plotW + 3, y - 8, 41, 16);
            ctx.fillStyle = "#090d16";
            ctx.font = "bold 10px sans-serif";
            ctx.fillText(p.weight.toFixed(1), padL + plotW + 6, y + 3);
        }
    });
}
setTimeout(() => { if (typeof renderWeightTerminal === "function") renderWeightTerminal(); }, 600);
