/** Shared phase / control metadata for Video + 3D tabs. */
window.Demo = window.Demo || {};

Demo.FPS = 20;

Demo.VLA_PHASES = new Set([
  "ARM_RAISE",
  "GRASP_CLOSE",
  "PLACE",
  "RELEASE",
]);

Demo.PHASE_LABELS = {
  NAV_TO_GRASP: "导航至抓取站",
  ARM_FOLD: "手臂折叠",
  ARM_RAISE: "抬臂对准",
  GRASP_CLOSE: "闭合抓取",
  RETRACT_OUT: "撤出货架",
  CARRY_RAISE: "携带抬升",
  NAV_TO_CHECKOUT: "导航至收银台",
  PLACE: "放置",
  RELEASE: "松开夹爪",
};

Demo.INSTRUCTIONS = {
  grasp: "Pick up the water bottle from the shelf.",
  place: "Place the water bottle onto the checkout counter.",
};

Demo.controlForPhase = function controlForPhase(phase) {
  return Demo.VLA_PHASES.has(phase) ? "vla" : "code";
};

Demo.CONTROL_COLORS = {
  code: "#5b8fb9",
  vla: "#c17f3a",
};

Demo.CAMERA_IDS = ["fetch_head", "fetch_hand", "checkout_camera"];

Demo.SEGMENT_LABELS = {
  code_pre_grasp: "导航到站",
  vla_grasp: "VLA 抓取",
  code_transport: "搬运",
  vla_place: "VLA 放置",
};

Demo.CAMERA_LABELS = {
  fetch_head: "Head Camera",
  fetch_hand: "Wrist Camera",
  checkout_camera: "Scene Camera",
};
