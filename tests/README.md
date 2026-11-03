# Pruebas

Las pruebas automatizadas viven en esta carpeta. Para validar las funciones del sistema y su recorrido desde una orden de voz hasta el handler:

```powershell
mi_entorno\Scripts\python.exe -m unittest tests.test_funciones_sistema -v
```

Se simulan teclado, ventanas, PowerShell, red, audio y modelos para que las pruebas no ejecuten acciones reales en el equipo.

Las suites manuales conservan su ejecución independiente:

```powershell
python tests\suite_memoria_semantica.py
python tests\prueba_procesador_manual.py
python tests\prueba_tts_manual.py
python tests\prueba_audio_turno_local.py
```

Las dos pruebas manuales de audio inicializan Vosk/Kokoro y pueden intentar descargar modelos. Por eso no se incluyen en el descubrimiento automático de unittest.
