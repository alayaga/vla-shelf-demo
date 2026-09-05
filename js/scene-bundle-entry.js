import * as THREE from "../lib/three/three.module.js";
import { OrbitControls } from "../lib/three/examples/jsm/controls/OrbitControls.js";

class SceneMode {
  constructor(rootEl) {
    this.rootEl = rootEl;
    this.frames = [];
    this.playing = false;
    this.frameIdx = 0;
    this._raf = null;
    this._inited = false;
    this.active = false;
  }

  load(trajectory) {
    this.frames = trajectory.frames || [];
    if (!this.frames.length) throw new Error("empty trajectory");
    if (!this._inited) this._initScene();
    this._applyFrame(0);
  }

  _initScene() {
    const w = this.rootEl.clientWidth || 800;
    const h = this.rootEl.clientHeight || 520;
    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x070b14);
    this.scene.fog = new THREE.FogExp2(0x070b14, 0.08);

    this.camera = new THREE.PerspectiveCamera(48, w / h, 0.05, 80);
    this.camera.position.set(3.5, 2.8, 3.5);

    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.setSize(w, h);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.rootEl.innerHTML = "";
    this.rootEl.appendChild(this.renderer.domElement);

    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.target.set(2.2, 1.0, 1.2);
    this.controls.enableDamping = true;

    const hemi = new THREE.HemisphereLight(0xbfd4ff, 0x101820, 0.9);
    this.scene.add(hemi);
    const dir = new THREE.DirectionalLight(0xffffff, 1.1);
    dir.position.set(4, 8, 2);
    this.scene.add(dir);

    const floor = new THREE.Mesh(
      new THREE.PlaneGeometry(12, 12),
      new THREE.MeshStandardMaterial({ color: 0x111827, roughness: 0.9 })
    );
    floor.rotation.x = -Math.PI / 2;
    this.scene.add(floor);

    const shelf = new THREE.Mesh(
      new THREE.BoxGeometry(1.2, 1.6, 0.35),
      new THREE.MeshStandardMaterial({ color: 0x334155, metalness: 0.2 })
    );
    shelf.position.set(2.35, 0.8, 1.25);
    this.scene.add(shelf);

    const counter = new THREE.Mesh(
      new THREE.BoxGeometry(1.8, 0.9, 0.6),
      new THREE.MeshStandardMaterial({ color: 0x475569 })
    );
    counter.position.set(0.8, 0.45, 0.2);
    this.scene.add(counter);

    this.robot = new THREE.Group();
    this.base = new THREE.Mesh(
      new THREE.CylinderGeometry(0.28, 0.28, 0.12, 32),
      new THREE.MeshStandardMaterial({ color: 0x64748b })
    );
    this.base.position.y = 0.06;
    this.robot.add(this.base);

    this.arm = new THREE.Group();
    this.arm.position.y = 0.12;
    this.robot.add(this.arm);

    const matArm = new THREE.MeshStandardMaterial({ color: 0x94a3b8, metalness: 0.35 });
    this.segments = [];
    let parent = this.arm;
    for (let i = 0; i < 6; i++) {
      const seg = new THREE.Group();
      const mesh = new THREE.Mesh(
        new THREE.BoxGeometry(0.08, 0.22, 0.08),
        matArm
      );
      mesh.position.y = 0.11;
      seg.add(mesh);
      if (i > 0) seg.position.y = 0.22;
      parent.add(seg);
      this.segments.push(seg);
      parent = seg;
    }

    this.gripper = new THREE.Mesh(
      new THREE.BoxGeometry(0.16, 0.04, 0.08),
      new THREE.MeshStandardMaterial({ color: 0xfbbf24 })
    );
    this.gripper.position.y = 0.24;
    parent.add(this.gripper);
    this.scene.add(this.robot);

    this.bottle = new THREE.Mesh(
      new THREE.CylinderGeometry(0.035, 0.035, 0.22, 20),
      new THREE.MeshStandardMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.95 })
    );
    this.scene.add(this.bottle);

    window.addEventListener("resize", () => this._onResize());
    this._inited = true;
    this._loop();
  }

  _onResize() {
    if (!this.renderer) return;
    const w = this.rootEl.clientWidth;
    const h = this.rootEl.clientHeight;
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
    this.renderer.setSize(w, h);
  }

  _applyFrame(idx) {
    const f = this.frames[idx];
    if (!f) return;
    const [bx, by, yaw] = f.base || [0, 0, 0];
    this.robot.position.set(bx, 0, by);
    this.robot.rotation.y = yaw;
    const q = f.arm_qpos || [];
    for (let i = 0; i < this.segments.length; i++) {
      this.segments[i].rotation.z = q[i] || 0;
    }
    const g = f.gripper ?? 0.04;
    this.gripper.scale.y = 0.5 + g * 8;
    const b = f.bottle || [2.32, 1.0, 1.29];
    this.bottle.position.set(b[0], b[2], b[1]);
  }

  seekTime(t, fps) {
    const idx = Math.min(this.frames.length - 1, Math.max(0, Math.round(t * fps)));
    if (idx !== this.frameIdx) {
      this.frameIdx = idx;
      this._applyFrame(idx);
    }
  }

  setPlaying(on) {
    this.playing = on;
  }

  setActive(on) {
    this.active = on;
  }

  _loop() {
    this._raf = requestAnimationFrame(() => this._loop());
    if (!this.active) return;
    this.controls?.update();
    this.renderer?.render(this.scene, this.camera);
  }
}

window.SceneMode = SceneMode;
