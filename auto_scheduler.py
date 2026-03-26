import schedule
import time
import subprocess
import sys
from datetime import datetime

def job_publicar():
    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Iniciando publicacion automatica programada...")
    
    # Ejecutamos el script publisher.py usando el mismo ejecutable de python actual
    try:
        resultado = subprocess.run([sys.executable, "publisher.py"], capture_output=True, text=True, encoding="utf-8")
        print("--- SALIDA DEL SCRIPT ---")
        print(resultado.stdout)
        
        if resultado.stderr:
            print("--- ERRORES (SI LOS HAY) ---")
            print(resultado.stderr)
            
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Tarea de publicacion finalizada con exito.")
    except Exception as e:
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Error al intentar correr el script: {e}")

# Configuracion de la hora (puedes cambiar "18:00" por la hora a la que quieras que publique en formato 24h)
HORA_PUBLICACION = "10:00"

print(f"Inicializando el Programador de Tareas MEGAGYM...")
print(f"El sistema ejecutara 'publisher.py' todos los dias a las {HORA_PUBLICACION}.")
print("NOTA: Necesitas dejar esta ventana de consola abierta o minimizada para que el reloj interno siga funcionando.\n")

# Programamos el horario
schedule.every().day.at(HORA_PUBLICACION).do(job_publicar)

# Bucle infinito que evalua el horario cada minuto
try:
    while True:
        schedule.run_pending()
        time.sleep(60) # Pausamos el bucle 60 segundos para no consumir recursos (CPU)
except KeyboardInterrupt:
    print("\nProgramador detenido manualmente por el usuario.")
