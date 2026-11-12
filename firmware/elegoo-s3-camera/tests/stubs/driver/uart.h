#pragma once
constexpr int UART_NUM_2=2,ESP_OK=0;
inline bool uartTxBusy=false;
inline int uart_wait_tx_done(int,int){return uartTxBusy?-1:ESP_OK;}
