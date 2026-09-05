window.Demo = window.Demo || {};

Demo.SEGMENT_LABELS = Demo.SEGMENT_LABELS || {
  code_pre_grasp: "导航到站",
  vla_grasp: "VLA 抓取",
  code_transport: "搬运",
  vla_place: "VLA 放置",
};

Demo.buildMissionPipeline = function buildMissionPipeline(container, task) {
  container.innerHTML = "";
  const steps = [];

  for (const seg of task.segments) {
    const li = document.createElement("li");
    li.className = `mission-step ${seg.control}`;
    li.dataset.segmentId = seg.id || seg.label_zh;
    const name = Demo.SEGMENT_LABELS[seg.id] || seg.label_zh;
    li.innerHTML = `<span class="step-marker"></span><span class="step-body"><strong>${name}</strong><span>${seg.control.toUpperCase()}</span></span>`;
    container.appendChild(li);
    steps.push(li);
  }

  return {
    setActiveSegmentIndex(idx) {
      steps.forEach((el, i) => {
        el.classList.remove("is-active", "is-done");
        if (i < idx) el.classList.add("is-done");
        else if (i === idx) el.classList.add("is-active");
      });
    },
    setAllDone() {
      steps.forEach((el) => {
        el.classList.remove("is-active");
        el.classList.add("is-done");
      });
    },
    reset() {
      steps.forEach((el) => el.classList.remove("is-active", "is-done"));
      if (steps[0]) steps[0].classList.add("is-active");
    },
  };
};

Demo.segmentIndexAtTime = function segmentIndexAtTime(task, t) {
  for (let i = task.segments.length - 1; i >= 0; i -= 1) {
    const seg = task.segments[i];
    if (t >= seg.time_start - 1e-6) return i;
  }
  return 0;
};

Demo.phaseAtTime = function phaseAtTime(task, t) {
  for (const p of task.phases) {
    if (t >= p.time_start && t <= p.time_end + 1e-6) return p;
  }
  if (t < 0.001) return task.phases[0];
  return task.phases[task.phases.length - 1];
};

Demo.stepAtTime = function stepAtTime(task, t) {
  return Math.min(task.total_steps, Math.max(0, Math.round(t * task.fps)));
};

Demo.CONTROL_DESC = {
  code: "Code · 导航 / 折叠 / 搬运",
  vla: "VLA · 抬臂 / 抓取 / 放置",
};

Demo.updateSidePanel = function updateSidePanel(task, phaseName, step) {
  const control = Demo.controlForPhase(phaseName);
  const label = Demo.PHASE_LABELS[phaseName] || phaseName;

  document.body.classList.remove("control-code", "control-vla");
  document.body.classList.add(`control-${control}`);

  const modeEl = document.getElementById("status-mode");
  if (modeEl) modeEl.textContent = control.toUpperCase();

  const badge = document.getElementById("window-control-label");
  if (badge) badge.textContent = control.toUpperCase();

  document.getElementById("window-phase-label").textContent = label;

  const card = document.getElementById("window-card");
  card.classList.remove("code", "vla");
  card.classList.add(control);

  document.getElementById("window-detail").textContent =
    control === "vla"
      ? phaseName === "ARM_RAISE" || phaseName === "GRASP_CLOSE"
        ? task.instructions.grasp
        : task.instructions.place
      : Demo.CONTROL_DESC.code;

  const skill =
    phaseName === "ARM_RAISE" || phaseName === "GRASP_CLOSE"
      ? "grasp"
      : phaseName === "PLACE" || phaseName === "RELEASE"
        ? "place"
        : "—";

  document.getElementById("vla-skill").textContent = skill;
  document.getElementById("vla-instruction").textContent =
    skill === "grasp"
      ? task.instructions.grasp
      : skill === "place"
        ? task.instructions.place
        : "当前由 Code 控制";

  const fsm = document.getElementById("fsm-list");
  fsm.innerHTML = task.phases
    .filter((p) => p.control === "code")
    .map((p) => {
      const cls = p.id === phaseName ? "is-active" : "";
      return `<li class="${cls}">${Demo.PHASE_LABELS[p.id] || p.id}</li>`;
    })
    .join("");

  if (typeof step === "number") {
    Demo.updateTelemetryPanel(task, step, phaseName);
  }
};

Demo.setMissionComplete = function setMissionComplete(task) {
  const res = task.result || {};
  document.getElementById("result-box").textContent = res.success
    ? `任务完成 · grasp=${res.grasp_success} · place=${res.placement_success}`
    : "任务完成";
};

Demo.setMissionIdle = function setMissionIdle() {
  document.getElementById("result-box").textContent = "场景已就绪 · 等待开始任务";
};

Demo.setMissionRunning = function setMissionRunning(task) {
  document.getElementById("result-box").textContent =
    "任务执行中 · Code + VLA 混合控制";
};

Demo.COMMAND_PENDING_MSG = {
  start: "正在向控制主机发送任务启动指令…",
  init: "正在向控制主机发送场景复位指令…",
};

Demo.COMMAND_ACK_MSG = {
  start: "任务启动指令已确认 · 混合控制链路在线",
  init: "场景复位指令已确认",
};

Demo.setCommandPending = function setCommandPending(kind) {
  const msg = Demo.COMMAND_PENDING_MSG[kind];
  if (msg) document.getElementById("result-box").textContent = msg;
};

Demo.setCommandAck = function setCommandAck(kind) {
  const msg = Demo.COMMAND_ACK_MSG[kind];
  if (msg) document.getElementById("result-box").textContent = msg;
};
