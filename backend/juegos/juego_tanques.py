import pygame
import random
import math
from pygame import mixer
import sys

# Inicialización
pygame.init()
mixer.init()
ANCHO, ALTO = 900, 700
pantalla = pygame.display.set_mode((ANCHO, ALTO))
pygame.display.set_caption("Batalla de Cañones - Edición Mejorada")
icono = pygame.Surface((32, 32))
icono.fill((200, 50, 50))
pygame.draw.circle(icono, (50, 50, 50), (16, 16), 12)
pygame.display.set_icon(icono)

# Fuentes
fuente_titulo = pygame.font.SysFont("Arial Black", 48)
fuente_normal = pygame.font.SysFont("Arial", 28)
fuente_pequeña = pygame.font.SysFont("Arial", 18)

# Colores
BLANCO = (255, 255, 255)
NEGRO = (0, 0, 0)
ROJO = (220, 20, 60)
AZUL = (30, 144, 255)
VERDE = (34, 139, 34)
VERDE_CLARO = (144, 238, 144)
CIELO = (135, 206, 235)
MARRON = (139, 69, 19)
GRIS = (128, 128, 128)
GRIS_OSCURO = (80, 80, 80)
NARANJA = (255, 165, 0)
AMARILLO = (255, 255, 0)

# Configuración de SFX y música (implementación sin dependencia de TTS)
class Sonido:
    def __init__(self):
        self.volumen = 0.5
        self.efectos = {}
        # Simularemos efectos con sonidos básicos de pygame
        self.cargar_sonidos()
        
    def cargar_sonidos(self):
        # Creamos sonidos básicos programáticamente
        self.efectos["disparo"] = self._crear_sonido_disparo()
        self.efectos["explosion"] = self._crear_sonido_explosion()
        self.efectos["victoria"] = self._crear_sonido_victoria()
        self.efectos["impacto"] = self._crear_sonido_impacto()
        
    def _crear_sonido_disparo(self):
        sonido = mixer.Sound(buffer=bytes([128]*22050))
        return sonido
        
    def _crear_sonido_explosion(self):
        sonido = mixer.Sound(buffer=bytes([128]*44100))
        return sonido
        
    def _crear_sonido_victoria(self):
        sonido = mixer.Sound(buffer=bytes([128]*22050))
        return sonido
        
    def _crear_sonido_impacto(self):
        sonido = mixer.Sound(buffer=bytes([128]*11025))
        return sonido
        
    def reproducir(self, efecto):
        if efecto in self.efectos:
            self.efectos[efecto].set_volume(self.volumen)
            self.efectos[efecto].play()
            
    def hablar(self, texto):
        # Simulación de TTS con un mensaje en pantalla
        global mensaje_actual, tiempo_mensaje
        mensaje_actual = texto
        tiempo_mensaje = pygame.time.get_ticks() + 3000  # Mostrar durante 3 segundos

# Variables globales para mensajes
mensaje_actual = ""
tiempo_mensaje = 0
sonido = Sonido()

# Terreno destructible
class Terreno:
    def __init__(self, ancho, alto):
        self.ancho = ancho
        self.alto = alto
        self.superficie = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        self.generar()
        self.mask = None
        
    def generar(self):
        # Crear terreno con forma de colinas
        self.superficie.fill((0, 0, 0, 0))
        puntos = []
        for x in range(0, self.ancho+1, 50):
            y = random.randint(self.alto//2, self.alto-100)
            puntos.append((x, y))
        
        # Suavizar terreno
        puntos_suaves = []
        for i in range(len(puntos)-1):
            x1, y1 = puntos[i]
            x2, y2 = puntos[i+1]
            for t in range(51):
                if i < len(puntos)-1:
                    x = x1 + (x2-x1) * t/50
                    y = y1 + (y2-y1) * t/50
                    puntos_suaves.append((x, y))
        
        # Dibujar terreno
        for x, altura in enumerate(puntos_suaves):
            if x < self.ancho:
                pygame.draw.line(self.superficie, MARRON, (x, altura[1]), (x, self.alto), 1)
        
        # Agregar detalles al terreno
        for _ in range(50):
            x = random.randint(0, self.ancho-20)
            y = random.randint(self.alto//2, self.alto-50)
            radio = random.randint(5, 15)
            pygame.draw.circle(self.superficie, VERDE_CLARO, (x, y), radio)
        
        self.actualizar_mask()
        
    def actualizar_mask(self):
        self.mask = pygame.mask.from_surface(self.superficie)
        
    def dibujar(self, pantalla):
        pantalla.blit(self.superficie, (0, 0))
        
    def explotar(self, x, y, radio):
        # Crear explosión circular
        pygame.draw.circle(self.superficie, (0, 0, 0, 0), (int(x), int(y)), radio)
        self.actualizar_mask()
        
    def colision_punto(self, x, y):
        if 0 <= x < self.ancho and 0 <= y < self.alto:
            try:
                pixel = self.superficie.get_at((int(x), int(y)))
                return pixel[3] > 0  # Verificar canal alfa
            except IndexError:
                return False
        return y >= self.alto  # Considerar que el suelo fuera de la pantalla siempre colisiona

# Mensajes para el juego
mensajes_cpu = [
    "¡Eres más lento que una bala sin pólvora!",
    "¿Eso fue un disparo o una caricia?",
    "¡Vamos! ¡Apunta mejor!",
    "¿Jugando o dando pena?",
    "¡Mi abuela dispara mejor!",
    "¡Te hace falta práctica!",
    "¡Ni le has rozado!"
]

mensajes_dos = [
    "¡Esta batalla está que arde!",
    "¡Disparen, cobardes!",
    "¡Vamos, no se queden dormidos!",
    "¡Esto sí que es guerra!",
    "¡Fuego a discreción!",
    "¡Demuestra tu puntería!",
    "¡Haz que valga la pena!"
]

# Efectos de partículas
class SistemaParticulas:
    def __init__(self):
        self.particulas = []
        
    def crear_explosion(self, x, y, color, cantidad=30):
        for _ in range(cantidad):
            velocidad = random.uniform(2, 8)
            angulo = random.uniform(0, 2 * math.pi)
            dx = math.cos(angulo) * velocidad
            dy = math.sin(angulo) * velocidad
            vida = random.randint(30, 60)
            tamaño = random.randint(2, 6)
            self.particulas.append({
                'x': x, 'y': y, 'dx': dx, 'dy': dy,
                'vida': vida, 'max_vida': vida,
                'color': color, 'tamaño': tamaño
            })
            
    def crear_humo(self, x, y):
        for _ in range(10):
            velocidad = random.uniform(0.5, 1.5)
            angulo = random.uniform(-math.pi*0.7, -math.pi*0.3)  # Hacia arriba principalmente
            dx = math.cos(angulo) * velocidad
            dy = math.sin(angulo) * velocidad
            vida = random.randint(40, 80)
            tamaño = random.randint(3, 8)
            self.particulas.append({
                'x': x, 'y': y, 'dx': dx, 'dy': dy,
                'vida': vida, 'max_vida': vida,
                'color': GRIS, 'tamaño': tamaño
            })
    
    def actualizar(self):
        for p in self.particulas[:]:
            p['x'] += p['dx']
            p['y'] += p['dy']
            p['dy'] += 0.1  # Gravedad
            p['vida'] -= 1
            if p['vida'] <= 0:
                self.particulas.remove(p)
                
    def dibujar(self, pantalla):
        for p in self.particulas:
            # Hacer que se desvanezcan con el tiempo
            alfa = int(255 * p['vida'] / p['max_vida'])
            color = list(p['color'])
            if len(color) == 3:
                color.append(alfa)
            else:
                color[3] = alfa
            
            radio = p['tamaño'] * p['vida'] / p['max_vida']
            pygame.draw.circle(pantalla, color, (int(p['x']), int(p['y'])), int(radio))

# PowerUps
class PowerUp:
    def __init__(self, x, y, tipo):
        self.x = x
        self.y = y
        self.tipo = tipo  # 'triple', 'health', 'power'
        self.radio = 15
        self.activo = True
        self.bobbing = 0
        
    def dibujar(self, pantalla):
        # Efecto de bobbing (flotar)
        self.bobbing += 0.05
        offset_y = math.sin(self.bobbing) * 5
        
        # Dibujar según tipo
        if self.tipo == 'triple':
            color = AMARILLO
            texto = "3X"
        elif self.tipo == 'health':
            color = (50, 200, 50)
            texto = "+"
        elif self.tipo == 'power':
            color = NARANJA
            texto = "P"
        
        pygame.draw.circle(pantalla, color, (int(self.x), int(self.y + offset_y)), self.radio)
        texto_img = fuente_pequeña.render(texto, True, NEGRO)
        pantalla.blit(texto_img, (self.x - texto_img.get_width()//2, self.y - texto_img.get_height()//2 + offset_y))
        
    def colisiona(self, x, y, radio=5):
        distancia = math.sqrt((self.x - x)**2 + (self.y - y)**2)
        return distancia < self.radio + radio

# Clase Jugador Mejorada
class Jugador:
    def __init__(self, x, color, nombre="Jugador"):
        self.x = x
        self.y = ALTO - 150
        self.angulo = 45
        self.color = color
        self.potencia = 20
        self.potencia_max = 40
        self.vida = 100
        self.nombre = nombre
        self.puntos = 0
        
        # Mejoras
        self.proyectiles = 1  # Cantidad de proyectiles (powerup triple)
        self.tamaño_proyectil = 5
        self.daño_base = 20
        
        # Estados y animación
        self.cargando = False
        self.tiempo_carga = 0
        self.cooldown = 0
        
        # Calcular posición real según terreno
        self.ajustar_altura()
        
    def ajustar_altura(self):
        # Buscar el terreno debajo del jugador
        for y_test in range(ALTO - 1, 0, -1):
            if terreno.colision_punto(self.x, y_test):
                self.y = y_test - 20
                break
        
    def dibujar(self, pantalla):
        # Base del cañón
        pygame.draw.circle(pantalla, self.color, (int(self.x), int(self.y)), 20)
        pygame.draw.circle(pantalla, NEGRO, (int(self.x), int(self.y)), 20, 2)
        
        # Cañón
        rad = math.radians(self.angulo)
        fin_x = self.x + math.cos(rad) * 40
        fin_y = self.y - math.sin(rad) * 40
        pygame.draw.line(pantalla, GRIS_OSCURO, (self.x, self.y), (fin_x, fin_y), 8)
        
        # Barra de potencia si está cargando
        if self.cargando:
            potencia_ratio = self.tiempo_carga / 100
            ancho_barra = 40 * potencia_ratio
            pygame.draw.rect(pantalla, NARANJA, (self.x - 20, self.y - 40, ancho_barra, 5))
        
        # Barra de vida
        vida_w = 40 * (self.vida / 100)
        pygame.draw.rect(pantalla, ROJO, (self.x - 20, self.y - 30, 40, 5))
        pygame.draw.rect(pantalla, (50, 200, 50), (self.x - 20, self.y - 30, vida_w, 5))
        
        # Nombre del jugador
        texto_nombre = fuente_pequeña.render(self.nombre, True, self.color)
        pantalla.blit(texto_nombre, (self.x - texto_nombre.get_width()//2, self.y - 50))

    def disparar(self):
        rad = math.radians(self.angulo)
        potencia_actual = self.potencia if not self.cargando else min(5 + self.tiempo_carga / 5, self.potencia_max)
        dx = math.cos(rad) * potencia_actual
        dy = -math.sin(rad) * potencia_actual
        
        proyectiles = []
        if self.proyectiles == 1:
            proyectiles.append(Proyectil(self.x, self.y, dx, dy, self.tamaño_proyectil, self.daño_base, self.color))
        else:
            # Disparo triple
            for i in range(self.proyectiles):
                ang_offset = (i - (self.proyectiles-1)/2) * 5
                rad_nuevo = math.radians(self.angulo + ang_offset)
                dx_nuevo = math.cos(rad_nuevo) * potencia_actual
                dy_nuevo = -math.sin(rad_nuevo) * potencia_actual
                proyectiles.append(Proyectil(self.x, self.y, dx_nuevo, dy_nuevo, self.tamaño_proyectil, self.daño_base, self.color))
        
        self.cooldown = 10  # Pequeño cooldown entre disparos
        sonido.reproducir("disparo")
        return proyectiles

# Clase Proyectil Mejorada
class Proyectil:
    def __init__(self, x, y, dx, dy, tamaño=5, daño=20, color=NEGRO):
        self.x = x
        self.y = y
        self.dx = dx
        self.dy = dy
        self.tamaño = tamaño
        self.daño = daño
        self.color = color
        self.activo = True
        self.estela = []
        
    def mover(self):
        # Guardar posición anterior para la estela
        self.estela.append((self.x, self.y))
        if len(self.estela) > 10:
            self.estela.pop(0)
            
        # Física
        self.x += self.dx
        self.y += self.dy
        self.dy += 0.2  # Gravedad
        
        # Fricción
        self.dx *= 0.99
        
    def dibujar(self, pantalla):
        # Dibujar estela
        for i, (ex, ey) in enumerate(self.estela):
            alfa = i * 25  # Transparencia aumenta con el índice
            radio = (i / len(self.estela)) * self.tamaño
            pygame.draw.circle(pantalla, (*self.color, alfa), (int(ex), int(ey)), int(radio))
        
        # Dibujar proyectil
        pygame.draw.circle(pantalla, self.color, (int(self.x), int(self.y)), self.tamaño)
        
    def colisiona(self, jugador):
        distancia = math.sqrt((self.x - jugador.x)**2 + (self.y - jugador.y)**2)
        return distancia < 20 + self.tamaño
    
    def colisiona_terreno(self):
        return terreno.colision_punto(self.x, self.y)
    
    def colisiona_powerup(self, powerups):
        for pu in powerups:
            if pu.colisiona(self.x, self.y, self.tamaño):
                return pu
        return None
        
    def explotar(self, particulas, radio=30):
        # Crear explosión visual
        particulas.crear_explosion(self.x, self.y, NARANJA, 20)
        particulas.crear_explosion(self.x, self.y, ROJO, 10)
        
        # Modificar terreno
        terreno.explotar(self.x, self.y, radio)
        
        sonido.reproducir("explosion")

# Menú principal
def mostrar_menu():
    fondo = pygame.Surface((ANCHO, ALTO))
    fondo.fill(CIELO)
    
    # Dibujar terreno decorativo
    for i in range(0, ANCHO, 2):
        altura = int(ALTO/2 + ALTO/6 * math.sin(i/100))
        pygame.draw.line(fondo, MARRON, (i, altura), (i, ALTO), 2)
    
    # Título con sombra
    titulo_texto = "BATALLA DE CAÑONES"
    sombra = fuente_titulo.render(titulo_texto, True, NEGRO)
    titulo = fuente_titulo.render(titulo_texto, True, BLANCO)
    fondo.blit(sombra, (ANCHO//2 - sombra.get_width()//2 + 3, ALTO//4 + 3))
    fondo.blit(titulo, (ANCHO//2 - titulo.get_width()//2, ALTO//4))
    
    # Botones
    boton1 = pygame.Rect(ANCHO//2 - 150, ALTO//2 - 10, 300, 60)
    boton2 = pygame.Rect(ANCHO//2 - 150, ALTO//2 + 80, 300, 60)
    
    # Dibujar botones con borde y sombra
    pygame.draw.rect(fondo, NEGRO, boton1.inflate(6, 6))
    pygame.draw.rect(fondo, AZUL, boton1)
    pygame.draw.rect(fondo, BLANCO, boton1, 2)
    
    pygame.draw.rect(fondo, NEGRO, boton2.inflate(6, 6))
    pygame.draw.rect(fondo, ROJO, boton2)
    pygame.draw.rect(fondo, BLANCO, boton2, 2)
    
    texto1 = fuente_normal.render("1 Jugador (vs CPU)", True, BLANCO)
    texto2 = fuente_normal.render("2 Jugadores", True, BLANCO)
    
    fondo.blit(texto1, (ANCHO//2 - texto1.get_width()//2, ALTO//2 + 10))
    fondo.blit(texto2, (ANCHO//2 - texto2.get_width()//2, ALTO//2 + 100))
    
    # Instrucciones
    instrucciones = [
        "Controles:",
        "P1: Flechas direccionales + Espacio (mantener para cargar)",
        "P2: W,A,S,D + Enter (mantener para cargar)",
        "Destruye el terreno y elimina a tu oponente",
        "Recoge power-ups para mejorar tus habilidades"
    ]
    
    y_pos = ALTO//2 + 160
    for instruccion in instrucciones:
        texto = fuente_pequeña.render(instruccion, True, BLANCO)
        fondo.blit(texto, (ANCHO//2 - texto.get_width()//2, y_pos))
        y_pos += 25
    
    pantalla.blit(fondo, (0, 0))
    pygame.display.flip()

    while True:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif evento.type == pygame.MOUSEBUTTONDOWN:
                if boton1.collidepoint(evento.pos):
                    return "cpu"
                elif boton2.collidepoint(evento.pos):
                    return "2"
                    
        pygame.display.flip()
        reloj = pygame.time.Clock()
        reloj.tick(60)

# Crear fondo con gradiente de cielo
def crear_fondo():
    fondo = pygame.Surface((ANCHO, ALTO))
    for y in range(ALTO):
        # Gradiente de azul para el cielo
        tono = max(0, min(255, int(135 + (y / ALTO) * 100)))
        pygame.draw.line(fondo, (135, 206, tono), (0, y), (ANCHO, y))
    
    # Añadir nubes
    for _ in range(6):
        x = random.randint(0, ANCHO)
        y = random.randint(0, ALTO//3)
        tamaño = random.randint(30, 100)
        for i in range(3):
            offset_x = random.randint(-tamaño//2, tamaño//2)
            offset_y = random.randint(-tamaño//4, tamaño//4)
            pygame.draw.circle(fondo, BLANCO, (x + offset_x, y + offset_y), tamaño//2)
    
    return fondo

# Pantalla de victoria
def mostrar_victoria(ganador):
    fondo = pygame.Surface((ANCHO, ALTO))
    fondo.fill(CIELO)
    
    texto = fuente_titulo.render(f"¡{ganador} ha ganado!", True, NARANJA)
    texto_rect = texto.get_rect(center=(ANCHO//2, ALTO//3))
    sombra = fuente_titulo.render(f"¡{ganador} ha ganado!", True, NEGRO)
    sombra_rect = sombra.get_rect(center=(ANCHO//2 + 3, ALTO//3 + 3))
    
    fondo.blit(sombra, sombra_rect)
    fondo.blit(texto, texto_rect)
    
    instruccion = fuente_normal.render("Presiona ESPACIO para jugar de nuevo", True, BLANCO)
    instruccion_rect = instruccion.get_rect(center=(ANCHO//2, ALTO//2 + 50))
    fondo.blit(instruccion, instruccion_rect)
    
    instruccion2 = fuente_normal.render("Presiona ESC para volver al menú", True, BLANCO)
    instruccion2_rect = instruccion2.get_rect(center=(ANCHO//2, ALTO//2 + 100))
    fondo.blit(instruccion2, instruccion2_rect)
    
    pantalla.blit(fondo, (0, 0))
    pygame.display.flip()
    
    sonido.reproducir("victoria")
    
    while True:
        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            elif evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_SPACE:
                    return True  # Jugar de nuevo
                elif evento.key == pygame.K_ESCAPE:
                    return False  # Volver al menú

# Añadir PowerUp aleatorio
def generar_powerup():
    tipos = ['triple', 'health', 'power']
    tipo = random.choice(tipos)
    x = random.randint(100, ANCHO-100)
    y = random.randint(100, ALTO//2)
    return PowerUp(x, y, tipo)

# Juego principal mejorado
def main():
    global terreno, mensaje_actual, tiempo_mensaje
    
    while True:
        modo_juego = mostrar_menu()
        jugando = True
        
        while jugando:
            # Inicializar el juego
            reloj = pygame.time.Clock()
            terreno = Terreno(ANCHO, ALTO)
            particulas = SistemaParticulas()
            fondo = crear_fondo()
            
            jugador1 = Jugador(100, AZUL, "Jugador 1")
            jugador2 = Jugador(ANCHO - 100, ROJO, "CPU" if modo_juego == "cpu" else "Jugador 2")
            
            # Ajustar altura inicial según terreno
            jugador1.ajustar_altura()
            jugador2.ajustar_altura()
            
            proyectiles = []
            powerups = []
            turno = 1
            turno_contador = 0
            
            # Probabilidades de spawn
            powerup_timer = 0
            
            corriendo = True
            
            while corriendo:
                tiempo_actual = pygame.time.get_ticks()
                
                # Procesar eventos
                for evento in pygame.event.get():
                    if evento.type == pygame.QUIT:
                        pygame.quit()
                        sys.exit()
                    
                    # Controles de disparos
                    if evento.type == pygame.KEYUP:
                        if turno == 1 and evento.key == pygame.K_SPACE and jugador1.cargando:
                            nuevos_proyectiles = jugador1.disparar()
                            proyectiles.extend(nuevos_proyectiles)
                            jugador1.cargando = False
                            jugador1.tiempo_carga = 0
                            turno_contador = 60  # Tiempo para mostrar la trayectoria
                        elif turno == 2 and modo_juego == "2" and evento.key == pygame.K_RETURN and jugador2.cargando:
                            nuevos_proyectiles = jugador2.disparar()
                            proyectiles.extend(nuevos_proyectiles)
                            jugador2.cargando = False
                            jugador2.tiempo_carga = 0
                            turno_contador = 60
                
                teclas = pygame.key.get_pressed()
                
                # Actualizar PowerUp Timer
                powerup_timer -= 1
                if powerup_timer <= 0 and len(powerups) < 3:
                    powerups.append(generar_powerup())
                    powerup_timer = random.randint(300, 600)  # 5-10 segundos
                
                # Controles de jugadores
                if turno == 1 and turno_contador == 0:
                    # Jugador 1
                    if jugador1.cooldown > 0:
                        jugador1.cooldown -= 1
                    
                    if teclas[pygame.K_LEFT]:
                        jugador1.x = max(jugador1.x - 3, 25)
                        jugador1.ajustar_altura()
                    if teclas[pygame.K_RIGHT]:
                        jugador1.x = min(jugador1.x + 3, ANCHO - 25)
                        jugador1.ajustar_altura()
                    if teclas[pygame.K_UP]:
                        jugador1.angulo = min(jugador1.angulo + 1, 90)
                    if teclas[pygame.K_DOWN]:
                        jugador1.angulo = max(jugador1.angulo - 1, 0)
                    
                    # Disparo cargado
                    if teclas[pygame.K_SPACE] and not proyectiles and jugador1.cooldown == 0:
                        if not jugador1.cargando:
                            jugador1.cargando = True
                            jugador1.tiempo_carga = 0
                        else:
                            jugador1.tiempo_carga = min(jugador1.tiempo_carga + 2, 100)
                            particulas.crear_humo(jugador1.x + math.cos(math.radians(jugador1.angulo)) * 40, 
                                             jugador1.y - math.sin(math.radians(jugador1.angulo)) * 40)
                
                elif turno == 2 and turno_contador == 0:
                    if jugador2.cooldown > 0:
                        jugador2.cooldown -= 1
                        
                    if modo_juego == "2":
                        # Control manual para modo 2 jugadores
                        if teclas[pygame.K_a]:
                            jugador2.x = max(jugador2.x - 3, 25)
                            jugador2.ajustar_altura()
                        if teclas[pygame.K_d]:
                            jugador2.x = min(jugador2.x + 3, ANCHO - 25)
                            jugador2.ajustar_altura()
                        if teclas[pygame.K_w]:
                            jugador2.angulo = min(jugador2.angulo + 1, 180)
                        if teclas[pygame.K_s]:
                            jugador2.angulo = max(jugador2.angulo - 1, 90)
                            
                        # Disparo cargado para jugador 2
                        if teclas[pygame.K_RETURN] and not proyectiles and jugador2.cooldown == 0:
                            if not jugador2.cargando:
                                jugador2.cargando = True
                                jugador2.jugador2.tiempo_carga = 0
                            else:
                                jugador2.tiempo_carga = min(jugador2.tiempo_carga + 2, 100)
                                particulas.crear_humo(jugador2.x + math.cos(math.radians(jugador2.angulo)) * 40, 
                                                 jugador2.y - math.sin(math.radians(jugador2.angulo)) * 40)
                    else:
                        # IA para CPU
                        if not proyectiles and jugador2.cooldown == 0:
                            # Movimiento aleatorio a veces
                            if random.random() < 0.02:
                                direccion = random.choice([-1, 1])
                                jugador2.x += direccion * 3
                                jugador2.x = max(25, min(jugador2.x, ANCHO - 25))
                                jugador2.ajustar_altura()
                            
                            # Apuntar al jugador con algo de variación
                            dx = jugador1.x - jugador2.x
                            dy = jugador1.y - jugador2.y
                            distancia = math.sqrt(dx*dx + dy*dy)
                            
                            # Calcular ángulo ideal con un poco de error
                            angulo_base = 180 - math.degrees(math.atan2(-dy, dx))
                            ajuste_distancia = random.uniform(0.8, 1.2) * (distancia / 15)
                            angulo_objetivo = angulo_base - ajuste_distancia
                            
                            # Limitar ángulo
                            angulo_objetivo = max(90, min(angulo_objetivo, 180))
                            
                            # Ajustar ángulo gradualmente
                            if jugador2.angulo < angulo_objetivo:
                                jugador2.angulo += 1
                            elif jugador2.angulo > angulo_objetivo:
                                jugador2.angulo -= 1
                            
                            # Cargar y disparar
                            if not jugador2.cargando:
                                jugador2.cargando = True
                                jugador2.tiempo_carga = 0
                            else:
                                # CPU carga más rápido según dificultad
                                jugador2.tiempo_carga = min(jugador2.tiempo_carga + 3, 100)
                                particulas.crear_humo(jugador2.x + math.cos(math.radians(jugador2.angulo)) * 40, 
                                                 jugador2.y - math.sin(math.radians(jugador2.angulo)) * 40)
                                
                                # Disparar cuando esté suficientemente cargado
                                if jugador2.tiempo_carga >= random.randint(60, 100):
                                    nuevos_proyectiles = jugador2.disparar()
                                    proyectiles.extend(nuevos_proyectiles)
                                    jugador2.cargando = False
                                    jugador2.tiempo_carga = 0
                                    mensaje_random = random.choice(mensajes_cpu)
                                    sonido.hablar(mensaje_random)
                                    turno_contador = 60
                
                # Contador de turno
                if turno_contador > 0:
                    turno_contador -= 1
                    if turno_contador == 0 and not proyectiles:
                        # Cambiar turno
                        turno = 2 if turno == 1 else 1
                
                # Actualizar proyectiles
                for p in proyectiles[:]:
                    p.mover()
                    
                    # Comprobar colisiones con jugadores
                    jugador_impactado = None
                    if turno == 1 and p.colisiona(jugador2):
                        jugador_impactado = jugador2
                    elif turno == 2 and p.colisiona(jugador1):
                        jugador_impactado = jugador1
                    
                    if jugador_impactado:
                        jugador_impactado.vida -= p.daño
                        p.explotar(particulas, 20)
                        proyectiles.remove(p)
                        sonido.reproducir("impacto")
                        continue
                    
                    # Comprobar colisiones con terreno
                    if p.colisiona_terreno():
                        p.explotar(particulas, 30)
                        proyectiles.remove(p)
                        continue
                    
                    # Comprobar límites del mapa
                    if p.x < 0 or p.x > ANCHO or p.y > ALTO:
                        proyectiles.remove(p)
                        continue
                    
                    # Comprobar colisiones con powerups
                    powerup_colision = p.colisiona_powerup(powerups)
                    if powerup_colision:
                        # Aplicar efecto según tipo
                        jugador_actual = jugador1 if turno == 1 else jugador2
                        if powerup_colision.tipo == 'triple':
                            jugador_actual.proyectiles = 3
                        elif powerup_colision.tipo == 'health':
                            jugador_actual.vida = min(jugador_actual.vida + 25, 100)
                        elif powerup_colision.tipo == 'power':
                            jugador_actual.daño_base += 10
                            jugador_actual.tamaño_proyectil += 1
                        
                        powerups.remove(powerup_colision)
                        p.explotar(particulas, 15)
                        proyectiles.remove(p)
                
                # Actualizar partículas
                particulas.actualizar()
                
                # Comprobar condición de victoria
                if jugador1.vida <= 0 or jugador2.vida <= 0:
                    ganador = jugador1.nombre if jugador2.vida <= 0 else jugador2.nombre
                    jugar_de_nuevo = mostrar_victoria(ganador)
                    if jugar_de_nuevo:
                        break  # Reinicia el juego
                    else:
                        corriendo = False
                        jugando = False
                
                # Dibujar escena
                pantalla.blit(fondo, (0, 0))
                
                # Dibujar terreno
                terreno.dibujar(pantalla)
                
                # Dibujar PowerUps
                for pu in powerups:
                    pu.dibujar(pantalla)
                
                # Dibujar jugadores
                jugador1.dibujar(pantalla)
                jugador2.dibujar(pantalla)
                
                # Dibujar proyectiles
                for p in proyectiles:
                    p.dibujar(pantalla)
                
                # Dibujar partículas
                particulas.dibujar(pantalla)
                
                # Mostrar HUD
                panel_info = pygame.Surface((ANCHO, 40))
                panel_info.fill((0, 0, 0, 128))
                panel_info.set_alpha(180)
                pantalla.blit(panel_info, (0, 0))
                
                # Información de jugadores en HUD
                texto_j1 = f"{jugador1.nombre}: {jugador1.vida}% | Daño: {jugador1.daño_base} | Proyectiles: {jugador1.proyectiles}"
                texto_j2 = f"{jugador2.nombre}: {jugador2.vida}% | Daño: {jugador2.daño_base} | Proyectiles: {jugador2.proyectiles}"
                
                img_j1 = fuente_normal.render(texto_j1, True, jugador1.color)
                img_j2 = fuente_normal.render(texto_j2, True, jugador2.color)
                
                pantalla.blit(img_j1, (10, 10))
                pantalla.blit(img_j2, (ANCHO - img_j2.get_width() - 10, 10))
                
                # Indicador de turno
                texto_turno = f"Turno: {'Jugador 1' if turno == 1 else 'Jugador 2'}"
                img_turno = fuente_normal.render(texto_turno, True, AZUL if turno == 1 else ROJO)
                pantalla.blit(img_turno, (ANCHO//2 - img_turno.get_width()//2, 10))
                
                # Mostrar mensajes de TTS simulados
                if tiempo_actual < tiempo_mensaje and mensaje_actual:
                    fondo_msg = pygame.Surface((ANCHO, 60))
                    fondo_msg.fill((0, 0, 0))
                    fondo_msg.set_alpha(150)
                    pantalla.blit(fondo_msg, (0, ALTO - 60))
                    
                    msg_img = fuente_normal.render(mensaje_actual, True, BLANCO)
                    pantalla.blit(msg_img, (ANCHO//2 - msg_img.get_width()//2, ALTO - 40))
                
                pygame.display.flip()
                reloj.tick(60)

# Función para mensajes random
def mensaje_random(modo, turno):
    if modo == "cpu" and turno == 1:
        mensaje = random.choice(mensajes_cpu)
        sonido.hablar(mensaje)
    elif modo == "2":
        mensaje = random.choice(mensajes_dos)
        sonido.hablar(mensaje)

# Punto de entrada principal
if __name__ == "__main__":
    pygame.display.set_caption("Batalla de Cañones - Edición Mejorada")
    main()
    pygame.quit()
    sys.exit()