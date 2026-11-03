"""
test_tts.py
───────────
Prueba del sistema TTS con métricas detalladas:
  - Latencia del primer fragmento
  - Tiempo de generación separado del tiempo de reproducción
  - Tiempo solapado (generación mientras reproduce) — ahora debería ser > 0
  - RAM antes / durante / después
  - Estado del gestor cada 10 segundos
"""

import time, threading, psutil, os, sys, types
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from backend.Generacion.from_TTS import MOTOR, async_tts_manager

PROCESO = psutil.Process(os.getpid())

FRAGMENTOS = [
    "Hola encantado de conocerte. ¿En qué puedo ayudarte hoy?",
    "Soy un asistente virtual listo para ayudarte con cualquier tarea que necesites.",
    "Puedo generar audio mientras haces otras cosas, sin bloquear tu experiencia.",
    "¡Disfruta de la magia del texto a voz asíncrono!",
    "Este es un fragmento más para probar la eficiencia del pipeline.",
    "la hora actual es 3:45 PM y el clima está soleado con una temperatura de 25 grados.",
    "o puedo decir numeros grandes como 500 o 10000 o manejar pesos de 3.000 pesos",
    "1000 dividido 4 es igual a 250 aparte 3000 pesos colombianos",
    "mi nombre es jarvis y estoy aquí para servirte con mi voz personalizada.",
    "tu perro se llama ragnart y es un husky siberiano de 3 años, muy juguetón y cariñoso.",
]


# ─────────────────────────────────────────────
# UTILIDADES
# ─────────────────────────────────────────────

def ram_mb() -> float:
    return PROCESO.memory_info().rss / 1024 ** 2

def fmt_t(s: float) -> str:
    return f"{s:.2f}s" if s < 60 else f"{int(s//60)}m {s%60:.2f}s"

def separador(titulo: str = "", ancho: int = 58):
    if titulo:
        print(f"\n── {titulo} {'─'*(max(0, ancho - len(titulo) - 4))}")
    else:
        print("═" * ancho)

def imprimir_estado(etiqueta: str = ""):
    e   = async_tts_manager.obtener_estado()
    rep = "▶ reproduciendo" if e["reproduciendo"] else "⏸ en pausa"
    pre = f"[{etiqueta}] " if etiqueta else ""
    print(
        f"  {pre}RAM {ram_mb():.1f}MB  │  "
        f"Texto: {e['cola_texto']}  │  "
        f"Audio: {e['cola_audio']}  │  "
        f"Gen: {'✅' if e['gen_activo'] else '❌'}  │  "
        f"Play: {'✅' if e['play_activo'] else '❌'}  │  "
        f"{rep}"
    )


# ─────────────────────────────────────────────
# INSTRUMENTACIÓN
# Parchamos _generar y _reproducir para capturar
# tiempos sin tocar la lógica del pipeline.
# ─────────────────────────────────────────────

class MetricasFragmento:
    def __init__(self, indice: int, texto: str):
        self.indice      = indice
        self.texto       = texto[:55]
        self.t_gen       = 0.0
        self.t_play      = 0.0
        self.duracion_s  = 0.0
        self.ram_antes   = 0.0
        self.ram_despues = 0.0
        self.t_gen_fin   = 0.0   # timestamp absoluto cuando terminó de generarse

_metricas: list[MetricasFragmento] = []
_metricas_lock = threading.Lock()
_primer_audio_listo = threading.Event()

# ── Parchar _generar ──────────────────────────
_orig_generar = async_tts_manager._generar

def _generar_instrumentado(self, texto: str):
    with _metricas_lock:
        indice = len(_metricas)
        m = MetricasFragmento(indice, texto)
        _metricas.append(m)

    m.ram_antes = ram_mb()
    t0 = time.time()

    resultado = _orig_generar(texto)

    m.t_gen       = time.time() - t0
    m.t_gen_fin   = time.time()
    m.ram_despues = ram_mb()

    audio, samplerate = resultado
    m.duracion_s = len(audio) / samplerate

    if indice == 0:
        _primer_audio_listo.set()

    return resultado

async_tts_manager._generar = types.MethodType(_generar_instrumentado, async_tts_manager)

# ── Parchar _reproducir ───────────────────────
_orig_reproducir = async_tts_manager._reproducir

def _reproducir_instrumentado(self, audio, samplerate):
    # Buscar la métrica correspondiente por orden de reproducción
    with _metricas_lock:
        reproducidos = sum(1 for m in _metricas if m.t_play > 0)
        m = _metricas[reproducidos] if reproducidos < len(_metricas) else None

    t0 = time.time()
    _orig_reproducir(audio, samplerate)
    if m:
        m.t_play = time.time() - t0

async_tts_manager._reproducir = types.MethodType(_reproducir_instrumentado, async_tts_manager)


# ─────────────────────────────────────────────
# MONITOR PERIÓDICO (sin duplicados)
# ─────────────────────────────────────────────

_stop_monitor = threading.Event()

def _monitor_loop():
    t = 0
    while not _stop_monitor.wait(timeout=10):
        t += 10
        separador(f"Monitor +{t}s")
        imprimir_estado(f"t={t}s")

def iniciar_monitor() -> threading.Thread:
    _stop_monitor.clear()
    hilo = threading.Thread(target=_monitor_loop, daemon=True)
    hilo.start()
    return hilo

def detener_monitor(hilo: threading.Thread):
    _stop_monitor.set()
    hilo.join(timeout=2.0)


# ─────────────────────────────────────────────
# TEST PRINCIPAL
# ─────────────────────────────────────────────

def main():
    separador()
    print(f"  TEST TTS — motor: {MOTOR.upper()}")
    separador()

    ram_inicial = ram_mb()
    print(f"\n  RAM inicial:  {ram_inicial:.1f} MB")
    print(f"  Fragmentos:   {len(FRAGMENTOS)}\n")

    # ── Encolar ──────────────────────────────
    separador("Encolando")
    t_enc = time.time()
    for i, frag in enumerate(FRAGMENTOS, 1):
        async_tts_manager.hablar_async(frag)
        print(f"  [{i}/{len(FRAGMENTOS)}] → \"{frag[:55]}...\"")
    t_enc = time.time() - t_enc
    print(f"\n  ⏱  Encolado en: {fmt_t(t_enc)}")
    imprimir_estado("tras encolar")

    # ── Arrancar ─────────────────────────────
    separador("Procesando  (monitor cada 10s)")
    monitor   = iniciar_monitor()
    t_inicio  = time.time()

    print("  ⏳ Esperando primer fragmento listo...")
    _primer_audio_listo.wait()
    t_latencia = time.time() - t_inicio
    print(f"  🎯 Latencia primer fragmento: {fmt_t(t_latencia)}  ← lo que siente el usuario")

    # ── Tareas paralelas ─────────────────────
    n = 0
    while async_tts_manager._pendientes > 0:
        n += 1
        print(f"  ⚙️  Tarea paralela #{n}  (RAM: {ram_mb():.1f} MB)")
        time.sleep(2)

    async_tts_manager.esperar_cola_vacia()
    t_total = time.time() - t_inicio
    detener_monitor(monitor)

    # ── Detalle por fragmento ─────────────────
    separador("Detalle por fragmento")
    total_gen  = 0.0
    total_play = 0.0
    for m in _metricas:
        rtf   = m.t_gen / m.duracion_s if m.duracion_s > 0 else 0
        ram_d = m.ram_despues - m.ram_antes
        print(
            f"\n  Fragmento #{m.indice+1}: \"{m.texto}...\"\n"
            f"    Generación:    {fmt_t(m.t_gen)}  (RTF {rtf:.2f})\n"
            f"    Reproducción:  {fmt_t(m.t_play)}  (duración real: {m.duracion_s:.2f}s)\n"
            f"    RAM δ:         {ram_d:+.1f} MB  ({m.ram_antes:.0f} → {m.ram_despues:.0f} MB)"
        )
        total_gen  += m.t_gen
        total_play += m.t_play

    # Tiempo solapado: cuánto de la generación ocurrió durante reproducción
    # Con pipeline ideal: total_gen + total_play - t_total = solapamiento real
    solapado = max(0.0, total_gen + total_play - t_total)

    # ── Resumen final ─────────────────────────
    ram_final = ram_mb()
    separador()
    print("  RESUMEN FINAL")
    separador()
    print(f"  Motor:                  {MOTOR.upper()}")
    print(f"  Fragmentos:             {len(FRAGMENTOS)}")
    print(f"  ⏱  Tiempo total:        {fmt_t(t_total)}")
    print(f"  🎯 Latencia 1er frag:   {fmt_t(t_latencia)}  ← percepción del usuario")
    print(f"  🔧 Generación total:    {fmt_t(total_gen)}")
    print(f"  🔊 Reproducción total:  {fmt_t(total_play)}")
    print(f"  ⚡ Tiempo solapado:     {fmt_t(solapado)}  ← generación mientras reproduce")
    eficiencia = (solapado / total_gen * 100) if total_gen > 0 else 0
    print(f"  📊 Eficiencia pipeline: {eficiencia:.0f}%  ← cuánta generación se 'escondió'")
    print(f"  📈 RAM inicial:         {ram_inicial:.1f} MB")
    print(f"  📈 RAM final:           {ram_final:.1f} MB")
    print(f"  📈 RAM delta total:     {ram_final - ram_inicial:+.1f} MB")
    separador()
    imprimir_estado("final")
    print()

    async_tts_manager.shutdown()
    print("✅ Test completado.\n")


if __name__ == "__main__":
    main()
