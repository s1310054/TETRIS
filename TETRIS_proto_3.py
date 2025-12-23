import pygame
import random



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


# 衝突判定
def check_collision(grid, shape, x, y):
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val:
                if x + j < 0 or x + j >= COLS or y + i >= ROWS:
                    return True
                if x + i >= 0 and grid[y + i][x + j]:
                    return True
    return False


# ミノ着地
def merge(grid, shape, x, y, color):
    for i, row in enumerate(shape):
        for j, val in enumerate(row):
            if val and y + i >= 0:
                grid[y + i][x + j] = color


# 揃えてミノ消滅
def clear_lines(grid, screen):
    new_grid = []
    flashing_rows = []

    for y, row in enumerate(grid):
        if all(cell != 0 for cell in row):
            flashing_rows.append(y)
        else:
            new_grid.append(row)

    if flashing_rows:
        for _ in range(3):
            for y in flashing_rows:
                grid[y] = [WHITE for _ in range(COLS)]
            draw_grid(screen, grid)
            pygame.display.flip()
            pygame.time.delay(100)

            for y in flashing_rows:
                grid[y] = [0 for _ in range(COLS)]
            draw_grid(screen, grid)
            pygame.display.flip()
            pygame.time.delay(100)

        for _ in flashing_rows:
            new_grid.insert(0, [0 for _ in range(COLS)])

    return new_grid


# グリッドの描画
def draw_grid(screen, grid):
    for y, row in enumerate(grid):
        for x, color in enumerate(row):
            if color:
                pygame.draw.rect(screen, color, (x * BLOCK_SIZE, y * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))
    for x in range(COLS + 1):
        pygame.draw.line(screen, GRAY, (x * BLOCK_SIZE, 0), (x * BLOCK_SIZE, HEIGHT))
    for y in range(ROWS):
        pygame.draw.line(screen, GRAY, (0, y * BLOCK_SIZE), (WIDTH, y * BLOCK_SIZE))


# ハードドロップ
def hard_drop(grid, current):
    while not check_collision(grid, current.shape, current.x, current.y + 1):
        current.y += 1
    merge(grid, current.shape, current.x, current.y, current.color)
    return Tetrimino()


# テキスト描画
def draw_text(screen, text, size, x, y, color = WHITE):
    font = pygame.font.SysFont("meiryo", size, bold = True)
    label = font.render(text, True, color)
    rect = label.get_rect(center = (x, y))
    screen.blit(label, rect)


# ボタン描画
def draw_button(screen, text, x, y, w, h, color, hover_color, mouse_pos):
    rect = pygame.Rect(x, y, w, h)
    is_hover = rect.collidepoint(mouse_pos)
    pygame.draw.rect(screen, hover_color if is_hover else color, rect)
    draw_text(screen, text, 24, x + w // 2, y + h // 2)
    return rect, is_hover


def draw_side_panel(screen, mouse_pos):
    panel_x = GRID_WIDTH + 10
    draw_text(screen, "Controls", 24, panel_x + 90, 40)
    instructions = [
        "← → ↓: Move",
        "↑: Rotate",
        "SPACE: Hard Drop",
        "ESC: Pause"
    ]
    for i, line in enumerate(instructions):
        draw_text(screen, line, 18, panel_x + 90, 80 + i * 30)

    # ポーズボタン
    pause_btn, is_hover = draw_button(screen, "PAUSE", panel_x + 20, 250, 150, 40, GRAY, (150, 150, 150), mouse_pos)
    return pause_btn, is_hover




def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    clock = pygame.time.Clock()
    grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
    current = Tetrimino()
    fall_time = 0
    fall_speed = 500
    game_state = "start"
    running = True

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
                    game_state = "play"
        
        elif game_state == "play":
            fall_time += dt
            if fall_time > fall_speed:
                if not check_collision(grid, current.shape, current.x, current.y + 1):
                    current.y += 1
                else:
                    merge(grid, current.shape, current.x, current.y, current.color)
                    grid = clear_lines(grid, screen)
                    current = Tetrimino()
                    if check_collision(grid, current.shape, current.x, current.y):
                        game_state = "gameover"
                fall_time = 0

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        game_state = "pause"
                    elif event.key == pygame.K_LEFT:
                        if not check_collision(grid, current.shape, current.x - 1, current.y):
                            current.x -= 1
                    elif event.key == pygame.K_RIGHT:
                        if not check_collision(grid, current.shape, current.x + 1, current.y):
                            current.x += 1
                    elif event.key == pygame.K_DOWN:
                        if not check_collision(grid, current.shape, current.x, current.y + 1):
                            current.y += 1
                    elif event.key == pygame.K_SPACE:
                        current = hard_drop(grid, current)
                        grid = clear_lines(grid, screen)
                        if check_collision(grid, current.shape, current.x, current.y):
                            game_state = "gameover"
                        fall_time = 0
                    elif event.key == pygame.K_UP:
                        rotated = [list(row) for row in zip(*current.shape[::-1])]
                        if not check_collision(grid, rotated, current.x, current.y):
                            current.shape = rotated

            # 描画
            draw_grid(screen, grid)
            for i, row in enumerate(current.shape):
                for j, val in enumerate(row):
                    if val:
                        pygame.draw.rect(screen, current.color,
                            ((current.x + j) * BLOCK_SIZE, (current.y + i) * BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE))

            pause_btn, is_hover = draw_side_panel(screen, mouse_pos)
            if pygame.mouse.get_pressed()[0] and is_hover:
                game_state = "pause"

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
            retry_btn, h1 = draw_button(screen, "Retry", WIDTH // 2 - 75, HEIGHT // 2 + 10, 150, 40, GRAY, (150,150,150), mouse_pos)
            title_btn, h2 = draw_button(screen, "Back to Title", WIDTH // 2 - 75, HEIGHT // 2 + 60, 150, 40, GRAY, (150,150,150), mouse_pos)
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if h1:
                        grid = [[0 for _ in range(COLS)] for _ in range(ROWS)]
                        current = Tetrimino()
                        game_state = "play"
                    elif h2:
                        game_state = "start"

        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()


# ーー操作方法ーー
# ← → ↓: 移動
# ↑: 回転
# スペースキー: ハードドロップ
# [×] ウィンドウを閉じると終了

