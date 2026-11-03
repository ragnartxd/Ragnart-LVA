import pygame
import random

# Inicializar Pygame
pygame.init()

# Dimensiones de la pantalla
ancho_pantalla = 400
alto_pantalla = 600
pantalla = pygame.display.set_mode((ancho_pantalla, alto_pantalla))
pygame.display.set_caption("Flappy Python (Código Puro)")

# Colores
blanco = (255, 255, 255)
amarillo = (255, 255, 0)
verde = (0, 255, 0)
rojo = (255, 0, 0)
azul_claro = (135, 206, 235)
marron = (139, 69, 19)
verde_tubo = (76, 187, 23)

# Clase para el pájaro
class Pajaro(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__()
        self.radio = 18
        self.color = amarillo
        self.image = pygame.Surface((self.radio * 2, self.radio * 2), pygame.SRCALPHA) # Crear una superficie transparente
        pygame.draw.circle(self.image, self.color, (self.radio, self.radio), self.radio)
        self.rect = self.image.get_rect(center=(x, y))
        self.velocidad = 0
        self.gravedad = 0.5
        self.impulso = -10

    def update(self):
        self.velocidad += self.gravedad
        self.rect.y += self.velocidad
        if self.rect.bottom > alto_pantalla - 50:
            self.rect.bottom = alto_pantalla - 50
            self.velocidad = 0
        if self.rect.top < 0:
            self.rect.top = 0
            self.velocidad = 0

    def volar(self):
        self.velocidad = self.impulso

    def dibujar(self, superficie):
        # Ya no necesitamos un método de dibujar separado, la imagen del sprite se bliteará
        pass

    def obtener_mascara(self):
        return pygame.mask.from_surface(self.image)

class Tubo(pygame.sprite.Sprite):
    def __init__(self, x, y, altura, tipo):
        super().__init__()
        self.ancho = 70
        self.altura = altura
        self.color = verde_tubo
        self.tipo = tipo
        self.image = pygame.Surface((self.ancho, self.altura))
        self.image.fill(self.color)
        if tipo == "superior":
            self.rect = self.image.get_rect(topleft=(x, y)) # Cambiamos a topleft para el superior
        else:
            self.rect = self.image.get_rect(topleft=(x, y))
        self.scored = False

    def update(self):
        self.rect.x -= 5
        if self.rect.right < 0:
            self.kill()

    def dibujar(self, superficie):
        # Ya no necesitamos un método de dibujar separado, la imagen del sprite se bliteará
        pass

    def obtener_mascara(self):
        return pygame.mask.from_surface(self.image)

# Clase para la base
class Base(pygame.sprite.Sprite):
    def __init__(self, y):
        super().__init__()
        self.alto = 50
        self.color = marron
        self.image = pygame.Surface((ancho_pantalla * 2, self.alto))
        self.image.fill(self.color)
        self.rect = self.image.get_rect(bottomleft=(0, y))
        self.velocidad = 5

    def update(self):
        self.rect.x -= self.velocidad
        if self.rect.left <= -ancho_pantalla:
            self.rect.left = 0

    def dibujar(self, superficie):
        # Ya no necesitamos un método de dibujar separado, la imagen del sprite se bliteará
        pass

# Funciones para dibujar
def dibujar_ventana(pajaro, tubos, base, puntuacion):
    pantalla.fill(azul_claro) # Fondo azul claro
    for tubo in tubos:
        pantalla.blit(tubo.image, tubo.rect)
    pantalla.blit(base.image, base.rect)
    pantalla.blit(pajaro.image, pajaro.rect)

    fuente = pygame.font.Font(None, 36)
    texto_puntuacion = fuente.render(f"Puntuación: {puntuacion}", True, blanco)
    pantalla.blit(texto_puntuacion, (10, 10))
    pygame.display.update()

def generar_tubos(x):
    altura_tubo_superior = random.randint(100, 300)
    espacio = 150
    # Tubo superior
    tubo_superior = Tubo(x, 0, altura_tubo_superior, "superior")
    # Tubo inferior, comenzando desde el suelo
    y_inferior = altura_tubo_superior + espacio
    altura_tubo_inferior = alto_pantalla - y_inferior
    tubo_inferior = Tubo(x, y_inferior, altura_tubo_inferior, "inferior")
    return tubo_superior, tubo_inferior

def mostrar_game_over(puntuacion):
    fuente_grande = pygame.font.Font(None, 74)
    fuente_pequena = pygame.font.Font(None, 36)
    texto_game_over = fuente_grande.render("¡Game Over!", True, rojo)
    texto_puntuacion = fuente_pequena.render(f"Puntuación final: {puntuacion}", True, blanco)
    texto_reiniciar = fuente_pequena.render("Presiona ESPACIO para reiniciar", True, blanco)
    texto_game_over_rect = texto_game_over.get_rect(center=(ancho_pantalla // 2, alto_pantalla // 3))
    texto_puntuacion_rect = texto_puntuacion.get_rect(center=(ancho_pantalla // 2, alto_pantalla // 2))
    texto_reiniciar_rect = texto_reiniciar.get_rect(center=(ancho_pantalla // 2, alto_pantalla * 2 // 3))

    pantalla.blit(texto_game_over, texto_game_over_rect)
    pantalla.blit(texto_puntuacion, texto_puntuacion_rect)
    pantalla.blit(texto_reiniciar, texto_reiniciar_rect)
    pygame.display.update()

# Bucle principal del juego
def juego():
    pajaro = Pajaro(ancho_pantalla // 4, alto_pantalla // 2)
    tubos = []
    base = Base(alto_pantalla - 50)
    grupo_tubos = pygame.sprite.Group()
    grupo_pajaro = pygame.sprite.GroupSingle(pajaro)
    grupo_base = pygame.sprite.GroupSingle(base)

    puntuacion = 0
    tiempo_tubo = 0
    frecuencia_tubo = 1500 # Milisegundos entre tubos
    ejecutando = True
    game_over = False

    while ejecutando:
        reloj = pygame.time.Clock()
        reloj.tick(30) # Limitar los fotogramas por segundo

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                ejecutando = False
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_SPACE and not game_over:
                    pajaro.volar()
                if evento.key == pygame.K_SPACE and game_over:
                    return # Reiniciar el juego

        if not game_over:
            # Generar nuevos tubos
            tiempo_tubo += reloj.get_time()
            if tiempo_tubo > frecuencia_tubo:
                nuevo_tubo_superior, nuevo_tubo_inferior = generar_tubos(ancho_pantalla)
                tubos.append(nuevo_tubo_superior)
                tubos.append(nuevo_tubo_inferior)
                grupo_tubos.add(nuevo_tubo_superior)
                grupo_tubos.add(nuevo_tubo_inferior)
                tiempo_tubo = 0

            # Actualizar elementos del juego
            grupo_pajaro.update()
            grupo_tubos.update()
            grupo_base.update()

            # Colisiones
            if pygame.sprite.spritecollide(pajaro, grupo_tubos, False, pygame.sprite.collide_mask) or \
               pygame.sprite.collide_rect(pajaro, base):
                game_over = True

            # Puntuación
            for tubo in tubos:
                if tubo.tipo == "inferior" and not tubo.rect.colliderect(pajaro.rect) and tubo.rect.left < pajaro.rect.left and not tubo.scored:
                    puntuacion += 0.5 # Sumar 0.5 por cada tubo pasado
                    tubo.scored = True # Marcar el tubo como ya puntuado

            # Dibujar la ventana
            dibujar_ventana(pajaro, tubos, base, int(puntuacion))
        else:
            mostrar_game_over(int(puntuacion))

    pygame.quit()

if __name__ == "__main__":
    while True:
        juego()