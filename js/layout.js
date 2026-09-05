/** Fit video grid to stage — containers match 16:9 + 1:1+1:1, minimal letterbox. */
window.Demo = window.Demo || {};

Demo.layoutVideoGrid = function layoutVideoGrid() {
  const stage = document.getElementById("stage");
  const grid = document.getElementById("camera-grid");
  if (!stage || !grid) return;

  const padY = 10;
  const padX = 12;
  const gap = 10;
  const availW = stage.clientWidth - padX * 2;
  const availH = stage.clientHeight - padY * 2;

  if (availW <= 0 || availH <= 0) return;

  if (grid.classList.contains("focus-scene")) {
    const h = Math.floor(Math.min(availH - 8, availW * (9 / 16)));
    grid.style.width = `${Math.floor(h * (16 / 9))}px`;
    grid.style.setProperty("--scene-h", `${h}px`);
    return;
  }

  if (grid.classList.contains("focus-head") || grid.classList.contains("focus-hand")) {
    const side = Math.floor(Math.min(availW, availH - 8));
    grid.style.width = `${side}px`;
    grid.style.setProperty("--bot-h", `${side}px`);
    return;
  }

  const sceneH = availW * (9 / 16);
  const botH = availW * 0.5;
  const totalH = sceneH + botH + gap;
  const scale = totalH > availH ? availH / totalH : 1;
  const w = Math.floor(availW * scale);

  grid.style.width = `${w}px`;
  grid.style.setProperty("--scene-h", `${Math.floor(w * (9 / 16))}px`);
  grid.style.setProperty("--bot-h", `${Math.floor(w * 0.5)}px`);
};

Demo.bindVideoLayout = function bindVideoLayout() {
  const run = () => Demo.layoutVideoGrid();
  run();
  window.addEventListener("resize", run);
  if (document.fonts?.ready) document.fonts.ready.then(run);
};
