const $ = (s, c=document) => c.querySelector(s);

function fmtLocal(input){
  try {
    if (input == null) return "";

    // Handle numeric epoch (seconds or milliseconds)
    if (typeof input === "number") {
      const ms = input < 1e12 ? input * 1000 : input;
      return new Date(ms).toLocaleString(undefined, {
        hour12: false,
        timeZoneName: "short"
      });
    }

    let s = String(input).trim();

    // Convert "YYYY-MM-DD HH:mm:ss" to ISO-friendly form
    if (/^\d{4}-\d{2}-\d{2} \d{2}:\d{2}/.test(s)) {
      s = s.replace(" ", "T");
    }

    // Add 'Z' if timestamp lacks timezone info (treat as UTC)
    const hasTZ = /([zZ]|[+\-]\d{2}:\d{2})$/.test(s);
    const d = new Date(hasTZ ? s : s + "Z");

    if (isNaN(d)) return s;

    return d.toLocaleString(undefined, {
      hour12: false,
      timeZoneName: "short"
    });
  } catch {
    return String(input);
  }
}

async function fetchJSON(url){
  const r = await fetch(url, { credentials: "same-origin" });
  if(!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function loadAll(){
  const [summary, logs] = await Promise.all([
    fetchJSON("/api/progress/summary"),
    fetchJSON("/api/progress/logs?limit=200")
  ]);

  // KPIs
  $("#kpi-total").textContent = summary.total || 0;
  $("#kpi-recycle").textContent = summary.totals?.Recyclable || 0;
  $("#kpi-compost").textContent = summary.totals?.Compost || 0;
  $("#kpi-landfill").textContent = summary.totals?.Landfill || 0;

  // Charts
  if (window.Chart){
    const donutCtx = document.getElementById("donutChart").getContext("2d");
    if (window.__donut) window.__donut.destroy();
    window.__donut = new Chart(donutCtx, {
      type: "doughnut",
      data: {
        labels: ["Recyclable","Compost","Landfill","Other"],
        datasets: [{
          data: [
            summary.totals?.Recyclable || 0,
            summary.totals?.Compost || 0,
            summary.totals?.Landfill || 0,
            summary.totals?.Other || 0
          ],
          backgroundColor: ["#34d399","#22c55e","#ef4444","#94a3b8"],
          borderColor: "rgba(0,0,0,.15)", borderWidth: 1
        }]
      },
      options: { plugins: { legend: { labels: { color: "#eafbf3" } } } }
    });

    const barCtx = document.getElementById("barChart").getContext("2d");
    if (window.__bars) window.__bars.destroy();
    const days = Object.keys(summary.per_day || {}).sort();
    const mk = k => days.map(d => summary.per_day[d]?.[k] || 0);
    window.__bars = new Chart(barCtx, {
      type: "bar",
      data: {
        labels: days,
        datasets: [
          { label:"Recyclable", data: mk("Recyclable"), backgroundColor:"#34d399" },
          { label:"Compost", data: mk("Compost"), backgroundColor:"#22c55e" },
          { label:"Landfill", data: mk("Landfill"), backgroundColor:"#ef4444" },
          { label:"Other", data: mk("Other"), backgroundColor:"#94a3b8" }
        ]
      },
      options: {
        interaction: { mode:'index', intersect:false },
        scales: {
          x: { stacked:true, ticks:{ color:"#c2e5d9" }, grid:{ color:"rgba(255,255,255,.06)" } },
          y: { stacked:true, ticks:{ color:"#c2e5d9", precision:0 }, grid:{ color:"rgba(255,255,255,.06)" } }
        },
        plugins: { legend: { labels: { color: "#eafbf3" } } }
      }
    });
  }

  // Logs table
  const rows = logs.logs || [];
  const tbody = $("#logRows");
  tbody.innerHTML = "";
  if (!rows.length) document.getElementById("emptyMsg").hidden = false;
  rows.forEach(l => {
    const tr = document.createElement("tr");
    const label = normalizeLabel(l.label);
    const badgeClass = label === "Recyclable" ? "badge--recycle" :
                       label === "Compost" ? "badge--compost" :
                       label === "Landfill" ? "badge--landfill" : "";
    tr.innerHTML = `
      <td>${fmtLocal(l.ts)}</td>
      <td><span class="badge ${badgeClass}">${label}</span></td>
      <td>${l.confidence ?? ""}</td>
      <td>${l.city || ""}</td>
    `;
    tbody.appendChild(tr);
  });

  // Export / Clear
  document.getElementById("exportCsv").onclick = () => {
    const header = ["timestamp_iso","label","confidence","city"].join(",");
    const lines = rows.map(r => [
      r.ts,
      `"${(r.label||"").replace(/"/g,'""')}"`,
      r.confidence ?? "",
      `"${(r.city||"").replace(/"/g,'""')}"`
    ].join(","));
    const csv = [header, ...lines].join("\n");
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `recycloai_logs_${new Date().toISOString().slice(0,10)}.csv`;
    a.click();
    URL.revokeObjectURL(a.href);
  };

  document.getElementById("clearLogs").onclick = async () => {
    if (!confirm("Clear all your saved logs?")) return;
    await fetch("/api/logs", { method:"DELETE", credentials:"same-origin" }).catch(()=>{});
    location.reload();
  };
}

function normalizeLabel(s){
  s = String(s || "").toLowerCase();
  if (s.includes("recycl")) return "Recyclable";
  if (s.includes("compost") || s.includes("organic")) return "Compost";
  if (s.includes("landfill") || s.includes("trash") || s.includes("garbage")) return "Landfill";
  return "Other";
}

document.addEventListener("DOMContentLoaded", loadAll);
