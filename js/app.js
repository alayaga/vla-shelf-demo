(function () {
  const INIT_FEEDBACK_MS = 400;
  const CMD_DELAY_MIN_MS = 400;
  const CMD_DELAY_MAX_MS = 950;
  const START_ACK_MS = 300;

  const CMD_UI = {
    start: {
      btn: "指令下发中…",
      badge: "指令中",
      result: "正在向控制主机发送任务启动指令…",
    },
    init: {
      btn: "复位指令下发中…",
      badge: "指令中",
      result: "正在向控制主机发送场景复位指令…",
    },
  };

  const state = {
    task: null,
    manifest: null,
    playing: false,
    time: 0,
    missionState: "idle",
    commandPending: null,
    lastPhaseId: null,
    lastSegIdx: null,
    initFeedbackTimer: null,
    commandTimer: null,
    startAckTimer: null,
  };

  let videoMode;
  let missionUi;

  const MISSION_LABELS = {
    idle: "就绪",
    running: "执行中",
    complete: "已完成",
  };

  async function loadData() {
    if (window.DEMO_DATA) {
      return {
        task: window.DEMO_DATA.task,
        manifest: window.DEMO_DATA.manifest,
      };
    }
    if (Demo.isFileProtocol) {
      throw new Error("演示数据未加载");
    }
    const [task, manifest] = await Promise.all([
      fetch("assets/meta/task.json").then((r) => r.json()),
      fetch("assets/meta/manifest.json").then((r) => r.json()),
    ]);
    return { task, manifest };
  }

  function validateManifest(manifest) {
    const durs = Demo.CAMERA_IDS.map((id) => {
      if (!manifest[id]) throw new Error(`manifest missing ${id}`);
      return manifest[id].duration_s;
    });
    if (Math.max(...durs) - Math.min(...durs) > 0.15) {
      throw new Error(`camera duration mismatch: ${durs.join(", ")}s`);
    }
  }

  function updateCycleDisplay(step) {
    const el = document.getElementById("status-cycle");
    if (el) el.textContent = `${String(step).padStart(3, "0")} / ${state.task.total_steps}`;

    const cycleStr = String(step).padStart(3, "0");
    for (const id of ["cam-cycle-scene", "cam-cycle-head", "cam-cycle-wrist"]) {
      const node = document.getElementById(id);
      if (node) node.textContent = cycleStr;
    }
  }

  function updatePhasePanel(t) {
    const phase = Demo.phaseAtTime(state.task, t);
    const segIdx = Demo.segmentIndexAtTime(state.task, t);
    const step = Demo.stepAtTime(state.task, t);

    missionUi?.setActiveSegmentIndex(segIdx);
    updateCycleDisplay(step);

    if (phase.id === state.lastPhaseId && state.lastSegIdx === segIdx) {
      Demo.updateSidePanel(state.task, phase.id, step);
      return;
    }
    state.lastPhaseId = phase.id;
    state.lastSegIdx = segIdx;
    Demo.updateSidePanel(state.task, phase.id, step);
  }

  function applyTime(t, opts = {}) {
    const { seekMedia = true, refreshPhase = true } = opts;
    state.time = Math.max(0, Math.min(state.task.total_time_s, t));
    if (refreshPhase) updatePhasePanel(state.time);
    if (seekMedia) videoMode.seek(state.time);
  }

  function paintPlayhead(t) {
    state.time = Math.max(0, Math.min(state.task.total_time_s, t));
    updatePhasePanel(state.time);
  }

  function randomCommandDelay() {
    return (
      CMD_DELAY_MIN_MS +
      Math.floor(Math.random() * (CMD_DELAY_MAX_MS - CMD_DELAY_MIN_MS + 1))
    );
  }

  function clearInitFeedbackTimer() {
    if (state.initFeedbackTimer) {
      clearTimeout(state.initFeedbackTimer);
      state.initFeedbackTimer = null;
    }
  }

  function clearStartAckTimer() {
    if (state.startAckTimer) {
      clearTimeout(state.startAckTimer);
      state.startAckTimer = null;
    }
  }

  function clearCommandTimer() {
    if (state.commandTimer) {
      clearTimeout(state.commandTimer);
      state.commandTimer = null;
    }
  }

  function setMissionState(next) {
    if (state.commandPending) return;

    state.missionState = next;

    document.body.classList.remove(
      "mission-idle",
      "mission-running",
      "mission-complete"
    );
    document.body.classList.add(`mission-${next}`);

    const badge = document.getElementById("status-task-state");
    if (badge) {
      badge.textContent = MISSION_LABELS[next] || next;
      badge.dataset.state = next;
    }

    const startBtn = document.getElementById("btn-start-task");
    const initBtn = document.getElementById("btn-init-scene");
    if (startBtn) {
      if (next === "idle") {
        startBtn.disabled = false;
        startBtn.classList.remove("is-busy");
        startBtn.textContent = "开始任务";
        startBtn.removeAttribute("aria-busy");
      } else {
        startBtn.disabled = true;
        startBtn.classList.add("is-busy");
        startBtn.textContent = "任务进行中";
        startBtn.removeAttribute("aria-busy");
      }
    }
    if (initBtn) {
      initBtn.disabled = false;
      initBtn.classList.remove("is-pending");
      initBtn.textContent = "初始化场景";
      initBtn.removeAttribute("aria-busy");
    }
  }

  function setCommandPending(kind) {
    const ui = CMD_UI[kind];
    if (!ui) return;

    state.commandPending = kind;
    document.body.classList.add("command-pending");

    const badge = document.getElementById("status-task-state");
    if (badge) {
      badge.textContent = ui.badge;
      badge.dataset.state = "pending";
    }

    const startBtn = document.getElementById("btn-start-task");
    const initBtn = document.getElementById("btn-init-scene");
    if (startBtn) {
      startBtn.disabled = true;
      startBtn.classList.remove("is-busy");
      if (kind === "start") {
        startBtn.classList.add("is-pending");
        startBtn.textContent = ui.btn;
        startBtn.setAttribute("aria-busy", "true");
      } else {
        startBtn.classList.remove("is-pending");
        startBtn.removeAttribute("aria-busy");
      }
    }
    if (initBtn) {
      initBtn.disabled = true;
      if (kind === "init") {
        initBtn.classList.add("is-pending");
        initBtn.textContent = ui.btn;
        initBtn.setAttribute("aria-busy", "true");
      } else {
        initBtn.classList.remove("is-pending");
        initBtn.removeAttribute("aria-busy");
      }
    }

    Demo.setCommandPending(kind);
  }

  function clearCommandPending() {
    state.commandPending = null;
    document.body.classList.remove("command-pending");
    clearCommandTimer();
  }

  function dispatchCommand(kind, executeFn) {
    if (state.commandPending) return;

    clearCommandTimer();
    clearInitFeedbackTimer();
    clearStartAckTimer();

    setCommandPending(kind);
    state.commandTimer = setTimeout(() => {
      state.commandTimer = null;
      executeFn();
    }, randomCommandDelay());
  }

  function startPlayback() {
    state.playing = true;
    Demo.setMissionRunning(state.task);
    videoMode.play();
  }

  function stopPlayback() {
    state.playing = false;
    videoMode.pause();
  }

  function executeInitScene() {
    clearCommandPending();
    Demo.setCommandAck("init");

    stopPlayback();
    videoMode.clearFocus();
    videoMode.reset();
    applyTime(0, { seekMedia: true, refreshPhase: true });
    missionUi?.reset();
    state.lastPhaseId = null;
    state.lastSegIdx = null;

    const resultBox = document.getElementById("result-box");
    if (resultBox) resultBox.textContent = "场景复位中…";

    state.initFeedbackTimer = setTimeout(() => {
      state.initFeedbackTimer = null;
      if (resultBox) {
        resultBox.textContent = "场景已就绪 · 等待开始任务";
      }
    }, INIT_FEEDBACK_MS);

    setMissionState("idle");
  }

  function executeStartTask() {
    clearCommandPending();
    setMissionState("running");
    Demo.setCommandAck("start");

    clearStartAckTimer();
    state.startAckTimer = setTimeout(() => {
      state.startAckTimer = null;
      startPlayback();
    }, START_ACK_MS);
  }

  function onInitSceneClick() {
    if (state.commandPending) return;
    dispatchCommand("init", executeInitScene);
  }

  function onStartTaskClick() {
    if (state.missionState !== "idle" || state.commandPending) return;
    dispatchCommand("start", executeStartTask);
  }

  function onMissionComplete() {
    stopPlayback();
    paintPlayhead(state.task.total_time_s);
    missionUi?.setAllDone();
    Demo.setMissionComplete(state.task);
    setMissionState("complete");
  }

  function bindPlayback() {
    videoMode.master.addEventListener("timeupdate", () => {
      if (!state.playing) return;
      videoMode.syncToMaster(false);
      const t = videoMode.getTime();
      if (t >= state.task.total_time_s - 0.04) {
        onMissionComplete();
        return;
      }
      paintPlayhead(t);
    });

    videoMode.master.addEventListener("ended", () => {
      if (state.playing) onMissionComplete();
    });
  }

  function bindMissionControls() {
    document.getElementById("btn-init-scene")?.addEventListener("click", onInitSceneClick);
    document.getElementById("btn-start-task")?.addEventListener("click", onStartTaskClick);
  }

  async function init() {
    videoMode = new Demo.VideoMode();

    try {
      const data = await loadData();
      state.task = data.task;
      state.manifest = data.manifest;
    } catch (err) {
      const mode = document.getElementById("status-mode");
      if (mode) mode.textContent = "ERR";
      document.getElementById("result-box").textContent = `系统初始化失败：${err.message}`;
      return;
    }

    await Demo.loadTrajectory();

    missionUi = Demo.buildMissionPipeline(
      document.getElementById("mission-pipeline"),
      state.task
    );
    missionUi.reset();

    try {
      await videoMode.load(state.manifest);
      validateManifest(state.manifest);
    } catch (err) {
      document.getElementById("result-box").textContent = `相机信号未连接：${err.message}`;
      return;
    }

    bindPlayback();
    bindMissionControls();
    Demo.bindVideoLayout();
    applyTime(0, { seekMedia: true, refreshPhase: true });
    setMissionState("idle");
    const resultBox = document.getElementById("result-box");
    if (resultBox) resultBox.textContent = "场景已就绪 · 等待开始任务";
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
