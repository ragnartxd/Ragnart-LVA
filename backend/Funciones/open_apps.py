import os, json, re, threading, logging, winreg, subprocess
from pathlib import Path
from typing import Dict, List, Optional, Union
from rapidfuzz import process, fuzz
from backend.utils.json_storage import guardar_json_atomico

class OpenApps:
    """
    Clase para abrir aplicaciones en Windows de forma portable.
    Funciona en cualquier PC sin depender de rutas específicas.
    """
    
    def __init__(self, fuzzy_threshold: int = 75, cache_enabled: bool = True):
        """
        Inicializa la clase OpenApps.
        
        Args:
            fuzzy_threshold: Umbral para coincidencia difusa (0-100)
            cache_enabled: Si se debe usar caché para mejorar rendimiento
        """
        self.fuzzy_threshold = fuzzy_threshold
        self.cache_enabled = cache_enabled
        
        # Configurar logging
        self.logger = logging.getLogger(__name__)
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            handler.setFormatter(formatter)
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
        
        # Inicializar estructuras de datos
        self.apps_cache: Dict[str, str] = {}
        self.registry_apps: Dict[str, str] = {}
        self.filesystem_apps: Dict[str, str] = {}
        self.uwp_apps: Dict[str, str] = {}
        
        # Directorio de configuración portable
        self.config_dir = self._get_config_dir()
        self.cache_file = self.config_dir / 'apps_cache.json'
        
        # Inicializar datos
        self._initialize()
    
    def _get_config_dir(self) -> Path:
        """Obtiene el directorio de configuración de forma portable."""
        appdata = os.getenv('APPDATA')
        if appdata:
            config_dir = Path(appdata) / 'VirtualAssistant'
        else:
            config_dir = Path.home() / '.virtualassistant'
        
        config_dir.mkdir(parents=True, exist_ok=True)
        return config_dir
    
    def _initialize(self):
        """Inicializa todos los sistemas de detección de aplicaciones."""
        if self.cache_enabled:
            self._load_cache()
        
        # Cargar aplicaciones de diferentes fuentes
        self._scan_registry()
        self._scan_filesystem()
        self._scan_uwp_apps()
        
        if self.cache_enabled:
            self._save_cache()
    
    def _load_cache(self):
        """Carga la caché desde archivo."""
        if self.cache_file.exists():
            try:
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.apps_cache = json.load(f)
                self.logger.debug(f"Cache cargada: {len(self.apps_cache)} aplicaciones")
            except (json.JSONDecodeError, IOError) as e:
                self.logger.warning(f"Error al cargar cache: {e}")
                self.apps_cache = {}
    
    def _save_cache(self):
        """Guarda la caché en archivo."""
        try:
            # Combinar todas las fuentes en la cache
            all_apps = {**self.registry_apps, **self.filesystem_apps, **self.apps_cache}
            guardar_json_atomico(
                self.cache_file,
                all_apps,
                ensure_ascii=False,
                indent=2,
                trailing_newline=False,
            )
            self.logger.debug(f"Cache guardada: {len(all_apps)} aplicaciones")
        except IOError as e:
            self.logger.error(f"Error al guardar cache: {e}")
    
    def _scan_registry(self):
        """Escanea el registro de Windows para encontrar aplicaciones."""
        self.logger.debug("Escaneando registro de Windows...")
        
        reg_paths = [
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
            (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
            (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        ]
        
        for root, subkey in reg_paths:
            try:
                with winreg.OpenKey(root, subkey) as key:
                    for i in range(winreg.QueryInfoKey(key)[0]):
                        try:
                            name = winreg.EnumKey(key, i)
                            with winreg.OpenKey(key, name) as app_key:
                                # Intentar obtener la ruta del ejecutable
                                path = None
                                try:
                                    path, _ = winreg.QueryValueEx(app_key, None)
                                except FileNotFoundError:
                                    try:
                                        path, _ = winreg.QueryValueEx(app_key, "DisplayIcon")
                                    except FileNotFoundError:
                                        try:
                                            path, _ = winreg.QueryValueEx(app_key, "InstallLocation")
                                        except FileNotFoundError:
                                            continue
                                
                                if path and os.path.exists(path):
                                    clean_name = self._clean_app_name(name)
                                    if clean_name:
                                        self.registry_apps[clean_name] = path
                        except (OSError, ValueError):
                            continue
            except OSError:
                continue
        
        self.logger.debug(f"Registro escaneado: {len(self.registry_apps)} aplicaciones encontradas")
    
    def _scan_filesystem(self):
        """Escanea el sistema de archivos para encontrar aplicaciones."""
        self.logger.debug("Escaneando sistema de archivos...")
        
        # Rutas estándar de Windows
        search_paths = [
            Path(os.getenv('ProgramFiles', 'C:/Program Files')),
            Path(os.getenv('ProgramFiles(x86)', 'C:/Program Files (x86)')),
            Path(os.path.expanduser("~")) / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path("C:/ProgramData/Microsoft/Windows/Start Menu/Programs"),
        ]
        
        # Agregar rutas del PATH
        path_env = os.getenv('PATH', '')
        for path_str in path_env.split(os.pathsep):
            if path_str.strip():
                search_paths.append(Path(path_str.strip()))
        
        for base_path in search_paths:
            if not base_path.exists():
                continue
            
            try:
                for root, dirs, files in os.walk(base_path):
                    # Limitar profundidad para evitar escaneos muy largos
                    level = len(Path(root).relative_to(base_path).parts)
                    if level > 3:
                        dirs.clear()
                        continue
                    
                    for file in files:
                        if file.lower().endswith(('.exe', '.lnk', '.url')):
                            clean_name = self._clean_app_name(file)
                            if clean_name and clean_name not in self.filesystem_apps:
                                full_path = str(Path(root) / file)
                                self.filesystem_apps[clean_name] = full_path
            except (OSError, PermissionError):
                continue
        
        self.logger.debug(f"Sistema de archivos escaneado: {len(self.filesystem_apps)} aplicaciones encontradas")
    
    def _scan_uwp_apps(self):
        """Escanea aplicaciones UWP/Store de Windows."""
        self.logger.debug("Escaneando aplicaciones UWP...")
        
        try:
            # Comando PowerShell para obtener aplicaciones UWP
            import subprocess
            result = subprocess.run([
                'powershell', '-Command',
                'Get-AppxPackage | Select-Object Name, PackageFamilyName | ConvertTo-Json'
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0 and result.stdout:
                apps_data = json.loads(result.stdout)
                if isinstance(apps_data, list):
                    for app in apps_data:
                        if isinstance(app, dict) and 'Name' in app:
                            clean_name = self._clean_app_name(app['Name'])
                            # Intentar obtener PackageFamilyName o PackageFullName
                            pkg = app.get('PackageFamilyName') or app.get('PackageFullName') or None
                            if clean_name and pkg:
                                # Guardar mapeo: 'netflix' -> '4DF9E0F8.Netflix_8wekyb3d8bbwe'
                                self.uwp_apps[clean_name] = pkg

        except (subprocess.TimeoutExpired, json.JSONDecodeError, ImportError, FileNotFoundError):
            # Si falla PowerShell, intentar método alternativo
            uwp_common = {
                'netflix', 'spotify', 'whatsapp', 'instagram', 'facebook',
                'twitter', 'youtube', 'microsoft store', 'calculator',
                'notepad', 'paint', 'photos', 'mail', 'calendar',
                'weather', 'news', 'maps', 'camera', 'voice recorder'
            }
            self.uwp_apps.update(uwp_common)
        
        self.logger.debug(f"UWP escaneado: {len(self.uwp_apps)} aplicaciones encontradas")
    
    def _clean_app_name(self, name: str) -> Optional[str]:
        """
        Limpia y normaliza el nombre de una aplicación.
        - Extrae correctamente el nombre real incluso desde UWP: "4DF9E0F8.Netflix" -> "netflix".
        - Evita instaladores/desinstaladores/actualizadores.
        - Maneja camelCase y tokens unidos.
        """
        if not name:
            return None

        # 1) Nombre base (sin eliminar sufijos tipo "package" que contienen '.')
        filename = Path(name).name
        # Sólo eliminar extensiones de archivo conocidas; no quitar tokens tipo ".Netflix"
        if re.search(r'\.(exe|lnk|url|msi|msix|appx)$', filename, re.IGNORECASE):
            base = Path(filename).stem.strip()
        else:
            base = filename.strip()

        if not base:
            return None

        # 2) Split por separadores comunes (., _, -, /, espacios)
        tokens = re.split(r'[._\-/\s]+', base)

        # 3) Expandir tokens tipo CamelCase (EpicGamesLauncher -> Epic, Games, Launcher)
        expanded = []
        for t in tokens:
            if not t:
                continue
            parts = re.findall(r'[A-Z]+(?=[A-Z][a-z])|[A-Z]?[a-z]+|[0-9]+', t)
            if parts:
                expanded.extend(parts)
            else:
                expanded.append(t)
        # normalizar a minúsculas
        tokens = [t.lower() for t in expanded if t]

        # 4) Eliminar tokens que son GUID / hex largos (ej. 4df9e0f8)
        tokens = [t for t in tokens if not re.fullmatch(r'[a-f0-9]{6,}', t)]

        # 5) Quitar tokens claramente irrelevantes (vendor / sistema)
        system_stop = {'microsoft', 'windows', 'win', 'uwp', 'app', 'application', 'desktop'}
        tokens = [t for t in tokens if t not in system_stop]

        if not tokens:
            return None

        # 6) Lista negra: si el conjunto contiene indicadores de instalador/desinstalador/soporte => descartar
        blacklist = {
            'uninstall', 'installer', 'setup', 'repair', 'update', 'updater', 'patch',
            'support', 'helper', 'assistant', 'cleanup', 'bugreport', 'feedback',
            'diagnostic', 'report', 'config', 'settings', 'crash', 'troubleshooter',
            'driver', 'firmware', 'utility', 'wizard', 'install'
        }
        joined = ''.join(tokens)
        if any(bad in joined for bad in blacklist):
            return None

        # 7) Preferir la última token "significativa" (no sufijo como 'music', 'app', 'desktop', etc.)
        suffixes = {'music', 'app', 'desktop', 'client', 'beta', 'store', 'viewer', 'player', 'service'}
        candidate = None
        for t in reversed(tokens):
            if t in suffixes:
                continue
            # preferir tokens con al menos una letra y longitud razonable
            if re.search(r'[a-z]', t) and len(t) >= 3:
                candidate = t
                break
        if not candidate:
            # fallback: tomar el último token válido
            candidate = tokens[-1]

        # 8) Si candidate es demasiado genérico (ej. 'games'), intentar juntar con token anterior
        generic_joiners = {'games', 'studio', 'team', 'labs', 'systems', 'soft'}
        if candidate in generic_joiners:
            # buscar token anterior si existe
            idx = None
            for i in range(len(tokens)-1, -1, -1):
                if tokens[i] == candidate:
                    idx = i
                    break
            if idx is not None and idx - 1 >= 0:
                prev = tokens[idx - 1]
                # unir prev+candidate (ej. epic + games -> epicgames)
                if prev and len(prev) >= 2:
                    candidate = prev + candidate

        # 9) Limpiar caracteres finales por si queda alguno
        candidate = re.sub(r'[^\w]', '', candidate).strip()

        # 10) Alias conocidos UWP (por si quedan nombres compactos)
        uwp_aliases = {
            'netflix': ['netflix', '4df9e0f8netflix', 'netflixinc', 'netflixapp'],
            'spotify': ['spotify', 'spotifyab', 'spotifyabspotifymusic'],
            'photos': ['photos', 'microsoftwindowsphotos', 'windowsphotos', 'photosapp'],
            'camera': ['camera', 'microsoftwindowscamera'],
            'calculator': ['calculator', 'microsoftwindowscalculator'],
            'store': ['store', 'microsoftstore', 'windowsstore'],
            'mail': ['mail', 'microsoftwindowscommunicationsapps'],
            'edge': ['edge', 'microsoftmicrosoftedge', 'microsoftedge'],
            'paint': ['paint', 'microsoftpaint', 'paintapp']
        }
        for alias, patterns in uwp_aliases.items():
            for p in patterns:
                if p in candidate:
                    return alias

        # 11) Filtrar nombres demasiado cortos o genéricos
        if len(candidate) < 3:
            return None
        if candidate in {'app', 'application', 'program', 'service', 'microsoft', 'windows'}:
            return None

        return candidate


    def _get_all_apps(self) -> Dict[str, str]:
        """Obtiene todas las aplicaciones disponibles."""
        all_apps = {}
        all_apps.update(self.apps_cache)
        all_apps.update(self.registry_apps)
        all_apps.update(self.filesystem_apps)
        return all_apps
    
    def _parse_apps_string(self, apps_string: str) -> List[str]:
        if not apps_string:
            return []
        
        apps_string = re.sub(r'[^\w\s]', '', apps_string).lower().strip()
        words = apps_string.split()
        all_apps = set(self.get_installed_apps())
        
        # Agrega esta línea para depurar
        print("¿Está 'netflix' en all_apps?", "netflix" in all_apps)
        
        max_app_words = max(len(app.split()) for app in all_apps) if all_apps else 1
        result = []
        i = 0
        while i < len(words):
            found = False
            for n in range(min(max_app_words, len(words) - i), 0, -1):
                candidate = ' '.join(words[i:i + n])
                if candidate in all_apps:
                    result.append(candidate)
                    i += n
                    found = True
                    break
            if not found:
                i += 1
        return result
    
    def _detect_known_apps_in_string(self, text: str) -> List[str]:
        """
        Detecta aplicaciones conocidas dentro de un texto continuo.
        """
        detected = []
        all_apps = self.get_installed_apps()
        
        # Buscar aplicaciones conocidas en el texto
        text_lower = text.lower()
        
        # Crear una lista de aplicaciones ordenadas por longitud (más largas primero)
        # para evitar que "note" capture "notepad"
        sorted_apps = sorted(all_apps, key=len, reverse=True)
        
        remaining_text = text_lower
        
        for app_name in sorted_apps:
            app_lower = app_name.lower()
            # Buscar la aplicación como palabra completa o parte del texto
            if app_lower in remaining_text:
                # Verificar que sea una palabra completa o al inicio/final
                pattern = r'\b' + re.escape(app_lower) + r'\b'
                if re.search(pattern, remaining_text):
                    detected.append(app_name)
                    # Remover la aplicación encontrada del texto restante
                    remaining_text = re.sub(pattern, '', remaining_text).strip()
        
        # Si se encontraron pocas apps, intentar búsqueda más flexible
        if len(detected) < 2:
            # Lista de aplicaciones comunes que podrían aparecer sin separadores
            common_apps = [
                'steam', 'netflix', 'chrome', 'firefox', 'discord', 'spotify', 
                'notepad', 'calculator', 'paint', 'word', 'excel', 'powerpoint',
                'photoshop', 'vlc', 'winrar', 'zoom', 'skype', 'teams',
                'outlook', 'whatsapp', 'telegram', 'youtube', 'twitch'
            ]
            
            detected_common = []
            remaining = text_lower
            
            for app in common_apps:
                if app in remaining:
                    # Verificar que no sea parte de otra palabra
                    if re.search(r'\b' + app + r'\b', remaining):
                        detected_common.append(app)
                        remaining = re.sub(r'\b' + app + r'\b', '', remaining).strip()
            
            if len(detected_common) > len(detected):
                return detected_common
        
        return detected
    
    def _could_be_app_name(self, word: str) -> bool:
        """
        Determina si una palabra podría ser el nombre de una aplicación.
        """
        # Palabras que probablemente NO son nombres de aplicaciones
        common_words = {
            'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
            'by', 'from', 'up', 'about', 'into', 'through', 'during', 'before',
            'after', 'above', 'below', 'between', 'among', 'through', 'during',
            'antes', 'despues', 'durante', 'entre', 'sobre', 'bajo', 'con', 'sin',
            'para', 'por', 'desde', 'hasta', 'hacia', 'contra', 'segun', 'mediante'
        }
        
        return word.lower() not in common_words and len(word) > 2
    
    def find_app_path(self, app_name: str) -> Optional[str]:
        """
        Encuentra la ruta de una aplicación usando coincidencia difusa.
        
        Args:
            app_name: Nombre de la aplicación a buscar
            
        Returns:
            Ruta de la aplicación o None si no se encuentra
        """
        app_name = app_name.lower().strip()
        all_apps = self._get_all_apps()
        
        # Búsqueda exacta
        if app_name in all_apps:
            path = all_apps[app_name]
            if os.path.exists(path):
                return path
        
        # Búsqueda por coincidencia parcial
        for name, path in all_apps.items():
            if app_name in name or name in app_name:
                if os.path.exists(path):
                    return path
        
        # Búsqueda difusa
        if len(all_apps) > 0:
            match, score, _ = process.extractOne(
                app_name, list(all_apps.keys()), scorer=fuzz.WRatio
            )
            
            if score >= self.fuzzy_threshold:
                path = all_apps[match]
                if os.path.exists(path):
                    self.logger.debug(f"Coincidencia difusa: '{app_name}' -> '{match}' ({score}%)")
                    return path
        
        return None
    
    def open_app(self, app_name: str) -> str:
        """
        Abre una aplicación específica.
        
        Args:
            app_name: Nombre de la aplicación
            
        Returns:
            Mensaje de resultado
        """
        app_name = app_name.strip()
        
        # Intentar encontrar la ruta de la aplicación
        app_path = self.find_app_path(app_name)
        
        if app_path:
            try:
                # Abrir en hilo separado para no bloquear
                threading.Thread(
                    target=os.startfile,
                    args=(app_path,),
                    daemon=True
                ).start()
                return f"✅ Abriendo {app_name}..."
            except Exception as e:
                self.logger.error(f"Error al abrir {app_name}: {e}")
                return f"❌ Error al abrir {app_name}: {str(e)}"
        
        # Intentar como aplicación UWP
                # Intentar como aplicación UWP usando PackageFamilyName
        clean_name = self._clean_app_name(app_name)
        pkg = self.uwp_apps.get(clean_name)
        if pkg:
            try:
                # Lanza la UWP mediante shell:AppsFolder\<PackageFamilyName>!App
                subprocess.Popen(
                    ['explorer.exe', f'shell:AppsFolder\\{pkg}!App'],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
                )
                self.logger.info(f"🔀 Lanzado UWP {app_name} -> {pkg}")
                return f"✅ Intentando abrir {app_name} (UWP)..."
            except Exception as e:
                self.logger.error(f"Error al abrir UWP {app_name}: {e}")

        
        # Último intento: búsqueda en PATH
        try:
            os.system(f'start "" "{app_name}"')
            return f"🔄 Intentando abrir {app_name}..."
        except Exception as e:
            return f"❌ No se pudo encontrar la aplicación '{app_name}'"
    
    def open_multiple_apps(self, apps_input: Union[str, List[str]]) -> str:
        """
        Abre múltiples aplicaciones.
        
        Args:
            apps_input: String con nombres separados o lista de nombres
            
        Returns:
            Mensaje con resultados de todas las aplicaciones
        """
        if isinstance(apps_input, str):
            apps_list = self._parse_apps_string(apps_input)
            self.logger.debug(f"🔍 Input: '{apps_input}' -> Detectadas: {apps_list}")
        elif isinstance(apps_input, list):
            apps_list = [app.strip().lower() for app in apps_input if app.strip()]
            self.logger.debug(f"📝 Lista recibida: {apps_list}")
        else:
            return "❌ Formato de entrada no válido"
        
        if not apps_list:
            return "❌ No se especificaron aplicaciones para abrir"
        
        self.logger.info(f"🚀 Intentando abrir {len(apps_list)} aplicaciones: {apps_list}")
        
        results = []
        for i, app in enumerate(apps_list, 1):
            self.logger.debug(f"📱 {i}/{len(apps_list)}: Procesando '{app}'")
            result = self.open_app(app)
            results.append(result)
        
        return " la aplicacion se abrio ".join(results)
    
    def refresh_apps_list(self):
        """Actualiza la lista de aplicaciones escaneando nuevamente."""
        self.logger.info("Actualizando lista de aplicaciones...")
        self.registry_apps.clear()
        self.filesystem_apps.clear()
        self.uwp_apps.clear()
        self._initialize()
        self.logger.info("Lista de aplicaciones actualizada")
    
    def get_installed_apps(self) -> List[str]:
        """
        Obtiene una lista de todas las aplicaciones instaladas.
        
        Returns:
            Lista de nombres de aplicaciones
        """
        all_apps = self._get_all_apps()
        uwp_list = list(self.uwp_apps)
        return sorted(list(set(all_apps.keys()) | set(uwp_list)))
    
    def abrir_aplicacion_por_nombre(self, **kwargs) -> str:
        """
        Método de conveniencia compatible con Gestor_Parametros.
        
        Args:
            **kwargs: Parámetros que deben incluir 'nombre_app'
            
        Returns:
            Mensaje con el resultado de abrir las aplicaciones
        """
        # Extraer el nombre de la aplicación de los parámetros
        nombre_app = kwargs.get('nombre_app', '')
        
        if not nombre_app:
            return "❌ No se especificó ninguna aplicación para abrir"
        
        self.logger.info(f"🎯 Solicitud de apertura: '{nombre_app}'")
        
        # Usar el método principal para abrir múltiples aplicaciones
        return self.open_multiple_apps(nombre_app)
    
    def get_stats(self) -> Dict[str, int]:
        """
        Obtiene estadísticas de las aplicaciones detectadas.
        
        Returns:
            Diccionario con estadísticas
        """
        return {
            'registry_apps': len(self.registry_apps),
            'filesystem_apps': len(self.filesystem_apps),
            'uwp_apps': len(self.uwp_apps),
            'cached_apps': len(self.apps_cache),
            'total_apps': len(self.get_installed_apps())
        }

    def search_apps(self, query: str, limit: int = 5):
        """
        Busca aplicaciones instaladas usando coincidencia difusa.

        Args:
            query: Texto de búsqueda
            limit: Número máximo de resultados

        Returns:
            Lista de tuplas (nombre_app, score)
        """
        all_apps = self.get_installed_apps()
        results = process.extract(query, all_apps, scorer=fuzz.WRatio, limit=limit)
        # results: List of tuples (match, score, index)
        return [(match, score) for match, score, _ in results]


# Ejemplo de uso y testing
if __name__ == "__main__":
    # Crear instancia de la clase
    opener = OpenApps()

