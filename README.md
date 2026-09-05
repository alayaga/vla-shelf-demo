# VLA 货架任务演示

浏览器端静态演示：货架取瓶场景的 **Code + VLA 混合控制** 任务监视界面。无需后端服务即可本地打开。

## 功能概览

- 三路相机画面（场景 / 头部 / 腕部），界面呈现为在线监视
- 任务控制：初始化场景、开始任务（含短时指令下发反馈）
- 右侧：任务流水线、VLA 指令、遥测与阶段列表
- 纯静态站点，不依赖额外服务进程

## 本地启动

**推荐**：双击 `start_demo.bat`，或直接用浏览器打开 `index.html`。

资源（视频、轨迹、元数据）均在本目录内，一般无需联网。

若提示缺少 `demo-data.js`，在项目根目录执行：

```bash
python tools/embed_demo_data.py
```

## 安全说明

- 连接远程服务器的主机、端口、账号、密码、SSH 密钥等，**只放在本机** `*.local.env` / `deploy.env` 或环境变量中。
- 仓库仅提供空模板：`tools/westc.local.env.example`、`deploy.env.example`。
- **切勿**把真实凭据提交到 Git，也勿写进 README。

## 目录结构

```text
.
├── index.html          # 入口页面
├── css/                # 样式
├── js/                 # 前端逻辑
├── assets/             # 视频、轨迹、元数据
├── tools/              # 本地辅助脚本与环境模板
├── deploy.ps1          # 部署入口（凭据走环境变量）
└── deploy.env.example  # 部署环境变量模板（无真实值）
```
