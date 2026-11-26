/*
 * Small SVG chart helpers for the analytics dashboard (Part 4).
 * No external library: the dashboard works offline and needs nothing from a CDN.
 * Every chart has a hover tooltip and a "Show as table" view (the numbers are never colour-only).
 */
(function () {
    const NS = "http://www.w3.org/2000/svg";
    const COLORS = ["#257de0", "#f47230"];  // series 1 (blue), series 2 (orange)

    function el(tag, attrs, parent) {
        const node = document.createElementNS(NS, tag);
        for (const k in attrs) node.setAttribute(k, attrs[k]);
        if (parent) parent.appendChild(node);
        return node;
    }

    function tooltip() {
        let tip = document.getElementById("chart-tooltip");
        if (!tip) {
            tip = document.createElement("div");
            tip.id = "chart-tooltip";
            tip.className = "chart-tooltip";
            document.body.appendChild(tip);
        }
        return tip;
    }

    function hover(node, text) {
        const tip = tooltip();
        node.addEventListener("mousemove", function (e) {
            tip.textContent = text;
            tip.style.display = "block";
            tip.style.left = (e.pageX + 12) + "px";
            tip.style.top = (e.pageY - 28) + "px";
        });
        node.addEventListener("mouseleave", function () { tip.style.display = "none"; });
    }

    // Axis maximum: the smallest "nice" number >= v that splits into 4 whole ticks (counts)
    function niceMax(v) {
        if (v <= 4) return 4;
        const p = Math.pow(10, Math.floor(Math.log10(v)));
        for (const m of [1, 2, 4, 5, 8, 10, 12, 20]) {
            const c = m * p;
            if (c >= v && Number.isInteger(c / 4)) return c;
        }
        return 20 * p;
    }

    function table(container, header, rows) {
        const d = document.createElement("details");
        d.className = "chart-table";
        d.innerHTML = "<summary>Show as table</summary>";
        const t = document.createElement("table");
        t.className = "table table-sm";
        t.innerHTML = "<thead><tr>" + header.map(h => "<th>" + h + "</th>").join("") + "</tr></thead>";
        const body = document.createElement("tbody");
        rows.forEach(r => {
            const tr = document.createElement("tr");
            r.forEach(c => { const td = document.createElement("td"); td.textContent = c; tr.appendChild(td); });
            body.appendChild(tr);
        });
        t.appendChild(body);
        d.appendChild(t);
        container.appendChild(d);
    }

    function empty(container, data) {
        if (!data.values.length || data.values.every(v => !v)) {
            container.innerHTML = '<p class="chart-empty">No data yet.</p>';
            return true;
        }
        return false;
    }

    // Vertical bars, one series (counts per category: hour, rank, length...)
    function bars(container, data, opts) {
        opts = opts || {};
        if (empty(container, data)) return;
        const W = 640, H = 230, L = 40, R = 10, T = 12, B = 36;
        const svg = el("svg", {viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img",
                              "aria-label": opts.title || "bar chart"}, container);
        const max = niceMax(Math.max(...data.values));
        const n = data.values.length, band = (W - L - R) / n, bw = Math.max(4, band - 2);
        for (let i = 0; i <= 4; i++) {  // recessive grid + y labels
            const y = T + (H - T - B) * (1 - i / 4);
            el("line", {x1: L, x2: W - R, y1: y, y2: y, class: "grid"}, svg);
            const lab = el("text", {x: L - 6, y: y + 4, class: "axis", "text-anchor": "end"}, svg);
            lab.textContent = Math.round(max * i / 4 * 10) / 10;
        }
        const every = Math.ceil(n / 24);
        data.values.forEach((v, i) => {
            const h = (H - T - B) * v / max, x = L + i * band + (band - bw) / 2, y = H - B - h;
            const r = Math.min(4, bw / 2, h / 2);
            // rounded data end, square at the baseline
            const path = `M${x},${H - B} V${y + r} Q${x},${y} ${x + r},${y} H${x + bw - r} Q${x + bw},${y} ${x + bw},${y + r} V${H - B} Z`;
            const bar = el("path", {d: h > 0 ? path : "", fill: opts.color || COLORS[0], class: "mark"}, svg);
            const hit = el("rect", {x: L + i * band, y: T, width: band, height: H - T - B, fill: "transparent"}, svg);
            hover(hit, `${opts.xTitle ? opts.xTitle + " " : ""}${data.labels[i]}: ${v} ${opts.unit || ""}`);
            if (i % every === 0) {
                const t = el("text", {x: L + i * band + band / 2, y: H - B + 15, class: "axis", "text-anchor": "middle"}, svg);
                t.textContent = data.labels[i];
            }
        });
        el("line", {x1: L, x2: W - R, y1: H - B, y2: H - B, class: "baseline"}, svg);
        if (opts.xTitle) {
            const t = el("text", {x: (L + W - R) / 2, y: H - 4, class: "axis-title", "text-anchor": "middle"}, svg);
            t.textContent = opts.xTitle;
        }
        table(container, [opts.xTitle || "Category", opts.unit || "Count"], data.labels.map((l, i) => [l, data.values[i]]));
    }

    // Horizontal "meter list": name, bar and figure per row (shares of a whole, top-N lists)
    function meters(container, data, opts) {
        opts = opts || {};
        if (empty(container, data)) return;
        const total = data.values.reduce((a, b) => a + b, 0);
        const max = Math.max(...data.values);
        const list = document.createElement("div");
        list.className = "meter-list";
        data.labels.forEach((label, i) => {
            const v = data.values[i];
            const share = total ? Math.round(1000 * v / total) / 10 : 0;
            const row = document.createElement("div");
            row.className = "meter-row";
            row.innerHTML = `<span class="meter-name"></span><span class="meter-track"><span class="meter-fill"></span></span><span class="meter-value"></span>`;
            row.querySelector(".meter-name").textContent = label;
            row.querySelector(".meter-fill").style.width = (100 * v / max) + "%";
            row.querySelector(".meter-value").textContent = opts.share ? `${v} (${share}%)` : `${v}`;
            hover(row, `${label}: ${v}${opts.share ? " (" + share + "% of " + total + ")" : ""}`);
            list.appendChild(row);
        });
        container.appendChild(list);
        table(container, [opts.name || "Item", "Count"].concat(opts.share ? ["%"] : []),
              data.labels.map((l, i) => [l, data.values[i]].concat(opts.share ? [Math.round(1000 * data.values[i] / total) / 10] : [])));
    }

    // Lines over time, one axis, up to two series (legend + direct labels at the end)
    function lines(container, data, opts) {
        opts = opts || {};
        const all = data.series.flatMap(s => s.values);
        if (!all.length || all.every(v => !v)) { container.innerHTML = '<p class="chart-empty">No data yet.</p>'; return; }
        const legend = document.createElement("div");
        legend.className = "chart-legend";
        data.series.forEach((s, k) => {
            legend.innerHTML += `<span><i style="background:${COLORS[k]}"></i>${s.name}</span>`;
        });
        container.appendChild(legend);
        const W = 640, H = 230, L = 40, R = 70, T = 12, B = 36;
        const svg = el("svg", {viewBox: `0 0 ${W} ${H}`, class: "chart-svg", role: "img", "aria-label": opts.title || "line chart"}, container);
        const max = niceMax(Math.max(...all));
        const n = data.labels.length;
        const x = i => n === 1 ? (L + W - R) / 2 : L + (W - L - R) * i / (n - 1);
        const y = v => T + (H - T - B) * (1 - v / max);
        for (let i = 0; i <= 4; i++) {
            const yy = T + (H - T - B) * (1 - i / 4);
            el("line", {x1: L, x2: W - R, y1: yy, y2: yy, class: "grid"}, svg);
            const lab = el("text", {x: L - 6, y: yy + 4, class: "axis", "text-anchor": "end"}, svg);
            lab.textContent = Math.round(max * i / 4);
        }
        const every = Math.ceil(n / 8);
        data.labels.forEach((l, i) => {
            if (i % every === 0 || i === n - 1) {
                const t = el("text", {x: x(i), y: H - B + 15, class: "axis", "text-anchor": "middle"}, svg);
                t.textContent = l;
            }
        });
        const labelY = [];  // y of the direct labels already placed, to avoid overlapping them
        data.series.forEach((s, k) => {
            const pts = s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
            el("polyline", {points: pts, fill: "none", stroke: COLORS[k], "stroke-width": 2, class: "line"}, svg);
            s.values.forEach((v, i) => {
                const c = el("circle", {cx: x(i), cy: y(v), r: 4, fill: COLORS[k], stroke: "#fff", "stroke-width": 2}, svg);
                hover(c, `${data.labels[i]} - ${s.name}: ${v}`);
            });
            const last = s.values.length - 1;  // direct label at the end of the line
            let ly = Math.min(H - B - 4, y(s.values[last]) + 4);
            while (labelY.some(other => Math.abs(other - ly) < 13)) ly -= 13;  // move up until it is free
            labelY.push(ly);
            const t = el("text", {x: x(last) + 8, y: ly, class: "direct-label"}, svg);
            t.textContent = s.name;
        });
        el("line", {x1: L, x2: W - R, y1: H - B, y2: H - B, class: "baseline"}, svg);
        table(container, ["Date"].concat(data.series.map(s => s.name)),
              data.labels.map((l, i) => [l].concat(data.series.map(s => s.values[i]))));
    }

    window.IRWACharts = {bars: bars, meters: meters, lines: lines};
})();
