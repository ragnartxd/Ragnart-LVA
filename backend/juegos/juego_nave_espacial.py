import pygame
import random
import sys
import math

# Inicializar Pygame
pygame.init()
pygame.font.init()

# Configuración de pantalla
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("SPACE RACER")

# Colores
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (0, 0, 255)
YELLOW = (255, 255, 0)
PURPLE = (128, 0, 128)
CYAN = (0, 255, 255)

# Fuentes
title_font = pygame.font.SysFont('Arial', 70, bold=True)
big_font = pygame.font.SysFont('Arial', 40, bold=True)
medium_font = pygame.font.SysFont('Arial', 30)
small_font = pygame.font.SysFont('Arial', 20)

# Mensajes aleatorios
random_messages = [
    "¡Increíble velocidad!",
    "¡Vas como un rayo!",
    "La CPU está sudando...",
    "¡Nitro activado!",
    "¡Esquiva los asteroides!",
    "¡Hiperpropulsión!",
    "¡Piloto estelar!",
    "¡Rompe la barrera del sonido!",
    "¡Demasiado rápido!",
    "¡Velocidad máxima!"
]

# Clase Nave Jugador
class PlayerShip:
    def __init__(self):
        self.width = 40
        self.height = 60
        self.x = WIDTH // 4
        self.y = HEIGHT // 2
        self.speed = 5
        self.color = BLUE
        self.trail = []
        self.boost = 0
        self.score = 0
        
    def draw(self):
        # Dibujar estela
        for i, pos in enumerate(self.trail):
            alpha = 255 - (i * 15)
            if alpha < 0:
                alpha = 0
            trail_color = (min(self.color[0] + 50, 255), 
                          min(self.color[1] + 50, 255), 
                          min(self.color[2] + 50, 255))
            s = pygame.Surface((10, 10))
            s.set_alpha(alpha)
            s.fill(trail_color)
            screen.blit(s, (pos[0], pos[1]))
        
        # Dibujar nave
        points = [
            (self.x, self.y - self.height//2),
            (self.x - self.width//2, self.y + self.height//2),
            (self.x, self.y + self.height//4),
            (self.x + self.width//2, self.y + self.height//2)
        ]
        pygame.draw.polygon(screen, self.color, points)
        
        # Dibujar propulsión
        if self.boost > 0:
            boost_points = [
                (self.x, self.y + self.height//4),
                (self.x - self.width//3, self.y + self.height//2 + 20),
                (self.x + self.width//3, self.y + self.height//2 + 20)
            ]
            pygame.draw.polygon(screen, YELLOW, boost_points)
        
    def update(self, keys):
        # Actualizar estela
        self.trail.insert(0, (self.x, self.y))
        if len(self.trail) > 20:
            self.trail.pop()
        
        # Movimiento
        if keys[pygame.K_w] and self.y > 0:
            self.y -= self.speed
        if keys[pygame.K_s] and self.y < HEIGHT:
            self.y += self.speed
        if keys[pygame.K_a] and self.x > 0:
            self.x -= self.speed
        if keys[pygame.K_d] and self.x < WIDTH:
            self.x += self.speed
        
        # Boost
        if keys[pygame.K_SPACE] and self.boost < 100:
            self.boost += 2
            self.score += 0.5
        else:
            self.boost = max(0, self.boost - 1)
        
        # Incrementar puntuación
        self.score += 0.1

# Clase Nave CPU
class CPUShip:
    def __init__(self):
        self.width = 40
        self.height = 60
        self.x = 3 * WIDTH // 4
        self.y = HEIGHT // 2
        self.speed = 4
        self.color = RED
        self.trail = []
        self.boost = 0
        self.score = 0
        self.direction_change_timer = 0
        self.direction = random.choice(["up", "down", "left", "right"])
        self.boost_timer = 0
        
    def draw(self):
        # Dibujar estela
        for i, pos in enumerate(self.trail):
            alpha = 255 - (i * 15)
            if alpha < 0:
                alpha = 0
            trail_color = (min(self.color[0] + 50, 255), 
                          min(self.color[1] + 50, 255), 
                          min(self.color[2] + 50, 255))
            s = pygame.Surface((10, 10))
            s.set_alpha(alpha)
            s.fill(trail_color)
            screen.blit(s, (pos[0], pos[1]))
            
        # Dibujar nave
        points = [
            (self.x, self.y - self.height//2),
            (self.x - self.width//2, self.y + self.height//2),
            (self.x, self.y + self.height//4),
            (self.x + self.width//2, self.y + self.height//2)
        ]
        pygame.draw.polygon(screen, self.color, points)
        
        # Dibujar propulsión
        if self.boost > 0:
            boost_points = [
                (self.x, self.y + self.height//4),
                (self.x - self.width//3, self.y + self.height//2 + 20),
                (self.x + self.width//3, self.y + self.height//2 + 20)
            ]
            pygame.draw.polygon(screen, YELLOW, boost_points)
        
    def update(self, player_y):
        # Actualizar estela
        self.trail.insert(0, (self.x, self.y))
        if len(self.trail) > 20:
            self.trail.pop()
        
        # Cambiar dirección aleatoriamente
        self.direction_change_timer += 1
        if self.direction_change_timer > 60:
            self.direction_change_timer = 0
            self.direction = random.choice(["up", "down", "left", "right"])
        
        # Seguir al jugador
        if random.random() < 0.7:  # 70% del tiempo sigue al jugador
            if self.y < player_y:
                self.y += self.speed
            else:
                self.y -= self.speed
        else:  # 30% movimiento aleatorio
            if self.direction == "up" and self.y > 0:
                self.y -= self.speed
            elif self.direction == "down" and self.y < HEIGHT:
                self.y += self.speed
            elif self.direction == "left" and self.x > WIDTH//2:
                self.x -= self.speed
            elif self.direction == "right" and self.x < WIDTH:
                self.x += self.speed
        
        # Activar boost aleatoriamente
        self.boost_timer += 1
        if self.boost_timer > 180:  # Cada 3 segundos intenta boost
            self.boost_timer = 0
            if random.random() < 0.5:  # 50% de probabilidad
                self.boost = min(100, self.boost + 30)
        
        # Usar boost
        if self.boost > 0:
            self.boost -= 1
            self.score += 0.8
        
        # Incrementar puntuación
        self.score += 0.1

# Clase Obstáculo
class Obstacle:
    def __init__(self):
        self.size = random.randint(10, 30)
        self.x = WIDTH + 100
        self.y = random.randint(0, HEIGHT)
        self.speed = random.randint(3, 8)
        self.color = PURPLE
        self.rotation = 0
        self.rotation_speed = random.uniform(-2, 2)
        
    def draw(self):
        rotated_points = []
        for angle in range(0, 360, 60):  # Hexágono
            rad = math.radians(angle + self.rotation)
            x = self.x + self.size * math.cos(rad)
            y = self.y + self.size * math.sin(rad)
            rotated_points.append((x, y))
        
        pygame.draw.polygon(screen, self.color, rotated_points)
        
    def update(self):
        self.x -= self.speed
        self.rotation += self.rotation_speed
        return self.x < -50

# Clase Estrellas (fondo)
class Star:
    def __init__(self):
        self.x = random.randint(0, WIDTH)
        self.y = random.randint(0, HEIGHT)
        self.size = random.randint(1, 3)
        self.speed = random.randint(1, 5)
        self.color = (random.randint(200, 255), random.randint(200, 255), random.randint(200, 255))
        
    def draw(self):
        pygame.draw.circle(screen, self.color, (self.x, self.y), self.size)
        
    def update(self):
        self.x -= self.speed
        if self.x < 0:
            self.x = WIDTH
            self.y = random.randint(0, HEIGHT)

# Clase Power Up
class PowerUp:
    def __init__(self):
        self.size = 20
        self.x = WIDTH + 50
        self.y = random.randint(50, HEIGHT - 50)
        self.speed = 3
        self.type = random.choice(["boost", "shield", "speed"])
        if self.type == "boost":
            self.color = YELLOW
        elif self.type == "shield":
            self.color = CYAN
        else:
            self.color = GREEN
        self.active = True
        self.pulse = 0
        self.pulse_dir = 1
        
    def draw(self):
        # Efecto de pulso
        self.pulse += 0.1 * self.pulse_dir
        if self.pulse > 1:
            self.pulse_dir = -1
        elif self.pulse < 0:
            self.pulse_dir = 1
            
        pulse_size = self.size * (1 + self.pulse * 0.2)
        
        pygame.draw.circle(screen, self.color, (int(self.x), int(self.y)), int(pulse_size))
        inner_color = (min(self.color[0] + 50, 255), 
                      min(self.color[1] + 50, 255), 
                      min(self.color[2] + 50, 255))
        pygame.draw.circle(screen, inner_color, (int(self.x), int(self.y)), int(pulse_size * 0.6))
        
    def update(self):
        self.x -= self.speed
        return self.x < -50

# Función para mostrar mensaje aleatorio
def show_random_message():
    message = random.choice(random_messages)
    text = medium_font.render(message, True, YELLOW)
    text_rect = text.get_rect(center=(WIDTH//2, HEIGHT//4))
    screen.blit(text, text_rect)

# Función para verificar colisión
def check_collision(x1, y1, w1, h1, x2, y2, w2, h2):
    return (x1 < x2 + w2 and
            x1 + w1 > x2 and
            y1 < y2 + h2 and
            y1 + h1 > y2)

# Pantalla de inicio
def start_screen():
    stars = [Star() for _ in range(100)]
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    return
                elif event.key == pygame.K_ESCAPE:
                    pygame.quit()
                    sys.exit()
        
        # Dibujar fondo
        screen.fill(BLACK)
        
        # Actualizar y dibujar estrellas
        for star in stars:
            star.update()
            star.draw()
        
        # Título
        title_text = title_font.render("SPACE RACER", True, CYAN)
        title_rect = title_text.get_rect(center=(WIDTH//2, HEIGHT//4))
        screen.blit(title_text, title_rect)
        
        # Instrucciones
        instructions = [
            "Controles: W, A, S, D para moverte",
            "SPACE para activar el impulso",
            "Consigue más puntos que la CPU",
            "¡Recoge power-ups y evita obstáculos!"
        ]
        
        for i, line in enumerate(instructions):
            text = medium_font.render(line, True, WHITE)
            text_rect = text.get_rect(center=(WIDTH//2, HEIGHT//2 + i * 40))
            screen.blit(text, text_rect)
        
        # Mensaje para comenzar
        start_text = big_font.render("Presiona ENTER para comenzar", True, GREEN)
        start_rect = start_text.get_rect(center=(WIDTH//2, HEIGHT - 100))
        
        # Efecto parpadeante
        if pygame.time.get_ticks() % 1000 < 700:
            screen.blit(start_text, start_rect)
        
        pygame.display.flip()
        pygame.time.Clock().tick(60)

# Pantalla de fin de juego
def game_over_screen(player_score, cpu_score):
    stars = [Star() for _ in range(100)]
    
    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_RETURN:
                    return True  # Jugar de nuevo
                elif event.key == pygame.K_ESCAPE:
                    return False  # Salir del juego
        
        # Dibujar fondo
        screen.fill(BLACK)
        
        # Actualizar y dibujar estrellas
        for star in stars:
            star.update()
            star.draw()
        
        # Título
        if player_score > cpu_score:
            title_text = title_font.render("¡HAS GANADO!", True, GREEN)
        else:
            title_text = title_font.render("HAS PERDIDO", True, RED)
        
        title_rect = title_text.get_rect(center=(WIDTH//2, HEIGHT//4))
        screen.blit(title_text, title_rect)
        
        # Puntuaciones
        score_text = big_font.render(f"Tu puntuación: {int(player_score)}", True, BLUE)
        score_rect = score_text.get_rect(center=(WIDTH//2, HEIGHT//2 - 30))
        screen.blit(score_text, score_rect)
        
        cpu_text = big_font.render(f"Puntuación CPU: {int(cpu_score)}", True, RED)
        cpu_rect = cpu_text.get_rect(center=(WIDTH//2, HEIGHT//2 + 30))
        screen.blit(cpu_text, cpu_rect)
        
        # Opciones
        replay_text = medium_font.render("Presiona ENTER para jugar de nuevo", True, WHITE)
        replay_rect = replay_text.get_rect(center=(WIDTH//2, HEIGHT - 100))
        screen.blit(replay_text, replay_rect)
        
        exit_text = medium_font.render("Presiona ESC para salir", True, WHITE)
        exit_rect = exit_text.get_rect(center=(WIDTH//2, HEIGHT - 60))
        screen.blit(exit_text, exit_rect)
        
        pygame.display.flip()
        pygame.time.Clock().tick(60)

# Función principal del juego
def main_game():
    # Crear objetos
    player = PlayerShip()
    cpu = CPUShip()
    obstacles = []
    power_ups = []
    stars = [Star() for _ in range(100)]
    
    # Variables de juego
    obstacle_timer = 0
    power_up_timer = 0
    message_timer = 0
    show_message = False
    message_type = ""
    game_time = 60 * 60  # 60 segundos a 60 FPS
    
    clock = pygame.time.Clock()
    
    # Bucle principal
    while game_time > 0:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
        
        # Obtener teclas presionadas
        keys = pygame.key.get_pressed()
        
        # Actualizar jugador y CPU
        player.update(keys)
        cpu.update(player.y)
        
        # Actualizar obstáculos
        obstacle_timer += 1
        if obstacle_timer > 60:  # Crear obstáculo cada segundo
            obstacle_timer = 0
            obstacles.append(Obstacle())
        
        obstacles = [obs for obs in obstacles if not obs.update()]
        
        # Actualizar power-ups
        power_up_timer += 1
        if power_up_timer > 300:  # Crear power-up cada 5 segundos
            power_up_timer = 0
            power_ups.append(PowerUp())
        
        power_ups = [pw for pw in power_ups if not pw.update()]
        
        # Actualizar estrellas
        for star in stars:
            star.update()
        
        # Comprobar colisiones con obstáculos
        for obs in obstacles:
            # Colisión con jugador
            if check_collision(player.x - player.width//2, player.y - player.height//2, 
                              player.width, player.height,
                              obs.x - obs.size, obs.y - obs.size, 
                              obs.size * 2, obs.size * 2):
                player.score -= 10
                obstacles.remove(obs)
                show_message = True
                message_timer = 120  # 2 segundos
                message_type = "obstacle_player"
            
            # Colisión con CPU
            if check_collision(cpu.x - cpu.width//2, cpu.y - cpu.height//2, 
                              cpu.width, cpu.height,
                              obs.x - obs.size, obs.y - obs.size, 
                              obs.size * 2, obs.size * 2):
                cpu.score -= 10
                obstacles.remove(obs)
                show_message = True
                message_timer = 120  # 2 segundos
                message_type = "obstacle_cpu"
        
        # Comprobar colisiones con power-ups
        for pw in power_ups:
            # Colisión con jugador
            if check_collision(player.x - player.width//2, player.y - player.height//2, 
                              player.width, player.height,
                              pw.x - pw.size, pw.y - pw.size, 
                              pw.size * 2, pw.size * 2):
                if pw.type == "boost":
                    player.boost = 100
                elif pw.type == "speed":
                    player.speed += 1
                player.score += 20
                power_ups.remove(pw)
                show_message = True
                message_timer = 120  # 2 segundos
                message_type = "powerup_player"
            
            # Colisión con CPU
            if check_collision(cpu.x - cpu.width//2, cpu.y - cpu.height//2, 
                              cpu.width, cpu.height,
                              pw.x - pw.size, pw.y - pw.size, 
                              pw.size * 2, pw.size * 2):
                if pw.type == "boost":
                    cpu.boost = 100
                elif pw.type == "speed":
                    cpu.speed += 1
                cpu.score += 20
                power_ups.remove(pw)
                show_message = True
                message_timer = 120  # 2 segundos
                message_type = "powerup_cpu"
        
        # Dibujar todo
        screen.fill(BLACK)
        
        # Dibujar estrellas
        for star in stars:
            star.draw()
        
        # Dibujar obstáculos
        for obs in obstacles:
            obs.draw()
        
        # Dibujar power-ups
        for pw in power_ups:
            pw.draw()
        
        # Dibujar jugador y CPU
        player.draw()
        cpu.draw()
        
        # Dibujar barras de boost
        pygame.draw.rect(screen, WHITE, (20, 20, 110, 20), 1)
        pygame.draw.rect(screen, BLUE, (21, 21, player.boost * 108 // 100, 18))
        boost_text = small_font.render("BOOST", True, WHITE)
        screen.blit(boost_text, (23, 22))
        
        pygame.draw.rect(screen, WHITE, (WIDTH - 130, 20, 110, 20), 1)
        pygame.draw.rect(screen, RED, (WIDTH - 129, 21, cpu.boost * 108 // 100, 18))
        cpu_boost_text = small_font.render("CPU BOOST", True, WHITE)
        screen.blit(cpu_boost_text, (WIDTH - 127, 22))
        
        # Dibujar puntuaciones
        score_text = medium_font.render(f"Puntos: {int(player.score)}", True, WHITE)
        screen.blit(score_text, (20, 50))
        
        cpu_score_text = medium_font.render(f"CPU: {int(cpu.score)}", True, WHITE)
        screen.blit(cpu_score_text, (WIDTH - 150, 50))
        
        # Dibujar tiempo restante
        time_text = medium_font.render(f"Tiempo: {game_time // 60}", True, WHITE)
        screen.blit(time_text, (WIDTH // 2 - 60, 20))
        
        # Mostrar mensaje aleatorio
        if random.random() < 0.001 or (show_message and message_timer > 0):
            if message_type == "obstacle_player":
                message = "¡Has chocado! -10 puntos"
                text = medium_font.render(message, True, RED)
            elif message_type == "obstacle_cpu":
                message = "¡CPU chocó! -10 puntos"
                text = medium_font.render(message, True, GREEN)
            elif message_type == "powerup_player":
                message = "¡Power-up conseguido! +20 puntos"
                text = medium_font.render(message, True, GREEN)
            elif message_type == "powerup_cpu":
                message = "¡CPU consiguió power-up! +20 puntos"
                text = medium_font.render(message, True, RED)
            else:
                show_random_message()
                
            if message_type:
                text_rect = text.get_rect(center=(WIDTH//2, HEIGHT//4))
                screen.blit(text, text_rect)
            
            message_timer -= 1
            if message_timer <= 0:
                show_message = False
                message_type = ""
        
        # Actualizar pantalla
        pygame.display.flip()
        clock.tick(60)
        
        # Reducir tiempo de juego
        game_time -= 1
    
    return player.score, cpu.score

# Función principal
def main():
    while True:
        start_screen()
        player_score, cpu_score = main_game()
        play_again = game_over_screen(player_score, cpu_score)
        if not play_again:
            break

if __name__ == "__main__":
    main()