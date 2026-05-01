import sys, cv2, numpy as np, os, winsound, shlex
from PyQt5.QtWidgets import *
from PyQt5.QtGui import *
from PyQt5.QtCore import *

# =========================
# VIDEO PLAYER
# =========================
class VideoPlayer(QWidget):
    def __init__(self):
        super().__init__()
        self.cap = None
        self.original_image = None

        layout = QVBoxLayout()
        layout.addWidget(QLabel("Video"))

        self.label = QLabel()
        self.label.setFixedSize(640, 360)
        layout.addWidget(self.label)

        self.slider = QSlider(Qt.Horizontal)
        self.slider.valueChanged.connect(self.seek)
        layout.addWidget(self.slider)

        self.setLayout(layout)

    def load(self, path):
        self.cap = cv2.VideoCapture(path)
        total = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.slider.setMaximum(total)

    def seek(self, frame):
        if not self.cap:
            return
        self.cap.set(cv2.CAP_PROP_POS_FRAMES, frame)
        ret, img = self.cap.read()
        if ret:
            self.original_image = img.copy()
            preview = cv2.resize(img, (640,360))
            rgb = cv2.cvtColor(preview, cv2.COLOR_BGR2RGB)
            qimg = QImage(rgb.data, 640,360,3*640,QImage.Format_RGB888)
            self.label.setPixmap(QPixmap.fromImage(qimg))


# =========================
# MASK EDITOR
# =========================
class MaskEditor(QLabel):
    def __init__(self):
        super().__init__()
        self.original = None
        self.base_pixmap = None
        self.mask = None
        self.scale_x = 1
        self.scale_y = 1
        self.base_brush = 20
        self.brush = 20
        self.mode = "paint"
        self.drawing = False
        self.last = None
        self.cursor_pos = QPoint(0,0)

        self.setMouseTracking(True)
        self.setCursor(Qt.BlankCursor)

    def set_brush_size(self, size):
        self.base_brush = size

    def set_frame(self, img):
        self.original = img.copy()
        display = cv2.resize(img,(640,360))
        self.mask = np.zeros(img.shape[:2], dtype=np.uint8)

        self.scale_x = img.shape[1]/640
        self.scale_y = img.shape[0]/360

        rgb = cv2.cvtColor(display, cv2.COLOR_BGR2RGB)
        qimg = QImage(rgb.data,640,360,3*640,QImage.Format_RGB888)
        self.base_pixmap = QPixmap.fromImage(qimg)
        self.update()

    def load_mask(self, path):
        m = cv2.imread(path,0)
        if m is None or self.original is None:
            return
        m = cv2.resize(m,(self.original.shape[1], self.original.shape[0]))
        self.mask = m
        self.update()

    def save_mask(self, path):
        if self.mask is not None:
            cv2.imwrite(path, self.mask)

    def draw_fast(self,p1,p2):
        x1,y1=p1.x(),p1.y()
        x2,y2=p2.x(),p2.y()
        steps=max(abs(x2-x1),abs(y2-y1))

        for i in range(steps):
            t=i/steps if steps else 0
            x=int((x1+(x2-x1)*t)*self.scale_x)
            y=int((y1+(y2-y1)*t)*self.scale_y)
            r=int(self.brush*self.scale_x)

            if self.mode=="paint":
                cv2.circle(self.mask,(x,y),r,255,-1)
            else:
                cv2.circle(self.mask,(x,y),r,0,-1)

    def mousePressEvent(self,e):
        self.drawing=True
        self.last=e.pos()

    def mouseMoveEvent(self,e):
        self.cursor_pos = e.pos()
        if self.drawing:
            self.brush = self.base_brush
            self.draw_fast(self.last,e.pos())
            self.last=e.pos()
        self.update()

    def mouseReleaseEvent(self,e):
        self.drawing=False
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)

        if self.base_pixmap:
            painter.drawPixmap(0,0,self.base_pixmap)

        if self.mask is not None:
            small = cv2.resize(self.mask,(160,90))
            small = cv2.GaussianBlur(small,(5,5),0)
            big = cv2.resize(small,(640,360), interpolation=cv2.INTER_LINEAR)

            overlay = np.zeros((360,640,4), dtype=np.uint8)
            alpha = (big/255.0)*120

            overlay[:,:,0] = 255
            overlay[:,:,1] = 0
            overlay[:,:,2] = 255
            overlay[:,:,3] = alpha.astype(np.uint8)

            qimg = QImage(overlay.data,640,360,4*640,QImage.Format_RGBA8888)
            painter.drawImage(0,0,qimg)

        pen = QPen(QColor(255,0,255),1)
        painter.setPen(pen)
        x = self.cursor_pos.x()
        y = self.cursor_pos.y()
        painter.drawLine(x-5,y,x+5,y)
        painter.drawLine(x,y-5,x,y+5)


# =========================
# APP
# =========================
class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("MatAnyone2 GUI v1.0")
        self.resize(1300,800)

        self.video_path=""
        self.mask_path="mask.png"
        self.output_dir=os.path.join(os.getcwd(),"outputs")
        os.makedirs(self.output_dir,exist_ok=True)

        self.init_ui()

    def init_ui(self):
        layout=QHBoxLayout()

        left=QVBoxLayout()
        self.player=VideoPlayer()
        left.addWidget(self.player)

        left.addWidget(QLabel("Mask"))

        self.canvas=MaskEditor()
        self.canvas.setFixedSize(640,360)
        left.addWidget(self.canvas)

        layout.addLayout(left)

        right=QVBoxLayout()

        # INPUTS
        btn=QPushButton("Load Video")
        btn.clicked.connect(self.load_video)
        right.addWidget(btn)

        btn=QPushButton("Load Mask")
        btn.clicked.connect(self.load_mask)
        right.addWidget(btn)

        btn_save = QPushButton("Save Mask")
        btn_save.clicked.connect(self.save_mask)
        right.addWidget(btn_save)

        # PAINT
        mode_layout = QHBoxLayout()
        btn_paint = QPushButton("Paint")
        btn_erase = QPushButton("Erase")
        btn_paint.clicked.connect(lambda:self.set_mode("paint"))
        btn_erase.clicked.connect(lambda:self.set_mode("erase"))
        mode_layout.addWidget(btn_paint)
        mode_layout.addWidget(btn_erase)
        right.addLayout(mode_layout)

        # BRUSH
        slider=QSlider(Qt.Horizontal)
        slider.setRange(1,100)
        slider.setValue(20)
        slider.valueChanged.connect(self.canvas.set_brush_size)
        right.addWidget(QLabel("Brush Size"))
        right.addWidget(slider)

        # OUTPUT FOLDER
        right.addWidget(QLabel("Output Folder"))

        out_layout = QHBoxLayout()
        self.output_edit = QLineEdit(self.output_dir)

        btn_folder = QPushButton("📁")
        btn_folder.clicked.connect(self.select_output)

        out_layout.addWidget(self.output_edit)
        out_layout.addWidget(btn_folder)
        right.addLayout(out_layout)

        # CLI
        right.addWidget(QLabel("Command for MatAnyone2"))
        self.cli = QTextEdit()
        right.addWidget(self.cli)

        btn_copy = QPushButton("Copy Command to Clipboard")
        btn_copy.clicked.connect(self.copy_cmd)
        right.addWidget(btn_copy)

        btn_run = QPushButton("Process")
        btn_run.clicked.connect(self.run)
        right.addWidget(btn_run)

        self.log = QTextEdit()
        self.log.setReadOnly(True)
        right.addWidget(QLabel("Log"))
        right.addWidget(self.log)

        layout.addLayout(right)
        self.setLayout(layout)

    def select_output(self):
        folder = QFileDialog.getExistingDirectory(self,"Select Folder")
        if folder:
            self.output_dir = folder
            self.output_edit.setText(folder)

    def set_mode(self,m):
        self.canvas.mode = m

    def save_mask(self):
        path,_ = QFileDialog.getSaveFileName(self,"Save Mask","mask.png","PNG (*.png)")
        if path:
            self.canvas.save_mask(path)

    def copy_cmd(self):
        QApplication.clipboard().setText(self.cli.toPlainText())

    def run(self):
        self.canvas.save_mask(self.mask_path)

        cmd = self.cli.toPlainText().strip()
        if not cmd:
            QMessageBox.warning(self,"Error","CLI Empty")
            return

        os.makedirs(self.output_dir, exist_ok=True)

        cmd += f' -o "{self.output_dir}"'

        parts = shlex.split(cmd)

        if parts[0].lower() == "python":
            parts[0] = sys.executable

        program = parts[0]
        arguments = parts[1:]

        self.process = QProcess(self)
        self.process.setProgram(program)
        self.process.setArguments(arguments)
        self.process.setWorkingDirectory(os.getcwd())
        self.process.setProcessChannelMode(QProcess.MergedChannels)

        self.process.readyReadStandardOutput.connect(self.read_output)
        self.process.finished.connect(self.on_finished)

        self.process.start()

    def read_output(self):
        data = self.process.readAllStandardOutput().data().decode(errors="ignore")
        self.log.append(data)

    def on_finished(self):
        try:
            winsound.PlaySound("bell.wav", winsound.SND_FILENAME | winsound.SND_ASYNC)
        except:
            winsound.Beep(1000,400)

        QMessageBox.information(self,"Listo","Processing Done! 🎬")

    def load_video(self):
        path,_=QFileDialog.getOpenFileName(self)
        if path:
            self.video_path=path
            self.player.load(path)
            self.player.seek(1)
            if self.player.original_image is not None:
                self.canvas.set_frame(self.player.original_image)

            self.cli.setText(f'python inference_matanyone2.py -i "{path}" -m "{self.mask_path}"')

    def load_mask(self):
        path,_=QFileDialog.getOpenFileName(self)
        if path:
            self.canvas.load_mask(path)


if __name__=="__main__":
    app=QApplication(sys.argv)
    w=App()
    w.show()
    sys.exit(app.exec_())