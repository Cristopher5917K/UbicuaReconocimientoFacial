"""
Sistema de control de acceso por reconocimiento facial (Haar Cascade)
Computación Ubicua - UDLA

- Detecta rostros con haarcascade_frontalface_default.xml (OpenCV).
- Envía por comunicación serial al microcontrolador:
    'G' -> rostro detectado  -> LED VERDE  + "acceso correcto"
    'R' -> no hay rostro     -> LED ROJO   + "acceso denegado"
- Interfaz gráfica en Python (Tkinter): cámara en vivo o cargar imagen.

Requisitos:  pip install opencv-python pyserial pillow
"""

import os
import sys
import time
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import cv2
import numpy as np
from PIL import Image, ImageTk

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

# ---------------------------- CONFIGURACIÓN ----------------------------
CASCADE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "haarcascade_frontalface_default.xml")
BAUDRATE = 9600
CAMARA_INDEX = 0
FRAMES_CONFIRMACION = 5      # frames seguidos con el mismo resultado antes de cambiar el LED
ANCHO_VISTA = 640

# Parámetros del detector Haar
SCALE_FACTOR = 1.1
MIN_NEIGHBORS = 5
MIN_SIZE = (60, 60)


# ---------------------------- DETECTOR ----------------------------
class DetectorRostros:
    def __init__(self, ruta_xml):
        self.cascade = cv2.CascadeClassifier(ruta_xml)
        if self.cascade.empty():
            raise FileNotFoundError(f"No se pudo cargar el modelo: {ruta_xml}")

    def detectar(self, frame_bgr):
        gris = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
        gris = cv2.equalizeHist(gris)
        rostros = self.cascade.detectMultiScale(
            gris, scaleFactor=SCALE_FACTOR,
            minNeighbors=MIN_NEIGHBORS, minSize=MIN_SIZE)
        return rostros

    @staticmethod
    def dibujar(frame_bgr, rostros, acceso):
        color = (0, 200, 0) if acceso else (0, 0, 255)
        for (x, y, w, h) in rostros:
            cv2.rectangle(frame_bgr, (x, y), (x + w, y + h), color, 2)
        texto = "ACCESO CORRECTO" if acceso else "ACCESO DENEGADO"
        cv2.rectangle(frame_bgr, (0, 0), (frame_bgr.shape[1], 40), color, -1)
        cv2.putText(frame_bgr, texto, (10, 28), cv2.FONT_HERSHEY_SIMPLEX,
                    0.9, (255, 255, 255), 2)
        return frame_bgr


# ---------------------------- SERIAL ----------------------------
class ConexionSerial:
    def __init__(self):
        self.ser = None

    @staticmethod
    def puertos_disponibles():
        if serial is None:
            return []
        return [p.device for p in serial.tools.list_ports.comports()]

    def conectar(self, puerto):
        self.desconectar()
        self.ser = serial.Serial(puerto, BAUDRATE, timeout=1)
        time.sleep(2)                 # el Arduino se reinicia al abrir el puerto
        self.ser.reset_input_buffer()

    def desconectar(self):
        if self.ser is not None:
            try:
                if self.ser.is_open:
                    self.ser.write(b'O')      # apaga ambos LEDs
                    self.ser.flush()
                self.ser.close()
            except Exception:
                pass                          # el cable pudo haberse desconectado
        self.ser = None

    @property
    def conectado(self):
        return self.ser is not None and self.ser.is_open

    def enviar(self, comando):
        """Envía 'G', 'R' u 'O'. Devuelve la respuesta del microcontrolador (si hay)."""
        if not self.conectado:
            return None
        try:
            self.ser.write(comando.encode())
            self.ser.flush()
            return self.ser.readline().decode(errors="ignore").strip()
        except Exception:
            self.ser = None                   # se perdió la conexión
            return None


# ---------------------------- INTERFAZ ----------------------------
class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Control de Acceso Facial - Sistema Domótico Bancario")
        self.root.protocol("WM_DELETE_WINDOW", self.cerrar)

        self.detector = DetectorRostros(CASCADE_PATH)
        self.serial = ConexionSerial()
        self.cap = None
        self.estado_actual = None        # True = acceso, False = denegado
        self.contador = 0
        self.ultimo_candidato = None

        self._construir_ui()
        self.refrescar_puertos()

    # ---------- UI ----------
    def _construir_ui(self):
        barra = ttk.Frame(self.root, padding=8)
        barra.pack(fill="x")

        ttk.Label(barra, text="Puerto:").pack(side="left")
        self.cb_puerto = ttk.Combobox(barra, width=12, state="readonly")
        self.cb_puerto.pack(side="left", padx=4)
        ttk.Button(barra, text="↻", width=3, command=self.refrescar_puertos).pack(side="left")
        self.btn_conectar = ttk.Button(barra, text="Conectar", command=self.toggle_serial)
        self.btn_conectar.pack(side="left", padx=6)

        ttk.Separator(barra, orient="vertical").pack(side="left", fill="y", padx=8)
        self.btn_camara = ttk.Button(barra, text="Iniciar cámara", command=self.toggle_camara)
        self.btn_camara.pack(side="left", padx=4)
        ttk.Button(barra, text="Cargar imagen", command=self.cargar_imagen).pack(side="left", padx=4)

        self.lbl_video = ttk.Label(self.root)
        self.lbl_video.pack(padx=8, pady=4)

        estado = ttk.Frame(self.root, padding=8)
        estado.pack(fill="x")
        self.canvas_led = tk.Canvas(estado, width=90, height=40, highlightthickness=0)
        self.canvas_led.pack(side="left")
        self.led_rojo = self.canvas_led.create_oval(5, 5, 35, 35, fill="#400")
        self.led_verde = self.canvas_led.create_oval(50, 5, 80, 35, fill="#040")
        self.lbl_estado = ttk.Label(estado, text="Esperando...", font=("Segoe UI", 16, "bold"))
        self.lbl_estado.pack(side="left", padx=10)

        ttk.Label(self.root, text="Consola:").pack(anchor="w", padx=8)
        self.txt_log = tk.Text(self.root, height=8, width=80, bg="#111", fg="#0f0",
                               font=("Consolas", 10))
        self.txt_log.pack(fill="both", padx=8, pady=(0, 8))

    def log(self, msg):
        linea = f"[{time.strftime('%H:%M:%S')}] {msg}"
        print(linea, flush=True)                     # también en la consola de Python
        self.txt_log.insert("end", linea + "\n")
        self.txt_log.see("end")

    def mostrar_frame(self, frame_bgr):
        h, w = frame_bgr.shape[:2]
        escala = ANCHO_VISTA / w
        frame = cv2.resize(frame_bgr, (ANCHO_VISTA, int(h * escala)))
        img = ImageTk.PhotoImage(Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)))
        self.lbl_video.configure(image=img)
        self.lbl_video.image = img

    # ---------- Serial ----------
    def refrescar_puertos(self):
        puertos = self.serial.puertos_disponibles()
        self.cb_puerto["values"] = puertos
        if puertos:
            self.cb_puerto.current(0)
        else:
            self.cb_puerto.set("")

    def toggle_serial(self):
        if self.serial.conectado:
            self.serial.desconectar()
            self.btn_conectar.config(text="Conectar")
            self.log("Microcontrolador desconectado.")
            return
        if serial is None:
            messagebox.showerror("Error", "Instala pyserial: pip install pyserial")
            return
        puerto = self.cb_puerto.get()
        if not puerto:
            messagebox.showwarning("Aviso", "No hay puertos disponibles.")
            return
        try:
            self.serial.conectar(puerto)
            self.btn_conectar.config(text="Desconectar")
            self.log(f"Conectado a {puerto} @ {BAUDRATE} baudios.")
            self.estado_actual = None   # fuerza reenviar el estado
        except Exception as e:
            messagebox.showerror(
                "Error serial",
                f"{e}\n\n¿Está abierto el Monitor Serie del Arduino IDE? Ciérralo e intenta de nuevo.")

    # ---------- Lógica de acceso ----------
    def aplicar_resultado(self, acceso):
        if acceso == self.estado_actual:
            return
        self.estado_actual = acceso
        if acceso:
            mensaje, comando = "acceso correcto", "G"
            self.canvas_led.itemconfig(self.led_verde, fill="#0f0")
            self.canvas_led.itemconfig(self.led_rojo, fill="#400")
            self.lbl_estado.config(text="ACCESO CORRECTO", foreground="green")
        else:
            mensaje, comando = "acceso denegado", "R"
            self.canvas_led.itemconfig(self.led_rojo, fill="#f00")
            self.canvas_led.itemconfig(self.led_verde, fill="#040")
            self.lbl_estado.config(text="ACCESO DENEGADO", foreground="red")

        self.log(mensaje)
        estaba_conectado = self.serial.conectado
        respuesta = self.serial.enviar(comando)
        if respuesta:
            self.log(f"Microcontrolador -> {respuesta}")
        elif estaba_conectado and not self.serial.conectado:
            self.btn_conectar.config(text="Conectar")
            self.log("Se perdió la conexión con el microcontrolador.")
        elif not self.serial.conectado:
            self.log("(sin microcontrolador conectado: solo simulación en pantalla)")

    def procesar(self, frame):
        rostros = self.detector.detectar(frame)
        acceso = len(rostros) > 0
        return self.detector.dibujar(frame, rostros, acceso), acceso, len(rostros)

    # ---------- Imagen ----------
    def cargar_imagen(self):
        if self.cap is not None:
            self.toggle_camara()
        ruta = filedialog.askopenfilename(
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.webp")])
        if not ruta:
            return
        # imdecode + fromfile en vez de imread: imread falla en Windows con tildes/ñ en la ruta
        frame = cv2.imdecode(np.fromfile(ruta, dtype=np.uint8), cv2.IMREAD_COLOR)
        if frame is None:
            messagebox.showerror("Error", "No se pudo leer la imagen.")
            return
        frame, acceso, n = self.procesar(frame)
        self.log(f"Imagen: {os.path.basename(ruta)} | rostros detectados: {n}")
        self.estado_actual = None        # cada imagen se evalúa por separado
        self.aplicar_resultado(acceso)
        self.mostrar_frame(frame)

    # ---------- Cámara ----------
    def toggle_camara(self):
        if self.cap is not None:
            self.cap.release()
            self.cap = None
            self.btn_camara.config(text="Iniciar cámara")
            self.log("Cámara detenida.")
            return
        # En Windows DirectShow abre la webcam mucho más rápido que el backend por defecto
        if sys.platform.startswith("win"):
            self.cap = cv2.VideoCapture(CAMARA_INDEX, cv2.CAP_DSHOW)
        else:
            self.cap = cv2.VideoCapture(CAMARA_INDEX)
        if not self.cap.isOpened():
            self.cap = None
            messagebox.showerror("Error", "No se pudo abrir la cámara.")
            return
        self.contador, self.ultimo_candidato = 0, None
        self.btn_camara.config(text="Detener cámara")
        self.log("Cámara iniciada.")
        self.loop_camara()

    def loop_camara(self):
        if self.cap is None:
            return
        ok, frame = self.cap.read()
        if ok:
            frame = cv2.flip(frame, 1)
            frame, acceso, _ = self.procesar(frame)
            # Confirmación por varios frames para evitar parpadeo del LED
            if acceso == self.ultimo_candidato:
                self.contador += 1
            else:
                self.ultimo_candidato, self.contador = acceso, 1
            if self.contador >= FRAMES_CONFIRMACION:
                self.aplicar_resultado(acceso)
            self.mostrar_frame(frame)
        self.root.after(30, self.loop_camara)

    def cerrar(self):
        if self.cap is not None:
            self.cap.release()
        self.serial.desconectar()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
