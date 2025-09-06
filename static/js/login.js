// Toggle this to use real endpoints instead of demo localStorage.
const USE_API = false;
const API = {
  login: "/api/login",
  signup: "/api/signup",
  reset: "/api/reset"
};

// ---------- Utilities ----------
const $ = (sel, ctx = document) => ctx.querySelector(sel);
const $$ = (sel, ctx = document) => Array.from(ctx.querySelectorAll(sel));

function showToast(msg, type = "ok") {
  const el = $("#toast");
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
  modal.hidden = true;
  if (modal._untrap) modal._untrap();
  if (lastActive) lastActive.focus();
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

  $("#open-signup").addEventListener("click", (e) => { e.preventDefault(); openModal(signupModal); });
  $("#open-reset").addEventListener("click", (e) => { e.preventDefault(); openModal(resetModal); });

  // Prefill remembered email
  const remembered = localStorage.getItem(LS_REMEMBER);
  if (remembered) {
    emailEl.value = remembered;
    remember.checked = true;
  }

  // ------ Login ------
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = emailEl.value.trim();
    const pass = passEl.value;

    if (!validateEmail(email)) return showToast("Enter a valid email", "error");
    if (!pass) return showToast("Password required", "error");

    const original = loginBtn.textContent;
    loginBtn.disabled = true;
    loginBtn.textContent = "Signing in...";

    try {
      if (USE_API) {
        const res = await fetch(API.login, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password: pass })
        });
        if (!res.ok) throw new Error("Login failed");
        const user = await res.json();
        postLogin(user, remember.checked, email);
      } else {
        const user = getUsers().find(u => u.email.toLowerCase() === email.toLowerCase() && u.pass === pass);
        if (!user) throw new Error("Invalid credentials");
        postLogin(user, remember.checked, email);
      }
    } catch (err) {
      showToast(err.message || "Unable to sign in", "error");
    } finally {
      loginBtn.disabled = false;
      loginBtn.textContent = original;
    }
  });

  function postLogin(user, rememberOn, email) {
    if (rememberOn) localStorage.setItem(LS_REMEMBER, email);
    else localStorage.removeItem(LS_REMEMBER);

    localStorage.setItem(LS_SESSION, JSON.stringify({ email: user.email, name: user.name }));
    showToast(`Welcome back, ${user.name || user.email}!`);
    // Redirect where you want after login:
    setTimeout(() => { window.location.href = "/dashboard"; }, 800);
  }

  // ------ Signup ------
  const suForm = $("#signup-form");
  suForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = $("#su-name").value.trim();
    const email = $("#su-email").value.trim();
    const pass = $("#su-pass").value;
    const pass2 = $("#su-pass2").value;

    if (!name) return showToast("Please enter your name", "error");
    if (!validateEmail(email)) return showToast("Enter a valid email", "error");
    if (pass.length < 6) return showToast("Password must be at least 6 characters", "error");
    if (pass !== pass2) return showToast("Passwords do not match", "error");

    const btn = $("#signup-btn");
    const original = btn.textContent;
    btn.disabled = true; btn.textContent = "Creating...";

    try {
      if (USE_API) {
        const res = await fetch(API.signup, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ name, email, password: pass })
        });
        if (!res.ok) throw new Error("Signup failed");
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
      $("#email").value = email; // convenience
      $("#password").focus();
    } catch (err) {
      showToast(err.message || "Unable to sign up", "error");
    } finally {
      btn.disabled = false; btn.textContent = original;
    }
  });

  // ------ Reset ------
  const rpForm = $("#reset-form");
  rpForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const email = $("#rp-email").value.trim();
    if (!validateEmail(email)) return showToast("Enter a valid email", "error");

    const btn = $("#reset-btn");
    const original = btn.textContent;
    btn.disabled = true; btn.textContent = "Sending...";

    try {
      if (USE_API) {
        const res = await fetch(API.reset, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email })
        });
        if (!res.ok) throw new Error("Unable to send reset link");
      } else {
        // Demo: pretend we sent it
        await new Promise(r => setTimeout(r, 600));
      }
      showToast("If an account exists, a reset link was sent.");
      closeModal(resetModal);
    } catch (err) {
      showToast(err.message || "Unable to reset password", "error");
    } finally {
      btn.disabled = false; btn.textContent = original;
    }
  });
});
