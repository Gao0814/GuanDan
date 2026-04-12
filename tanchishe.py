 import pygame
 import random
 from enum import Enum

 # 初始化pygame
 pygame.in
 # 定义颜色
 BLACK = (0, 0, 0)
 WHITE = (255, 255, 255)
 RED = (213, 50, 80)
 GREEN = (0, 255, 0)
 BLUE = (50, 153, 213)

 # 游戏设置
 WINDOW_WIDTH = 600
 WINDOW_HEIGHT = 400
 BLOCK_SIZE = 20
 SPEED = 10

 class Direction(Enum):
     UP = 1
     DOWN = 2
     LEFT = 3
     RIGHT = 4

 class SnakeGame:
     def __init__(self):
         self.display = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
         pygame.display.set_caption('贪吃蛇游戏')
         self.clock = pygame.time.Clock()
         self.reset()

     def reset(self):
         self.direction = Direction.RIGHT
         self.head = [WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2]
         self.snake = [
             self.head,
             [self.head[0] - BLOCK_SIZE, self.head[1]],
             [self.head[0] - 2 * BLOCK_SIZE, self.head[1]]
         ]
         self.score = 0
         self.food = None
         self._place_food()

     def _place_food(self):
         x = random.randint(0, (WINDOW_WIDTH - BLOCK_SIZE) // BLOCK_SIZE) * BLOCK_SIZE
         y = random.randint(0, (WINDOW_HEIGHT - BLOCK_SIZE) // BLOCK_SIZE) * BLOCK_SIZE
         self.food = [x, y]
         if self.food in self.snake:
             self._place_food()
               self.food = [x, y]
        if self.food in self.snake:
          self._place_food()

    def play_step(self):
          # 处理事件
         for event in pygame.event.get():
              if event.type == pygame.QUIT:
                  pygame.quit()
               quit()
            if event.type == pygame.KEYDOWN:
               if event.key == pygame.K_UP and self.direction != Direction.DOWN:
                   self.direction = Direction.UP
                elif event.key == pygame.K_DOWN and self.direction != Direction.UP:
                  self.direction = Direction.DOWN
       64 +       65 +                    self.direction = Direction.LEFT
       66 +                elif event.key == pygame.K_RIGHT and self.direction != Direction.LEFT:
       67 +                    self.direction = Direction.RIGHT
       68 +
       69 +        # 移动蛇
       70 +        self._move()
       71 +        self.snake.insert(0, self.head.copy())
       72 +
       73 +        # 检查游戏结束
       74 +        game_over = False
       75 +        if self._is_collision():
       76 +            game_over = True
       77 +            return game_over, self.score
       78 +
       79 +        # 检查是否吃到食物
       80 +        if self.head == self.food:
       81 +            self.score += 1
       82 +            self._place_food()
       83 +        else:
       84 +            self.snake.pop()
       85 +
       86 +        # 更新UI和时钟
       87 +        self._update_ui()
       88 +        self.clock.tick(SPEED)
       89 +        return game_over, self.score
       90 +
       91 +    def _is_collision(self):
       92 +        # 撞墙
       93 +        if (self.head[0] >= WINDOW_WIDTH or self.head[0] < 0 or
       94 +            self.head[1] >= WINDOW_HEIGHT or self.head[1] < 0):
       95 +            return True
       96 +        # 撞自己
       97 +        if self.head in self.snake[1:]:
       98 +            return True
       99 +        return False
      100 +
      101 +    def _move(self):
      102 +        x, y = self.head
      103 +        if self.direction == Direction.UP:
      104 +            y -= BLOCK_SIZE
      105 +        elif self.direction == Direction.DOWN:
      106 +            y += BLOCK_SIZE
      107 +        elif self.direction == Direction.LEFT:
      108 +            x -= BLOCK_SIZE
      109 +        elif self.direction == Direction.RIGHT:
      110 +            x += BLOCK_SIZE
      111 +        self.head = [x, y]
      112 +
      113 +    def _update_ui(self):
      114 +        self.display.fill(BLACK)
      115 +
      116 +        # 绘制蛇
      117 +        for segment in self.snake:
      118 +            pygame.draw.rect(self.display, GREEN,
      119 +                           pygame.Rect(segment[0], segment[1], BLOCK_SIZE, BLOCK_SIZE))
      120 +
      121 +        # 绘制食物
      122 +        pygame.draw.rect(self.display, RED,
      123 +                        pygame.Rect(self.food[0], self.food[1], BLOCK_SIZE, BLOCK_SIZE))
      124 +
      125 +        # 显示分数
      126 +        font = pygame.font.SysFont('simsun', 25)
      127 +        text = font.render(f'得分: {self.score}', True, WHITE)
      128 +        self.display.blit(text, [10, 10])
      129 +        pygame.display.flip()
      130 +
      131 +def main():
      132 +    game = SnakeGame()
      133 +
      134 +    # 游戏循环
      135 +    while True:
      136 +        game_over, score = game.play_step()
      137 +
      138 +        if game_over:
      139 +            break
      140 +
      141 +    # 显示游戏结束信息
      142 +    font = pygame.font.SysFont('simsun', 50)
      143 +    text = font.render(f'游戏结束! 最终得分: {score}', True, RED)
      144 +    game.display.blit(text, [WINDOW_WIDTH // 2 - 200, WINDOW_HEIGHT // 2 - 25])
      145 +    pygame.display.flip()
      146 +    pygame.time.wait(3000)
      147 +
      148 +    pygame.quit()
      149 +
      150 +if __name__ == '__main__':
      151 +    main()

 
