window.Demo = window.Demo || {};

const MASTER = "fetch_head";
const SYNC_THRESHOLD = 0.18;
const SYNC_MIN_INTERVAL_MS = 400;

Demo.VideoMode = class VideoMode {
  constructor() {
    this.videos = {};
    for (const id of Demo.CAMERA_IDS) {
      this.videos[id] = document.getElementById(`vid-${id}`);
    }
    this.master = this.videos[MASTER];
    this.slaves = Demo.CAMERA_IDS.filter((id) => id !== MASTER).map((id) => this.videos[id]);
    this.lastSyncAt = 0;
    this.grid = document.querySelector(".camera-grid");
    this._bindFocus();
  }

  async load(manifest) {
    for (const id of Demo.CAMERA_IDS) {
      const meta = manifest[id];
      const frame = document.getElementById(`frame-${id}`);
      if (meta?.width && meta?.height) {
        frame.style.aspectRatio = `${meta.width} / ${meta.height}`;
      }
      const v = this.videos[id];
      v.preload = id === MASTER ? "auto" : "metadata";
      v.src = Demo.assetUrl(`assets/videos/${id}.mp4`);
      v.load();
      await new Promise((resolve, reject) => {
        const onOk = () => resolve();
        const onErr = () =>
          reject(new Error(`${id} 相机信号未连接`));
        v.addEventListener("loadedmetadata", () => {
          Demo.layoutVideoGrid?.();
          resolve();
        }, { once: true });
        v.addEventListener("error", onErr, { once: true });
      });
    }
  }

  _bindFocus() {
    let clickTimer = null;
    for (const slot of document.querySelectorAll(".cam-slot")) {
      slot.addEventListener("click", () => {
        if (clickTimer) clearTimeout(clickTimer);
        clickTimer = setTimeout(() => {
          const cam = slot.dataset.cam;
          this.grid.classList.remove("focus-head", "focus-hand", "focus-scene");
          this.grid.classList.add(
            cam === "fetch_head"
              ? "focus-head"
              : cam === "fetch_hand"
                ? "focus-hand"
                : "focus-scene"
          );
          Demo.layoutVideoGrid?.();
        }, 220);
      });
      slot.addEventListener("dblclick", () => {
        if (clickTimer) clearTimeout(clickTimer);
        this.grid.classList.remove("focus-head", "focus-hand", "focus-scene");
        Demo.layoutVideoGrid?.();
      });
    }
  }

  /** Soft sync only when drift is large — avoids decode stutter from frequent seeks. */
  syncToMaster(force = false) {
    const now = performance.now();
    if (!force && now - this.lastSyncAt < SYNC_MIN_INTERVAL_MS) return;
    const t = this.master.currentTime;
    let corrected = false;
    for (const v of this.slaves) {
      const drift = Math.abs(v.currentTime - t);
      if (drift > SYNC_THRESHOLD) {
        v.currentTime = t;
        corrected = true;
      }
    }
    if (corrected || force) this.lastSyncAt = now;
  }

  seek(t) {
    const time = Math.max(0, t);
    for (const id of Demo.CAMERA_IDS) {
      this.videos[id].currentTime = time;
    }
    this.lastSyncAt = performance.now();
  }

  async play() {
    const t = this.master.currentTime;
    for (const v of this.slaves) {
      if (Math.abs(v.currentTime - t) > 0.05) v.currentTime = t;
    }
    const starts = Demo.CAMERA_IDS.map((id) => {
      const p = this.videos[id].play();
      return p?.catch ? p.catch(() => {}) : Promise.resolve();
    });
    await Promise.all(starts);
    this.syncToMaster(true);
  }

  pause() {
    for (const id of Demo.CAMERA_IDS) this.videos[id].pause();
  }

  reset() {
    this.pause();
    this.seek(0);
  }

  clearFocus() {
    if (!this.grid) return;
    this.grid.classList.remove("focus-head", "focus-hand", "focus-scene");
    Demo.layoutVideoGrid?.();
  }

  getTime() {
    return this.master.currentTime;
  }
};
