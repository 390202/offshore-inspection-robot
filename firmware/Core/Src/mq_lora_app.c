#include "mq_lora_app.h"
#include "main.h"

#define MQ_DEVICE_ID              1U
#define MQ_SAMPLE_PERIOD_MS       2000U
#define MQ_DEBOUNCE_DELAY_MS      20U

/*
 * The MQ modules are used through their digital comparator output (DO).
 * DO = 0 means the concentration is above the threshold set by the module.
 * DO = 1 means the concentration is below that threshold.
 *
 * PA12 = MQ5 DO, PB12 = MQ6 DO, PB9 = MQ8 DO.
 */
#define LORA_FRAME_LENGTH         22U
#define LORA_FRAME_SOF_0          0xAAU
#define LORA_FRAME_SOF_1          0x55U
#define LORA_FRAME_VERSION        1U
#define LORA_FRAME_TYPE_SENSORS   0x10U

#define STATUS_UART_ERROR          0x02U
#define STATUS_PREHEAT             0x04U

static UART_HandleTypeDef *s_uart;
static uint16_t s_sequence;
static uint32_t s_last_sample_tick;
static uint8_t s_uart_error;

static void PutU16Le(uint8_t *destination, uint16_t value)
{
  destination[0] = (uint8_t)(value & 0xFFU);
  destination[1] = (uint8_t)((value >> 8) & 0xFFU);
}

static uint16_t Crc16CcittFalse(const uint8_t *data, uint32_t length)
{
  uint16_t crc = 0xFFFFU;
  uint32_t i;
  uint8_t bit;

  for (i = 0U; i < length; ++i)
  {
    crc ^= (uint16_t)((uint16_t)data[i] << 8);
    for (bit = 0U; bit < 8U; ++bit)
    {
      if ((crc & 0x8000U) != 0U)
      {
        crc = (uint16_t)((crc << 1) ^ 0x1021U);
      }
      else
      {
        crc = (uint16_t)(crc << 1);
      }
    }
  }

  return crc;
}

static void ReadDigitalSensors(uint8_t triggered[3])
{
  GPIO_PinState first[3];
  GPIO_PinState second[3];
  /* Frame order: MQ5, MQ6, MQ8. Each input has its own GPIO port. */
  GPIO_TypeDef * const ports[3] = {MQ5_DO_GPIO_Port, MQ6_DO_GPIO_Port, MQ8_DO_GPIO_Port};
  const uint16_t pins[3] = {MQ5_DO_Pin, MQ6_DO_Pin, MQ8_DO_Pin};
  uint32_t i;

  for (i = 0U; i < 3U; ++i)
  {
    first[i] = HAL_GPIO_ReadPin(ports[i], pins[i]);
  }

  /* Same purpose as the delay and second read in the original 8051 code. */
  HAL_Delay(MQ_DEBOUNCE_DELAY_MS);

  for (i = 0U; i < 3U; ++i)
  {
    second[i] = HAL_GPIO_ReadPin(ports[i], pins[i]);
    /* 1 means the corresponding MQ concentration exceeded its threshold. */
    triggered[i] = (first[i] == GPIO_PIN_RESET &&
                   second[i] == GPIO_PIN_RESET) ? 1U : 0U;
  }
}

static void SendSensorFrame(const uint8_t triggered[3], uint8_t status)
{
  uint8_t frame[LORA_FRAME_LENGTH];
  uint16_t crc;
  uint32_t i;

  frame[0] = LORA_FRAME_SOF_0;
  frame[1] = LORA_FRAME_SOF_1;
  frame[2] = LORA_FRAME_VERSION;
  frame[3] = MQ_DEVICE_ID;
  frame[4] = LORA_FRAME_TYPE_SENSORS;
  PutU16Le(&frame[5], s_sequence);

  /*
   * Keep the existing 22-byte layout for LoRa/server compatibility.
   * raw[0..2] now contain digital states: 0 = normal, 1 = over-threshold.
   * The former voltage fields are zero because ADC sampling is not used.
   */
  for (i = 0U; i < 3U; ++i)
  {
    PutU16Le(&frame[7U + (i * 2U)], triggered[i]);
    PutU16Le(&frame[13U + (i * 2U)], 0U);
  }

  if (HAL_GetTick() < 86400000U)
  {
    status |= STATUS_PREHEAT;
  }
  frame[19] = (uint8_t)(status | s_uart_error);
  s_uart_error = 0U;

  crc = Crc16CcittFalse(&frame[2], 18U);
  PutU16Le(&frame[20], crc);

  if (HAL_UART_Transmit(s_uart, frame, LORA_FRAME_LENGTH, 1000U) != HAL_OK)
  {
    s_uart_error = STATUS_UART_ERROR;
  }

  ++s_sequence;
}

void MqLoRaApp_Init(UART_HandleTypeDef *uart)
{
  s_uart = uart;
  s_sequence = 0U;
  s_uart_error = 0U;
  s_last_sample_tick = HAL_GetTick() - MQ_SAMPLE_PERIOD_MS;
}

void MqLoRaApp_Process(void)
{
  uint8_t triggered[3] = {0U, 0U, 0U};

  if ((HAL_GetTick() - s_last_sample_tick) < MQ_SAMPLE_PERIOD_MS)
  {
    return;
  }

  s_last_sample_tick = HAL_GetTick();
  ReadDigitalSensors(triggered);
  SendSensorFrame(triggered, 0U);
}
