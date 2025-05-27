import sys
import os
from PyQt5.QtWidgets import QApplication, QLabel, QWidget, QMenu, QAction, QTextEdit
from PyQt5.QtGui import QPixmap, QMovie
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer
import time
import hashlib
import hmac
import base64
import json
import websocket
import ssl
import _thread as thread
from datetime import datetime
from time import mktime
from urllib.parse import urlparse, urlencode
from wsgiref.handlers import format_date_time

# 全局变量
answer = ""
isFirstcontent = False
conversation_history = []
SYSTEM_PROMPT = "你现在是一只可爱的小狗，你的名字是奥莉，你两岁了，是一只串串小狗，你不是深度推理模型X1。现在我是你的爸爸，你回答我的每句话都要简洁，不超过50字，而且每句话后面都要加上'汪'。"

class Ws_Param(object):
    def __init__(self, APPID, APIKey, APISecret, Spark_url):
        self.APPID = APPID
        self.APIKey = APIKey
        self.APISecret = APISecret
        self.host = urlparse(Spark_url).netloc
        self.path = urlparse(Spark_url).path
        self.Spark_url = Spark_url

    def create_url(self):
        now = datetime.now()
        date = format_date_time(mktime(now.timetuple()))

        signature_origin = "host: " + self.host + "\n"
        signature_origin += "date: " + date + "\n"
        signature_origin += "GET " + self.path + " HTTP/1.1"

        signature_sha = hmac.new(self.APISecret.encode('utf-8'), signature_origin.encode('utf-8'),
                               digestmod=hashlib.sha256).digest()
        signature_sha_base64 = base64.b64encode(signature_sha).decode(encoding='utf-8')
        authorization_origin = f'api_key="{self.APIKey}", algorithm="hmac-sha256", headers="host date request-line", signature="{signature_sha_base64}"'
        authorization = base64.b64encode(authorization_origin.encode('utf-8')).decode(encoding='utf-8')

        v = {
            "authorization": authorization,
            "date": date,
            "host": self.host
        }
        return self.Spark_url + '?' + urlencode(v)

class SparkThread(QThread):
    finished = pyqtSignal(str)
    
    def __init__(self, text):
        super().__init__()
        self.text = text
        
    def run(self):
        try:
            appid = "80124952"
            api_key = "add002a1c41822a23ae549952b57511d"
            api_secret = "ZDZiOWFiMTZhNDlhODg1NjFmNWRiNjU4"
            spark_url = "wss://spark-api.xf-yun.com/v1/x1"
            domain = "x1"
            
            global conversation_history
            if not conversation_history or conversation_history[0].get("role") != "system":
                conversation_history.insert(0, {"role": "system", "content": SYSTEM_PROMPT})
            conversation_history.append({"role": "user", "content": self.text})
            while sum(len(msg["content"]) for msg in conversation_history) > 8000:
                conversation_history.pop(0)
            
            wsParam = Ws_Param(appid, api_key, api_secret, spark_url)
            websocket.enableTrace(False)
            wsUrl = wsParam.create_url()
            
            global answer, isFirstcontent
            answer = ""
            isFirstcontent = False
            
            ws = websocket.WebSocketApp(wsUrl,
                                      on_message=self.on_message,
                                      on_error=self.on_error,
                                      on_close=self.on_close,
                                      on_open=self.on_open)
            ws.appid = appid
            ws.question = conversation_history
            ws.domain = domain
            ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
            
            conversation_history.append({"role": "assistant", "content": answer})
            self.finished.emit(answer)
            
        except Exception as e:
            self.finished.emit(f"奥莉好像有点累了：{e}")

    def on_error(self, ws, error):
        print("### error:", error)

    def on_close(self, ws, one, two):
        print(" ")

    def on_open(self, ws):
        thread.start_new_thread(self.run_ws, (ws,))

    def run_ws(self, ws, *args):
        data = {
            "header": {
                "app_id": ws.appid,
                "uid": "1234",
            },
            "parameter": {
                "chat": {
                    "domain": ws.domain,
                    "temperature": 0.5,
                    "max_tokens": 32768
                }
            },
            "payload": {
                "message": {
                    "text": ws.question
                }
            }
        }
        ws.send(json.dumps(data))

    def on_message(self, ws, message):
        global answer, isFirstcontent
        data = json.loads(message)
        code = data['header']['code']
        if code != 0:
            print(f'请求错误: {code}, {data}')
            ws.close()
        else:
            choices = data["payload"]["choices"]
            status = choices["status"]
            text = choices['text'][0]
            
            if 'reasoning_content' in text and text['reasoning_content']:
                reasoning_content = text["reasoning_content"]
                print(reasoning_content, end="")
                isFirstcontent = True

            if 'content' in text and text['content']:
                content = text["content"]
                if isFirstcontent:
                    print("\n*******************以上为思维链内容，模型回复内容如下********************\n")
                print(content, end="")
                isFirstcontent = False
                answer += content
                
            if status == 2:
                ws.close()

def resource_path(relative_path):
    """获取资源文件的绝对路径"""
    try:
        # PyInstaller创建临时文件夹，将路径存储在_MEIPASS中
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class DogPet(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.offset = None
        self.installEventFilter(self)
        self.is_playing_animation = False
        self.is_dragging = False

    def initUI(self):
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(300, 450)  # 增大窗口高度

        # 加载小狗图片
        self.label = QLabel(self)
        self.static_pixmap = QPixmap(resource_path("hello_video.gif"))
        print("图片是否加载成功：", not self.static_pixmap.isNull())
        self.static_pixmap = self.static_pixmap.scaled(300, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # 准备动画
        self.animation = QMovie(resource_path("hello_video.gif"))
        self.animation.setScaledSize(self.static_pixmap.size())
        self.animation.setCacheMode(QMovie.CacheAll)
        self.animation.finished.connect(self.reset_to_static_image)

        # 新增：拖拽动画
        self.hold_animation = QMovie(resource_path("hold_video.gif"))
        self.hold_animation.setScaledSize(self.static_pixmap.size())
        self.hold_animation.setCacheMode(QMovie.CacheAll)
        self.hold_animation.finished.connect(self.reset_to_static_image)
        
        self.label.setPixmap(self.static_pixmap)
        self.label.setGeometry(0, 0, self.static_pixmap.width(), self.static_pixmap.height())
        # self.setFixedSize(self.static_pixmap.width(), self.static_pixmap.height())  # 注释掉
        
        # 设置鼠标追踪
        self.setMouseTracking(True)
        self.label.setMouseTracking(True)
        self.label.installEventFilter(self)  # 让label支持事件过滤器

        # 输入框（改用QTextEdit）
        self.input_box = QTextEdit(self)
        self.input_box.setPlaceholderText("和奥莉说点什么吧…")
        self.input_box.setGeometry(10, 250, 280, 45)
        self.input_box.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.input_box.textChanged.connect(self.adjust_input_box_height)
        self.input_box.installEventFilter(self)  # 安装事件过滤器
        self.input_box.hide()

        # 回复显示框
        self.reply_box = QTextEdit(self)
        self.reply_box.setGeometry(10, 300, 280, 75)
        self.reply_box.setReadOnly(True)
        self.reply_box.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.reply_box.textChanged.connect(self.adjust_reply_box_height)
        self.reply_box.hide()

        # 统一样式美化
        main_color = "#f0f4ff"  # 主色调
        border_color = "#a3b1c6"
        highlight_color = "#dbeafe"
        font_family = "微软雅黑"

        # 输入框样式
        self.input_box.setStyleSheet(f"""
            QTextEdit {{
                background: {main_color};
                border: 2px solid {border_color};
                border-radius: 12px;
                padding: 6px 10px;
                font-size: 15px;
                font-family: {font_family};
                color: #333;
            }}
            QTextEdit:focus {{
                border: 2px solid {highlight_color};
                background: #fff;
            }}
        """)

        # 输出框样式
        self.reply_box.setStyleSheet(f"""
            QTextEdit {{
                background: {main_color};
                border: 2px solid {border_color};
                border-radius: 12px;
                padding: 6px 10px;
                font-size: 15px;
                font-family: {font_family};
                color: #333;
            }}
        """)

        # 菜单栏样式
        self.setStyleSheet(f"""
            QMenu {{
                background: {main_color};
                border: 1.5px solid {border_color};
                border-radius: 10px;
                font-size: 15px;
                font-family: {font_family};
                color: #333;
                padding: 6px 10px;
            }}
            QMenu::item {{
                background: transparent;
                padding: 6px 20px;
                border-radius: 8px;
            }}
            QMenu::item:selected {{
                background: {highlight_color};
                color: #222;
            }}
        """)

    def adjust_input_box_height(self):
        # 输入框高度自适应
        document_height = self.input_box.document().size().height()
        new_height = int(min(100, max(30, document_height + 5)))
        current_geometry = self.input_box.geometry()
        self.input_box.setGeometry(current_geometry.x(), current_geometry.y(), current_geometry.width(), new_height)

        # 输出框位置随输入框高度变化
        reply_geometry = self.reply_box.geometry()
        self.reply_box.setGeometry(
            reply_geometry.x(),
            self.input_box.geometry().y() + new_height + 10,  # 紧跟输入框下方
            reply_geometry.width(),
            reply_geometry.height()
        )
        self.adjust_reply_box_height()  # 让输出框也自适应

    def adjust_reply_box_height(self):
        # 输出框高度自适应
        document_height = self.reply_box.document().size().height()
        new_height = int(min(200, max(60, document_height + 5)))
        current_geometry = self.reply_box.geometry()
        self.reply_box.setGeometry(
            current_geometry.x(),
            current_geometry.y(),
            current_geometry.width(),
            new_height
        )

        # 如果输出框底部超出窗口，则增大窗口高度
        bottom = current_geometry.y() + new_height + 10
        if bottom > self.height():
            self.setFixedHeight(bottom)

    def mousePressEvent(self, event):
        if event.button() == Qt.RightButton:
            menu = QMenu(self)
            close_action = QAction("去睡觉吧", self)
            close_action.triggered.connect(self.close)
            menu.addAction(close_action)
            menu.exec_(self.mapToGlobal(event.pos()))

    def mouseMoveEvent(self, event):
        pass  # 不再在这里处理拖动

    def reset_to_static_image(self):
        # 动画播放完成后的处理
        self.animation.stop()
        self.label.setMovie(None)
        self.label.setPixmap(self.static_pixmap)
        self.is_playing_animation = False

    def mouseDoubleClickEvent(self, event):
        # 双击显示输入框和回复框
        self.input_box.show()
        self.reply_box.show()
        self.input_box.setFocus()

    def handle_input(self):
        user_text = self.input_box.toPlainText()
        if not user_text.strip():
            return
        self.reply_box.clear()  # 清除之前的内容
        self.reply_box.append("奥莉努力思考中...")
        self.spark_thread = SparkThread(user_text)
        self.spark_thread.finished.connect(self.show_ai_reply)
        self.spark_thread.start()

    def show_ai_reply(self, reply):
        self.reply_box.clear()  # 清除"思考中..."
        self.reply_box.append(reply)  # 只显示AI的回复

    def focusOutEvent(self, event):
        # 当窗口失去焦点时，隐藏输入框和回复框
        self.input_box.hide()
        self.reply_box.hide()
        super().focusOutEvent(event)

    def eventFilter(self, obj, event):
        # 拖动窗口只允许在label（小狗图片）上
        if obj == self.label:
            if event.type() == event.MouseButtonPress:
                # 新增：如果聊天框显示，单击小狗隐藏聊天框
                if (self.input_box.isVisible() or self.reply_box.isVisible()):
                    self.input_box.hide()
                    self.reply_box.hide()
                    return True
            if event.type() == event.MouseButtonPress and event.button() == Qt.LeftButton:
                self.offset = event.globalPos() - self.frameGeometry().topLeft()
                self.is_dragging = True
                # 拖拽开始，切换为hold_video动画
                self.label.setMovie(self.hold_animation)
                self.hold_animation.stop()
                self.hold_animation.start()
                return True
            elif event.type() == event.MouseMove and self.is_dragging and self.offset is not None:
                self.move(event.globalPos() - self.offset)
                return True
            elif event.type() == event.MouseButtonRelease and event.button() == Qt.LeftButton:
                self.offset = None
                self.is_dragging = False
                # 拖拽结束，切换回静态图片
                self.reset_to_static_image()
                return True
        # 输入框回车处理
        if obj == self.input_box and event.type() == event.KeyPress:
            if event.key() == Qt.Key_Return and event.modifiers() == Qt.NoModifier:
                self.handle_input()
                return True
            elif event.key() == Qt.Key_Return and event.modifiers() == Qt.ShiftModifier:
                return False
        elif event.type() == event.MouseButtonPress:
            # 检查点击是否在输入框和输出框之外
            pos = event.pos()
            if self.input_box.isVisible() or self.reply_box.isVisible():
                input_rect = self.input_box.geometry()
                reply_rect = self.reply_box.geometry()
                if not (input_rect.contains(pos) or reply_rect.contains(pos)):
                    self.input_box.hide()
                    self.reply_box.hide()
        return super().eventFilter(obj, event)

    def enterEvent(self, event):
        if not self.is_playing_animation:
            self.is_playing_animation = True
            self.label.setMovie(self.animation)
            self.animation.stop()  # 确保从头开始播放
            self.animation.start()
        super().enterEvent(event)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    pet = DogPet()
    pet.show()
    print("窗口已显示")
    sys.exit(app.exec_())

