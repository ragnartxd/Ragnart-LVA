import pygame
import sys
# import os # No es necesario si no cargas assets externos

# --- Constantes ---
SCREEN_WIDTH = 1000
SCREEN_HEIGHT = 700
FPS = 60

# Colores (usaremos estos para dibujar)
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 0, 0)
GREEN = (0, 255, 0) # Color del jugador
BLUE = (0, 0, 255)  # Color de plataformas estándar
SKY_BLUE = (135, 206, 235) # Color del fondo
GROUND_GREEN = (34, 139, 34) # Color del suelo

# Propiedades del Jugador
PLAYER_ACC = 0.7  # Aceleración
PLAYER_FRICTION = -0.12 # Fricción (debe ser negativa)
PLAYER_GRAV = 0.8   # Gravedad
PLAYER_JUMP_STRENGTH = -18 # Fuerza del salto (negativa porque Y aumenta hacia abajo)
PLAYER_WIDTH = 40
PLAYER_HEIGHT = 60

# Propiedades de las Plataformas
PLATFORM_HEIGHT = 20

# --- Clases ---

class Player(pygame.sprite.Sprite):
    """ Represents the player character. """
    def __init__(self, game):
        """ Initialize the player sprite. """
        super().__init__()
        self.game = game # Reference to the main game object

        # --- Crear la apariencia del jugador usando un rectángulo ---
        self.image = pygame.Surface((PLAYER_WIDTH, PLAYER_HEIGHT))
        self.image.fill(GREEN) # Rellenar con el color definido
        # self.image.set_colorkey(BLACK) # Opcional: si quieres un color transparente

        self.rect = self.image.get_rect()
        self.rect.centerx = SCREEN_WIDTH / 2
        self.rect.bottom = SCREEN_HEIGHT - 50 # Start near the bottom

        # Physics vectors (position, velocity, acceleration)
        # Using vectors simplifies physics calculations
        self.pos = pygame.math.Vector2(self.rect.centerx, self.rect.bottom)
        self.vel = pygame.math.Vector2(0, 0)
        self.acc = pygame.math.Vector2(0, 0)

        self.on_ground = False
        self.facing_right = True # To know direction (useful for future attacks/sprites)

    def jump(self):
        """ Makes the player jump, but only if standing on a platform. """
        # Check if player is standing on a platform before jumping
        # Move down 1 pixel to check for collision, then move back
        self.rect.y += 1
        hits = pygame.sprite.spritecollide(self, self.game.platforms, False)
        self.rect.y -= 1
        if hits: # Only jump if touching a platform
            self.vel.y = PLAYER_JUMP_STRENGTH
            self.on_ground = False # Player is airborne after jumping

    def update(self):
        """ Update player state every frame (physics and input). """
        # --- Apply Gravity ---
        # Default acceleration is gravity pulling down
        self.acc = pygame.math.Vector2(0, PLAYER_GRAV)

        # --- Horizontal Movement Input ---
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT] or keys[pygame.K_a]:
            self.acc.x = -PLAYER_ACC
            self.facing_right = False
        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            self.acc.x = PLAYER_ACC
            self.facing_right = True

        # --- Apply Friction ---
        # Friction opposes motion (acts opposite to velocity)
        self.acc.x += self.vel.x * PLAYER_FRICTION

        # --- Equations of Motion (Kinematics) ---
        # v = v0 + a*t (where t=1 frame, so just v += a)
        self.vel += self.acc
        # Limit horizontal speed (optional but good)
        if abs(self.vel.x) > 10:
             self.vel.x = 10 if self.vel.x > 0 else -10
        # Stop if velocity is very small (avoids drifting)
        if abs(self.vel.x) < 0.1:
            self.vel.x = 0

        # p = p0 + v*t + 0.5*a*t^2 (where t=1 frame)
        self.pos += self.vel + 0.5 * self.acc

        # --- Screen Boundary Check (Horizontal) ---
        if self.pos.x > SCREEN_WIDTH - PLAYER_WIDTH / 2:
            self.pos.x = SCREEN_WIDTH - PLAYER_WIDTH / 2
            self.vel.x = 0 # Stop at edge
        if self.pos.x < PLAYER_WIDTH / 2:
            self.pos.x = PLAYER_WIDTH / 2
            self.vel.x = 0 # Stop at edge

        # Update the sprite's rect position based on the physics vector self.pos
        # Collisions will be handled using self.rect in the collision checks
        self.rect.midbottom = self.pos

        # Note: Collision detection is handled more robustly in the Game.update method
        # by checking X and Y movement separately.

    def collide_with_platforms(self, platforms):
        """
        Handles collision detection and response between the player and platforms.
        This method is called AFTER the player's position has been updated based on velocity.
        It corrects the player's position if a collision occurs.
        """

        # --- Horizontal Collision Check ---
        # Move rect horizontally based on current velocity
        self.rect.x += int(self.vel.x)
        hits = pygame.sprite.spritecollide(self, platforms, False) # Check for horizontal collision
        if hits:
            # If moving right and hit something
            if self.vel.x > 0:
                 # Find the platform hit that is closest to the player's right side
                 closest_platform = min(hits, key=lambda p: abs(p.rect.left - self.rect.right))
                 self.rect.right = closest_platform.rect.left # Snap player's right edge to platform's left edge
            # If moving left and hit something
            elif self.vel.x < 0:
                 # Find the platform hit that is closest to the player's left side
                 closest_platform = min(hits, key=lambda p: abs(p.rect.right - self.rect.left))
                 self.rect.left = closest_platform.rect.right # Snap player's left edge to platform's right edge
            self.pos.x = self.rect.centerx # Update the precise position vector based on corrected rect
            self.vel.x = 0 # Stop horizontal movement upon collision

        # --- Vertical Collision Check ---
        # Move rect vertically based on current velocity
        self.rect.y += int(self.vel.y)
        hits = pygame.sprite.spritecollide(self, platforms, False) # Check for vertical collision
        self.on_ground = False # Assume not on ground unless collision proves otherwise
        if hits:
            # If moving down (falling) and hit something
            if self.vel.y > 0:
                # Find the platform hit that is closest below the player
                closest_platform = min(hits, key=lambda p: abs(p.rect.top - self.rect.bottom))
                # Check if the player's bottom was actually above the platform top before this frame's movement
                # This prevents snapping up if slightly embedded from the side
                if self.pos.y - self.vel.y <= closest_platform.rect.top: # Compare previous bottom position
                   self.rect.bottom = closest_platform.rect.top # Snap player's bottom to platform's top
                   self.on_ground = True # Player has landed
                   self.vel.y = 0 # Stop vertical movement (falling)
            # If moving up (jumping) and hit something (head bonk)
            elif self.vel.y < 0:
                # Find the platform hit that is closest above the player
                closest_platform = min(hits, key=lambda p: abs(p.rect.bottom - self.rect.top))
                # Check if the player's top was actually below the platform bottom before this frame's movement
                if self.pos.y - self.rect.height - self.vel.y >= closest_platform.rect.bottom:
                    self.rect.top = closest_platform.rect.bottom # Snap player's top to platform's bottom
                    self.vel.y = 0 # Stop vertical movement (jumping)

            # Update the precise position vector based on corrected rect
            self.pos.y = self.rect.midbottom[1]

        # If player is falling very fast and somehow passed through, double check ground
        if not self.on_ground and self.vel.y > 1:
             self.rect.y += 1
             hits_check = pygame.sprite.spritecollide(self, platforms, False)
             self.rect.y -= 1
             if hits_check:
                 closest_platform = min(hits_check, key=lambda p: abs(p.rect.top - self.rect.bottom))
                 if self.rect.bottom <= closest_platform.rect.top + 5: # Allow small tolerance
                     self.rect.bottom = closest_platform.rect.top
                     self.pos.y = self.rect.midbottom[1]
                     self.on_ground = True
                     self.vel.y = 0


class Platform(pygame.sprite.Sprite):
    """ Represents a platform obstacle. """
    def __init__(self, x, y, width, height, color=BLUE):
        """ Initialize the platform sprite. """
        super().__init__()
        # Create the visual appearance (a colored rectangle)
        self.image = pygame.Surface((width, height))
        self.image.fill(color)
        self.rect = self.image.get_rect()
        # Set its position
        self.rect.x = x
        self.rect.y = y

# --- Main Game Class ---
class Game:
    """ Manages the main game loop and game states. """
    def __init__(self):
        """ Initialize Pygame and set up the game window. """
        pygame.init()
        pygame.mixer.init() # Initialize mixer for potential future sound
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("Mi Juego 2D Estilo Retro (Sin Imágenes)")
        self.clock = pygame.time.Clock() # To control frame rate
        self.running = True
        self.font_name = pygame.font.match_font('arial') # Get a default font
        self.load_assets() # Placeholder for loading sounds, fonts etc.

    def load_assets(self):
        """ Load game assets (currently none needed for graphics). """
        # This is where you would load sounds in the future:
        # self.jump_sound = pygame.mixer.Sound(...)
        pass

    def new_game(self):
        """ Starts a new game instance. """
        # --- Sprite Groups ---
        # Using groups makes managing sprites (updating, drawing) easier
        self.all_sprites = pygame.sprite.Group() # Group for ALL sprites (for drawing/updating)
        self.platforms = pygame.sprite.Group()   # Group specifically for platforms (for collisions)
        # self.enemies = pygame.sprite.Group()     # Add more groups as needed
        # self.projectiles = pygame.sprite.Group()
        # self.items = pygame.sprite.Group()

        # --- Create Player ---
        self.player = Player(self) # Create an instance of the Player class
        self.all_sprites.add(self.player) # Add player to the main group

        # --- Create Platforms (Example Level) ---
        # Ground platform
        ground = Platform(0, SCREEN_HEIGHT - PLATFORM_HEIGHT, SCREEN_WIDTH, PLATFORM_HEIGHT, GROUND_GREEN)
        # Some floating platforms
        p1 = Platform(200, SCREEN_HEIGHT - 150, 200, PLATFORM_HEIGHT)
        p2 = Platform(500, SCREEN_HEIGHT - 300, 150, PLATFORM_HEIGHT)
        p3 = Platform(SCREEN_WIDTH - 300, SCREEN_HEIGHT - 450, 250, PLATFORM_HEIGHT)

        # Add platforms to relevant groups
        self.all_sprites.add(ground, p1, p2, p3) # Add to main group for drawing
        self.platforms.add(ground, p1, p2, p3)   # Add to platform group for collision checks

        # --- Start the Game Loop ---
        self.run()

    def run(self):
        """ The main game loop. """
        self.playing = True
        while self.playing:
            self.dt = self.clock.tick(FPS) / 1000.0 # Delta time in seconds (for frame-rate independent physics)
            self.events() # Process inputs
            self.update() # Update game state
            self.draw()   # Render the screen

    def events(self):
        """ Handles all player input and window events. """
        for event in pygame.event.get():
            # Check for closing the window
            if event.type == pygame.QUIT:
                if self.playing:
                    self.playing = False # Stop the current game loop
                self.running = False # Stop the outer loop (exit program)
            # Check for key presses
            if event.type == pygame.KEYDOWN:
                # Jump action
                if event.key == pygame.K_SPACE or event.key == pygame.K_UP or event.key == pygame.K_w:
                    self.player.jump()
            # --- Add more event handling here ---
            # Example: Attack on key press
            # if event.type == pygame.KEYDOWN:
            #     if event.key == pygame.K_x:
            #         self.player.attack() # Need to implement attack method in Player

            # Example: Open inventory
            # if event.type == pygame.KEYDOWN:
            #      if event.key == pygame.K_e:
            #          self.show_inventory_screen() # Need to implement this screen

    def update(self):
        """ Updates all game objects and handles interactions. """
        # Update all sprites in the main group by calling their update() methods
        self.all_sprites.update()

        # --- Collision Detection and Response ---
        # Player vs Platforms collision
        # This is now handled more robustly by moving X, checking, then moving Y, checking
        self.player.collide_with_platforms(self.platforms)


        # --- Add other collision checks here ---
        # Example: Player vs Enemies
        # hits = pygame.sprite.spritecollide(self.player, self.enemies, False)
        # if hits:
        #     self.player_takes_damage() # Implement damage logic
        #     # Could add knockback: self.player.vel.x = KNOCKBACK_VALUE

        # Example: Projectiles vs Enemies
        # hits = pygame.sprite.groupcollide(self.projectiles, self.enemies, True, True) # True, True = both disappear
        # for projectile, enemies_hit in hits.items():
        #      for enemy in enemies_hit:
        #          enemy.take_damage(projectile.damage) # Implement damage logic

        # --- Camera Scrolling (if level wider than screen) ---
        # Basic scrolling: Keep player between 1/4 and 3/4 of the screen width
        # if self.player.rect.right >= SCREEN_WIDTH * 0.75:
        #     scroll_amount = self.player.rect.right - (SCREEN_WIDTH * 0.75)
        #     # Shift player back
        #     self.player.pos.x -= scroll_amount
        #     # Shift all other sprites (platforms, enemies, items)
        #     for sprite in self.all_sprites:
        #         if sprite != self.player: # Don't scroll the player itself again
        #             sprite.rect.x -= scroll_amount
        #     # You might need to generate new platforms/enemies off-screen

        # if self.player.rect.left <= SCREEN_WIDTH * 0.25:
        #     scroll_amount = (SCREEN_WIDTH * 0.25) - self.player.rect.left
        #     # Shift player forward
        #     self.player.pos.x += scroll_amount
        #     # Shift all other sprites
        #     for sprite in self.all_sprites:
        #         if sprite != self.player:
        #             sprite.rect.x += scroll_amount

        # --- Game Over Condition ---
        # Example: Player falls off the bottom
        if self.player.rect.top > SCREEN_HEIGHT:
             self.playing = False # End current game loop

    def draw_text(self, text, size, color, x, y):
        """ Utility function to draw text on the screen. """
        font = pygame.font.Font(self.font_name, size)
        text_surface = font.render(text, True, color) # True for anti-aliasing
        text_rect = text_surface.get_rect()
        text_rect.midtop = (x, y)
        self.screen.blit(text_surface, text_rect)

    def draw(self):
        """ Renders all elements to the screen. """
        # Draw background
        self.screen.fill(SKY_BLUE)
        # Draw all sprites
        self.all_sprites.draw(self.screen)

        # --- Draw HUD (Heads-Up Display) ---
        # Example: Draw player's Y velocity for debugging
        # self.draw_text(f"Vel Y: {self.player.vel.y:.2f}", 18, WHITE, SCREEN_WIDTH / 2, 15)
        # self.draw_text(f"On Ground: {self.player.on_ground}", 18, WHITE, SCREEN_WIDTH / 2, 35)


        # *AFTER* drawing everything, flip the display
        pygame.display.flip() # Makes everything drawn visible

    def show_start_screen(self):
        """ Displays the start screen (optional). """
        # Simple example: Wait for key press
        self.screen.fill(BLACK)
        self.draw_text("MI JUEGO RETRO", 48, WHITE, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 4)
        self.draw_text("Flechas/WASD para mover, Espacio/W/Arriba para saltar", 22, WHITE, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2)
        self.draw_text("Presiona cualquier tecla para empezar", 22, WHITE, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 3 / 4)
        pygame.display.flip()
        self.wait_for_key()

    def show_game_over_screen(self):
        """ Displays the game over screen (optional). """
        if not self.running: # Don't show if we are quitting entirely
            return
        self.screen.fill(BLACK)
        self.draw_text("GAME OVER", 48, RED, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 4)
        self.draw_text("Presiona cualquier tecla para jugar de nuevo", 22, WHITE, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 3 / 4)
        pygame.display.flip()
        self.wait_for_key()

    def wait_for_key(self):
        """ Utility function to pause until a key is pressed. """
        waiting = True
        while waiting:
            self.clock.tick(FPS) # Keep clock ticking
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    waiting = False
                    self.running = False # Allow quitting from wait screens
                if event.type == pygame.KEYUP: # Wait for key release
                    waiting = False


# --- Run the Game ---
g = Game()
g.show_start_screen() # Show the start screen first
while g.running:
    g.new_game() # Start a new game session
    g.show_game_over_screen() # Show game over when new_game() finishes

pygame.quit() # Uninitialize Pygame modules
sys.exit()    # Exit the program