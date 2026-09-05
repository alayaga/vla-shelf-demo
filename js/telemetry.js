window.Demo = window.Demo || {};

Demo._trajectoryFrames = null;
Demo._trajectoryLoading = null;

Demo.loadTrajectory = async function loadTrajectory() {
  if (Demo._trajectoryFrames) return Demo._trajectoryFrames;
  if (Demo._trajectoryLoading) return Demo._trajectoryLoading;
  if (Demo.isFileProtocol) return null;

  Demo._trajectoryLoading = fetch(Demo.assetUrl("assets/trajectory.json"))
    .then((r) => {
      if (!r.ok) throw new Error("trajectory fetch failed");
      return r.json();
    })
    .then((data) => {
      Demo._trajectoryFrames = data.frames || [];
      return Demo._trajectoryFrames;
    })
    .catch(() => null)
    .finally(() => {
      Demo._trajectoryLoading = null;
    });

  return Demo._trajectoryLoading;
};

Demo.frameAtStep = function frameAtStep(frames, step) {
  if (!frames?.length) return null;
  let lo = 0;
  let hi = frames.length - 1;
  while (lo < hi) {
    const mid = (lo + hi + 1) >> 1;
    if (frames[mid].step <= step) lo = mid;
    else hi = mid - 1;
  }
  return frames[lo];
};

Demo.fallbackTelemetry = function fallbackTelemetry(task, phaseId) {
  const phase = phaseId || task.phases[0]?.id;
  let gripper = 15;
  if (phase === "GRASP_CLOSE" || phase === "CARRY_RAISE" || phase === "NAV_TO_CHECKOUT" || phase === "PLACE") {
    gripper = 85;
  } else if (phase === "RELEASE") {
    gripper = 20;
  }
  return {
    gripper,
    base: [0, 0],
    phase: phaseId,
  };
};

Demo.updateTelemetryPanel = function updateTelemetryPanel(task, step, phaseId) {
  const frame =
    Demo.frameAtStep(Demo._trajectoryFrames, step) ||
    Demo.fallbackTelemetry(task, phaseId);

  const gripEl = document.getElementById("tel-gripper");
  const xEl = document.getElementById("tel-base-x");
  const yEl = document.getElementById("tel-base-y");
  const phaseEl = document.getElementById("tel-phase");

  if (gripEl) gripEl.textContent = `${Math.round(frame.gripper * 100)}%`;
  if (xEl && frame.base) xEl.textContent = frame.base[0].toFixed(2);
  if (yEl && frame.base) yEl.textContent = frame.base[1].toFixed(2);
  if (phaseEl) {
    phaseEl.textContent = Demo.PHASE_LABELS[phaseId] || phaseId || "—";
  }
};
