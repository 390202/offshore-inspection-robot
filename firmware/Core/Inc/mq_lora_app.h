#ifndef MQ_LORA_APP_H
#define MQ_LORA_APP_H

#ifdef __cplusplus
extern "C" {
#endif

#include "stm32f1xx_hal.h"

void MqLoRaApp_Init(UART_HandleTypeDef *uart);
void MqLoRaApp_Process(void);

#ifdef __cplusplus
}
#endif

#endif
