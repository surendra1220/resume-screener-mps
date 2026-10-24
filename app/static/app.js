"use strict";
const $ = (s) => document.querySelector(s);
const state = {
  jd: null,
  defaults: null,
  resume: null,
  reviewed: true,
  report: null,
  busy: 0,
  jdGeneration: 0,
  resumeGeneration: 0,
  revision: 0,
};
function el(tag, text, cls) {
  const n = document.createElement(tag);
  if (text !== undefined) n.textContent = text;
  if (cls) n.className = cls;
  return n;
}
function notify(text, type = "") {
  const n = $("#notice");
  n.textContent = text;
  n.className = "notice " + type;
}
async function api(url, options = {}) {
  const r = await fetch(url, options);
  let data;
  try {
    data = await r.json();
  } catch {
    throw Error(
      "The server returned an unreadable response. Check that the app is running.",
    );
  }
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : "Please check the document and requirement fields.",
    );
  return data;
}
function ready() {
  $("#analyze-button").disabled =
    !!state.busy || !state.resume || !state.jd || !state.reviewed;
  $("#analyze-button").textContent = state.busy
    ? "Processing…"
    : !state.reviewed
      ? "Review JD to continue →"
      : "Screen candidate →";
}
function invalidate() {
  state.revision++;
  state.report = null;
  $("#report-panel").classList.add("hidden");
  $("#empty-state").classList.remove("hidden");
}
function view(name) {
  document.querySelectorAll(".view").forEach((n) => n.classList.add("hidden"));
  $(
    "#" +
      (name === "screen"
        ? "screen"
        : name === "requirements"
          ? "requirements"
          : "method") +
      "-view",
  ).classList.remove("hidden");
  document
    .querySelectorAll(".nav")
    .forEach((n) => n.classList.toggle("active", n.dataset.view === name));
  $("#breadcrumb").textContent =
    name === "screen"
      ? "Candidate screening"
      : name === "requirements"
        ? "Job requirements"
        : "Scoring methodology";
  if (name === "requirements") renderEditor();
}
document
  .querySelectorAll("[data-view]")
  .forEach((n) => n.addEventListener("click", () => view(n.dataset.view)));
function jdSummary() {
  if (!state.jd) return;
  const a = state.jd.requirements.filter(
    (r) => r.category === "Mandatory",
  ).length;
  $("#jd-summary").textContent =
    `${a} mandatory · ${state.jd.requirements.length - a} good to have`;
  $("#jd-source").textContent = state.jd.text;
  $("#step-review").classList.toggle("current", state.reviewed);
  ready();
}
$("#default-toggle").addEventListener("click", () => {
  state.jdGeneration++;
  state.jd = structuredClone(state.defaults);
  state.reviewed = true;
  $("#default-panel").classList.remove("hidden");
  $("#jd-drop").classList.add("hidden");
  $("#default-toggle").classList.add("selected");
  $("#custom-toggle").classList.remove("selected");
  invalidate();
  jdSummary();
});
$("#custom-toggle").addEventListener("click", () => {
  $("#default-panel").classList.add("hidden");
  $("#jd-drop").classList.remove("hidden");
  $("#default-toggle").classList.remove("selected");
  $("#custom-toggle").classList.add("selected");
  state.jdGeneration++;
  state.jd = null;
  state.reviewed = false;
  invalidate();
  $("#jd-summary").textContent = "Upload a JD to extract draft requirements";
  ready();
});
async function upload(file, kind) {
  if (!file) return;
  if (file.size > 10 * 1024 * 1024) {
    notify(
      "This file exceeds 10 MB. Please upload a smaller document.",
      "error",
    );
    return;
  }
  const generation =
    kind === "jd" ? ++state.jdGeneration : ++state.resumeGeneration;
  state.busy++;
  if (kind === "jd") {
    state.jd = null;
    state.reviewed = false;
  } else {
    state.resume = null;
  }
  invalidate();
  ready();
  const form = new FormData();
  form.append("file", file);
  try {
    const data = await api(kind === "jd" ? "/api/parse-jd" : "/api/extract", {
      method: "POST",
      body: form,
    });
    if (
      generation !==
      (kind === "jd" ? state.jdGeneration : state.resumeGeneration)
    )
      return;
    if (kind === "jd") {
      state.jd = data;
      state.reviewed = false;
      $("#jd-drop strong").textContent = data.filename;
      $("#jd-drop>span:not(.upload-symbol)").textContent =
        "Draft extracted · review required";
      jdSummary();
      notify(
        "JD extracted. Review the draft requirements before screening.",
        "success",
      );
      view("requirements");
    } else {
      state.resume = data;
      $("#resume-filename").textContent = data.filename;
      $("#resume-caption").textContent =
        `✓ ${data.text.length.toLocaleString()} characters extracted · click to replace`;
      $("#resume-status").textContent = "✓ Resume ready for evidence review";
      $("#preview-button").classList.remove("hidden");
      notify(
        "Resume loaded. You can review extracted text before screening.",
        "success",
      );
    }
  } catch (e) {
    notify(e.message, "error");
  } finally {
    state.busy--;
    ready();
  }
}
for (const kind of ["jd", "resume"]) {
  const input = $("#" + kind + "-file"),
    zone = $("#" + kind + "-drop");
  input.addEventListener("change", () => upload(input.files[0], kind));
  zone.addEventListener("dragover", (e) => {
    e.preventDefault();
    zone.classList.add("dragging");
  });
  zone.addEventListener("dragleave", () => zone.classList.remove("dragging"));
  zone.addEventListener("drop", (e) => {
    e.preventDefault();
    zone.classList.remove("dragging");
    upload(e.dataTransfer.files[0], kind);
  });
}
$("#review-button").addEventListener("click", () => view("requirements"));
$("#preview-button").addEventListener("click", () => {
  $("#resume-text").value = state.resume.text;
  $("#text-dialog").showModal();
});
$("#close-dialog").addEventListener("click", () => $("#text-dialog").close());
$("#save-text").addEventListener("click", () => {
  const text = $("#resume-text").value.trim();
  if (text.length < 40 || text.length > 120000) {
    alert("Resume text must contain 40–120,000 characters.");
    return;
  }
  state.resume.text = text;
  invalidate();
  $("#text-dialog").close();
  notify(
    "Extracted text updated. Run screening to apply the corrections.",
    "success",
  );
});
function field(label, value, onchange, tag = "input") {
  const wrap = el("label", label),
    input = el(tag);
  input.value = value;
  if (tag === "textarea") input.rows = 2;
  input.addEventListener("change", () => {
    onchange(input.value);
    state.reviewed = false;
    invalidate();
    ready();
  });
  wrap.append(input);
  return wrap;
}
function renderEditor() {
  const root = $("#requirements-editor");
  root.replaceChildren();
  if (!state.jd) {
    root.append(
      el("p", "Upload a job description or select the default JD first."),
    );
    return;
  }
  $("#review-warning").textContent = state.jd.needs_review
    ? "Custom JD extraction is a draft. Check every requirement, alternative, category, and omitted condition. Alternatives use OR; required facets use AND. This engine uses literal terms for custom JDs."
    : "The supplied SDET JD has been curated. Alternatives and knowledge exceptions follow its explicit wording. Review or adjust the benchmark below.";
  state.jd.requirements.forEach((r, i) => {
    const card = el("article", undefined, "card requirement-card"),
      row = el("div", undefined, "requirement-fields");
    row.append(field("Requirement", r.name, (v) => (r.name = v)));
    const cat = el("label", "Category"),
      select = el("select");
    ["Mandatory", "Good to Have"].forEach((c) => {
      const opt = el("option", c);
      opt.selected = c === r.category;
      select.append(opt);
    });
    select.addEventListener("change", () => {
      r.category = select.value;
      state.reviewed = false;
      invalidate();
      jdSummary();
    });
    cat.append(select);
    row.append(cat);
    card.append(
      row,
      field(
        "Requirement description",
        r.description,
        (v) => (r.description = v),
        "textarea",
      ),
    );
    const source = el("div", undefined, "requirement-source");
    source.append(
      el("b", "Original JD source: "),
      el("span", r.source || "Reviewer-added requirement"),
    );
    card.append(
      source,
      field(
        "Accepted alternatives (comma-separated; any one may qualify)",
        r.alternatives.join(", "),
        (v) =>
          (r.alternatives = v
            .split(",")
            .map((x) => x.trim())
            .filter(Boolean)),
      ),
    );
    card.append(
      field(
        "Required facets (semicolon-separated; all required in one work statement; | means OR)",
        r.all_of.join("; "),
        (v) => {
          r.all_of = v
            .split(";")
            .map((x) => x.trim())
            .filter(Boolean);
          if (!r.id.startsWith("custom-"))
            r.id = "custom-edited-" + crypto.randomUUID().slice(0, 8);
        },
      ),
    );
    if (!r.id.startsWith("custom-") && r.all_of.length)
      card.append(
        el(
          "small",
          "Default JD uses audited matching patterns for these facets. Editing facets switches this requirement to literal matching.",
        ),
      );
    const actions = el("div", undefined, "requirement-actions"),
      knowledge = el("label"),
      check = el("input");
    check.type = "checkbox";
    check.checked = r.knowledge_ok;
    check.addEventListener("change", () => {
      r.knowledge_ok = check.checked;
      state.reviewed = false;
      invalidate();
      ready();
    });
    knowledge.append(
      check,
      document.createTextNode(
        " JD explicitly accepts knowledge/minimal experience",
      ),
    );
    const del = el("button", "Remove requirement", "delete-requirement");
    del.addEventListener("click", () => {
      state.jd.requirements.splice(i, 1);
      state.reviewed = false;
      invalidate();
      renderEditor();
      jdSummary();
    });
    actions.append(knowledge, del);
    card.append(actions);
    root.append(card);
  });
  $("#jd-source").textContent = state.jd.text;
}
$("#add-requirement").addEventListener("click", () => {
  if (!state.jd || state.jd.requirements.length >= 60) return;
  state.jd.requirements.push({
    id: "custom-" + crypto.randomUUID().slice(0, 8),
    name: "New requirement",
    category: "Mandatory",
    description: "Describe the job requirement",
    source: "",
    alternatives: [],
    all_of: [],
    weight: 1,
    knowledge_ok: false,
  });
  state.reviewed = false;
  invalidate();
  renderEditor();
  jdSummary();
});
$("#approve-jd").addEventListener("click", () => {
  document.activeElement.blur();
  if (!state.jd || !state.jd.requirements.length) {
    alert("At least one requirement is needed.");
    return;
  }
  if (
    state.jd.requirements.some(
      (r) =>
        !r.name.trim() ||
        !r.description.trim() ||
        (!r.alternatives.length && r.id !== "experience"),
    )
  ) {
    alert(
      "Each requirement needs a name, description, and at least one accepted term.",
    );
    return;
  }
  state.reviewed = true;
  jdSummary();
  view("screen");
  notify(
    "Requirements approved. The evidence matrix will use this benchmark.",
    "success",
  );
});
$("#analyze-button").addEventListener("click", async () => {
  if (state.busy || !state.jd || !state.resume || !state.reviewed) return;
  state.busy++;
  const revision = state.revision;
  ready();
  notify("Reviewing project context, required facets, and evidence gaps…");
  try {
    const report = await api("/api/analyze", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        resume_text: state.resume.text,
        jd_text: state.jd.text,
        requirements: state.jd.requirements,
        jd_label: state.jd.label,
        candidate_label: state.resume.filename.replace(/\.[^.]+$/, ""),
        resume_filename: state.resume.filename,
      }),
    });
    if (revision !== state.revision) {
      notify(
        "Documents or requirements changed while screening. Run screening again with the updated inputs.",
      );
      return;
    }
    state.report = report;
    renderReport();
    notify(
      "Screening complete. Review evidence and mandatory gaps before making a decision.",
      "success",
    );
    $("#report-panel").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    notify(e.message, "error");
  } finally {
    state.busy--;
    ready();
  }
});
function renderReport() {
  const r = state.report;
  $("#empty-state").classList.add("hidden");
  $("#report-panel").classList.remove("hidden");
  $("#report-candidate").textContent = r.candidate;
  $("#report-meta").textContent =
    `${r.jd_label} · ${new Date(r.generated_at).toLocaleString()} · Report ${r.id}`;
  $("#score").textContent = r.score;
  $("#score-fill").style.width = r.score + "%";
  $("#category-score").textContent =
    `Mandatory ${r.scores.Mandatory ?? "N/A"}% · Good to Have ${r.scores["Good to Have"] ?? "N/A"}%`;
  $("#verdict").textContent = r.recommendation;
  $("#gap-summary").textContent = r.mandatory_gaps.length
    ? `${r.mandatory_gaps.length} mandatory requirements need review: ${r.mandatory_gaps.join("; ")}.`
    : "Every mandatory requirement has supporting resume evidence. Verify claims and implementation depth in interview.";
  $("#export-html").href = `/api/reports/${r.download_id}/html`;
  $("#export-pdf").href = `/api/reports/${r.download_id}/pdf`;
  $("#step-report").classList.add("current");
  const counts = $("#counts");
  counts.replaceChildren();
  const cls = ["matched", "partial", "claimed", "missing"];
  Object.entries(r.counts).forEach(([k, v], i) => {
    const n = el("span");
    n.append(
      el("i", undefined, "dot " + cls[i]),
      document.createTextNode(`${v} ${k}`),
    );
    counts.append(n);
  });
  $("#status-filter").value = "all";
  renderMatrix();
}
function renderMatrix() {
  const root = $("#matrix");
  root.replaceChildren();
  const filter = $("#status-filter").value;
  state.report.requirements
    .filter((r) => filter === "all" || r.status === filter)
    .forEach((r) => {
      const row = el("details", undefined, "evidence-row"),
        summary = el("summary");
      summary.append(
        el("span", r.name, "skill-name"),
        el("span", r.category, "category-label"),
        el("span", r.status, "status-badge status-" + r.status.split(" ")[0]),
      );
      row.append(summary);
      const detail = el("div", undefined, "evidence-detail"),
        jd = el("p");
      jd.append(
        el("b", "JD requirement: "),
        document.createTextNode(r.description),
      );
      detail.append(jd);
      r.evidence.forEach((u) => {
        const q = el("blockquote", u.quote);
        q.append(
          el(
            "cite",
            `${u.section} · Line ${u.line}${u.page ? " · " + u.page : ""}`,
          ),
        );
        detail.append(q);
      });
      if (!r.evidence.length)
        detail.append(el("p", "No supporting excerpt found."));
      detail.append(el("p", r.reason));
      const q = el("p");
      q.append(
        el("b", "Ask in interview: "),
        document.createTextNode(r.question),
      );
      detail.append(q);
      row.append(detail);
      root.append(row);
    });
  if (!root.children.length)
    root.append(
      el("p", "No requirements with this status.", "evidence-detail"),
    );
}
$("#status-filter").addEventListener("change", renderMatrix);
api("/api/default-jd")
  .then((data) => {
    state.defaults = structuredClone(data);
    state.jd = data;
    jdSummary();
  })
  .catch((e) => notify(e.message, "error"));
api("/api/health")
  .then((data) => {
    if (data.reference_available)
      $("#reference-button").classList.remove("hidden");
  })
  .catch(() => {});
$("#reference-button").addEventListener("click", async () => {
  try {
    state.report = await api("/api/reference-report");
    renderReport();
    $("#report-panel").scrollIntoView({ behavior: "smooth" });
  } catch (e) {
    notify(e.message, "error");
  }
});
