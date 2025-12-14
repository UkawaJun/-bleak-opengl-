#include <SoftwareSerial.h>

// 定义蓝牙连接的引脚: RX, TX
// Arduino Pin 2 连接 HC-08 TX
// Arduino Pin 3 连接 HC-08 RX

SoftwareSerial ble(2, 3); 
// 7 口连接灯泡
#define LIGHT 7
bool Light_state = false;
void setup() {
  // 初始化 USB 串口监视器
  Serial.begin(9600);
  pinMode(LIGHT, OUTPUT);
  Serial.println("Arduino Bluetooth System Started");
  Serial.println("By UkawaJun");
  // 初始化 HC-08 蓝牙串口 (默认波特率通常是 9600)
  ble.begin(9600); 
}

void loop() {
  // 1. 检查蓝牙是否发来了数据
  if (ble.available()) {
    // 读取字符串直到遇到换行或者超时
    // 注意：HC-08发来的数据可能没有换行符，所以这里为了简单用 readString
    String received = ble.readString();
    
    // 打印到 USB 串口监视器
    Serial.print("Received from Python: ");
    Serial.println(received);

    // 2. 判断逻辑
    // 为了防止收到 "XYZ\r\n" 这种情况，我们先去除首尾空格/换行
    received.trim(); 
    
    if (received == "TEST") {
      Serial.println("Command Match! Sending response...");
      // 3. 反向发送给 Python
      ble.print("Arduino command match function is good");
    }

    if (received == "LIGHT") {
      Serial.println("Command Match! Sending response...");
      
      Light_state = !(Light_state);
      if (Light_state) analogWrite(LIGHT,255);
      else  analogWrite(LIGHT,0);
      ble.print("开关灯泡成功");
    }
    
    
  }
  
}