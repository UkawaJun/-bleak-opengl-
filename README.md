# python图形化蓝牙通信基站

本项目提供了使用python制作的一款“图形化数字基站”，其具备的功能有：

1. 运行该python程序后，可以**扫描**附近的**蓝牙设备**并连接。
2. 连接蓝牙设备后可以与该蓝牙设备进行收发信息的**通信**。
3. 该程序的UI右侧提供了一个基于opengl的**图形化**窗口，可以用于编写你自己的可视化程序，使用`glbegin()`和`glEnd()`绘制基本的三角形图元。

该程序还附带一份对应的arduino代码，可以将连接好蓝牙模块的arduino烧录这段代码，再运行提供的py脚本就可以实现蓝牙通信了。
___
**开发的初衷**:为了制作数字孪生类的程序，不仅需要软硬件之间的相互通信，还需要实现一定程度上的三维可视化功能，而本项目是以轻量化为目的而制，不需要使用Unity那样庞大的引擎，也不需要使用云端数据
库，主打的就是一个轻量化设计，仅靠python来实现的轻量型图形化程序。

## 例 1
如果你将提供的arduino代码烧录进你的arduino板，并连接好蓝牙模块后，你启动这个python程序，连接到你的蓝牙后发送`LIGHT`指令能够实现控制灯泡的亮灭。

## 例 2
二次开发的方法则是在程序的opengl主循环中加入你自己的gl绘制命令，如下例所示,插入这段代码后可以看到一个悬浮在空中的倒三角跳动的动画（效果参考下面的*效果图1*）：

```python

glPushMatrix()

glRotatef(pygame.time.get_ticks() * 0.05, 0, 0, 1) # 自转
glTranslatef( 0, 0, math.sin(pygame.time.get_ticks()*0.003) * 1)
glBegin(GL_TRIANGLES)
_basicHeight = 6
glColor3f(1, 1, 0); glVertex3f(0, 0, _basicHeight)
glColor3f(0, 1, 1); glVertex3f(0, 0.5, _basicHeight+2)
glColor3f(1, 0, 1); glVertex3f(0, -0.5,_basicHeight+2)
glEnd()
glPopMatrix()

glPushMatrix()

glRotatef(pygame.time.get_ticks() * 0.05, 0, 0, 1) # 自转
glCallList(_displayList)
glPopMatrix()
```
## 效果图1 - 二次开发后渲染stl模型的效果
<img width="1500" height="918" alt="a0082f0070d53a1653a3a8b6460b8b7c" src="https://github.com/user-attachments/assets/83966382-1d60-4e23-ad58-747e66bc10f0" />

## 效果图2 - 和模块通信连接与断开
<img width="834" height="525" alt="f145265b7131d736678f2260514498e3" src="https://github.com/user-attachments/assets/061fd793-9073-4230-bc3b-b451c1fb3c93" />


