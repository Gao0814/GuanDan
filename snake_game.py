import random
import sys
from pathlib import Path

import numpy as np
import pygame

pygame.init()

SCREEN_WIDTH = 900
SCREEN_HEIGHT = 640
BLOCK_SIZE = 20

PLAY_LEFT = 40
PLAY_TOP = 100
PLAY_RIGHT = SCREEN_WIDTH - 40
PLAY_BOTTOM = SCREEN_HEIGHT - 40

UP = (0, -1)
DOWN = (0, 1)
LEFT = (-1, 0)
RIGHT = (1, 0)
DIRECTIONS = [UP, DOWN, LEFT, RIGHT]

BG_COLOR = (18, 22, 33)
PANEL_COLOR = (28, 35, 52)
WALL_COLOR = (234, 202, 130)
GRID_COLOR = (42, 52, 72)
SNAKE_HEAD_COLOR = (87, 236, 141)
SNAKE_BODY_COLOR = (52, 182, 107)
FOOD_COLOR = (255, 95, 86)
MONSTER_COLOR = (129, 98, 255)
TEXT_COLOR = (241, 243, 255)
SUBTITLE_BG = (0, 0, 0, 160)

FPS = 60
HIGHSCORE_FILE = Path("snake_highscore.txt")


def to_pixel(grid_pos):
    return PLAY_LEFT + grid_pos[0] * BLOCK_SIZE, PLAY_TOP + grid_pos[1] * BLOCK_SIZE


def grid_limits():
    cols = (PLAY_RIGHT - PLAY_LEFT) // BLOCK_SIZE
    rows = (PLAY_BOTTOM - PLAY_TOP) // BLOCK_SIZE
    return cols, rows


class Snake:
    def __init__(self, start_len=2):
        cols, rows = grid_limits()
        head = (cols // 2, rows // 2)
        self.direction = RIGHT
        self.positions = [head]
        for i in range(1, start_len):
            self.positions.append((head[0] - i, head[1]))
        self.grow_pending = 0

    def head(self):
        return self.positions[0] if self.positions else None

    def set_direction(self, direction):
        if not self.positions:
            return
        if len(self.positions) > 1 and direction == (-self.direction[0], -self.direction[1]):
            return
        self.direction = direction

    def move(self):
        if not self.positions:
            return
        hx, hy = self.positions[0]
        dx, dy = self.direction
        new_head = (hx + dx, hy + dy)
        self.positions.insert(0, new_head)
        if self.grow_pending > 0:
            self.grow_pending -= 1
        else:
            self.positions.pop()

    def grow(self, amount=1):
        self.grow_pending += amount

    def shrink(self, amount):
        if amount <= 0:
            return
        for _ in range(amount):
            if self.positions:
                self.positions.pop()

    def ensure_min_length(self, minimum):
        if not self.positions:
            return
        while len(self.positions) < minimum:
            self.positions.append(self.positions[-1])

    def is_self_collision(self):
        if len(self.positions) < 2:
            return False
        return self.positions[0] in self.positions[1:]

    def draw(self, surface):
        for i, grid_pos in enumerate(self.positions):
            px, py = to_pixel(grid_pos)
            rect = pygame.Rect(px, py, BLOCK_SIZE, BLOCK_SIZE)
            color = SNAKE_HEAD_COLOR if i == 0 else SNAKE_BODY_COLOR
            pygame.draw.rect(surface, color, rect, border_radius=4)
            pygame.draw.rect(surface, (10, 13, 20), rect, 1, border_radius=4)


class Food:
    def __init__(self):
        self.position = (0, 0)

    def respawn(self, blocked_positions):
        cols, rows = grid_limits()
        while True:
            p = (random.randint(0, cols - 1), random.randint(0, rows - 1))
            if p not in blocked_positions:
                self.position = p
                break

    def draw(self, surface):
        px, py = to_pixel(self.position)
        rect = pygame.Rect(px, py, BLOCK_SIZE, BLOCK_SIZE)
        pygame.draw.rect(surface, FOOD_COLOR, rect, border_radius=6)
        pygame.draw.rect(surface, (120, 20, 20), rect, 1, border_radius=6)


class Monster:
    def __init__(self, blocked_positions):
        self.position = (0, 0)
        self.direction = random.choice(DIRECTIONS)
        self.respawn(blocked_positions)

    def respawn(self, blocked_positions):
        cols, rows = grid_limits()
        while True:
            p = (random.randint(0, cols - 1), random.randint(0, rows - 1))
            if p not in blocked_positions:
                self.position = p
                break

    def move(self):
        cols, rows = grid_limits()
        if random.random() < 0.35:
            self.direction = random.choice(DIRECTIONS)
        nx = self.position[0] + self.direction[0]
        ny = self.position[1] + self.direction[1]
        if nx < 0 or ny < 0 or nx >= cols or ny >= rows:
            self.direction = random.choice(DIRECTIONS)
            nx = max(0, min(cols - 1, self.position[0] + self.direction[0]))
            ny = max(0, min(rows - 1, self.position[1] + self.direction[1]))
        self.position = (nx, ny)

    def draw(self, surface):
        px, py = to_pixel(self.position)
        rect = pygame.Rect(px, py, BLOCK_SIZE, BLOCK_SIZE)
        pygame.draw.rect(surface, MONSTER_COLOR, rect, border_radius=6)
        pygame.draw.rect(surface, (36, 20, 94), rect, 1, border_radius=6)


class SnakeGame:
    def __init__(self):
        self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
        pygame.display.set_caption("贪吃蛇 - 三阶挑战版")
        self.clock = pygame.time.Clock()

        self.font = pygame.font.SysFont("microsoftyahei", 24)
        self.big_font = pygame.font.SysFont("microsoftyahei", 52, bold=True)
        self.mid_font = pygame.font.SysFont("microsoftyahei", 32, bold=True)

        self.state = "start"
        self.running = True

        self.snake = None
        self.food = Food()
        self.monster = None
        self.monster_mode = "length"

        self.score = 0
        self.stage = 1
        self.speed = 6
        self.paused = False
        self.high_score = self.load_high_score()

        self.move_accumulator = 0
        self.monster_accumulator = 0
        self.narrator_accumulator = 0

        self.subtitle = ""
        self.subtitle_deadline = 0

        self.bgm_channel = None
        self.bgm_sound = None
        self.setup_music()

    def setup_music(self):
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(frequency=44100, size=-16, channels=2)
            melody = [440, 523, 587, 659, 587, 523, 440, 392]
            duration = 0.18
            sample_rate = 44100
            wave_chunks = []
            for freq in melody:
                t = np.linspace(0, duration, int(sample_rate * duration), False)
                tone = np.sin(2 * np.pi * freq * t) * 0.22
                chunk = np.int16(tone * 32767)
                stereo = np.column_stack((chunk, chunk))
                wave_chunks.append(stereo)
            all_samples = np.concatenate(wave_chunks)
            self.bgm_sound = pygame.sndarray.make_sound(all_samples)
            self.bgm_channel = self.bgm_sound.play(loops=-1)
        except pygame.error:
            self.bgm_sound = None
            self.bgm_channel = None

    def load_high_score(self):
        if not HIGHSCORE_FILE.exists():
            return 0
        try:
            value = int(HIGHSCORE_FILE.read_text(encoding="utf-8").strip() or "0")
            return max(0, value)
        except (OSError, ValueError):
            return 0

    def save_high_score(self):
        try:
            HIGHSCORE_FILE.write_text(str(self.high_score), encoding="utf-8")
        except OSError:
            pass

    def set_subtitle(self, text, milliseconds=2200):
        self.subtitle = text
        self.subtitle_deadline = pygame.time.get_ticks() + milliseconds

    def apply_penalty(self, score_loss, length_loss, text):
        self.score = max(0, self.score - score_loss)
        self.snake.shrink(length_loss)
        self.set_subtitle(text)
        if len(self.snake.positions) <= 0:
            self.end_game("蛇身耗尽，游戏结束")

    def start_game(self):
        self.score = 0
        self.stage = 1
        self.speed = 6
        self.paused = False
        self.snake = Snake(start_len=2)
        self.monster = None
        self.monster_mode = "length"
        self.move_accumulator = 0
        self.monster_accumulator = 0
        self.narrator_accumulator = 0

        blocked = set(self.snake.positions)
        self.food.respawn(blocked)

        self.state = "playing"
        self.set_subtitle("旁白：欢迎来到蛇蛇竞技场，准备出发")

    def update_stage(self):
        if self.stage == 1 and self.score >= 100:
            self.stage = 2
            self.speed = 9
            self.snake.ensure_min_length(5)
            self.set_subtitle("旁白：进入中阶规则，碰墙和自撞将受到惩罚")
        if self.stage == 2 and self.score >= 220:
            self.stage = 3
            self.speed = 11
            self.monster = Monster(set(self.snake.positions) | {self.food.position})
            self.set_subtitle("旁白：高阶开启，怪兽登场！按M切换怪兽惩罚模式")

    def end_game(self, reason):
        self.state = "game_over"
        if self.score > self.high_score:
            self.high_score = self.score
            self.save_high_score()
        self.set_subtitle(f"旁白：{reason}", milliseconds=3000)

    def handle_input(self, event):
        if self.state == "start":
            if event.type == pygame.KEYDOWN or (event.type == pygame.MOUSEBUTTONDOWN and event.button == 1):
                self.start_game()
            return

        if self.state == "game_over":
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.start_game()
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                self.start_game()
            return

        if self.state != "playing" or event.type != pygame.KEYDOWN:
            return

        if event.key == pygame.K_p:
            self.paused = not self.paused
            if self.paused:
                self.set_subtitle("旁白：游戏已暂停，按P继续", milliseconds=1800)
            else:
                self.set_subtitle("旁白：继续前进", milliseconds=1200)
            return

        if self.paused:
            return

        if event.key in (pygame.K_UP, pygame.K_w):
            self.snake.set_direction(UP)
        elif event.key in (pygame.K_DOWN, pygame.K_s):
            self.snake.set_direction(DOWN)
        elif event.key in (pygame.K_LEFT, pygame.K_a):
            self.snake.set_direction(LEFT)
        elif event.key in (pygame.K_RIGHT, pygame.K_d):
            self.snake.set_direction(RIGHT)
        elif event.key == pygame.K_m and self.stage == 3:
            modes = ["score", "length", "death"]
            idx = modes.index(self.monster_mode)
            self.monster_mode = modes[(idx + 1) % len(modes)]
            self.set_subtitle(f"旁白：怪兽惩罚模式切换为 {self.monster_mode}")

    def step_game(self):
        if self.state != "playing" or self.paused:
            return

        previous_positions = list(self.snake.positions)
        self.snake.move()
        head = self.snake.head()
        if head is None:
            self.end_game("蛇身耗尽，游戏结束")
            return

        cols, rows = grid_limits()
        hit_wall = head[0] < 0 or head[1] < 0 or head[0] >= cols or head[1] >= rows
        if hit_wall:
            if self.stage == 1:
                self.end_game("撞墙，游戏结束")
                return
            self.snake.positions = previous_positions
            self.apply_penalty(50, 5, "旁白：撞墙惩罚 -50分 -5节")
            return

        if self.snake.is_self_collision():
            if self.stage == 1:
                self.end_game("蛇头撞到自己，游戏结束")
                return
            self.snake.positions = previous_positions
            self.apply_penalty(20, 2, "旁白：自撞惩罚 -20分 -2节")
            return

        if head == self.food.position:
            self.snake.grow(1)
            self.score += 10
            blocked = set(self.snake.positions)
            if self.monster:
                blocked.add(self.monster.position)
            self.food.respawn(blocked)
            self.set_subtitle("旁白：美味到手，+10分 +1节")

        if self.stage == 3 and self.monster and head == self.monster.position:
            if self.monster_mode == "score":
                self.apply_penalty(30, 0, "旁白：碰到怪兽，扣30分")
            elif self.monster_mode == "length":
                self.apply_penalty(0, 3, "旁白：碰到怪兽，减3节")
            else:
                self.end_game("碰到怪兽，直接死亡")
                return
            blocked = set(self.snake.positions) | {self.food.position}
            self.monster.respawn(blocked)

        self.update_stage()

    def update_narrator(self, dt):
        if self.state != "playing":
            return
        self.narrator_accumulator += dt
        if self.narrator_accumulator < 5500:
            return
        self.narrator_accumulator = 0

        lines = {
            1: [
                "旁白：稳住节奏，别让蛇头冲过围墙",
                "旁白：蛇只能往前，不能瞬间反向",
            ],
            2: [
                "旁白：中阶模式下失误会扣分扣节",
                "旁白：速度提升了，注意预判转向",
            ],
            3: [
                "旁白：怪兽四处乱窜，小心贴脸",
                "旁白：按M可切换怪兽惩罚策略",
            ],
        }
        self.set_subtitle(random.choice(lines[self.stage]), milliseconds=2400)

    def update_monster(self, dt):
        if self.stage != 3 or not self.monster or self.state != "playing":
            return
        self.monster_accumulator += dt
        if self.monster_accumulator >= 220:
            self.monster_accumulator = 0
            self.monster.move()

    def draw_start_screen(self):
        self.screen.fill(BG_COLOR)
        title = self.big_font.render("贪吃蛇三阶挑战", True, TEXT_COLOR)
        subtitle = self.mid_font.render("带旁白与怪兽模式", True, (183, 218, 255))
        tip = self.font.render("按任意键或鼠标左键开始游戏", True, (250, 235, 170))
        rule_text = [
            "规则1：初阶 撞墙/自撞即结束，初始2节",
            "规则2：中阶(>=100分) 撞墙-50分-5节，自撞-20分-2节，至少5节",
            "规则3：高阶(>=220分) 增加怪兽，按M切换惩罚：扣分/减节/死亡",
        ]
        self.screen.blit(title, (SCREEN_WIDTH // 2 - title.get_width() // 2, 150))
        self.screen.blit(subtitle, (SCREEN_WIDTH // 2 - subtitle.get_width() // 2, 220))
        self.screen.blit(tip, (SCREEN_WIDTH // 2 - tip.get_width() // 2, 290))

        for i, text in enumerate(rule_text):
            line = self.font.render(text, True, (210, 218, 230))
            self.screen.blit(line, (80, 360 + i * 34))

        music_tip = self.font.render("背景音乐已开启（若设备支持音频）", True, (151, 246, 187))
        self.screen.blit(music_tip, (SCREEN_WIDTH // 2 - music_tip.get_width() // 2, 520))

    def draw_playing_screen(self):
        self.screen.fill(BG_COLOR)
        pygame.draw.rect(self.screen, PANEL_COLOR, pygame.Rect(0, 0, SCREEN_WIDTH, 80))

        wall_rect = pygame.Rect(
            PLAY_LEFT,
            PLAY_TOP,
            PLAY_RIGHT - PLAY_LEFT,
            PLAY_BOTTOM - PLAY_TOP,
        )
        pygame.draw.rect(self.screen, (12, 16, 25), wall_rect)
        pygame.draw.rect(self.screen, WALL_COLOR, wall_rect, 4)

        cols, rows = grid_limits()
        for x in range(cols):
            for y in range(rows):
                px, py = to_pixel((x, y))
                pygame.draw.rect(self.screen, GRID_COLOR, pygame.Rect(px, py, BLOCK_SIZE, BLOCK_SIZE), 1)

        self.food.draw(self.screen)
        self.snake.draw(self.screen)
        if self.stage == 3 and self.monster:
            self.monster.draw(self.screen)

        hud = [
            f"分数: {self.score}",
            f"最高分: {self.high_score}",
            f"长度: {len(self.snake.positions)}",
            f"阶段: {self.stage}",
            f"速度: {self.speed}",
        ]
        if self.stage == 3:
            hud.append(f"怪兽模式: {self.monster_mode}")
        hud_text = "   |   ".join(hud)
        hud_surface = self.font.render(hud_text, True, TEXT_COLOR)
        self.screen.blit(hud_surface, (20, 24))

    def draw_game_over(self):
        self.draw_playing_screen()
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 150))
        self.screen.blit(overlay, (0, 0))

        over = self.big_font.render("游戏结束", True, (255, 210, 210))
        detail = self.mid_font.render(f"最终得分：{self.score}", True, TEXT_COLOR)
        best = self.font.render(f"历史最高分：{self.high_score}", True, (201, 255, 212))
        retry = self.font.render("按 R 或鼠标左键重新开始", True, (255, 244, 178))
        self.screen.blit(over, (SCREEN_WIDTH // 2 - over.get_width() // 2, 220))
        self.screen.blit(detail, (SCREEN_WIDTH // 2 - detail.get_width() // 2, 300))
        self.screen.blit(best, (SCREEN_WIDTH // 2 - best.get_width() // 2, 340))
        self.screen.blit(retry, (SCREEN_WIDTH // 2 - retry.get_width() // 2, 360))

    def draw_pause_hint(self):
        if self.state != "playing" or not self.paused:
            return
        tip = self.mid_font.render("暂停中", True, (255, 245, 170))
        resume = self.font.render("按 P 继续游戏", True, (255, 255, 255))
        self.screen.blit(tip, (SCREEN_WIDTH // 2 - tip.get_width() // 2, 40))
        self.screen.blit(resume, (SCREEN_WIDTH // 2 - resume.get_width() // 2, 74))

    def draw_subtitle(self):
        if not self.subtitle or pygame.time.get_ticks() > self.subtitle_deadline:
            return
        sub_surface = self.font.render(self.subtitle, True, (255, 255, 255))
        bg = pygame.Surface((sub_surface.get_width() + 20, sub_surface.get_height() + 14), pygame.SRCALPHA)
        bg.fill(SUBTITLE_BG)
        x = SCREEN_WIDTH // 2 - bg.get_width() // 2
        y = SCREEN_HEIGHT - 34 - bg.get_height()
        self.screen.blit(bg, (x, y))
        self.screen.blit(sub_surface, (x + 10, y + 7))

    def run(self):
        while self.running:
            dt = self.clock.tick(FPS)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                    break
                self.handle_input(event)

            if self.state == "playing" and not self.paused:
                self.move_accumulator += dt
                move_interval = max(70, int(1000 / self.speed))
                while self.move_accumulator >= move_interval and self.state == "playing":
                    self.move_accumulator -= move_interval
                    self.step_game()
                self.update_monster(dt)
                self.update_narrator(dt)

            if self.state == "start":
                self.draw_start_screen()
            elif self.state == "playing":
                self.draw_playing_screen()
            else:
                self.draw_game_over()

            self.draw_pause_hint()
            self.draw_subtitle()
            pygame.display.flip()

        pygame.quit()
        sys.exit()


def main():
    SnakeGame().run()


if __name__ == "__main__":
    main()