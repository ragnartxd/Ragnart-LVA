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
pygame.display.set_caption("CRYSTAL QUEST")

# Colores
BLACK = (0, 0, 0)
WHITE = (255, 255, 255)
RED = (255, 0, 0)
GREEN = (0, 255, 0)
BLUE = (50, 50, 255)
YELLOW = (255, 255, 0)
PURPLE = (175, 0, 175)
CYAN = (0, 255, 255)
ORANGE = (255, 165, 0)
GRAY = (100, 100, 100)
DARK_BLUE = (25, 25, 100)

# Fuentes
title_font = pygame.font.SysFont('Arial', 70, bold=True)
big_font = pygame.font.SysFont('Arial', 40, bold=True)
medium_font = pygame.font.SysFont('Arial', 30)
small_font = pygame.font.SysFont('Arial', 20)

# Mensajes aleatorios
random_messages = [
    "¡Crystal conseguido!",
    "¡Excelente salto!",
    "¡La CPU está nerviosa!",
    "¡Poder activado!",
    "¡Cuidado con las trampas!",
    "¡Movimiento perfecto!",
    "¡Buen timing!",
    "¡Increíble velocidad!",
    "¡Nivel superado!",
    "¡Eres un maestro!",
    "¡La CPU te alcanza!",
    "¡Recoge más cristales!",
    "¡Usa tu poder especial!",
    "¡Aplasta a tus enemigos!",
    "¡Salta más alto!"
]

# Clase Jugador
class Player:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 30
        self.height = 50
        self.velocity_y = 0
        self.velocity_x = 0
        self.jump_power = 15
        self.speed = 5
        self.is_jumping = False
        self.color = BLUE
        self.score = 0
        self.power = 0
        self.has_special = False
        self.special_type = None
        self.special_timer = 0
        self.facing_right = True
        self.animation_frame = 0
        self.animation_cooldown = 0
        self.invincible = False
        self.invincible_timer = 0
        
    def draw(self):
        # Efecto de invencibilidad
        if self.invincible and pygame.time.get_ticks() % 200 < 100:
            return
            
        # Color basado en poder especial
        current_color = self.color
        if self.has_special:
            if self.special_type == "speed":
                current_color = GREEN
            elif self.special_type == "jump":
                current_color = YELLOW
            elif self.special_type == "invincible":
                current_color = WHITE
        
        # Dibujar cuerpo
        pygame.draw.rect(screen, current_color, (self.x, self.y, self.width, self.height))
        
        # Dibujar cabeza
        head_size = 20
        pygame.draw.circle(screen, current_color, (self.x + self.width // 2, self.y - head_size // 2), head_size // 2)
        
        # Dibujar ojos
        eye_color = BLACK
        eye_size = 4
        if self.facing_right:
            pygame.draw.circle(screen, eye_color, (self.x + self.width // 2 + 5, self.y - head_size // 2 - 2), eye_size)
        else:
            pygame.draw.circle(screen, eye_color, (self.x + self.width // 2 - 5, self.y - head_size // 2 - 2), eye_size)
        
        # Dibujar brazos
        arm_width = 10
        arm_height = 20
        if self.animation_frame == 0:
            pygame.draw.rect(screen, current_color, (self.x - arm_width, self.y + 10, arm_width, arm_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width, self.y + 10, arm_width, arm_height))
        else:
            pygame.draw.rect(screen, current_color, (self.x - arm_width, self.y + 15, arm_width, arm_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width, self.y + 15, arm_width, arm_height))
        
        # Dibujar piernas
        leg_width = 10
        leg_height = 15
        if self.animation_frame == 0:
            pygame.draw.rect(screen, current_color, (self.x + 5, self.y + self.height, leg_width, leg_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width - 15, self.y + self.height, leg_width, leg_height))
        else:
            pygame.draw.rect(screen, current_color, (self.x, self.y + self.height, leg_width, leg_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width - 10, self.y + self.height, leg_width, leg_height))
        
        # Animar mientras se mueve
        if abs(self.velocity_x) > 0:
            self.animation_cooldown += 1
            if self.animation_cooldown > 5:
                self.animation_cooldown = 0
                self.animation_frame = (self.animation_frame + 1) % 2
    
    def update(self, platforms, crystals, powerups, enemies, keys):
        current_speed = self.speed
        
        # Aplicar poderes especiales
        if self.has_special:
            self.special_timer -= 1
            if self.special_timer <= 0:
                self.has_special = False
                self.special_type = None
            else:
                if self.special_type == "speed":
                    current_speed = self.speed * 1.8
                elif self.special_type == "jump":
                    self.jump_power = 20
                elif self.special_type == "invincible":
                    self.invincible = True
        else:
            self.jump_power = 15
            self.invincible = False
        
        # Decrementar temporizador de invencibilidad
        if self.invincible_timer > 0:
            self.invincible_timer -= 1
            self.invincible = True
        elif not self.has_special or self.special_type != "invincible":
            self.invincible = False
        
        # Aplicar gravedad
        self.velocity_y += 0.8
        
        # Control de movimiento horizontal
        self.velocity_x = 0
        if keys[pygame.K_LEFT]:
            self.velocity_x = -current_speed
            self.facing_right = False
        if keys[pygame.K_RIGHT]:
            self.velocity_x = current_speed
            self.facing_right = True
        
        # Saltar
        if keys[pygame.K_UP] and not self.is_jumping:
            self.velocity_y = -self.jump_power
            self.is_jumping = True
        
        # Actualizar posición
        next_x = self.x + self.velocity_x
        next_y = self.y + self.velocity_y
        
        # Comprobar colisión con plataformas horizontal
        for platform in platforms:
            # Colisión horizontal
            if (next_x + self.width > platform.x and 
                next_x < platform.x + platform.width and 
                self.y + self.height > platform.y and 
                self.y < platform.y + platform.height):
                next_x = self.x
        
        self.x = next_x
        
        # Comprobar colisión con plataformas vertical
        on_ground = False
        for platform in platforms:
            # Caer sobre plataforma
            if (self.x + self.width > platform.x and 
                self.x < platform.x + platform.width and 
                next_y + self.height > platform.y and 
                next_y + self.height < platform.y + platform.height/2 and
                self.velocity_y > 0):
                next_y = platform.y - self.height
                self.velocity_y = 0
                self.is_jumping = False
                on_ground = True
            # Golpear plataforma desde abajo
            elif (self.x + self.width > platform.x and 
                  self.x < platform.x + platform.width and 
                  next_y < platform.y + platform.height and 
                  next_y > platform.y + platform.height/2 and
                  self.velocity_y < 0):
                next_y = platform.y + platform.height
                self.velocity_y = 0
        
        self.y = next_y
        
        # Comprobar si cae fuera de la pantalla
        if self.y > HEIGHT:
            self.y = 0
            self.score -= 20
            self.invincible_timer = 60  # Invencible por 1 segundo al reaparecer
        
        # Recoger cristales
        crystals_to_remove = []
        for crystal in crystals:
            if self.collides_with(crystal):
                self.score += crystal.value
                self.power += 10
                crystals_to_remove.append(crystal)
        
        # Recoger powerups
        powerups_to_remove = []
        for powerup in powerups:
            if self.collides_with(powerup):
                self.activate_special(powerup.type)
                powerups_to_remove.append(powerup)
        
        # Comprobar colisión con enemigos
        if not self.invincible:
            for enemy in enemies:
                if self.collides_with(enemy):
                    # Si se salta encima del enemigo
                    if self.velocity_y > 0 and self.y + self.height < enemy.y + enemy.height / 2:
                        self.velocity_y = -self.jump_power / 1.5
                        enemy.hit()
                        self.score += 15
                    else:
                        # Si choca con el enemigo
                        self.score -= 10
                        self.invincible_timer = 60  # Invencible por 1 segundo
                        
                        # Rebote
                        if self.x < enemy.x:
                            self.velocity_x = -10
                        else:
                            self.velocity_x = 10
                        self.velocity_y = -5
        
        return crystals_to_remove, powerups_to_remove
    
    def collides_with(self, obj):
        return (self.x < obj.x + obj.width and
                self.x + self.width > obj.x and
                self.y < obj.y + obj.height and
                self.y + self.height > obj.y)
    
    def activate_special(self, type):
        self.has_special = True
        self.special_type = type
        self.special_timer = 300  # 5 segundos
        self.score += 10

# Clase CPU (enemigo inteligente)
class CPU:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 30
        self.height = 50
        self.velocity_y = 0
        self.velocity_x = 0
        self.jump_power = 15
        self.speed = 4
        self.is_jumping = False
        self.color = RED
        self.score = 0
        self.power = 0
        self.has_special = False
        self.special_type = None
        self.special_timer = 0
        self.target_crystal = None
        self.target_platform = None
        self.decision_timer = 0
        self.decision_cooldown = 30
        self.facing_right = False
        self.animation_frame = 0
        self.animation_cooldown = 0
        self.jump_timer = 0
        self.invincible = False
        self.invincible_timer = 0
        
    def draw(self):
        # Efecto de invencibilidad
        if self.invincible and pygame.time.get_ticks() % 200 < 100:
            return
            
        # Color basado en poder especial
        current_color = self.color
        if self.has_special:
            if self.special_type == "speed":
                current_color = GREEN
            elif self.special_type == "jump":
                current_color = YELLOW
            elif self.special_type == "invincible":
                current_color = WHITE
        
        # Dibujar cuerpo
        pygame.draw.rect(screen, current_color, (self.x, self.y, self.width, self.height))
        
        # Dibujar cabeza
        head_size = 20
        pygame.draw.circle(screen, current_color, (self.x + self.width // 2, self.y - head_size // 2), head_size // 2)
        
        # Dibujar ojos
        eye_color = BLACK
        eye_size = 4
        if self.facing_right:
            pygame.draw.circle(screen, eye_color, (self.x + self.width // 2 + 5, self.y - head_size // 2 - 2), eye_size)
        else:
            pygame.draw.circle(screen, eye_color, (self.x + self.width // 2 - 5, self.y - head_size // 2 - 2), eye_size)
        
        # Dibujar brazos
        arm_width = 10
        arm_height = 20
        if self.animation_frame == 0:
            pygame.draw.rect(screen, current_color, (self.x - arm_width, self.y + 10, arm_width, arm_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width, self.y + 10, arm_width, arm_height))
        else:
            pygame.draw.rect(screen, current_color, (self.x - arm_width, self.y + 15, arm_width, arm_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width, self.y + 15, arm_width, arm_height))
        
        # Dibujar piernas
        leg_width = 10
        leg_height = 15
        if self.animation_frame == 0:
            pygame.draw.rect(screen, current_color, (self.x + 5, self.y + self.height, leg_width, leg_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width - 15, self.y + self.height, leg_width, leg_height))
        else:
            pygame.draw.rect(screen, current_color, (self.x, self.y + self.height, leg_width, leg_height))
            pygame.draw.rect(screen, current_color, (self.x + self.width - 10, self.y + self.height, leg_width, leg_height))
        
        # Animar mientras se mueve
        if abs(self.velocity_x) > 0:
            self.animation_cooldown += 1
            if self.animation_cooldown > 5:
                self.animation_cooldown = 0
                self.animation_frame = (self.animation_frame + 1) % 2
    
    def update(self, platforms, crystals, powerups, enemies):
        current_speed = self.speed
        
        # Aplicar poderes especiales
        if self.has_special:
            self.special_timer -= 1
            if self.special_timer <= 0:
                self.has_special = False
                self.special_type = None
            else:
                if self.special_type == "speed":
                    current_speed = self.speed * 1.8
                elif self.special_type == "jump":
                    self.jump_power = 20
                elif self.special_type == "invincible":
                    self.invincible = True
        else:
            self.jump_power = 15
            self.invincible = False
        
        # Decrementar temporizador de invencibilidad
        if self.invincible_timer > 0:
            self.invincible_timer -= 1
            self.invincible = True
        elif not self.has_special or self.special_type != "invincible":
            self.invincible = False
        
        # IA: Tomar decisiones periódicamente
        self.decision_timer += 1
        if self.decision_timer >= self.decision_cooldown:
            self.decision_timer = 0
            
            # Buscar el cristal más cercano
            closest_dist = float('inf')
            for crystal in crystals:
                dist = abs(crystal.x - self.x) + abs(crystal.y - self.y)
                if dist < closest_dist:
                    closest_dist = dist
                    self.target_crystal = crystal
            
            # Buscar plataforma objetivo si está cayendo
            if self.velocity_y > 0:
                best_platform = None
                best_score = float('inf')
                
                for platform in platforms:
                    # Solo considerar plataformas debajo del CPU
                    if platform.y > self.y + self.height:
                        # Puntuar plataforma (distancia horizontal y vertical)
                        h_dist = abs((platform.x + platform.width/2) - (self.x + self.width/2))
                        v_dist = platform.y - (self.y + self.height)
                        
                        if v_dist > 0:  # Solo plataformas debajo
                            score = h_dist + v_dist * 0.5
                            
                            if score < best_score:
                                best_score = score
                                best_platform = platform
                
                self.target_platform = best_platform
        
        # Aplicar gravedad
        self.velocity_y += 0.8
        
        # IA: Moverse hacia el objetivo
        self.velocity_x = 0
        
        # Si tiene un cristal objetivo
        if self.target_crystal:
            if self.x + self.width/2 < self.target_crystal.x:
                self.velocity_x = current_speed
                self.facing_right = True
            else:
                self.velocity_x = -current_speed
                self.facing_right = False
            
            # Decidir si saltar (si el cristal está arriba o hay un obstáculo)
            self.jump_timer -= 1
            if not self.is_jumping and self.jump_timer <= 0:
                # Saltar si el cristal está arriba
                if self.target_crystal.y < self.y - 50:
                    self.velocity_y = -self.jump_power
                    self.is_jumping = True
                    self.jump_timer = 30  # Cooldown
                
                # Saltar si hay un enemigo cerca
                for enemy in enemies:
                    dist_x = abs(enemy.x - self.x)
                    if dist_x < 100 and self.y + self.height >= enemy.y:
                        self.velocity_y = -self.jump_power
                        self.is_jumping = True
                        self.jump_timer = 30
                        break
        
        # Actualizar posición
        next_x = self.x + self.velocity_x
        next_y = self.y + self.velocity_y
        
        # Comprobar colisión con plataformas horizontal
        for platform in platforms:
            # Colisión horizontal
            if (next_x + self.width > platform.x and 
                next_x < platform.x + platform.width and 
                self.y + self.height > platform.y and 
                self.y < platform.y + platform.height):
                next_x = self.x
                
                # Saltar si hay colisión horizontal para superar el obstáculo
                if not self.is_jumping and self.jump_timer <= 0:
                    self.velocity_y = -self.jump_power
                    self.is_jumping = True
                    self.jump_timer = 30
        
        self.x = next_x
        
        # Comprobar colisión con plataformas vertical
        on_ground = False
        for platform in platforms:
            # Caer sobre plataforma
            if (self.x + self.width > platform.x and 
                self.x < platform.x + platform.width and 
                next_y + self.height > platform.y and 
                next_y + self.height < platform.y + platform.height/2 and
                self.velocity_y > 0):
                next_y = platform.y - self.height
                self.velocity_y = 0
                self.is_jumping = False
                on_ground = True
            # Golpear plataforma desde abajo
            elif (self.x + self.width > platform.x and 
                  self.x < platform.x + platform.width and 
                  next_y < platform.y + platform.height and 
                  next_y > platform.y + platform.height/2 and
                  self.velocity_y < 0):
                next_y = platform.y + platform.height
                self.velocity_y = 0
        
        self.y = next_y
        
        # Comprobar si cae fuera de la pantalla
        if self.y > HEIGHT:
            self.y = 0
            self.score -= 20
            self.invincible_timer = 60  # Invencible por 1 segundo al reaparecer
        
        # Recoger cristales
        crystals_to_remove = []
        for crystal in crystals:
            if self.collides_with(crystal):
                self.score += crystal.value
                self.power += 10
                crystals_to_remove.append(crystal)
                # Resetear objetivo
                if self.target_crystal == crystal:
                    self.target_crystal = None
        
        # Recoger powerups
        powerups_to_remove = []
        for powerup in powerups:
            if self.collides_with(powerup):
                self.activate_special(powerup.type)
                powerups_to_remove.append(powerup)
        
        # Comprobar colisión con enemigos
        if not self.invincible:
            for enemy in enemies:
                if self.collides_with(enemy):
                    # Si se salta encima del enemigo
                    if self.velocity_y > 0 and self.y + self.height < enemy.y + enemy.height / 2:
                        self.velocity_y = -self.jump_power / 1.5
                        enemy.hit()
                        self.score += 15
                    else:
                        # Si choca con el enemigo
                        self.score -= 10
                        self.invincible_timer = 60  # Invencible por 1 segundo
                        
                        # Rebote
                        if self.x < enemy.x:
                            self.velocity_x = -10
                        else:
                            self.velocity_x = 10
                        self.velocity_y = -5
        
        return crystals_to_remove, powerups_to_remove
    
    def collides_with(self, obj):
        return (self.x < obj.x + obj.width and
                self.x + self.width > obj.x and
                self.y < obj.y + obj.height and
                self.y + self.height > obj.y)
    
    def activate_special(self, type):
        self.has_special = True
        self.special_type = type
        self.special_timer = 300  # 5 segundos
        self.score += 10

# Clase Plataforma
class Platform:
    def __init__(self, x, y, width, height, type="normal"):
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.type = type
        self.velocity = 0
        
        if type == "normal":
            self.color = GRAY
        elif type == "moving":
            self.color = ORANGE
            self.direction = 1
            self.original_x = x
            self.move_range = 100
            self.speed = 2
        elif type == "falling":
            self.color = CYAN
            self.falling = False
            self.fall_timer = 0
    
    def draw(self):
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))
        
        # Dibujar detalles según el tipo
        if self.type == "normal":
            for i in range(3):
                pygame.draw.rect(screen, DARK_BLUE, (self.x + 10 + i * 30, self.y + 5, 20, 5))
        elif self.type == "moving":
            # Flechas indicando movimiento
            pygame.draw.polygon(screen, YELLOW, [(self.x + 10, self.y + self.height//2), 
                                                (self.x + 25, self.y + 5), 
                                                (self.x + 25, self.y + self.height - 5)])
            pygame.draw.polygon(screen, YELLOW, [(self.x + self.width - 10, self.y + self.height//2), 
                                                (self.x + self.width - 25, self.y + 5), 
                                                (self.x + self.width - 25, self.y + self.height - 5)])
        elif self.type == "falling":
            # Líneas que indican inestabilidad
            for i in range(5):
                x_start = self.x + (i * self.width // 4)
                pygame.draw.line(screen, RED, (x_start, self.y + self.height - 3), 
                                 (x_start + self.width // 8, self.y + self.height - 10), 2)
                pygame.draw.line(screen, RED, (x_start + self.width // 8, self.y + self.height - 10), 
                                 (x_start + self.width // 4, self.y + self.height - 3), 2)
    
    def update(self, player, cpu):
        if self.type == "moving":
            # Mover la plataforma horizontal
            self.x += self.direction * self.speed
            
            # Cambiar dirección al llegar a los límites
            if self.x > self.original_x + self.move_range:
                self.direction = -1
            elif self.x < self.original_x - self.move_range:
                self.direction = 1
            
            # Mover con la plataforma
            if (player.x + player.width > self.x and 
                player.x < self.x + self.width and 
                player.y + player.height <= self.y + 5 and 
                player.y + player.height >= self.y - 5):
                player.x += self.direction * self.speed
            
            if (cpu.x + cpu.width > self.x and 
                cpu.x < self.x + self.width and 
                cpu.y + cpu.height <= self.y + 5 and 
                cpu.y + cpu.height >= self.y - 5):
                cpu.x += self.direction * self.speed
                
        elif self.type == "falling":
            # Comprobar si alguien está sobre la plataforma
            if ((player.x + player.width > self.x and 
                player.x < self.x + self.width and 
                player.y + player.height <= self.y + 5 and 
                player.y + player.height >= self.y - 5) or
                (cpu.x + cpu.width > self.x and 
                cpu.x < self.x + self.width and 
                cpu.y + cpu.height <= self.y + 5 and 
                cpu.y + cpu.height >= self.y - 5)):
                self.falling = True
            
            # Si está cayendo, incrementar velocidad
            if self.falling:
                self.fall_timer += 1
                if self.fall_timer > 30:  # Esperar medio segundo antes de caer
                    self.velocity += 0.5
                    self.y += self.velocity
                    
                    # Arrastrar al jugador/CPU si están encima
                    if (player.x + player.width > self.x and 
                        player.x < self.x + self.width and 
                        player.y + player.height <= self.y + 5 and 
                        player.y + player.height >= self.y - 5):
                        player.y += self.velocity
                    
                    if (cpu.x + cpu.width > self.x and 
                        cpu.x < self.x + self.width and 
                        cpu.y + cpu.height <= self.y + 5 and 
                        cpu.y + cpu.height >= self.y - 5):
                        cpu.y += self.velocity

# Clase Cristal
class Crystal:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 20
        self.height = 20
        self.value = 5
        self.color = random.choice([BLUE, GREEN, YELLOW, PURPLE, CYAN])
        self.pulse = 0
        self.pulse_dir = 1
        self.rotation = 0
    
    def draw(self):
        # Efecto de rotación y pulso
        self.rotation = (self.rotation + 2) % 360
        self.pulse += 0.05 * self.pulse_dir
        if self.pulse > 1:
            self.pulse_dir = -1
        elif self.pulse < 0:
            self.pulse_dir = 1
        
        size = self.width * (1 + self.pulse * 0.2)
        
        # Dibujar cristal como diamante rotando
        rad = math.radians(self.rotation)
        points = []
        for i in range(5):
            angle = math.radians(72 * i + self.rotation)
            radius = size if i % 2 == 0 else size * 0.5
            x = self.x + radius * math.cos(angle)
            y = self.y + radius * math.sin(angle)
            points.append((x, y))
        
        pygame.draw.polygon(screen, self.color, points)
        
        # Brillo
        # Brillo
        pygame.draw.circle(screen, WHITE, (int(self.x + size/4), int(self.y - size/4)), int(size/6))

# Clase PowerUp
class PowerUp:
    def __init__(self, x, y):
        self.x = x
        self.y = y
        self.width = 25
        self.height = 25
        self.type = random.choice(["speed", "jump", "invincible"])
        self.pulse = 0
        self.pulse_dir = 1
        
        if self.type == "speed":
            self.color = GREEN
        elif self.type == "jump":
            self.color = YELLOW
        else:  # invincible
            self.color = WHITE
    
    def draw(self):
        # Efecto de pulso
        self.pulse += 0.1 * self.pulse_dir
        if self.pulse > 1:
            self.pulse_dir = -1
        elif self.pulse < 0:
            self.pulse_dir = 1
        
        size = self.width * (1 + self.pulse * 0.3)
        
        # Dibujar base
        pygame.draw.circle(screen, self.color, (int(self.x + self.width/2), int(self.y + self.height/2)), int(size/2))
        
        # Dibujar símbolo según tipo
        if self.type == "speed":
            # Flecha
            pygame.draw.polygon(screen, BLACK, [
                (self.x + self.width/2, self.y + 5),
                (self.x + self.width - 5, self.y + self.height/2),
                (self.x + self.width/2, self.y + self.height - 5),
                (self.x + self.width/2 - 3, self.y + self.height/2)
            ])
        elif self.type == "jump":
            # Flecha hacia arriba
            pygame.draw.polygon(screen, BLACK, [
                (self.x + self.width/2, self.y + 5),
                (self.x + self.width - 5, self.y + self.height/2),
                (self.x + self.width/2 + 3, self.y + self.height/2),
                (self.x + self.width/2 + 3, self.y + self.height - 5),
                (self.x + self.width/2 - 3, self.y + self.height - 5),
                (self.x + self.width/2 - 3, self.y + self.height/2),
                (self.x + 5, self.y + self.height/2)
            ])
        else:  # invincible
            # Escudo
            pygame.draw.rect(screen, BLACK, (self.x + self.width/2 - 5, self.y + 7, 10, 15))
            pygame.draw.circle(screen, BLACK, (int(self.x + self.width/2), int(self.y + 7)), 5)

# Clase Enemigo
class Enemy:
    def __init__(self, x, y, type="normal"):
        self.x = x
        self.y = y
        self.width = 30
        self.height = 30
        self.type = type
        self.health = 1
        self.velocity_x = 0
        self.velocity_y = 0
        self.direction = random.choice([-1, 1])
        self.speed = 2
        self.animation_frame = 0
        self.animation_cooldown = 0
        self.is_active = True
        
        if type == "normal":
            self.color = PURPLE
        elif type == "flying":
            self.color = ORANGE
            self.y_offset = 0
            self.fly_direction = 1
        elif type == "jumping":
            self.color = GREEN
            self.jump_timer = random.randint(30, 90)
    
    def draw(self):
        if not self.is_active:
            return
            
        # Dibujar cuerpo
        pygame.draw.rect(screen, self.color, (self.x, self.y, self.width, self.height))
        
        # Dibujar ojos
        eye_color = WHITE
        pygame.draw.circle(screen, eye_color, (int(self.x + 10), int(self.y + 10)), 5)
        pygame.draw.circle(screen, eye_color, (int(self.x + self.width - 10), int(self.y + 10)), 5)
        
        # Dibujar pupilas
        pupil_color = BLACK
        pupil_offset = 2 if self.direction > 0 else -2
        pygame.draw.circle(screen, pupil_color, (int(self.x + 10 + pupil_offset), int(self.y + 10)), 2)
        pygame.draw.circle(screen, pupil_color, (int(self.x + self.width - 10 + pupil_offset), int(self.y + 10)), 2)
        
        # Dibujar boca
        if self.animation_frame == 0:
            pygame.draw.rect(screen, RED, (self.x + 10, self.y + 20, self.width - 20, 5))
        else:
            pygame.draw.rect(screen, RED, (self.x + 5, self.y + 20, self.width - 10, 5))
    
    def update(self, platforms):
        if not self.is_active:
            return
            
        # Animar
        self.animation_cooldown += 1
        if self.animation_cooldown > 15:
            self.animation_cooldown = 0
            self.animation_frame = (self.animation_frame + 1) % 2
        
        # Comportamiento según tipo
        if self.type == "normal":
            # Mover horizontalmente
            self.x += self.direction * self.speed
            
            # Comprobar colisiones con plataformas
            on_platform = False
            for platform in platforms:
                # Colisión horizontal
                if (self.x + self.width > platform.x and 
                    self.x < platform.x + platform.width and 
                    self.y + self.height > platform.y and 
                    self.y < platform.y + platform.height):
                    self.direction *= -1
                    break
                
                # Comprobar si está sobre una plataforma
                if (self.x + self.width > platform.x and 
                    self.x < platform.x + platform.width and 
                    self.y + self.height >= platform.y and 
                    self.y + self.height <= platform.y + 5):
                    on_platform = True
                
                # Comprobar si llega al borde de una plataforma
                if on_platform and (self.x + self.width + self.direction * 5 <= platform.x or
                                  self.x + self.direction * 5 >= platform.x + platform.width):
                    self.direction *= -1
                    break
            
            # Aplicar gravedad si no está en plataforma
            if not on_platform:
                self.velocity_y += 0.8
                self.y += self.velocity_y
            else:
                self.velocity_y = 0
        
        elif self.type == "flying":
            # Volar en patrón sinusoidal
            self.x += self.direction * self.speed
            
            self.y_offset += 0.1 * self.fly_direction
            if abs(self.y_offset) > 20:
                self.fly_direction *= -1
            
            self.y += self.fly_direction * 0.5
            
            # Cambiar dirección al llegar a los bordes
            if self.x <= 0 or self.x + self.width >= WIDTH:
                self.direction *= -1
        
        elif self.type == "jumping":
            # Mover horizontalmente
            self.x += self.direction * self.speed
            
            # Saltar periódicamente
            self.jump_timer -= 1
            if self.jump_timer <= 0 and self.velocity_y == 0:
                self.velocity_y = -10
                self.jump_timer = random.randint(60, 120)
            
            # Aplicar gravedad
            self.velocity_y += 0.8
            self.y += self.velocity_y
            
            # Colisión con plataformas
            for platform in platforms:
                # Horizontal
                if (self.x + self.width > platform.x and 
                    self.x < platform.x + platform.width and 
                    self.y + self.height > platform.y and 
                    self.y < platform.y + platform.height and
                    abs(self.velocity_y) < 5):  # Solo si no está saltando o cayendo rápido
                    self.direction *= -1
                    break
                
                # Vertical - caer sobre plataforma
                if (self.x + self.width > platform.x and 
                    self.x < platform.x + platform.width and 
                    self.y + self.height > platform.y and 
                    self.y + self.height < platform.y + platform.height/2 and
                    self.velocity_y > 0):
                    self.y = platform.y - self.height
                    self.velocity_y = 0
                
                # Cambiar dirección al llegar al borde
                if (self.velocity_y == 0 and
                    ((self.direction > 0 and self.x + self.width + 10 > platform.x + platform.width) or
                     (self.direction < 0 and self.x - 10 < platform.x))):
                    self.direction *= -1
        
        # Reaparecer si cae fuera de la pantalla
        if self.y > HEIGHT:
            self.y = 0
            self.is_active = False
    
    def hit(self):
        self.health -= 1
        if self.health <= 0:
            self.is_active = False

# Función para mostrar mensaje aleatorio
def show_random_message():
    message = random.choice(random_messages)
    text = medium_font.render(message, True, YELLOW)
    text_rect = text.get_rect(center=(WIDTH//2, HEIGHT//4))
    screen.blit(text, text_rect)

# Pantalla de inicio
def start_screen():
    # Crear unas plataformas y cristales para la pantalla de inicio
    platforms = [
        Platform(100, 400, 200, 20, "normal"),
        Platform(400, 350, 250, 20, "moving"),
        Platform(200, 250, 150, 20, "falling"),
        Platform(500, 200, 200, 20, "normal")
    ]
    
    crystals = [
        Crystal(150, 370),
        Crystal(250, 220),
        Crystal(550, 170)
    ]
    
    player = Player(200, 300)
    cpu = CPU(500, 300)
    
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
        
        # Fondo de estrellas
        for i in range(100):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            size = random.randint(1, 3)
            color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            pygame.draw.circle(screen, color, (x, y), size)
        
        # Actualizar y dibujar objetos de decoración
        for platform in platforms:
            platform.update(player, cpu)
            platform.draw()
        
        for crystal in crystals:
            crystal.draw()
        
        player.draw()
        cpu.draw()
        
        # Título
        title_text = title_font.render("CRYSTAL QUEST", True, CYAN)
        title_rect = title_text.get_rect(center=(WIDTH//2, HEIGHT//4))
        screen.blit(title_text, title_rect)
        
        # Instrucciones
        instructions = [
            "Controles: Flechas para moverte",
            "↑ para saltar",
            "Recoge cristales y power-ups",
            "Consigue más puntos que la CPU"
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
        
        # Fondo de estrellas
        for i in range(100):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            size = random.randint(1, 3)
            color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            pygame.draw.circle(screen, color, (x, y), size)
        
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

# Crear nivel
def create_level():
    platforms = [
        # Plataformas base
        Platform(0, 500, 800, 20, "normal"),
        # Plataformas nivel intermedio
        Platform(100, 400, 200, 20, "normal"),
        Platform(400, 400, 200, 20, "normal"),
        # Plataformas superiores
        Platform(50, 300, 150, 20, "falling"),
        Platform(300, 250, 200, 20, "moving"),
        Platform(600, 300, 150, 20, "falling"),
        # Plataformas pequeñas
        Platform(200, 150, 100, 20, "normal"),
        Platform(500, 150, 100, 20, "normal"),
        # Plataforma superior
        Platform(350, 100, 100, 20, "normal"),
    ]
    
    crystals = []
    for _ in range(20):
        placed = False
        while not placed:
            # Elegir una plataforma aleatoria
            platform = random.choice(platforms)
            x = random.randint(int(platform.x + 10), int(platform.x + platform.width - 30))
            y = platform.y - 30
            
            # Comprobar si ya hay un cristal cercano
            too_close = False
            for crystal in crystals:
                dist = math.sqrt((crystal.x - x)**2 + (crystal.y - y)**2)
                if dist < 50:
                    too_close = True
                    break
            
            if not too_close:
                crystals.append(Crystal(x, y))
                placed = True
    
    powerups = []
    # Crear powerups en posiciones fijas estratégicas
    powerups.append(PowerUp(150, 370))
    powerups.append(PowerUp(450, 370))
    powerups.append(PowerUp(350, 220))
    powerups.append(PowerUp(400, 70))
    
    enemies = []
    # Crear enemigos normales en plataformas largas
    enemies.append(Enemy(150, 470, "normal"))
    enemies.append(Enemy(500, 470, "normal"))
    enemies.append(Enemy(450, 370, "normal"))
    
    # Crear enemigos voladores
    enemies.append(Enemy(300, 200, "flying"))
    enemies.append(Enemy(500, 100, "flying"))
    
    # Crear enemigos saltarines
    enemies.append(Enemy(200, 470, "jumping"))
    
    return platforms, crystals, powerups, enemies

# Función principal del juego
def main_game():
    # Crear objetos
    player = Player(100, 400)
    cpu = CPU(700, 400)
    
    platforms, crystals, powerups, enemies = create_level()
    
    # Variables de juego
    player_crystals_removed = []
    cpu_crystals_removed = []
    player_powerups_removed = []
    cpu_powerups_removed = []
    
    message_timer = 0
    show_message = False
    message_type = ""
    game_time = 60 * 60  # 60 segundos a 60 FPS
    
    # Para crear nuevos cristales
    crystal_timer = 0
    crystal_cooldown = 180  # Crear nuevo cristal cada 3 segundos
    
    # Para crear nuevos power-ups
    powerup_timer = 0
    powerup_cooldown = 600  # Crear nuevo power-up cada 10 segundos
    
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
        player_crystals_removed, player_powerups_removed = player.update(platforms, crystals, powerups, enemies, keys)
        cpu_crystals_removed, cpu_powerups_removed = cpu.update(platforms, crystals, powerups, enemies)
        
        # Eliminar cristales recogidos
        for crystal in player_crystals_removed:
            if crystal in crystals:
                crystals.remove(crystal)
                show_message = True
                message_timer = 60
                message_type = "crystal_player"
        
        for crystal in cpu_crystals_removed:
            if crystal in crystals:
                crystals.remove(crystal)
                show_message = True
                message_timer = 60
                message_type = "crystal_cpu"
        
        # Eliminar power-ups recogidos
        for powerup in player_powerups_removed:
            if powerup in powerups:
                powerups.remove(powerup)
                show_message = True
                message_timer = 60
                message_type = "powerup_player"
        
        for powerup in cpu_powerups_removed:
            if powerup in powerups:
                powerups.remove(powerup)
                show_message = True
                message_timer = 60
                message_type = "powerup_cpu"
        
        # Actualizar plataformas
        for platform in platforms:
            platform.update(player, cpu)
        
        # Actualizar enemigos
        for enemy in enemies:
            enemy.update(platforms)
        
        # Crear nuevos cristales periódicamente
        crystal_timer += 1
        if crystal_timer >= crystal_cooldown and len(crystals) < 10:
            crystal_timer = 0
            # Elegir plataforma aleatoria
            platform = random.choice(platforms)
            x = random.randint(int(platform.x + 10), int(platform.x + platform.width - 30))
            y = platform.y - 30
            crystals.append(Crystal(x, y))
        
        # Crear nuevos power-ups periódicamente
        powerup_timer += 1
        if powerup_timer >= powerup_cooldown and len(powerups) < 3:
            powerup_timer = 0
            # Elegir plataforma aleatoria
            platform = random.choice(platforms)
            x = random.randint(int(platform.x + 10), int(platform.x + platform.width - 30))
            y = platform.y - 30
            powerups.append(PowerUp(x, y))
        
        # Respawnear enemigos inactivos
        for i, enemy in enumerate(enemies):
            if not enemy.is_active:
                # Elegir plataforma aleatoria
                platform = random.choice(platforms)
                x = random.randint(int(platform.x + 10), int(platform.x + platform.width - 30))
                y = platform.y - enemy.height
                
                if enemy.type == "normal":
                    enemies[i] = Enemy(x, y, "normal")
                elif enemy.type == "flying":
                    enemies[i] = Enemy(x, y - 50, "flying")
                elif enemy.type == "jumping":
                    enemies[i] = Enemy(x, y, "jumping")
        
        # Dibujar todo
        screen.fill(BLACK)
        
        # Fondo de estrellas
        for i in range(50):
            x = random.randint(0, WIDTH)
            y = random.randint(0, HEIGHT)
            size = random.randint(1, 2)
            color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            pygame.draw.circle(screen, color, (x, y), size)
        
        # Dibujar plataformas
        for platform in platforms:
            platform.draw()
        
        # Dibujar cristales
        for crystal in crystals:
            crystal.draw()
        
        # Dibujar power-ups
        for powerup in powerups:
            powerup.draw()
        
        # Dibujar enemigos
        for enemy in enemies:
            enemy.draw()
        
        # Dibujar jugador y CPU
        player.draw()
        cpu.draw()
        
        # Dibujar barras de poder
        pygame.draw.rect(screen, WHITE, (20, 20, 110, 20), 1)
        pygame.draw.rect(screen, BLUE, (21, 21, player.power, 18))
        power_text = small_font.render("PODER", True, WHITE)
        screen.blit(power_text, (23, 22))
        
        pygame.draw.rect(screen, WHITE, (WIDTH - 130, 20, 110, 20), 1)
        pygame.draw.rect(screen, RED, (WIDTH - 129, 21, cpu.power, 18))
        cpu_power_text = small_font.render("CPU PODER", True, WHITE)
        screen.blit(cpu_power_text, (WIDTH - 127, 22))
        
        # Dibujar puntuaciones
        score_text = medium_font.render(f"Puntos: {int(player.score)}", True, WHITE)
        screen.blit(score_text, (20, 50))
        
        cpu_score_text = medium_font.render(f"CPU: {int(cpu.score)}", True, WHITE)
        screen.blit(cpu_score_text, (WIDTH - 150, 50))
        
        # Dibujar tiempo restante
        time_text = medium_font.render(f"Tiempo: {game_time // 60}", True, WHITE)
        screen.blit(time_text, (WIDTH // 2 - 60, 20))
        
        # Mostrar mensaje aleatorio
        if (random.random() < 0.002 or 
            (show_message and message_timer > 0)):
            
            if message_type == "crystal_player":
                message = "¡Crystal conseguido! +5 puntos"
                text = medium_font.render(message, True, GREEN)
            elif message_type == "crystal_cpu":
                message = "¡CPU consiguió crystal! +5 puntos"
                text = medium_font.render(message, True, RED)
            elif message_type == "powerup_player":
                message = "¡Power-up activado! +10 puntos"
                text = medium_font.render(message, True, GREEN)
            elif message_type == "powerup_cpu":
                message = "¡CPU activó power-up! +10 puntos"
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

# Iniciar el juego
if __name__ == "__main__":
    main()