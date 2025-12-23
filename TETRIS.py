import pygame
import random
import time
import gpiozero
import RPi.GPIO as GPIO
import LCD1602

btn = gpiozero.DigitalInputDevice(pin=25, pull_up=False)

GPIO.setmode(GPIO.BCM)
PIR_PIN = 17
GPIO.setup(PIR_PIN, GPIO.IN)
previous_pir_state = 0


# ゲーム画面設定
BLOCK_SIZE = 30
GRID_WIDTH, GRID_HEIGHT = 300, 600
PANEL_WIDTH = 200
WIDTH, HEIGHT = GRID_WIDTH + PANEL_WIDTH, GRID_HEIGHT

COLS = GRID_WIDTH // BLOCK_SIZE
ROWS = GRID_HEIGHT // BLOCK_SIZE


# 色の定義
BLACK = (0, 0, 0)
GRAY = (100, 100, 100)
WHITE = (255, 255, 255)


# テトリミノの定義
MINOS = [
    ([[1, 1, 1, 1]], (0, 255, 255)),         # I
    ([[1, 0, 0], [1, 1, 1]], (0, 0, 255)),   # J
    ([[0, 0, 1], [1, 1, 1]], (255, 165, 0)), # L
    ([[1, 1], [1, 1]], (255, 255, 0)),       # O
    ([[0, 1, 1], [1, 1, 0]], (0, 255, 0)),   # S
    ([[0, 1, 0], [1, 1, 1]], (128, 0, 128)), # T
    ([[1, 1, 0], [0, 1, 1]], (255, 0, 0)),   # Z
]

class Tetrimino:
    def __init__(self):
        self.shape, self.color = random.choice(MINOS)
        self.x = COLS // 2 - len(self.shape[0]) // 2
        self.y = 0

    def rotate(self):
        self.shape = [list(row) for row in zip(*self.shape[::-1])]


# スコアエフェクト
class ScoreEffect:
    def __init__(self, x, y, text, color, duration=2000):
        self.x = x
        self.y = y
        self.text = text
        self.color = color
        self.start_time = pygame.time.get_ticks()
        self.duration = duration

    def draw(self, screen):
        elapsed = pygame.time.get_ticks() - self.start_time
        if elapsed < self.duration:
            alpha = max(255 - (elapsed / self.duration) * 255, 0)
            font = pygame.font.SysFont("meiryo", 40, bold=True)
            label = font.render(self.text, True, self.color)
            label.set_alpha(alpha)
            rect = label.get_rect(center=(WIDTH // 2, self.y - (elapsed / self.duration) * 20))
            screen.blit(label, rect)
            return True
        return False
    

# ランダムイベント発生処理(関数化)
def trigger_random_event(grid, score_effects, abnormal_states, NORMAL_FALL_SPEED):
    abnormal_active = any([
        abnormal_states["reverse"],
        abnormal_states["command_confusion"],
        abnormal_states["speed_up"]
    ])
    available_abnormal_events = []
    if not abnormal_states["reverse"]:
        available_abnormal_events.append(3)
    if not abnormal_states["command_confusion"]:
        available_abnormal_events.append(4)
    if not abnormal_states["speed_up"]:
        available_abnormal_events.append(5)
    possible_events = [1, 2]
    if abnormal_active:
        possible_events.append(6)
    possible_events.extend(available_abnormal_events)
    event_num = random.choice(possible_events)

    if event_num == 1:
        for _ in range(3):
            hole_pos = random.randint(0, COLS - 1)
            new_row = [GRAY if i != hole_pos else 0 for i in range(COLS)]
            grid.pop(0)
            grid.append(new_row)
        score_effects.append(ScoreEffect(WIDTH // 2, HEIGHT // 2, "+ BLOCKS", (255, 0, 0)))

    elif event_num == 2:
        grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
        score_effects.append(ScoreEffect(WIDTH // 2, HEIGHT // 2, "CLEAN UP", (0, 255, 255)))

    elif event_num == 3:
        abnormal_states["reverse"] = True
        score_effects.append(ScoreEffect(WIDTH // 2, HEIGHT // 2, "REVERSE", (128, 0, 128)))

    elif event_num == 4:
        abnormal_states["command_confusion"] = True
        keys = [pygame.K_LEFT, pygame.K_RIGHT, pygame.K_DOWN, pygame.K_UP, pygame.K_SPACE]
        shuffled = keys[:]
        while True:
            random.shuffle(shuffled)
            if any(k != s for k, s in zip(keys, shuffled)):
                break
        abnormal_states["shuffled_commands"] = dict(zip(keys, shuffled))
        score_effects.append(ScoreEffect(WIDTH // 2, HEIGHT // 2, "COMMAND CONFUSION", (0, 255, 0)))

    elif event_num == 5:
        abnormal_states["speed_up"] = True
        score_effects.append(ScoreEffect(WIDTH // 2, HEIGHT // 2, "SPEED UP", (255, 165, 0)))

    elif event_num == 6:
        abnormal_states["reverse"] = False
        abnormal_states["command_confusion"] = False
        abnormal_states["speed_up"] = False
        abnormal_states["shuffled_commands"] = {}
        score_effects.append(ScoreEffect(WIDTH // 2, HEIGHT // 2, "RESET", (255, 255, 255)))
    return grid


# 衝突判定
def check_collision(grid, shape, x, y):
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val:
                if x + j < 0 or x + j >= COLS or y + i >= ROWS:
                    return True
                if y + i >= 0 and grid[y + i][x + j]:
                    return True
    return False


# ミノ着地
def merge(grid, shape, x, y, color):
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val and y + i >= 0:
                grid[y + i][x + j] = color

                
# ミノ消滅描画補助
def draw_entire_grid(screen, grid, current=None, reverse=False):
    temp_surf = pygame.Surface((GRID_WIDTH, GRID_HEIGHT))
    draw_game_grid(temp_surf, grid)
    if current:
        for i, row in enumerate(current.shape):
            for j, val in enumerate(row):
                if val:
                    pygame.draw.rect(temp_surf, current.color,
                        ((current.x + j) * BLOCK_SIZE, (current.y + i) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))
    if reverse:
        temp_surf = pygame.transform.flip(temp_surf, False, True)
    screen.blit(temp_surf, (0, 0))

    
# 揃えてミノ消滅
def clear_lines(grid, screen, score_effects, score, abnormal_states):
    new_grid = []
    flashing_rows = []
    for y, row in enumerate(grid):
        if all(cell != 0 for cell in row):
            flashing_rows.append(y)
        else:
            new_grid.append(row)

    line_count = len(flashing_rows)
    if line_count:
        points = {1: 100, 2: 300, 3: 500, 4: 800}.get(line_count, 0)
        score += points
        effect = ScoreEffect(120, flashing_rows[0]*BLOCK_SIZE, f"+{points}", (255, 255, 0))
        score_effects.append(effect)

        for _ in range(3):
            for y in flashing_rows:
                grid[y] = [WHITE for _ in range(COLS)]
            draw_entire_grid(screen, grid, reverse=abnormal_states.get("reverse", False))
            pygame.display.flip()
            pygame.time.delay(100)

            for y in flashing_rows:
                grid[y] = [0 for _ in range(COLS)]
            draw_entire_grid(screen, grid, reverse=abnormal_states.get("reverse", False))
            pygame.display.flip()
            pygame.time.delay(100)

        for _ in flashing_rows:
            new_grid.insert(0, [0 for _ in range(COLS)])

    flashing = line_count > 0
    return new_grid, score, flashing


# グリッドの描画
def draw_game_grid(screen, grid):
    for y, row in enumerate(grid):
        for x, color in enumerate(row):
            if color:
                pygame.draw.rect(screen, color, (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))
    for x in range(COLS + 1):
        pygame.draw.line(screen, GRAY, (x * BLOCK_SIZE, 0), (x * BLOCK_SIZE, HEIGHT))
    for y in range(ROWS):
        pygame.draw.line(screen, GRAY, (0, y * BLOCK_SIZE), (GRID_WIDTH, y * BLOCK_SIZE))


def draw_simple_grid(screen, grid):
    for y, row in enumerate(grid):
        for x, color in enumerate(row):
            if color:
                pygame.draw.rect(screen, color, (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))


# ハードドロップ
def hard_drop(grid, current):
    while not check_collision(grid, current.shape, current.x, current.y + 1):
        current.y += 1
    merge(grid, current.shape, current.x, current.y, current.color)
    return Tetrimino()


# テキスト描画
def draw_text(screen, text, size, x, y, color=WHITE):
    font = pygame.font.SysFont("meiryo", size, bold=True)
    label = font.render(text, True, color)
    rect = label.get_rect(center=(x, y))
    screen.blit(label, rect)


# ボタン描画
def draw_button(screen, text, x, y, w, h, color, hover_color, mouse_pos):
    rect = pygame.Rect(x, y, w, h)
    is_hover = rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, hover_color if is_hover else color, rect)
    draw_text(screen, text, 24, x + w // 2, y + h // 2)
    return rect, is_hover


# サイド画面描画
def draw_side_panel(screen, mouse_pos, next_mino, change_count, score, abnormal_states):
    panel_x = GRID_WIDTH + 10
    draw_text(screen, "Controls", 24, panel_x + 90, 40)
    
    cmd_display = {
        "←": "←",
        "→": "→",
        "↓": "↓",
        "↑": "↑",
        "SPACE": "SPACE"
    }
    if abnormal_states["command_confusion"]:
        for k in cmd_display.keys():
            cmd_display[k] = "???"

    instructions = [
        f"{cmd_display['←']} {cmd_display['→']} {cmd_display['↓']}: Move",
        f"{cmd_display['↑']}: Rotate",
        f"{cmd_display['SPACE']}: Hard Drop",
        "BUTTON: Change Mino",
        "SENSOR: Random Event",
        "ESC: Pause"
    ]
    for i, line in enumerate(instructions):
        draw_text(screen, line, 18, panel_x + 90, 80 + i * 30)

    pause_btn, is_hover = draw_button(screen, "PAUSE", panel_x + 20, 250, 150, 40, GRAY, (150, 150, 150), mouse_pos)

    draw_text(screen, "Next:", 20, panel_x + 90, 330)
    
    next_shape = next_mino.shape
    shape_width = len(next_shape[0])
    shape_height = len(next_shape)
    start_x = panel_x + 90 - (shape_width * 10)
    start_y = 350

    for i, row in enumerate(next_shape):
        for j, val in enumerate(row):
            if val:
                pygame.draw.rect(screen, next_mino.color,
                    (start_x + j * 20, start_y + i * 20, 20, 20))

    draw_text(screen, f"Change: {change_count}/3", 28, panel_x + 90, 480)
    draw_text(screen, f"Score: {score}", 28, panel_x + 90, 530, (255, 255, 0))

    return pause_btn, is_hover





def main():
    pygame.init()
    LCD1602.init(0x3f, 1)
    LCD1602.write(0, 0, "Score: 0")
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    current = Tetrimino()
    next_mino = Tetrimino()
    change_count = 3
    fall_time = 0
    NORMAL_FALL_SPEED = 500
    fall_speed = NORMAL_FALL_SPEED
    game_state = "start"
    running = True
    score = 0
    score_effects = []
    btn_held = False
    global previous_pir_state

    # 状態異常管理用辞書
    abnormal_states = {
        "reverse": False,
        "command_confusion": False,
        "speed_up": False,
        "shuffled_commands": {}
    }

    # オリジナルコマンドキー（左、右、下、上、スペース）
    original_commands = {
        pygame.K_LEFT: pygame.K_LEFT,
        pygame.K_RIGHT: pygame.K_RIGHT,
        pygame.K_DOWN: pygame.K_DOWN,
        pygame.K_UP: pygame.K_UP,
        pygame.K_SPACE: pygame.K_SPACE,
    }

    # スコアエフェクト追加用の簡易関数
    def add_score_effect(score_effects, text, color):
        score_effects.append(ScoreEffect(WIDTH // 2, HEIGHT // 2, text, color))

    # I2Cキャラクタ表示液晶にスコアを表示
    def update_lcd_score(score):
        if not hasattr(update_lcd_score, "last_score"):
            update_lcd_score.last_score = -1
        if update_lcd_score.last_score != score:
            LCD1602.write(0, 0, f"Score: {score:<10}")
            update_lcd_score.last_score = score


    while running:
        dt = clock.tick()
        mouse_pos = pygame.mouse.get_pos()
        screen.fill(BLACK)

        if game_state == "start":
            draw_text(screen, "TETRIS", 60, WIDTH // 2, HEIGHT // 3)
            start_btn, hover = draw_button(screen, "Play", WIDTH // 2 - 75, HEIGHT // 2, 150, 50, GRAY, (180, 180, 180), mouse_pos)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN and hover:
                    grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
                    current = Tetrimino()
                    next_mino = Tetrimino()
                    change_count = 3
                    score = 0
                    score_effects.clear()
                    # 状態異常リセット
                    for k in abnormal_states:
                        if k != "shuffled_commands":
                            abnormal_states[k] = False
                    abnormal_states["shuffled_commands"] = {}
                    fall_speed = NORMAL_FALL_SPEED
                    game_state = "play"

        elif game_state == "play":
            fall_time += dt
            current_pir_state = GPIO.input(PIR_PIN)
            if current_pir_state == 1 and previous_pir_state == 0:
                grid = trigger_random_event(grid, score_effects, abnormal_states, NORMAL_FALL_SPEED)
            previous_pir_state = current_pir_state
                
            # SPEED UP状態なら速度を半分に
            current_fall_speed = fall_speed // 2 if abnormal_states["speed_up"] else fall_speed

            if btn.value and change_count > 0 and not btn_held:
                current, next_mino = next_mino, Tetrimino()
                change_count -= 1
                add_score_effect(score_effects, "CHANGE", (255, 255, 0))
                btn_held = True
            elif not btn.value:
                btn_held = False

            if fall_time > current_fall_speed:
                if not check_collision(grid, current.shape, current.x, current.y + 1):
                    current.y += 1
                else:
                    merge(grid, current.shape, current.x, current.y, current.color)
                    score += 10
                    update_lcd_score(score)
                    grid, score, flashing = clear_lines(grid, screen, score_effects, score, abnormal_states)
                    current = next_mino
                    next_mino = Tetrimino()
                    if check_collision(grid, current.shape, current.x, current.y):
                        game_state = "gameover"
                fall_time = 0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game_state = "pause"

                    # COMMAND CONFUSION時はキー操作をシャッフル辞書に基づいて入れ替え
                    def get_mapped_key(k):
                        if abnormal_states["command_confusion"] and k in abnormal_states["shuffled_commands"]:
                            return abnormal_states["shuffled_commands"][k]
                        return k

                    k = event.key
                    mapped_key = get_mapped_key(k)

                    if mapped_key == pygame.K_LEFT:
                        if not check_collision(grid, current.shape, current.x - 1, current.y):
                            current.x -= 1
                    elif mapped_key == pygame.K_RIGHT:
                        if not check_collision(grid, current.shape, current.x + 1, current.y):
                            current.x += 1
                    elif mapped_key == pygame.K_DOWN:
                        if not check_collision(grid, current.shape, current.x, current.y + 1):
                            current.y += 1
                    elif mapped_key == pygame.K_SPACE:
                        current = hard_drop(grid, current)
                        score += 10
                        update_lcd_score(score)
                        grid, score, flashing = clear_lines(grid, screen, score_effects, score, abnormal_states)
                        update_lcd_score(score)
                        if flashing and abnormal_states["reverse"]:
                            pygame.display.flip()
                            pygame.time.delay(300)
                        current = next_mino
                        next_mino = Tetrimino()
                        if check_collision(grid, current.shape, current.x, current.y):
                            game_state = "gameover"
                        fall_time = 0
                    elif mapped_key == pygame.K_UP:
                        rotated = [list(row) for row in zip(*current.shape[::-1])]
                        if not check_collision(grid, rotated, current.x, current.y):
                            current.shape = rotated
                            

            # REVERSE状態なら描画を上下反転
            if abnormal_states["reverse"]:
                # 画面上下反転
                temp_surf = pygame.Surface((GRID_WIDTH, GRID_HEIGHT))
                draw_game_grid(temp_surf, grid)
                for i, row in enumerate(current.shape):
                    for j, val in enumerate(row):
                        if val:
                            pygame.draw.rect(temp_surf, current.color,
                                ((current.x + j) * BLOCK_SIZE, (current.y + i) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))
                screen.blit(pygame.transform.flip(temp_surf, False, True), (0, 0))
            else:
                draw_game_grid(screen, grid)
                for i, row in enumerate(current.shape):
                    for j, val in enumerate(row):
                        if val:
                            pygame.draw.rect(screen, current.color,
                                ((current.x + j) * BLOCK_SIZE, (current.y + i) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))

            pause_btn, is_hover = draw_side_panel(screen, mouse_pos, next_mino, change_count, score, abnormal_states)
            if pygame.mouse.get_pressed()[0] and is_hover:
                game_state = "pause"

            for effect in score_effects[:]:
                if not effect.draw(screen):
                    score_effects.remove(effect)

        elif game_state == "pause":
            draw_text(screen, "PAUSED", 40, WIDTH // 2, HEIGHT // 3)
            resume_btn, h1 = draw_button(screen, "Resume", WIDTH // 2 - 75, HEIGHT // 2 - 30, 150, 40, GRAY, (150,150,150), mouse_pos)
            back_btn, h2 = draw_button(screen, "Back to Title", WIDTH // 2 - 75, HEIGHT // 2 + 30, 150, 40, GRAY, (150,150,150), mouse_pos)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if h1:
                        game_state = "play"
                    elif h2:
                        game_state = "start"

        elif game_state == "gameover":
            draw_text(screen, "GAME OVER", 40, WIDTH // 2, HEIGHT // 3)
            draw_text(screen, f"Final Score: {score}", 28, WIDTH // 2, HEIGHT // 3 + 50, (255, 255, 0))
            retry_btn, h1 = draw_button(screen, "Retry", WIDTH // 2 - 75, HEIGHT // 2 + 10, 150, 40, GRAY, (150,150,150), mouse_pos)
            title_btn, h2 = draw_button(screen, "Back to Title", WIDTH // 2 - 75, HEIGHT // 2 + 60, 150, 40, GRAY, (150,150,150), mouse_pos)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if h1:
                        grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
                        current = Tetrimino()
                        next_mino = Tetrimino()
                        change_count = 3
                        score = 0
                        update_lcd_score(score)
                        score_effects.clear()
                        # 状態異常リセット
                        for k in abnormal_states:
                            if k != "shuffled_commands":
                                abnormal_states[k] = False
                        abnormal_states["shuffled_commands"] = {}
                        fall_speed = NORMAL_FALL_SPEED
                        game_state = "play"
                    elif h2:
                        game_state = "start"

        pygame.display.flip()

    pygame.quit()
    GPIO.cleanup()
    
if __name__ == "__main__":
    main()



    

    
# ーー操作方法ーー
# ← → ↓: 移動
# ↑: 回転
# スペースキー: ハードドロップ
# タクトスイッチ: ミノチェンジ(３回まで)
# モーションセンサー: ランダムイベント
# [×] ウィンドウを閉じると終了

