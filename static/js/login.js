// Toggle this to use real endpoints instead of demo localStorage.
const USE_API = true;
const API = {
  login: "/login",
  signup: "/signup",
  reset: "/api/reset"
};

// ---------- Utilities ----------
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

function showToast(msg, type = "ok") {
  const el = $("#toast");
  if (!el) return;
  el.textContent = msg;
  el.classList.toggle("error", type === "error");
  el.classList.add("show");
  setTimeout(() => el.classList.remove("show"), 2000);
}

function validateEmail(e) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e);
}

// ---------- Demo storage (localStorage) ----------
const LS_USERS = "recycloai_users";
const LS_REMEMBER = "recycloai_remember";
const LS_SESSION = "recycloai_session";

function getUsers() {
  const raw = localStorage.getItem(LS_USERS);
  try {
    const users = raw ? JSON.parse(raw) : [];
    // Seed a demo user once.
    if (!users.length) {
      users.push({ name: "Demo User", email: "demo@recyclo.ai", pass: "demo123" });
      localStorage.setItem(LS_USERS, JSON.stringify(users));
    }
    return users;
  } catch { return []; }
}

function saveUsers(users) {
  localStorage.setItem(LS_USERS, JSON.stringify(users));
}

// ---------- Parallax (non-accumulating) ----------
(() => {
  const leaves = $$(".leaf");
  if (!leaves.length) return;
  let raf = null;
  let target = { x: 0, y: 0 };

  function onMove(e) {
    const mx = e.clientX / window.innerWidth;
    const my = e.clientY / window.innerHeight;
    target.x = mx; target.y = my;
    if (!raf) raf = requestAnimationFrame(apply);
  }

  function apply() {
    leaves.forEach((leaf, i) => {
      const speed = (i + 1) * 6; // tweak strength
      const x = (target.x - 0.5) * speed;
      const y = (target.y - 0.5) * speed;
      leaf.style.setProperty("--tx", `${x}px`);
      leaf.style.setProperty("--ty", `${y}px`);
    });
    raf = null;
  }

  document.addEventListener("mousemove", onMove);
})();

// ---------- Modal controls (focus trap + ESC) ----------
function trapFocus(modal) {
  const focusable = "a[href], button:not([disabled]), textarea, input, select, [tabindex]:not([tabindex='-1'])";
  const nodes = $$(focusable, modal);
  if (!nodes.length) return;
  let first = nodes[0], last = nodes[nodes.length - 1];

  function onKey(e) {
    if (e.key === "Escape") closeModal(modal);
    if (e.key !== "Tab") return;
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault(); last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault(); first.focus();
    }
  }
  modal._untrap = () => modal.removeEventListener("keydown", onKey);
  modal.addEventListener("keydown", onKey);
  first.focus();
}

let lastActive = null;

function openModal(modal) {
  if (!modal) return;
  lastActive = document.activeElement;
  modal.hidden = false;
  // Click outside to close
  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal(modal);
  }, { once: true });
  // [data-close] buttons
  $$("[data-close]", modal).forEach(btn => btn.addEventListener("click", () => closeModal(modal), { once: true }));
  trapFocus(modal);
}

function closeModal(modal) {
  if (!modal) return;
  modal.hidden = true;
  if (modal._untrap) modal._untrap();
  if (lastActive) lastActive.focus();
}

// ---------- Logout (server + client fallback) ----------
async function doLogout(e) {
  if (e) e.preventDefault();
  // Try POST /logout so Flask can clear the session cookie
  try {
    const res = await fetch("/logout", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "same-origin"
    });
    if (!res.ok && res.status !== 204) {
      // Some apps only support GET: fall back to a navigation
      window.location.href = "/logout";
      return;
    }
  } catch {
    // If POST fails (no route), try GET
    window.location.href = "/logout";
    return;
  }

  // Client-side cleanup (harmless; real auth is server cookie)
  try { localStorage.removeItem(LS_SESSION); } catch {}
  // Send them somewhere public; adjust if your login page is different
  window.location.href = "/";
}

function bindLogout(scope = document) {
  const candidates = [
    '#logout-btn',
    '[data-action="logout"]',
    'a[href="/logout"]' // intercept plain links to ensure POST + cleanup
  ];
  candidates.forEach(sel => {
    $$(sel, scope).forEach(el => {
      el.addEventListener("click", doLogout);
    });
  });
}

// ---------- Clone homepage header (exact markup + styles) ----------
async function syncHeaderFromHome() {
  try {
    const res = await fetch("/", { credentials: "same-origin" });
    if (!res.ok) return;

    const html = await res.text();
    const doc = new DOMParser().parseFromString(html, "text/html");

    // Copy stylesheet <link> tags so header looks identical
    const homeLinks = doc.querySelectorAll('link[rel="stylesheet"]');
    homeLinks.forEach(link => {
      const href = link.getAttribute("href");
      if (!href) return;
      if (!document.querySelector(`link[rel="stylesheet"][href="${href}"]`)) {
        document.head.appendChild(link.cloneNode(true));
      }
    });

    // Replace current header with homepage header (prefer #site-header)
    const homeHeader = doc.querySelector("#site-header") || doc.querySelector("header");
    const currentHeader = document.querySelector("#site-header") || document.querySelector("header");
    if (homeHeader && currentHeader) {
      const clone = homeHeader.cloneNode(true);
      currentHeader.replaceWith(clone);
      // Re-bind logout (new nodes)
      bindLogout(document);
    }
  } catch {
    // Silently ignore if homepage not reachable
  }
}

// ---------- Wire up UI ----------
document.addEventListener("DOMContentLoaded", () => {
  const loginForm = $("#login-form");
  const loginBtn = $("#login-btn");
  const remember = $("#remember");
  const emailEl = $("#email");
  const passEl = $("#password");

  const signupModal = $("#signup-modal");
  const resetModal = $("#reset-modal");

  $("#open-signup")?.addEventListener("click", (e) => { e.preventDefault(); openModal(signupModal); });
  $("#open-reset")?.addEventListener("click", (e) => { e.preventDefault(); openModal(resetModal); });

  // Prefill remembered email
  const remembered = localStorage.getItem(LS_REMEMBER);
  if (remembered && emailEl) {
    emailEl.value = remembered;
    if (remember) remember.checked = true;
  }

  // ------ Login ------
  if (loginForm) {
    loginForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = (emailEl?.value || "").trim();
      const pass = passEl?.value || "";

      if (!validateEmail(email)) return showToast("Enter a valid email", "error");
      if (!pass) return showToast("Password required", "error");

      const original = loginBtn?.textContent;
      if (loginBtn) { loginBtn.disabled = true; loginBtn.textContent = "Signing in..."; }

      try {
        if (USE_API) {
          const res = await fetch(API.login, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin", // send/receive Flask session cookie
            redirect: "follow",
            body: JSON.stringify({ email, password: pass })
          });
          if (!res.ok && res.status !== 204) {
            let msg = "Login failed";
            try {
              const ct = res.headers.get("content-type") || "";
              if (ct.includes("application/json")) {
                const j = await res.json();
                msg = j.error || j.message || msg;
              } else {
                const t = await res.text();
                if (t) msg = t;
              }
            } catch {}
            throw new Error(msg);
          }

          if (res.redirected) {
            window.location.href = "/progress";
            return;
          }

          let user = { email, name: email.split("@")[0] };
          try {
            const ct = res.headers.get("content-type") || "";
            if (ct.includes("application/json")) {
              const j = await res.json();
              if (j && (j.email || j.user)) {
                const u = j.user || j;
                user = { email: u.email || email, name: u.name || user.name };
              }
            }
          } catch {}
          postLogin(user, !!(remember && remember.checked), email);
        } else {
          const user = getUsers().find(u => u.email.toLowerCase() === email.toLowerCase() && u.pass === pass);
          if (!user) throw new Error("Invalid credentials");
          postLogin(user, !!(remember && remember.checked), email);
        }
      } catch (err) {
        showToast(err.message || "Unable to sign in", "error");
      } finally {
        if (loginBtn) { loginBtn.disabled = false; loginBtn.textContent = original || "Sign in"; }
      }
    });
  }

  function postLogin(user, rememberOn, email) {
    if (rememberOn) localStorage.setItem(LS_REMEMBER, email);
    else localStorage.removeItem(LS_REMEMBER);
    try {
      localStorage.setItem(LS_SESSION, JSON.stringify({ email: user.email, name: user.name }));
    } catch {}
    showToast(`Welcome back, ${user.name || user.email}!`);
    setTimeout(() => { window.location.href = "/progress"; }, 300);
  }

  // ------ Signup ------
  const suForm = $("#signup-form");
  if (suForm) {
    suForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const name = $("#su-name")?.value.trim() || "";
      const email = $("#su-email")?.value.trim() || "";
      const pass = $("#su-pass")?.value || "";
      const pass2 = $("#su-pass2")?.value || "";

      if (!name) return showToast("Please enter your name", "error");
      if (!validateEmail(email)) return showToast("Enter a valid email", "error");
      if (pass.length < 6) return showToast("Password must be at least 6 characters", "error");
      if (pass !== pass2) return showToast("Passwords do not match", "error");

      const btn = $("#signup-btn");
      const original = btn?.textContent;
      if (btn) { btn.disabled = true; btn.textContent = "Creating..."; }

      try {
        if (USE_API) {
          const res = await fetch(API.signup, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ name, email, password: pass })
          });
          if (!res.ok && res.status !== 201) throw new Error("Signup failed");
          showToast("Account created! You can sign in now.");
        } else {
          const users = getUsers();
          if (users.some(u => u.email.toLowerCase() === email.toLowerCase())) {
            throw new Error("Email already registered");
          }
          users.push({ name, email, pass });
          saveUsers(users);
          showToast("Account created! You can sign in now.");
        }
        closeModal(signupModal);
        const emailInput = $("#email");
        if (emailInput) emailInput.value = email;
        $("#password")?.focus();
      } catch (err) {
        showToast(err.message || "Unable to sign up", "error");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = original || "Create account"; }
      }
    });
  }

  // ------ Reset ------
  const rpForm = $("#reset-form");
  if (rpForm) {
    rpForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const email = $("#rp-email")?.value.trim() || "";
      if (!validateEmail(email)) return showToast("Enter a valid email", "error");

      const btn = $("#reset-btn");
      const original = btn?.textContent;
      if (btn) { btn.disabled = true; btn.textContent = "Sending..."; }

      try {
        if (USE_API) {
          const res = await fetch(API.reset, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            credentials: "same-origin",
            body: JSON.stringify({ email })
          });
          if (!res.ok && res.status !== 204) throw new Error("Unable to send reset link");
        } else {
          await new Promise(r => setTimeout(r, 600));
        }
        showToast("If an account exists, a reset link was sent.");
        closeModal(resetModal);
      } catch (err) {
        showToast(err.message || "Unable to reset password", "error");
      } finally {
        if (btn) { btn.disabled = false; btn.textContent = original || "Send reset link"; }
      }
    });
  }

  // Make sure logout works wherever the button/link appears
  bindLogout(document);

  // Ensure header (markup + styles) exactly matches homepage
  syncHeaderFromHome();
});
