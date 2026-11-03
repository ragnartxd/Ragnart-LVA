def decir_y_escuchar(instruccion: str,
                     idioma: str = "es-ES",
                     ajuste_ruido: float = 1.0,
                     timeout_escucha: float = 5.0,
                     phrase_time_limit: float = 5.0) -> str | None:

    from backend import yatusabe
    from backend.Generacion.from_TTS import hablar, estado_audio
    from backend.Gestor import gestor_audio
    import time, json

    # 1. Decir instrucción
    hablar(instruccion)

    # 2. ESPERAR a que termine el TTS (CLAVE)
    yatusabe.esperando_respuesta_directa = True
    time.sleep(0.15)  # pequeño delay para asegurar arranque
    inicio_tts = time.time()
    while estado_audio().get("reproduciendo", False):
        if time.time() - inicio_tts > 6.0:
            break
        time.sleep(0.05)

    # 3. Limpiar cola de audio (evita basura previa)
    gestor_audio._vaciar_queue()

    # 4. Activar procesamiento limpio
    gestor_audio.activar_procesamiento()

    rec = yatusabe.rec_main()
    rec.Reset()

    try:
        start_time = time.time()
        result = ""

        while True:
            data = gestor_audio.obtener_audio_data(timeout=0.1)

            if data is None:
                if time.time() - start_time > timeout_escucha:
                    return None
                continue

            # PROCESAMIENTO
            if rec.AcceptWaveform(data):
                result = rec.Result()
                break

            # límite de duración de frase
            if time.time() - start_time > phrase_time_limit:
                result = rec.FinalResult()
                break

        result_dict = json.loads(result)
        texto = result_dict.get("text", "").strip()

        return texto if texto else None

    except Exception as e:
        print(f"Error en decir_y_escuchar: {e}")
        return None

    finally:
        # 5. MUY IMPORTANTE: desactivar correctamente
        gestor_audio.desactivar()
        yatusabe.esperando_respuesta_directa = False
        rec.Reset()