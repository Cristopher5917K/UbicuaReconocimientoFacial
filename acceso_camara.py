

import sys
import time
import argparse

import cv2

from acceso_imagenes import (cargar_modelo, detectar_rostros, conectar_arduino,
                             enviar, VERDE, ROJO, RESET)

FRAMES_CONFIRMACION = 5   

def main():
    parser = argparse.ArgumentParser(description="Control de acceso facial con cámara")
    parser.add_argument("--puerto", help="puerto serial del Arduino, ej. COM5")
    parser.add_argument("--camara", type=int, default=0, help="índice de la cámara (0 por defecto)")
    args = parser.parse_args()

    cascade = cargar_modelo()
    ser = conectar_arduino(args.puerto) if args.puerto else None

    if sys.platform.startswith("win"):
        cap = cv2.VideoCapture(args.camara, cv2.CAP_DSHOW)
    else:
        cap = cv2.VideoCapture(args.camara)
    if not cap.isOpened():
        print(f"{ROJO}No se pudo abrir la cámara {args.camara}.{RESET}")
        return

    print("=" * 55)
    print(" CONTROL DE ACCESO - CÁMARA EN VIVO  (q para salir)")
    print("=" * 55)

    estado = None            # True = acceso, False = denegado
    candidato, contador = None, 0

    try:
        while True:
            ok, frame = cap.read()
            if not ok:
                print(f"{ROJO}No se pudo leer de la cámara.{RESET}")
                break
            frame = cv2.flip(frame, 1)

            rostros = detectar_rostros(cascade, frame)
            acceso = len(rostros) > 0

            # Confirmación por varios frames para evitar parpadeo del LED
            if acceso == candidato:
                contador += 1
            else:
                candidato, contador = acceso, 1

            if contador >= FRAMES_CONFIRMACION and acceso != estado:
                estado = acceso
                hora = time.strftime("%H:%M:%S")
                if acceso:
                    print(f"\n[{hora}] {VERDE}ROSTRO DETECTADO ({len(rostros)}){RESET}")
                    print(f"   {VERDE}>>> acceso correcto  (LED VERDE){RESET}")
                    enviar(ser, "G")
                else:
                    print(f"\n[{hora}] {ROJO}NO SE DETECTÓ ROSTRO{RESET}")
                    print(f"   {ROJO}>>> acceso denegado  (LED AMARILLO){RESET}")
                    enviar(ser, "R")

            # Ventana de video con los rostros marcados
            color = (0, 200, 0) if estado else (0, 0, 255)
            for (x, y, w, h) in rostros:
                cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            texto = "ACCESO CORRECTO" if estado else "ACCESO DENEGADO"
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 40), color, -1)
            cv2.putText(frame, texto, (10, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (255, 255, 255), 2)
            cv2.imshow("Camara - pulsa q para salir", frame)

            if cv2.waitKey(1) & 0xFF in (ord("q"), 27):
                break
    finally:
        cap.release()
        cv2.destroyAllWindows()
        if ser is not None:
            enviar(ser, "O")   # apaga los LEDs al salir
            ser.close()
        print("\nCámara cerrada.")


if __name__ == "__main__":
    main()
