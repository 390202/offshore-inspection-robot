# MQ5 / MQ6 / MQ8 数字采集与 LoRa 串口接线

## 1. 实际引脚分配

| 功能 | STM32F103C8T6 引脚 | 配置 |
| --- | --- | --- |
| MQ8 DO | PB9（B9） | 上拉输入，低电平触发 |
| MQ5 DO | PA12（A12） | 上拉输入，低电平触发 |
| MQ6 DO | PB12（B12） | 上拉输入，低电平触发 |
| 串口 TX | PA2（A2）/ USART2_TX | 复用推挽输出 |
| 串口 RX | PA3（A3）/ USART2_RX | 输入 |
| 原有辅助输入 | PA8 | 上拉输入 |
| SWD 下载调试 | PA13 / PA14 | SWDIO / SWCLK |

USART2 使用默认 PA2/PA3 引脚，不重映射。
串口参数：9600 bps、8 位数据、1 位停止位、无校验、无流控。

```text
MQ5 DO --> PA12
MQ6 DO --> PB12
MQ8 DO --> PB9

STM32 PA2 / TX --> LoRa 模块 RX
STM32 PA3 / RX <-- LoRa 模块 TX
STM32 GND     --- 模块 GND
```

MQ 模块按实际模块要求供电，与 MCU 和 LoRa 共地。
当前代码读取 DO，不采集 AO。DO 必须满足 MCU 输入电平要求；
若模块 DO 输出或上拉为 5 V，需要进行 3.3 V 电平适配。

## 2. 采集和发送

三路输入均使用上拉。每路读取两次，间隔 20 ms；两次均为低电平，
才判定为超过模块阈值。帧中 0 表示正常，1 表示超过阈值。
每 2 秒通过 USART2 发送一帧，数据字段顺序为 MQ5、MQ6、MQ8。

## 3. 串口帧格式

帧长 22 字节，多字节字段使用小端格式：

| 偏移 | 长度 | 字段 |
| --- | --- | --- |
| 0 | 2 | 帧头 AA 55 |
| 2 | 1 | 协议版本 01 |
| 3 | 1 | 设备 ID，默认 01 |
| 4 | 1 | 帧类型 10 |
| 5 | 2 | 递增序号 |
| 7 | 2 | MQ5 DO 状态：0 正常，1 超阈值 |
| 9 | 2 | MQ6 DO 状态：0 正常，1 超阈值 |
| 11 | 2 | MQ8 DO 状态：0 正常，1 超阈值 |
| 13 | 2 | 原第一路电压字段，固定 0 |
| 15 | 2 | 原第二路电压字段，固定 0 |
| 17 | 2 | 原第三路电压字段，固定 0 |
| 19 | 1 | 状态：bit0 保留，bit1 UART 错误，bit2 上电不足 24 h |
| 20 | 2 | CRC-16/CCITT-FALSE，覆盖偏移 2 到 19 |

服务端 raw 元组顺序也是 MQ5、MQ6、MQ8，CSV 第一通道列名为 mq5_*。
若有旧 CSV 使用 mq3_* 表头，请改用新的 CSV 文件，以免表头误标。
DO 只表示是否超过电位器设定阈值，不能换算为 ppm。

## 4. 网关服务器

将 server 目录复制到 Ubuntu 虚拟机，运行：

```bash
cd server
python3 lora_gateway_server.py --bind 0.0.0.0 --udp-port 5000 --tcp-port 5001 --csv lora_data.csv --json
```

网关将原始 22 字节帧通过 UDP 5000 或 TCP 5001 转发给服务器。
LoRa 两端需使用相同的频段、信道、速率和透明传输配置。

在另一个终端发送数字状态测试帧：

```bash
python3 lora_test_sender.py --host 127.0.0.1 --port 5000 --raw 0 1 0 --mv 0 0 0
```

预期输出包含 raw=(0, 1, 0)，表示 MQ6 超阈值，MQ5 和 MQ8 正常。

## 5. 工程文件

- Core/Inc/main.h：MQ5/MQ6/MQ8 的 GPIO 端口与引脚定义。
- Core/Src/main.c：GPIOA/GPIOB 时钟、DO 上拉输入、USART2 9600 8N1 初始化。
- Core/Src/mq_lora_app.c：按各自端口读取 PA12/PB12/PB9，消抖并发送数据。
- Core/Src/stm32f1xx_hal_msp.c：USART2 时钟、PA2 TX / PA3 RX 初始化和反初始化。
- USART.ioc：同步保存串口与三个 DO 的引脚、标签和上拉配置。
- MDK-ARM/USART.uvprojx：Keil 工程。
- server/lora_gateway_server.py：解码、数字报警状态和 CSV 输出。

重新使用 CubeMX 生成时保留用户代码。应用通过 MqLoRaApp_Init(&huart2)
使用 USART2。编译后仍需下载到 STM32，并检查实际硬件通信。
