"""
Control de acceso facial - SOLO IMÁGENES, salida en terminal
Computación Ubicua - UDLA

Uso:
  python acceso_imagenes.py                      -> abre un selector para elegir imágenes
  python acceso_imagenes.py foto.jpg             -> evalúa una imagen
  python acceso_imagenes.py img1.jpg img2.png    -> evalúa varias
  python acceso_imagenes.py carpeta_imagenes/    -> evalúa todas las imágenes de la carpeta

Opciones:
  --puerto COM3   envía el resultado al Arduino ('G' = LED verde, 'R' = LED rojo)
  --mostrar       abre una ventana con la imagen y los rostros marcados
"""

import os
import sys
import time
import argparse

import cv2
import numpy as np

CASCADE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "haarcascade_frontalface_default.xml")
EXTENSIONES = (".jpg", ".jpeg", ".png", ".bmp", ".webp")
BAUDRATE = 9600

VERDE = "\033[92m"
ROJO = "\033[91m"
RESET = "\033[0m"


def cargar_modelo():
    cascade = cv2.CascadeClassifier(CASCADE_PATH)
    if cascade.empty():
        print(f"{ROJO}ERROR: no se pudo cargar el modelo {CASCADE_PATH}{RESET}")
        print("Copia haarcascade_frontalface_default.xml en la misma carpeta que este script.")
        sys.exit(1)
    return cascade


def detectar_rostros(cascade, imagen):
    gris = cv2.cvtColor(imagen, cv2.COLOR_BGR2GRAY)
    gris = cv2.equalizeHist(gris)
    return cascade.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60))


def conectar_arduino(puerto):
    try:
        import serial
    except ImportError:
        print(f"{ROJO}Falta pyserial: python -m pip install pyserial{RESET}")
        return None
    try:
        ser = serial.Serial(puerto, BAUDRATE, timeout=1)
        time.sleep(2)  # el Arduino se reinicia al abrir el puerto
        ser.reset_input_buffer()
        print(f"Conectado al Arduino en {puerto}\n")
        return ser
    except Exception as e:
        print(f"{ROJO}No se pudo abrir {puerto}: {e}{RESET}")
        print("Se continúa sin Arduino (solo terminal).\n")
        return None


def enviar(ser, comando):
    if ser is None:
        return
    ser.write(comando.encode())
    ser.flush()
    respuesta = ser.readline().decode(errors="ignore").strip()
    if respuesta:
        print(f"   Arduino -> {respuesta}")


def obtener_rutas(entradas):
    if not entradas:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        rutas = filedialog.askopenfilenames(
            title="Selecciona imágenes",
            filetypes=[("Imágenes", "*.jpg *.jpeg *.png *.bmp *.webp")])
        root.destroy()
        return list(rutas)

    rutas = []
    for e in entradas:
        if os.path.isdir(e):
            rutas += [os.path.join(e, f) for f in sorted(os.listdir(e))
                      if f.lower().endswith(EXTENSIONES)]
        else:
            rutas.append(e)
    return rutas


def main():
    parser = argparse.ArgumentParser(description="Control de acceso facial con imágenes")
    parser.add_argument("imagenes", nargs="*", help="imágenes o carpetas a evaluar")
    parser.add_argument("--puerto", help="puerto serial del Arduino, ej. COM3")
    parser.add_argument("--mostrar", action="store_true", help="mostrar la imagen con los rostros")
    args = parser.parse_args()

    cascade = cargar_modelo()
    rutas = obtener_rutas(args.imagenes)
    if not rutas:
        print("No se seleccionó ninguna imagen.")
        return

    ser = conectar_arduino(args.puerto) if args.puerto else None

    print("=" * 55)
    print(" SISTEMA DE CONTROL DE ACCESO - RECONOCIMIENTO FACIAL")
    print("=" * 55)

    correctos = denegados = 0
    for ruta in rutas:
        nombre = os.path.basename(ruta)
        # imdecode + fromfile en vez de imread: imread falla en Windows con tildes/ñ en la ruta
        imagen = (cv2.imdecode(np.fromfile(ruta, dtype=np.uint8), cv2.IMREAD_COLOR)
                  if os.path.isfile(ruta) else None)
        if imagen is None:
            print(f"\n[{nombre}] {ROJO}no se pudo leer la imagen{RESET}")
            continue

        rostros = detectar_rostros(cascade, imagen)
        acceso = len(rostros) > 0

        print(f"\nImagen: {nombre}")
        print(f"   Rostros detectados: {len(rostros)}")
        if acceso:
            print(f"   {VERDE}ROSTRO DETECTADO{RESET}")
            correctos += 1
            print(f"   {VERDE}>>> acceso correcto  (LED VERDE){RESET}")
            enviar(ser, "G")
        else:
            print(f"   {ROJO}NO SE DETECTÓ ROSTRO{RESET}")
            denegados += 1
            print(f"   {ROJO}>>> acceso denegado  (LED AMARILLO){RESET}")
            enviar(ser, "R")

        if args.mostrar:
            color = (0, 200, 0) if acceso else (0, 0, 255)
            for (x, y, w, h) in rostros:
                cv2.rectangle(imagen, (x, y), (x + w, y + h), color, 2)
            cv2.imshow(f"{nombre} - presiona una tecla", imagen)
            cv2.waitKey(0)
            cv2.destroyAllWindows()
        elif ser is not None and len(rutas) > 1:
            time.sleep(1.5)  # para que se vea el LED antes de la siguiente imagen

    print("\n" + "-" * 55)
    print(f" Total: {len(rutas)} | {VERDE}Correctos: {correctos}{RESET} | {ROJO}Denegados: {denegados}{RESET}")
    print("-" * 55)

    if ser is not None:
        ser.close()


if __name__ == "__main__":
    main()
