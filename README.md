# 海洋平台燃油管道泄漏巡检机械臂小车

## 目录

- `frontend/`：Vue 前端。
- `backend/`：Node.js 后端与 PostgreSQL 数据库接口。
- `arm-control/`：小车底盘与机械臂控制脚本及动作文件。
- `firmware/`：STM32 传感器与 LoRa 固件、Keil/CubeMX 工程及网关脚本。

此仓库由项目提供的三个源码压缩包整理而成，不包含论文和演示视频。

## 后端

在 PostgreSQL 中准备数据库和用户，参考 `backend/.env.example` 设置环境变量，
其中 `JWT_SECRET` 必须设置为随机密钥。示例文件仅供参考，程序不会自动读取 `.env`。
在 `backend` 目录运行 `npm ci`，随后运行 `npm start`。
原代码中固定的 JWT 签名密钥已移除；已部署系统应更换密钥并使旧令牌失效。

## 前端

在 `frontend` 目录运行 `npm ci` 和 `npm run dev`。默认代理到
`http://127.0.0.1:3000`，可通过启动前设置 `VITE_BACKEND_URL` 修改。

## 固件和机械臂

STM32 工程入口为 `firmware/MDK-ARM/USART.uvprojx` 和
`firmware/USART.ioc`，传感器接线和 LoRa 帧协议见
`firmware/docs/MQ_LORA_DEPLOYMENT.md`。
机械臂脚本依赖相应的 ROS 环境和硬件，实机运行前应检查配置及安全条件；
`forward_wait_left_demo.py --dry-run` 可仅输出动作计划。

本项目包含演示逻辑，不应未经安全审查就用于实际海上设施。
