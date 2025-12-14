import pygame
from pygame.locals import *
from OpenGL.GL import *
from OpenGL.GLU import *
import asyncio
import threading
import queue
import math
import time
from bleak import BleakScanner, BleakClient


# ==========================================
#自定义常量区
MOVE_SPEED = 0.2
UPDOWN_SPEED = 0.1
MAX_MESSAGES = 20
# ==========================================
# ==========================================
# 1. 蓝牙工作线程 (处理异步通信)
# ==========================================
class BluetoothWorker(threading.Thread):
    def __init__(self, cmd_queue, msg_queue):
        super().__init__()
        self.cmd_queue = cmd_queue  # 主线程发给蓝牙的指令
        self.msg_queue = msg_queue  # 蓝牙发给主线程的消息
        self.loop = None
        self.client = None
        self.running = True
        self.scan_results = []
        self.connected_device_name = None

    def run(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        self.loop.run_until_complete(self.main_loop())

    async def main_loop(self):
        while self.running:
            # 检查是否有指令
            try:
                cmd = self.cmd_queue.get(block=False)
                if cmd[0] == "SCAN":
                    await self.do_scan()
                elif cmd[0] == "CONNECT":
                    await self.do_connect(cmd[1])
                
                # ### 1. 判断断开指令 ###
                elif cmd[0] == "DISCONNECT":
                    await self.do_disconnect()
                
                elif cmd[0] == "SEND":
                    await self.do_send(cmd[1])
                elif cmd[0] == "CLOSE":
                    # 关闭线程前，也可以先尝试断开
                    if self.client: 
                        await self.do_disconnect()
                    self.running = False
            except queue.Empty:
                await asyncio.sleep(0.1)

    # ### 2. 执行断开的函数 ###
    async def do_disconnect(self):
        if self.client and self.client.is_connected:
            self.msg_queue.put(("[系统]", f"正在断开 {self.connected_device_name}..."))
            try:
                await self.client.disconnect()
                self.msg_queue.put(("[系统]", "已断开连接"))
            except Exception as e:
                self.msg_queue.put(("[系统]", f"断开失败: {e}"))
        else:
            self.msg_queue.put(("[系统]", "当前未连接任何设备"))
        
        # 清理状态，非常重要，否则下次连接会报错
        self.client = None
        self.connected_device_name = None

    async def do_scan(self):
        self.msg_queue.put(("[系统]", "正在扫描..."))
        devices = await BleakScanner.discover()
        # 过滤掉没有名字的设备
        self.scan_results = [d for d in devices if d.name]
        names = [d.name for d in self.scan_results]
        self.msg_queue.put(("SCAN_RESULT", names))
        self.msg_queue.put(("[系统]", f"扫描完成，找到 {len(names)} 个设备"))

    async def do_connect(self, name):
        # 如果当前已经连着别的，先断开
        if self.client and self.client.is_connected:
            await self.do_disconnect()

        target = next((d for d in self.scan_results if d.name == name), None)
        if not target:
            self.msg_queue.put(("[系统]", "未找到选中的设备"))
            return

        self.msg_queue.put(("[系统]", f"正在连接 {name}..."))
        try:
            self.client = BleakClient(target)
            await self.client.connect()
            self.connected_device_name = name
            self.msg_queue.put(("[系统]", f"已连接到 {name}"))
            
            # 开启通知监听
            UART_RX_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb" 
            await self.client.start_notify(UART_RX_UUID, self.notification_handler)
            
        except Exception as e:
            self.msg_queue.put(("[系统]", f"连接失败: {e}"))
            # 连接失败也要清理 self.client
            self.client = None

    def notification_handler(self, sender, data):
        text = data.decode('utf-8', errors='ignore')
        self.msg_queue.put(("[接收]", text))

    async def do_send(self, text):
        if self.client and self.client.is_connected:
            UART_TX_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"
            try:
                # 添加换行符并在编码前转为 bytes，response=False 提高速度
                data = text.encode('utf-8')
                await self.client.write_gatt_char(UART_TX_UUID, data, response=False)
                self.msg_queue.put(("[发送]", text))
            except Exception as e:
                self.msg_queue.put(("[系统]", f"发送失败: {e}"))
        else:
            self.msg_queue.put(("[系统]", "蓝牙未连接"))


"""【摄像机】3D 摄像机与渲染类"""
class Camera:
    #初始化
    def __init__(self):
        self.pos = [0, -10, 5] # 初始位置
        self.yaw = 0
        self.pitch = 30
 
    # update - 操作简单的 WSAD 移动 (相对于朝向)    
    def update(self, keys):
        # rad_yaw - 这个是摄像机的仰角
        rad_yaw = math.radians(self.yaw)
        dx = math.sin(rad_yaw) * 0.5
        dy = math.cos(rad_yaw) * 0.5
        
        if keys[K_w]:
            self.pos[0] += dx * MOVE_SPEED
            self.pos[1] += dy * MOVE_SPEED
        if keys[K_s]:
            self.pos[0] -= dx * MOVE_SPEED
            self.pos[1] -= dy * MOVE_SPEED
        if keys[K_a]:
            self.pos[0] -= dy * MOVE_SPEED
            self.pos[1] += dx * MOVE_SPEED
        if keys[K_d]:
            self.pos[0] += dy * MOVE_SPEED
            self.pos[1] -= dx * MOVE_SPEED
        if keys[K_SPACE]:
            self.pos[2] += UPDOWN_SPEED
        if keys[K_LSHIFT]:
            self.pos[2] -= UPDOWN_SPEED
            
    #计算相机的 视点 （三个向量就可以定义一个相机）
    def apply(self):
        glLoadIdentity()

        rad_yaw = math.radians(self.yaw)
        rad_pitch = math.radians(self.pitch)
        
        look_x = self.pos[0] + math.sin(rad_yaw) * math.cos(rad_pitch)
        look_y = self.pos[1] + math.cos(rad_yaw) * math.cos(rad_pitch)
        look_z = self.pos[2] + math.sin(rad_pitch)
        
        gluLookAt(self.pos[0], self.pos[1], self.pos[2],look_x, look_y, look_z,0, 0, 1) # Z轴向上

# ==========================================
# 3. 简易 UI 组件类 (为了不依赖 pygame_gui)
# ==========================================
class SimpleButton:
    def __init__(self, rect, text, color=(100, 100, 100)):
        self.rect = pygame.Rect(rect)
        self.text = text
        self.color = color
        self.font = pygame.font.SysFont("SimHei", 20) # 使用黑体支持中文

    def draw(self, screen):
        pygame.draw.rect(screen, self.color, self.rect)
        pygame.draw.rect(screen, (200, 200, 200), self.rect, 2)
        txt_surf = self.font.render(self.text, True, (255, 255, 255))
        screen.blit(txt_surf, (self.rect.x + 10, self.rect.y + 10))

    def is_clicked(self, pos):
        return self.rect.collidepoint(pos)

class SimpleInput:
    def __init__(self, rect):
        self.rect = pygame.Rect(rect)
        self.text = ""
        self.active = False
        self.font = pygame.font.SysFont("SimHei", 20)

    def handle_event(self, event):
        if event.type == MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == KEYDOWN and self.active:
            if event.key == K_RETURN:
                return self.text # 返回输入内容
            elif event.key == K_BACKSPACE:
                self.text = self.text[:-1]
            else:
                self.text += event.unicode
        return None

    def draw(self, screen):
        color = (255, 255, 255) if self.active else (200, 200, 200)
        pygame.draw.rect(screen, color, self.rect)
        pygame.draw.rect(screen, (0, 0, 0), self.rect, 2)
        txt_surf = self.font.render(self.text, True, (0, 0, 0))
        screen.blit(txt_surf, (self.rect.x + 5, self.rect.y + 5))

# ==========================================
# 4. 主程序
# ==========================================
def run_app():
    pygame.init()
    # 屏幕尺寸
    W, H = 1200, 720
    # 左侧 UI 宽度
    UI_WIDTH = 300
    
    screen = pygame.display.set_mode((W, H), DOUBLEBUF | OPENGL)
    pygame.display.set_caption("Python 蓝牙 3D 控制台")

    # 线程通信队列
    cmd_queue = queue.Queue()
    msg_queue = queue.Queue()
    
    # 启动蓝牙线程
    bt_thread = BluetoothWorker(cmd_queue, msg_queue)
    bt_thread.start()

    # 初始化 3D 摄像机
    camera = Camera()
    
    # UI 状态
    messages = []
    scan_list = []
    selected_device_idx = -1
    dropdown_open = False
    
    # UI 组件 (坐标需要根据 2D 绘制逻辑转换，稍后在 draw_2d_ui 中处理)
    # 这里定义相对坐标或固定坐标
    font_log = pygame.font.SysFont("SimHei", 16)
    
    # 组件实例化
    btn_scan = SimpleButton((10, 10, 80, 40), "扫描")
    btn_connect = SimpleButton((210, 10, 80, 40), "连接", (0, 150, 0))
    input_box = SimpleInput((10, H - 50, 200, 40))
    btn_send = SimpleButton((220, H - 50, 70, 40), "发送")
    btn_clear = SimpleButton((10, H - 120, 280, 45), "清空历史", (150, 50, 50))
    btn_disconnect = SimpleButton((10, H - 160, 280, 45), "断开BT连接", (50, 50, 150))
    # 右下角 GOGOGOGO 按钮
    rect_gogo = pygame.Rect(W - 120, H - 60, 100, 40)

    clock = pygame.time.Clock()
    running = True
    mouse_dragging = False
    last_mouse_pos = (0, 0)
    focus_3d = False # 是否正在操作 3D 界面

    while running:
        # --- 1. 处理消息队列 ---
        try:
            while True:
                data = msg_queue.get_nowait()
                if data[0] == "SCAN_RESULT":
                    scan_list = data[1]
                    if not scan_list: scan_list = ["未找到设备"]
                    selected_device_idx = 0
                else:
                    # 聊天记录
                    tag, content = data
                    messages.append(f"{tag} {content}")
                    if len(messages) > MAX_MESSAGES: messages.pop(0) # 保持最新的30条
        except queue.Empty:
            pass

        # --- 2. 事件处理 ---
        events = pygame.event.get()
        keys = pygame.key.get_pressed()
        
        for event in events:
            if event.type == QUIT:
                running = False
                cmd_queue.put(("CLOSE",))
            
            # 全局鼠标点击
            if event.type == MOUSEBUTTONDOWN:
                mx, my = event.pos
                
                # 判断点击是在 UI 区域还是 3D 区域
                if mx < UI_WIDTH:
                    focus_3d = False
                    # 处理左侧 UI 点击
                    if btn_scan.is_clicked((mx, my)):
                        cmd_queue.put(("SCAN",))
                    
                    elif btn_connect.is_clicked((mx, my)):
                        if scan_list and selected_device_idx >= 0:
                            cmd_queue.put(("CONNECT", scan_list[selected_device_idx]))
                            
                    elif btn_send.is_clicked((mx, my)):
                        if input_box.text:
                            cmd_queue.put(("SEND", input_box.text))
                            input_box.text = ""
                            
                    elif btn_clear.is_clicked((mx, my)):
                        messages = []
                    elif btn_disconnect.is_clicked((mx, my)):
                        cmd_queue.put(("DISCONNECT", None))
                    # 下拉菜单逻辑 (简化版)
                    dropdown_rect = pygame.Rect(100, 10, 100, 40)
                    if dropdown_rect.collidepoint((mx, my)):
                        dropdown_open = not dropdown_open
                    elif dropdown_open:
                        # 检查是否点击了下拉项
                        for i in range(len(scan_list)):
                            item_rect = pygame.Rect(100, 50 + i*30, 200, 30)
                            if item_rect.collidepoint((mx, my)):
                                selected_device_idx = i
                                dropdown_open = False
                                break
                else:
                    # 3D 区域点击
                    focus_3d = True
                    # 检查 GOGOGOGO 按钮
                    if rect_gogo.collidepoint((mx, my)):
                        print("[系统] 触发 GOGOGOGO 指令")
                        cmd_queue.put(("SEND", "GOGOGOGO"))
                    else:
                        # 射线检测 Raycasting
                        if event.button == 1: # 左键点击场景
                            # 获取点击坐标 (相对于 viewport)
                            viewport_x = mx
                            viewport_y = H - my # OpenGL Y轴向上，Pygame向下
                            
                            # 获取矩阵
                            modelview = glGetDoublev(GL_MODELVIEW_MATRIX)
                            projection = glGetDoublev(GL_PROJECTION_MATRIX)
                            viewport = glGetIntegerv(GL_VIEWPORT)
                            
                            # 读取深度 (这里简化，假设点击的是 Z=0 平面)
                            # 更严谨的做法是 UnProject 两个点 (near, far) 形成射线
                            try:
                                winX = float(mx)
                                winY = float(viewport[3] - my) # Viewport Height - Y
                                winZ = glReadPixels(winX, winY, 1, 1, GL_DEPTH_COMPONENT, GL_FLOAT)
                                
                                # 转换为世界坐标
                                world_x, world_y, world_z = gluUnProject(winX, winY, winZ, modelview, projection, viewport)
                                
                                # 由于深度缓冲可能不准确，我们计算射线与 Z=0 平面的交点
                                # 射线起点 (Near Plane)
                                start = gluUnProject(winX, winY, 0.0, modelview, projection, viewport)
                                # 射线终点 (Far Plane)
                                end = gluUnProject(winX, winY, 1.0, modelview, projection, viewport)
                                
                                # 射线方程 P = start + t * (end - start)
                                # 我们需要 P.z = 0 -> 0 = start.z + t * (end.z - start.z)
                                # t = -start.z / (end.z - start.z)
                                dir_z = end[2] - start[2]
                                if abs(dir_z) > 0.0001:
                                    t = -start[2] / dir_z
                                    final_x = start[0] + t * (end[0] - start[0])
                                    final_y = start[1] + t * (end[1] - start[1])
                                    print(f"鼠标点击的屏幕坐标 (Z=0平面): X={final_x:.2f}, Y={final_y:.2f}")
                            except Exception as e:
                                print(f"计算坐标出错: {e}")

                    mouse_dragging = True
                    last_mouse_pos = event.pos

            if event.type == MOUSEBUTTONUP:
                mouse_dragging = False

            if event.type == MOUSEMOTION and mouse_dragging and focus_3d:
                dx = event.pos[0] - last_mouse_pos[0]
                dy = event.pos[1] - last_mouse_pos[1]
                camera.yaw += dx * 0.3
                camera.pitch -= dy * 0.3
                # 限制俯仰角
                camera.pitch = max(-89, min(89, camera.pitch))
                last_mouse_pos = event.pos

            # 输入框事件
            res = input_box.handle_event(event)
            if res:
                cmd_queue.put(("SEND", res))
                input_box.text = ""

        # --- 3. 逻辑更新 ---
        if focus_3d:
            camera.update(keys)

        # --- 4. 渲染 ---
        glClearColor(0.1, 0.1, 0.1, 1) # 3D 背景色
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        
        # === 渲染 3D 部分 (右侧) ===

        # - Viewport 只在右边
        glViewport(UI_WIDTH, 0, W - UI_WIDTH, H)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45, (W - UI_WIDTH) / H, 0.1, 1000.0)
        glMatrixMode(GL_MODELVIEW)
        glEnable(GL_DEPTH_TEST)
        
        camera.apply()
        
        # - 绘制坐标的网格 x - 红色轴 y - 蓝色轴 z -高度轴
        glLineWidth(1)
        glBegin(GL_LINES)
        glColor3f(0.3, 0.3, 0.3)
        grid_size = 100
        step = 1
        for i in range(-grid_size, grid_size + 1):
            # 平行于 X 轴的线
            glVertex3f(-grid_size, i, 0)
            glVertex3f(grid_size, i, 0)
            # 平行于 Y 轴的线
            glVertex3f(i, -grid_size, 0)
            glVertex3f(i, grid_size, 0)
        glEnd()
        
        # - 绘制坐标轴 (X=红, Y=蓝, Z=绿)
        glLineWidth(3)
        glBegin(GL_LINES)
        # X Axis
        glColor3f(1, 0, 0)
        glVertex3f(0, 0, 0); glVertex3f(15, 0, 0)
        # Y Axis 
        glColor3f(0, 0, 1)
        glVertex3f(0, 0, 0); glVertex3f(0, 15, 0)
        # Z Axis 
        glColor3f(0, 1, 0)
        glVertex3f(0, 0, 0); glVertex3f(0, 0, 15)
        glEnd()
        
        # 4.3 渲染三角形 (简单的渲染手法：渐变色 + 旋转)
        glPushMatrix()
        glTranslatef(0, 0, 2) # 悬浮在空中
        glRotatef(pygame.time.get_ticks() * 0.05, 0, 0, 1) # 自转
        
        glBegin(GL_TRIANGLES)
        glColor3f(1, 1, 1); glVertex3f(0, 1, 0)
        glColor3f(0, 1, 0); glVertex3f(-0.866, -0.5, 0)
        glColor3f(0, 0, 1); glVertex3f(0.866, -0.5, 0)
        glEnd()
        glPopMatrix()

        # === 渲染 2D UI 部分 (通过 Pygame Surface 覆盖) ===
        # 注意：PyOpenGL 和 Pygame 混合渲染需要把 Surface 转为纹理或直接 Blit
        # Pygame 直接 Blit 到 OPENGL 窗口比较麻烦，通常做法是：
        # 1. 渲染 3D 
        # 2. 切换到 2D 正交投影绘制 2D 
        # 或者更简单：使用 Pygame 的 display.flip 机制，但 Pygame 在 OPENGL 模式下不能直接 draw.rect
        # 所以我们必须用 GL 绘制 2D，或者——我们可以把 UI 画在一个 Surface 上，然后作为纹理贴在屏幕左边。
        # 为了代码简单，我这里使用 "切换投影矩阵绘制 2D" 的方法。

        # 切换到 2D 模式（因为接下来要绘制一个按钮在右下角，此时我们不再需要空间变换了）
        glViewport(0, 0, W, H)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluOrtho2D(0, W, H, 0) # 左上角 (0,0)
        glMatrixMode(GL_MODELVIEW)
        glLoadIdentity()
        glDisable(GL_DEPTH_TEST)
        
        # 使用 Pygame 创建一个 UI Surface，然后转换成 Texture 贴上去
        # 这是混合 Pygame UI 和 OpenGL 最稳健的方法
        ui_surface = pygame.Surface((W, H), pygame.SRCALPHA)
        ui_surface.fill((0,0,0,0)) # 透明背景
        
        # --- 在 ui_surface 上画左侧背景 ---
        pygame.draw.rect(ui_surface, (230, 230, 230), (0, 0, UI_WIDTH, H))
        pygame.draw.line(ui_surface, (100, 100, 100), (UI_WIDTH, 0), (UI_WIDTH, H), 2)
        
        # --- 画组件 ---
        btn_scan.draw(ui_surface)
        btn_connect.draw(ui_surface)
        input_box.draw(ui_surface)
        btn_send.draw(ui_surface)
        btn_clear.draw(ui_surface)
        btn_disconnect.draw(ui_surface)
        # 下拉选框显示
        current_dev = scan_list[selected_device_idx] if scan_list and selected_device_idx >= 0 else "选择设备"
        pygame.draw.rect(ui_surface, (255, 255, 255), (100, 10, 100, 40))
        pygame.draw.rect(ui_surface, (0,0,0), (100, 10, 100, 40), 1)
        txt = font_log.render(current_dev[:10], True, (0,0,0))
        ui_surface.blit(txt, (105, 20))
        
        if dropdown_open:
            for i, name in enumerate(scan_list):
                r = pygame.Rect(100, 50 + i*30, 200, 30)
                pygame.draw.rect(ui_surface, (240, 240, 240), r)
                pygame.draw.rect(ui_surface, (0,0,0), r, 1)
                t = font_log.render(name, True, (0,0,0))
                ui_surface.blit(t, (105, 50 + i*30 + 5))

        # --- 画消息日志 ---
        log_y = 80
        for msg in messages:
            color = (0, 0, 0)
            if "[系统]" in msg: color = (100, 100, 100)
            if "[发送]" in msg: color = (0, 0, 150)
            if "[接收]" in msg: color = (0, 100, 0)
            
            txt_surf = font_log.render(msg, True, color)
            ui_surface.blit(txt_surf, (10, log_y))
            log_y += 20
        
        # --- 画右下角的 GOGOGOGO 按钮 ---
        pygame.draw.rect(ui_surface, (255, 100, 100), rect_gogo)
        pygame.draw.rect(ui_surface, (255, 255, 255), rect_gogo, 2)
        txt_go = font_log.render("Go Here", True, (255, 255, 255))
        ui_surface.blit(txt_go, (rect_gogo.x + 10, rect_gogo.y + 10))

        # --- 将 Surface 转为 OpenGL 纹理并绘制 ---
        # 这一步稍微有点技术含量
        texture_data = pygame.image.tostring(ui_surface, "RGBA", True)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        tex_id = glGenTextures(1)
        glBindTexture(GL_TEXTURE_2D, tex_id)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_LINEAR)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_LINEAR)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, W, H, 0, GL_RGBA, GL_UNSIGNED_BYTE, texture_data)
        
        # 绘制全屏矩形贴图
        glColor4f(1, 1, 1, 1)
        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, H) # Pygame data is flipped vertically by tostring(True)
        glTexCoord2f(1, 0); glVertex2f(W, H)
        glTexCoord2f(1, 1); glVertex2f(W, 0)
        glTexCoord2f(0, 1); glVertex2f(0, 0)
        glEnd()
        
        glDeleteTextures([tex_id]) # 清理显存
        glDisable(GL_TEXTURE_2D)
        glDisable(GL_BLEND)

        pygame.display.flip()
        clock.tick(60)

    # 退出前清理
    cmd_queue.put(("CLOSE",))
    bt_thread.join()
    pygame.quit()

if __name__ == "__main__":
    run_app()