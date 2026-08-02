/* ============================================================
   Machine 4 — Decimal32 · frontend logic
   ============================================================ */

"use strict";

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));
const escapeHtml = (s) =>
  String(s).replace(/[&<>"']/g, (c) =>
    ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c])
  );

/* ---------------- Theme toggle ---------------- */

const themeToggle = $("#theme-toggle");

function setTheme(theme, persist = true) {
  document.documentElement.setAttribute("data-theme", theme);
  if (persist) {
    try {
      localStorage.setItem("m4-theme", theme);
    } catch (e) {}
  }
  if (themeToggle) {
    const next = theme === "light" ? "Switch to dark mode" : "Switch to light mode";
    themeToggle.classList.toggle("is-light", theme === "light");
    themeToggle.setAttribute("aria-label", next);
    themeToggle.title = next;
  }
}

if (themeToggle) {
  themeToggle.addEventListener("click", () => {
    const cur =
      document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
    setTheme(cur === "light" ? "dark" : "light");
  });
}

(function initThemeUI() {
  const cur =
    document.documentElement.getAttribute("data-theme") === "light" ? "light" : "dark";
  setTheme(cur, false);
})();

/* ---------------- Tabs ---------------- */

$$(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    $$(".tab").forEach((t) => {
      const on = t === tab;
      t.classList.toggle("is-active", on);
      t.setAttribute("aria-selected", on);
    });
    $$(".panel").forEach((p) => {
      p.hidden = p.id !== `panel-${tab.dataset.tab}`;
      p.classList.toggle("is-active", p.id === `panel-${tab.dataset.tab}`);
    });
  });
});

/* ---------------- Shared request helper ---------------- */

async function postJSON(url, payload) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(`Server error (${res.status})`);
  return res.json();
}

function bindForm(form, run) {
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const btn = $('button[type="submit"]', form);
    btn.disabled = true;
    btn.textContent = btn.dataset.busy || "Working…";
    try {
      await run(new FormData(form));
    } catch (err) {
      showError(form, err.message || "Something went wrong.");
    } finally {
      btn.disabled = false;
      btn.textContent = btn.dataset.idle || "Submit";
    }
  });
  const reset = $('button[type="reset"]', form);
  if (reset) {
    form.addEventListener("reset", () => {
      setTimeout(() => {
        $$('.switch-row input[type="hidden"]', form).forEach((input) => {
          input.value = input._defaultValue !== undefined ? input._defaultValue : input.getAttribute("value");
          syncSwitchRow(input);
          if (typeof input._onSwitchChange === "function") input._onSwitchChange(input.value);
        });
        const box = form.closest(".panel").querySelector(".result");
        if (box) box.hidden = true;
      }, 0);
    });
  }
}

function showError(form, message) {
  const panel = form.closest(".panel");
  const result = $(".result", panel);
  if (result) result.hidden = true;
  panel.querySelectorAll(".error-box").forEach((el) => el.remove());
  const box = document.createElement("div");
  box.className = "error-box";
  box.innerHTML = `<span class="error-label">ERROR</span><p>${escapeHtml(message)}</p>`;
  form.insertAdjacentElement("afterend", box);
}

function clearError(form) {
  form.closest(".panel").querySelectorAll(".error-box").forEach((el) => el.remove());
}

/* ---------------- Panel 1: Converter ---------------- */

const formConvert = $("#form-convert");
const specialChips = $$("[data-special]");

specialChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    $("#convert-base").value = chip.dataset.special;
    $("#convert-base").focus();
  });
});

bindForm(formConvert, async (fd) => {
  clearError(formConvert);
  const base = fd.get("base").trim();
  const exp = fd.get("exp").trim();

  const data = await postJSON("/api/encode", { base, exp });
  if (!data.ok) throw new Error(data.error);

  const out = $("#result-convert");
  out.hidden = false;
  out.innerHTML = "";

  const inputBlock = block("Input");
  inputBlock.appendChild(kv([
    ["Number", data.input],
    ["Hexadecimal", `<span class="dim">0x</span>${data.hex.replace("0x", "")}`],
  ]));

  const fieldsBlock = block("Field breakdown");
  const chips = document.createElement("div");
  chips.className = "bits";
  const f = data.fields;
  chips.appendChild(bitChip("Sign", f.sign, "1 bit"));
  chips.appendChild(bitChip("Combination", f.combination, "5 bits"));
  chips.appendChild(bitChip("Exponent cont.", f.exponent_continuation, "6 bits"));
  chips.appendChild(bitChip("Coefficient cont.", f.coefficient_continuation, "20 bits"));
  fieldsBlock.appendChild(chips);

  const binBlock = block("Binary · 32-bit representation");
  binBlock.appendChild(output(data.binary, "is-large"));

  const hexBlock = block("Hexadecimal");
  hexBlock.appendChild(output(data.hex, "is-hex"));

  const traceBlock = trace(data.trace, "Show step-by-step trace");

  out.append(inputBlock, fieldsBlock, binBlock, hexBlock, traceBlock);
  out.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

/* ---------------- Panel 2: Rounding ---------------- */

const formRound = $("#form-round");

function updateRoundHint(type) {
  const bin = type === "binary";
  $("#round-value").placeholder = bin
    ? "e.g. 0.100101110 or 1.001p5"
    : "e.g. -0.7783";
  $("#round-hint").textContent = bin
    ? "Binary accepts 0/1 and an optional p-exponent, e.g. 1.001p5"
    : "Decimal accepts scientific notation, e.g. 1.23e5";
}

bindSwitch($("#rtype"), (val) => {
  updateRoundHint(val);
  $("#round-value").value = "";
});
bindSwitch($("#op"));
bindSwitch($("#fmt"), (val) => {
  $("#arith-op1").value = "";
  $("#arith-op2").value = "";
  const hex = val === "hex";
  $("#arith-op1").placeholder = hex ? "e.g. 0x22400525" : "e.g. 122.5";
  $("#arith-op2").placeholder = hex ? "e.g. 0x22400005" : "e.g. 0.5";
});

bindForm(formRound, async (fd) => {
  clearError(formRound);
  const payload = {
    value: fd.get("value").trim(),
    input_type: fd.get("rtype"),
    target_digits: fd.get("digits").trim(),
  };

  const data = await postJSON("/api/round", payload);
  if (!data.ok) throw new Error(data.error);

  const out = $("#result-round");
  out.hidden = false;
  out.innerHTML = "";

  const unit = data.input_type === "decimal" ? "digits" : "bits";

  const inputBlock = block("Input");
  inputBlock.appendChild(kv([
    ["Input type", data.input_type],
    ["Original value", data.original],
    ["Target precision", `${data.target_digits} significant ${unit}`],
  ]));
  inputBlock.appendChild(para(data.explanation.input));

  const gridBlock = block("Four rounding methods");
  const grid = document.createElement("div");
  grid.className = "round-grid";
  grid.appendChild(roundCard(1, "Chopping · toward zero", data.chopping, data.explanation.chopping));
  grid.appendChild(roundCard(2, "Round up · toward +∞", data.round_up, data.explanation.round_up));
  grid.appendChild(roundCard(3, "Round down · toward −∞", data.round_down, data.explanation.round_down));
  grid.appendChild(roundCard(4, "Nearest · ties to even", data.ties_to_even, data.explanation.ties_to_even));
  gridBlock.appendChild(grid);

  out.append(inputBlock, gridBlock);
  out.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

/* ---------------- Panel 3: Arithmetic ---------------- */

const formArith = $("#form-arith");

bindForm(formArith, async (fd) => {
  clearError(formArith);
  const payload = {
    operation: fd.get("op"),
    format: fd.get("fmt"),
    op1: fd.get("op1").trim(),
    op2: fd.get("op2").trim(),
    rounding: fd.get("rounding"),
  };

  const data = await postJSON("/api/arith", payload);
  if (!data.ok) throw new Error(data.error);

  const out = $("#result-arith");
  out.hidden = false;
  out.innerHTML = "";

  if (data.special) {
    const badge = document.createElement("div");
    badge.className = "special-badge";
    badge.textContent = `Special case · ${data.special}`;
    out.appendChild(badge);
  }

  const metaBlock = block("Operation");
  metaBlock.appendChild(kv([
    ["Operation", data.operation],
    ["Rounding method", data.rounding],
  ]));

  const stepsBlock = block("Step-by-step solution");
  stepsBlock.appendChild(steps(data.steps));

  const resultsBlock = block("Final result");
  const rows = [["Decimal", data.decimal]];
  rows.push(["Binary (spaced)", data.binary ? escapeHtml(data.binary) : "— unavailable —"]);
  rows.push(["Hexadecimal", data.hex || "— unavailable —"]);
  resultsBlock.appendChild(kv(rows));

  if (data.encoding_note) resultsBlock.appendChild(para(data.encoding_note));

  const extra = [];
  if (data.binary) {
    const b = block("Binary · 32-bit");
    b.appendChild(output(data.binary, "is-large"));
    extra.push(b);
  }
  if (data.hex) {
    const b = block("Hexadecimal");
    b.appendChild(output(data.hex, "is-hex"));
    extra.push(b);
  }
  const traceBlock = trace(data.encode_trace, "Show encoding trace");

  out.append(metaBlock, stepsBlock, resultsBlock, ...extra, traceBlock);
  out.scrollIntoView({ behavior: "smooth", block: "nearest" });
});

/* ---------------- Toggle switches ---------------- */

function syncSwitchRow(input) {
  const row = input.closest(".switch-row");
  if (!row) return;
  const btn = $(".switch", row);
  const opts = $$(".switch-opt", row);
  const rightActive = input.value === opts[1].dataset.value;
  btn.setAttribute("aria-checked", rightActive);
  opts[0].classList.toggle("is-active", !rightActive);
  opts[1].classList.toggle("is-active", rightActive);
}

function bindSwitch(input, onChange) {
  if (!input) return;
  input._onSwitchChange = onChange || null;
  input._defaultValue = input.value;
  $(".switch", input.closest(".switch-row")).addEventListener("click", () => {
    const opts = $$(".switch-opt", input.closest(".switch-row"));
    input.value =
      input.value === opts[1].dataset.value ? opts[0].dataset.value : opts[1].dataset.value;
    syncSwitchRow(input);
    if (onChange) onChange(input.value);
  });
  syncSwitchRow(input);
}

/* ---------------- Render helpers ---------------- */

function block(title) {
  const el = document.createElement("div");
  el.className = "result-block";
  const t = document.createElement("div");
  t.className = "result-title";
  t.textContent = title;
  el.appendChild(t);
  return el;
}

function output(text, cls = "") {
  const el = document.createElement("div");
  el.className = `mono-output ${cls}`;
  el.textContent = text;
  return el;
}

function kv(rows) {
  const dl = document.createElement("dl");
  dl.className = "kv";
  rows.forEach(([k, v]) => {
    const dt = document.createElement("dt");
    dt.textContent = k;
    const dd = document.createElement("dd");
    dd.innerHTML = v;
    dl.append(dt, dd);
  });
  return dl;
}

function para(text) {
  const p = document.createElement("p");
  p.className = "hint";
  p.style.marginTop = "10px";
  p.textContent = text;
  return p;
}

function bitChip(label, bits, sub) {
  const el = document.createElement("div");
  el.className = "bit-chip";
  el.innerHTML = `
    <span class="bit-label">${escapeHtml(label)}</span>
    <code>${escapeHtml(bits)}</code>
    <span class="bit-sub">${escapeHtml(sub)}</span>`;
  return el;
}

function roundCard(num, name, value, note) {
  const el = document.createElement("div");
  el.className = "round-card";
  el.innerHTML = `
    <div class="round-method">
      <span class="round-num">${num}</span>
      <h4>${escapeHtml(name)}</h4>
    </div>
    <div class="round-value">${escapeHtml(value)}</div>
    <div class="round-note">${escapeHtml(note)}</div>`;
  return el;
}

function steps(text) {
  const el = document.createElement("div");
  el.className = "steps";
  el.textContent = text || "No steps produced.";
  return el;
}

function trace(text, summary) {
  const el = document.createElement("details");
  el.className = "trace";
  el.innerHTML = `<summary>${escapeHtml(summary)}</summary>`;
  el.appendChild(steps(text));
  return el;
}
