"""
Test del clasificador de intenciones — 3 capas

Estructura esperada del proyecto:
    proyecto/
    ├── importaciones/
    │   └── intents.json        ← aquí vive el json
    ├── backend/
    │   ├── Gestor/
    │   │   └── procesador_intencion.py
    └── tests/
        └── prueba_procesador_manual.py

Ejecutar desde la raíz del proyecto:
    python tests/prueba_procesador_manual.py
"""

import sys, os, time

# ─── Rutas ───────────────────────────────────────────────────────────────────
PROJECT_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR  = os.path.join(PROJECT_DIR, "backend")
INTENTS_PATH = os.path.join(PROJECT_DIR, "importaciones", "intenciones", "intents.json")

sys.path.insert(0, BACKEND_DIR)

if not os.path.exists(INTENTS_PATH):
    print(f"\n❌ No se encontró intents.json en:\n   {INTENTS_PATH}")
    print("   Asegúrate de que importaciones/ existe al mismo nivel que backend/\n")
    sys.exit(1)

# ─── Colores terminal ────────────────────────────────────────────────────────
VERDE    = "\033[92m"
ROJO     = "\033[91m"
AMARILLO = "\033[93m"
AZUL     = "\033[94m"
GRIS     = "\033[90m"
RESET    = "\033[0m"
BOLD     = "\033[1m"

def color_capa(capa):
    if capa == 0: return f"\033[95mCapa 0 (spaCy){RESET}"
    if capa == 1: return f"{VERDE}Capa 1 (sinónimos){RESET}"
    if capa == 2: return f"{AZUL}Capa 2 (embeddings){RESET}"
    if capa == 3: return f"{AMARILLO}Capa 3 (RoBERTa){RESET}"
    return "Capa ?"

def color_accion(accion, tipo):
    if tipo == "conversacion": return f"{GRIS}{accion}{RESET}"
    if accion == "preguntar":  return f"{ROJO}{accion}{RESET}"
    return f"{VERDE}{accion}{RESET}"

# ─── Casos de prueba ─────────────────────────────────────────────────────────
CASOS = [

    # ================================
    # ABRIR APLICACIÓN
    # ================================
    ("abre el navegador", "abrir_aplicacion"),
    ("abre google chrome", "abrir_aplicacion"),
    ("inicia chrome", "abrir_aplicacion"),
    ("lanza el navegador", "abrir_aplicacion"),
    ("abre spotify", "abrir_aplicacion"),
    ("abre discord por favor", "abrir_aplicacion"),
    ("puedes abrir telegram", "abrir_aplicacion"),
    ("quiero abrir el bloc de notas", "abrir_aplicacion"),
    ("abre visual studio code", "abrir_aplicacion"),
    ("abre el panel de configuración", "abrir_configuracion"),
    ("muéstrame el panel de configuración", "abrir_configuracion"),
    ("abre chrome si puedes", "abrir_aplicacion"),
    ("abre chrome ahora mismo", "abrir_aplicacion"),
    ("abre chrome maldita sea", "abrir_aplicacion"),
    ("abre chrome por favor gracias", "abrir_aplicacion"),
    ("abre chrome cuando puedas", "abrir_aplicacion"),
    ("necesito que abras el navegador", "abrir_aplicacion"),
    ("pon a correr spotify", "abrir_aplicacion"),
    ("ejecuta el notepad", "abrir_aplicacion"),

    # ================================
    # CERRAR APLICACIÓN
    # ================================
    ("cierra chrome", "cerrar_aplicacion"),
    ("cierra el navegador", "cerrar_aplicacion"),
    ("sal de discord", "cerrar_aplicacion"),
    ("termina spotify", "cerrar_aplicacion"),
    ("cierra la aplicación actual", "cerrar_aplicacion"),
    ("mata el proceso de chrome", "cerrar_aplicacion"),
    ("cierra discord ahora mismo", "cerrar_aplicacion"),
    ("cierra discord si puedes", "cerrar_aplicacion"),
    ("apaga spotify", "cerrar_aplicacion"),
    ("cierra todo", "cerrar_aplicacion"),

    # ================================
    # VOLUMEN
    # ================================
    ("sube un poco el volumen", "subir_volumen"),
    ("sube el audio", "subir_volumen"),
    ("aumenta el volumen", "subir_volumen"),
    ("sube el volumen ya", "subir_volumen"),
    ("sube el volumen por favor", "subir_volumen"),
    ("sube el volumen si no es molestia", "subir_volumen"),
    ("ponle más volumen", "subir_volumen"),
    ("haz que suene más fuerte", "subir_volumen"),
    ("baja el audio", "bajar_volumen"),
    ("reduce el volumen", "bajar_volumen"),
    ("baja el volumen inmediatamente", "bajar_volumen"),
    ("baja el volumen por favor", "bajar_volumen"),
    ("silencia el audio", "bajar_volumen"),
    ("mutea el audio", "bajar_volumen"),
    ("quítale volumen", "bajar_volumen"),
    ("haz que suene más bajo", "bajar_volumen"),
    ("silencia el sistema", "bajar_volumen"),

    # ================================
    # BRILLO
    # ================================
    ("sube el brillo", "ajustar_brillo"),
    ("aumenta el brillo de la pantalla", "ajustar_brillo"),
    ("la pantalla está muy brillante bájala", "ajustar_brillo"),
    ("reduce el brillo", "ajustar_brillo"),
    ("haz la pantalla más oscura", "ajustar_brillo"),
    ("haz la pantalla más clara", "ajustar_brillo"),
    ("baja el brillo un poco", "ajustar_brillo"),
    ("pon el brillo al máximo", "ajustar_brillo"),

    # ================================
    # CAPTURA DE PANTALLA
    # ================================
    ("haz una captura", "tomar_captura"),
    ("captura la pantalla", "tomar_captura"),
    ("saca un screenshot", "tomar_captura"),
    ("toma screenshot", "tomar_captura"),
    ("guarda una captura de pantalla", "tomar_captura"),
    ("necesito una captura ahora", "tomar_captura"),
    ("fotografía la pantalla", "tomar_captura"),

    # ================================
    # SISTEMA
    # ================================
    ("bloquea el computador", "bloquear_sistema"),
    ("bloquea la computadora", "bloquear_sistema"),
    ("bloquea el equipo", "bloquear_sistema"),
    ("suspende el sistema", "suspender_sistema"),
    ("pon el equipo en suspensión", "suspender_sistema"),
    ("apaga el computador", "apagar_sistema"),
    ("apaga el equipo", "apagar_sistema"),
    ("reinicia el computador", "reiniciar_sistema"),
    ("reinicia el sistema", "reiniciar_sistema"),

    # ================================
    # ALARMA Y TEMPORIZADOR
    # ================================
    ("pon un temporizador de 10 minutos", "poner_cronometro"),
    ("inicia un cronómetro", "poner_cronometro"),
    ("activa un temporizador de 30 segundos", "poner_cronometro"),
    ("pon una alarma para mañana", "poner_alarma"),
    ("despiértame a las 6", "poner_alarma"),
    ("crea una alarma a las 8 de la mañana", "poner_alarma"),
    ("ponme una alarma para las 7", "poner_alarma"),

    # ================================
    # CLIMA
    # ================================
    ("cómo está el clima hoy", "consultar_clima"),
    ("va a llover hoy", "consultar_clima"),
    ("qué clima hay en bogotá", "consultar_clima"),
    ("temperatura actual", "consultar_clima"),
    ("qué clima hará mañana", "consultar_clima"),
    ("está lloviendo afuera", "consultar_clima"),
    ("necesito saber el clima", "consultar_clima"),
    ("quiero saber si va a llover", "consultar_clima"),

    # ================================
    # NOTICIAS
    # ================================
    ("qué noticias hay hoy", "consultar_noticias"),
    ("dame las noticias del día", "consultar_noticias"),
    ("muéstrame titulares", "consultar_noticias"),
    ("noticias de tecnología", "consultar_noticias"),
    ("quiero saber qué pasa en el mundo", "consultar_noticias"),
    ("qué pasó hoy en el mundo", "consultar_noticias"),
    ("hay algo importante en las noticias", "consultar_noticias"),

    # ================================
    # WIKIPEDIA
    # ================================
    ("quién fue albert einstein", "consultar_wikipedia"),
    ("qué es un agujero negro", "consultar_wikipedia"),
    ("busca información sobre inteligencia artificial", "consultar_wikipedia"),
    ("explícame qué es la fotosíntesis", "consultar_wikipedia"),
    ("tengo curiosidad por los agujeros negros", "consultar_wikipedia"),
    ("cuéntame sobre la segunda guerra mundial", "consultar_wikipedia"),
    ("qué es el cambio climático", "consultar_wikipedia"),
    ("quién inventó el teléfono", "consultar_wikipedia"),

    # ================================
    # MENSAJES Y CORREO
    # ================================
    ("envía un whatsapp a juan", "enviar_whatsapp"),
    ("escríbele a carlos por whatsapp", "enviar_whatsapp"),
    ("manda mensaje a ana", "enviar_whatsapp"),
    ("manda un email a mi jefe", "enviar_correo"),
    ("envía un correo a maria", "enviar_correo"),
    ("redacta un email para soporte", "enviar_correo"),
    ("escríbele un correo a pedro", "enviar_correo"),

    # ================================
    # CIFRADO
    # ================================
    ("encripta este archivo", "cifrar_archivo"),
    ("cifra este documento", "cifrar_archivo"),
    ("desencripta este archivo", "descifrar_archivo"),
    ("descifra el documento", "descifrar_archivo"),
    ("quiero cifrar esta carpeta", "cifrar_archivo"),

    # ================================
    # VENTANAS
    # ================================
    ("maximiza la ventana", "maximizar_aplicacion"),
    ("pon la aplicación en pantalla completa", "maximizar_aplicacion"),
    ("minimiza la ventana", "minimizar_aplicacion"),
    ("pon la ventana en la mitad", "minimizar_aplicacion"),

    # ================================
    # CONVERSACIÓN
    # ================================
    ("hola", "conversacion"),
    ("qué tal", "conversacion"),
    ("cómo estás hoy", "conversacion"),
    ("cuéntame algo interesante", "conversacion"),
    ("dime un dato curioso", "conversacion"),
    ("cuéntame una historia", "conversacion"),
    ("qué opinas del futuro de la ia", "conversacion"),
    ("me aburro", "conversacion"),
    ("estoy cansado", "conversacion"),
    ("qué puedes hacer tú", "conversacion"),
    ("cuál es tu nombre", "conversacion"),
    ("háblame de música", "conversacion"),

    # ================================
    # IMPLÍCITOS — VOLUMEN
    # ================================
    ("no escucho nada", "subir_volumen"),
    ("esto suena muy fuerte", "bajar_volumen"),
    ("el audio casi no se escucha", "subir_volumen"),
    ("esto está demasiado ruidoso", "bajar_volumen"),
    ("no oigo nada", "subir_volumen"),
    ("el volumen está muy bajo", "subir_volumen"),
    ("me está reventando los oídos", "bajar_volumen"),
    ("está muy alto el sonido", "bajar_volumen"),
    ("apenas se escucha algo", "subir_volumen"),

    # ================================
    # IMPLÍCITOS — BRILLO
    # ================================
    ("no veo bien la pantalla", "ajustar_brillo"),
    ("la pantalla me está quemando los ojos", "ajustar_brillo"),
    ("no puedo ver bien la pantalla", "ajustar_brillo"),
    ("la pantalla está muy oscura", "ajustar_brillo"),
    ("me encandila la pantalla", "ajustar_brillo"),
    ("no distingo nada en la pantalla", "ajustar_brillo"),

    # ================================
    # IMPLÍCITOS — ALARMA / NOTICIAS / CLIMA
    # ================================
    ("quiero dormir temprano mañana", "poner_alarma"),
    ("quiero levantarme temprano mañana", "conversacion"),  # ambiguo sin hora
    ("quiero saber qué pasa en el mundo", "consultar_noticias"),
    ("tengo curiosidad por los agujeros negros", "consultar_wikipedia"),

    # ================================
    # ADVERSARIALES — RUIDO EN LA FRASE
    # ================================
    ("abre chrome si puedes", "abrir_aplicacion"),
    ("abre chrome ahora mismo", "abrir_aplicacion"),
    ("abre chrome maldita sea", "abrir_aplicacion"),
    ("abre chrome por favor gracias", "abrir_aplicacion"),
    ("abre chrome cuando puedas", "abrir_aplicacion"),
    ("sube el volumen ya", "subir_volumen"),
    ("sube el volumen por favor", "subir_volumen"),
    ("sube el volumen si no es molestia", "subir_volumen"),
    ("baja el volumen inmediatamente", "bajar_volumen"),
    ("baja el volumen por favor", "bajar_volumen"),
    ("cierra discord ahora mismo", "cerrar_aplicacion"),
    ("cierra discord si puedes", "cerrar_aplicacion"),
    ("oye abre chrome", "abrir_aplicacion"),
    ("mira necesito que abras spotify", "abrir_aplicacion"),
    ("che podés cerrar discord", "cerrar_aplicacion"),

    # ================================
    # MULTI-INTENCIÓN
    # ================================
    ("abre chrome y luego spotify", None),
    ("sube el volumen y abre youtube", None),
    ("cierra discord y abre telegram", None),
    ("baja el brillo y silencia el audio", None),
    ("abre chrome y busca gatos", None),
    ("abre spotify y sube el volumen", None),
    ("apaga la pantalla y pon una alarma para mañana", None),
    ("cierra chrome y abre firefox", None),

    # ================================
    # NEGACIÓN
    # ================================
    ("no abras chrome", None),
    ("no abras discord", None),
    ("no subas el volumen", None),
    ("no bajes el volumen", None),
    ("no cierres spotify", None),
    ("no tomes captura de pantalla", None),
    ("no pongas ninguna alarma", None),
    ("no abras el navegador", None),
    ("no quiero que abras chrome", None),
    ("no subas el brillo", None),
    ("no apagues el equipo", None),
    ("no reinicies el sistema", None),
    ("no me mandes mensajes", None),
    ("no cierres nada", None),

    # ================================
    # AMBIGUOS / BORDE
    # ================================
    ("sube eso", None),           # sin contexto, ambiguo
    ("baja eso", None),           # sin contexto, ambiguo
    ("abre eso", None),           # sin contexto, ambiguo
    ("ciérralo", None),           # clítico sin contexto
    ("ponlo arriba", None),       # ambiguo
    ("abre chrome y firefox", None),
    ("dime las diferencias entre el agua y el fuego", "conversacion"),
    ("cuéntame sobre la historia y la geografía de colombia", "conversacion"),
    ("se me está pasando la hora muy rápido", "conversacion"),
]

# ─── Runner ──────────────────────────────────────────────────────────────────
def ejecutar_tests():
    print(f"\n{BOLD}{'='*65}{RESET}")
    print(f"{BOLD}  TEST CLASIFICADOR DE INTENCIONES — 3 CAPAS{RESET}")
    print(f"{BOLD}{'='*65}{RESET}")
    print(f"  proyecto/ → {PROJECT_DIR}")
    print(f"  intents   → {INTENTS_PATH}\n")

    print("⏳ Cargando módulo (spaCy + embeddings)...")
    t0 = time.time()
    try:
        from Gestor.procesador_intencion import (
            procesar_intencion, clasificar_subcomando, limpiar_texto, analizar_estructura
        )
    except ModuleNotFoundError as e:
        print(f"{ROJO}❌ Error de importación: {e}{RESET}")
        print("   Ejecuta el script desde dentro de backend/")
        sys.exit(1)
    print(f"✅ Módulo listo en {time.time()-t0:.1f}s\n")

    ok_count = fallo_count = obs_count = 0
    tiempos = []

    for i, (frase, intent_esp) in enumerate(CASOS, 1):
        t_ini = time.time()
        try:
            texto_limpio = limpiar_texto(frase)
            señales = analizar_estructura(texto_limpio)
            intent_det, matched, score, tipo = clasificar_subcomando(texto_limpio, señales)
            acciones = procesar_intencion(frase)
            t_ms = (time.time() - t_ini) * 1000
            tiempos.append(t_ms)

            accion_principal = acciones[0]["accion"] if acciones else "ninguna"
            tipo_principal   = acciones[0]["tipo"]   if acciones else "?"

            # Detectar qué capa resolvió
            if señales["es_descriptiva"] and not señales["es_imperativa"]:
                capa_usada = 0  # spaCy → conversación directa
            elif señales["intent_directo"]:
                capa_usada = 0  # spaCy → imperativo directo
            elif score == 1.0 and matched is not None:
                capa_usada = 1
            elif score >= 0.72:
                capa_usada = 2
            else:
                capa_usada = 3

            if intent_esp is None:
                estado = f"{AZUL}ℹ{RESET}"
                obs_count += 1
                razon_fallo = ""
            else:
                paso = accion_principal == intent_esp
                if paso:
                    estado = f"{VERDE}✓{RESET}"
                    ok_count += 1
                    razon_fallo = ""
                else:
                    estado = f"{ROJO}✗{RESET}"
                    fallo_count += 1
                    razon_fallo = f"esperaba [{intent_esp}] → obtuvo [{accion_principal}]"

            print(f"[{i:02d}] {estado} {BOLD}{frase!r}{RESET}")
            print(f"      → {color_accion(accion_principal, tipo_principal)}"
                  f"  score={score:.3f}  {color_capa(capa_usada)}  {t_ms:.0f}ms")

            if razon_fallo:
                print(f"      {ROJO}⚠  {razon_fallo}{RESET}")
            if len(acciones) > 1:
                print(f"      📋 {[a['accion'] for a in acciones]}")

        except Exception as e:
            t_ms = (time.time() - t_ini) * 1000
            print(f"[{i:02d}] {ROJO}✗ EXCEPCIÓN en {frase!r}{RESET}")
            print(f"      {ROJO}{type(e).__name__}: {e}{RESET}")
            fallo_count += 1

        print()

    evaluados = ok_count + fallo_count
    pct = (ok_count / evaluados * 100) if evaluados > 0 else 0

    print(f"{BOLD}{'─'*65}{RESET}")
    print(f"{BOLD}  RESUMEN{RESET}")
    print(f"{'─'*65}")
    print(f"  {VERDE}✓ Correctos  : {ok_count}{RESET}")
    print(f"  {ROJO}✗ Fallos     : {fallo_count}{RESET}")
    print(f"  {AZUL}ℹ Observados : {obs_count}{RESET}")
    print(f"  📊 Precisión : {BOLD}{pct:.1f}%{RESET}  ({ok_count}/{evaluados})")
    if tiempos:
        print(f"  ⏱  Tiempos   : "
              f"avg={sum(tiempos)/len(tiempos):.0f}ms  "
              f"min={min(tiempos):.0f}ms  "
              f"max={max(tiempos):.0f}ms")
    print(f"{BOLD}{'─'*65}{RESET}\n")

    if fallo_count == 0:
        print(f"{VERDE}{BOLD}  🎉 Todos los tests pasaron.{RESET}\n")
    else:
        print(f"{AMARILLO}{BOLD}  ⚠  Hay fallos. Ajustes sugeridos:{RESET}")
        print(f"  · Muchos fallos en Capa 2 → baja UMBRAL_EMBEDDING_ALTO (0.72 → 0.65)")
        print(f"  · Embedding adivina mal   → sube UMBRAL_EMBEDDING_ALTO (0.72 → 0.80)")
        print(f"  · RoBERTa aparece siempre → agrega más ejemplos al intent en intents.json\n")


if __name__ == "__main__":
    ejecutar_tests()
