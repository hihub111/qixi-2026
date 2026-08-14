"""
爱心 → 玫瑰 → 烟花 → 诗句（第三版）
流程：画笔描爱心 → 停留1秒 → 绽放消散 → 画笔同步描6朵玫瑰（中间大、环绕5小）→ 停留0.5秒 → 绽放 → 15秒烟花表演（全程发射）→ 最后一个烟花消失1秒后 → 诗句浮现（停留至手动关闭）
玫瑰线参考 Keith Peters《Coding Curves》第11章 ROSES：
  r = a * cos(k * t)，k=5（奇数）→ 5 个花瓣
"""
import pygame
import pygame.freetype   # 真斜体 + 更清晰的字形渲染
import sys
import math
import random

pygame.init()
screen = pygame.display.set_mode((1000, 700))
pygame.display.set_caption("爱心与玫瑰")
clock = pygame.time.Clock()

# ── 爱心参数方程（与 heart_shaped.py 相同）──
def heart_x(t):
    return 16 * (math.sin(t) ** 3)

def heart_y(t):
    return 13 * math.cos(t) - 5 * math.cos(2*t) - 2 * math.cos(3*t) - math.cos(4*t)

# ── 玫瑰线参数方程（极坐标转直角坐标）──
# r = a * cos(k * t)：半径随角度波动，形成花瓣
def rose_x(t, a, k):
    return a * math.cos(k * t) * math.cos(t)

def rose_y(t, a, k):
    return a * math.cos(k * t) * math.sin(t)

# ── 颜色 ──
PINK_PALETTE = [
    (255, 182, 193), (255, 105, 180), (255, 20, 147),
    (255, 240, 245), (255, 160, 190), (230, 90, 170),
]
# 所有玫瑰都是粉色同色系：中间大玫瑰最浓艳，环绕的 5 朵深浅各不相同
ROSE_PALETTES = [
    [(255, 20, 147), (255, 105, 180), (255, 80, 160), (255, 140, 170), (255, 50, 155)],    # 中心：浓艳粉
    [(255, 182, 193), (255, 200, 210), (255, 170, 185), (255, 190, 200), (255, 210, 220)], # 浅粉
    [(255, 160, 190), (255, 175, 200), (255, 145, 180), (255, 165, 195), (255, 155, 185)], # 玫瑰粉
    [(255, 130, 165), (255, 150, 180), (255, 120, 155), (255, 140, 170), (255, 135, 165)], # 中粉
    [(255, 90, 145), (255, 110, 160), (255, 80, 135), (255, 100, 150), (255, 95, 145)],    # 深粉
    [(255, 220, 235), (255, 235, 245), (255, 210, 225), (255, 225, 238), (255, 215, 230)], # 极浅粉
]

CX, CY = 500, 350          # 画面中心（爱心用）
HEART_SCALE = 14           # 爱心大小

# ── 预计算两种形状的轮廓点 ──
def sample_heart(count=350):
    pts = []
    for i in range(count):
        t = (i / count) * math.pi * 2
        x = CX + heart_x(t) * HEART_SCALE
        y = CY - heart_y(t) * HEART_SCALE      # pygame 的 y 向下为正，取负翻转
        pts.append((x, y))
    return pts

def sample_rose(cx, cy, a, k, count=400):
    pts = []
    for i in range(count):
        t = (i / count) * math.pi * 2
        x = cx + rose_x(t, a, k)
        y = cy - rose_y(t, a, k)
        pts.append((x, y))
    return pts

heart_points = sample_heart()

# 玫瑰布局：中间一朵大玫瑰，环绕 count 朵小玫瑰
def ring_layout(cx, cy, big_a, small_a, ring_r, count):
    """返回 [(中心x, 中心y, 半径a, 花瓣数k), ...]，第一朵是大玫瑰"""
    layout = [(cx, cy, big_a, 5)]
    for i in range(count):
        angle = -math.pi / 2 + i * (2 * math.pi / count)   # 从正上方开始绕一圈
        x = cx + ring_r * math.cos(angle)
        y = cy + ring_r * math.sin(angle)
        layout.append((x, y, small_a, 5))
    return layout

ROSE_LAYOUT = ring_layout(CX, CY, big_a=120, small_a=70, ring_r=210, count=5)
rose_sets = [sample_rose(cx, cy, a, k) for (cx, cy, a, k) in ROSE_LAYOUT]


# ── 通用光点粒子：心形和玫瑰都用它 ──
class Particle:
    def __init__(self, x, y, color=None, bloom_center=(CX, CY)):
        self.home_x = x
        self.home_y = y
        self.x = x
        self.y = y
        self.vx = 0.0
        self.vy = 0.0
        self.color = color or random.choice(PINK_PALETTE)
        self.twinkle = random.uniform(0, math.pi * 2)
        self.age = 0.0          # 出生后经过的秒数（用于出生闪光）
        self.life = None        # 绽放后剩余寿命（帧），None = 还没绽放
        # 绽放时以自己所属形状的中心为原点向外炸
        self.bloom_cx, self.bloom_cy = bloom_center

    def bloom(self):
        """绽放：从所属中心向外给初速度，并开始生命倒计时"""
        dx = self.x - self.bloom_cx
        dy = self.y - self.bloom_cy
        dist = math.hypot(dx, dy) or 1.0
        speed = random.uniform(150, 420)
        self.vx = dx / dist * speed + random.uniform(-60, 60)
        self.vy = dy / dist * speed + random.uniform(-60, 60)
        self.life = random.randint(40, 90)
        self.max_life = self.life

    def update(self, dt):
        self.age += dt
        if self.life is None:
            # 未绽放：停在轮廓上，轻轻呼吸
            self.x = self.home_x + math.sin(self.twinkle) * 2
            self.y = self.home_y + math.cos(self.twinkle) * 2
            self.twinkle += 2 * dt
        else:
            # 绽放中：重力 + 位移 + 寿命衰减
            self.vy += 350 * dt
            self.x += self.vx * dt
            self.y += self.vy * dt
            self.life -= 1

    @property
    def dead(self):
        return self.life is not None and self.life <= 0

    def draw(self, surf):
        """画自己：光晕 + 亮核；绽放时随寿命变淡"""
        if self.life is not None:
            ratio = self.life / self.max_life
            glow_alpha = int(40 * ratio)
            core_alpha = int(255 * ratio)
        else:
            glow_alpha = 40
            core_alpha = 255
            # 出生闪光：刚画出来 0.4 秒内特别亮
            flash = max(0.0, 1 - self.age / 0.4)
            core_alpha = min(255, core_alpha + int(150 * flash))

        glow = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(glow, (*self.color, glow_alpha), (15, 15), 14)
        surf.blit(glow, (int(self.x) - 15, int(self.y) - 15))
        core = pygame.Surface((12, 12), pygame.SRCALPHA)
        pygame.draw.circle(core, (*self.color, core_alpha), (6, 6), 5)
        surf.blit(core, (int(self.x) - 6, int(self.y) - 6))


# ════════════════════════════════════════════════════════════
# 结尾烟花表演：火箭升空 → 顶点爆炸 → 火花消散
# ════════════════════════════════════════════════════════════
FIREWORK_DURATION = 15.0   # 表演时长 15 秒
# 叠加发光：重叠的光晕颜色相加 → 火光越密越亮（和 flower3d.py 同款）
ADD_BLEND = pygame.BLEND_RGBA_ADD if hasattr(pygame, "BLEND_RGBA_ADD") else pygame.BLEND_ADD
FIREWORK_PALETTE = [
    (255, 105, 180),   # 粉
    (255, 182, 193),   # 浅粉
    (200, 120, 255),   # 紫
    (255, 220, 150),   # 金
    (255, 240, 245),   # 白粉
]


class Rocket:
    """火箭：从屏幕底部升起，拖着渐隐尾巴，到顶点爆炸"""
    def __init__(self):
        self.x = random.uniform(80, screen.get_width() - 80)
        self.y = screen.get_height() - 10
        self.vx = random.uniform(-25, 25)          # 水平漂移
        self.vy = random.uniform(-520, -460)       # 初速向上（屏幕 y 向下，负=向上）
        self.color = random.choice(FIREWORK_PALETTE)
        self.trail = []                            # 拖尾：最近的位置

    def update(self, dt):
        self.vy += 300 * dt                        # 重力：约1.5秒到达顶点
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.trail.append((self.x, self.y))
        if len(self.trail) > 10:
            self.trail.pop(0)

    def draw(self, surf):
        """画火箭：渐隐拖尾 + 发光头部"""
        for i, (tx, ty) in enumerate(self.trail):
            alpha = int(255 * i / max(1, len(self.trail) - 1))
            pygame.draw.circle(surf, (*self.color, alpha), (int(tx), int(ty)), 2)
        # 光晕 + 亮点
        pygame.draw.circle(surf, (*self.color, 90), (int(self.x), int(self.y)), 8)
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), 3)

    @property
    def ready_to_explode(self):
        return self.vy >= -40      # 上升速度接近 0 = 到达顶点


class Spark:
    """爆炸火花：圆形炸开 + 光晕光效"""
    def __init__(self, x, y, color):
        self.x = x
        self.y = y
        # 圆形爆炸：随机角度 × 随机速度 → 全方位均匀散开
        angle = random.uniform(0, math.pi * 2)
        speed = random.uniform(60, 230)            # 像素/秒
        self.vx = math.cos(angle) * speed
        self.vy = math.sin(angle) * speed
        self.color = color
        self.life = random.randint(40, 80)         # 寿命（帧）
        self.max_life = self.life

    def update(self, dt):
        self.vy += 180 * dt                        # 重力：整团火光缓缓下落
        self.x += self.vx * dt
        self.y += self.vy * dt
        self.life -= 1

    @property
    def dead(self):
        return self.life <= 0

    def draw(self, surf):
        """光晕(大而淡) + 亮核(小而亮)，随寿命渐隐"""
        ratio = self.life / self.max_life
        alpha = int(255 * ratio)
        r = max(1, int(3 * ratio))
        pygame.draw.circle(surf, (*self.color, alpha // 3), (int(self.x), int(self.y)), r * 4)
        pygame.draw.circle(surf, (*self.color, alpha), (int(self.x), int(self.y)), r)


# ── 状态机 ──
# draw_heart → hold_heart → bloom_heart → draw_rose → hold_rose → bloom_rose → firework → poem_wait → poem
state = "draw_heart"
state_time = 0
DRAW_DURATION = 3.0        # 画笔描边耗时
HOLD_HEART = 1.0           # 爱心成形后停留 1 秒
HOLD_ROSE = 0.5            # 玫瑰成形后停留 0.5 秒

particles = []
drawn_count = 0
current_sets = [heart_points]   # 当前绘制中的形状点集（可能是多朵玫瑰）

# 烟花表演状态
rockets = []          # 升空中的火箭
sparks = []           # 爆炸后的火花
next_launch = 0.0     # 下一次发射倒计时
fx_surf = pygame.Surface(screen.get_size(), pygame.SRCALPHA)   # 烟花渲染层（保留半透明）

# 结尾诗句：莎士比亚《十四行诗》第29首 结尾两句
POEM_LINES = [
    "For the sweet love remembered such wealth brings,",
    "That then I scorn to change my state with kings.",
]
POEM_FADE = 2.5            # 诗句淡入耗时（秒）

# 艺术字体候选：按优先级（优先可读性好的衬线斜体，其次花体）
ART_FONTS = [
    ("didot", True),          # Didot 斜体：高对比衬线，优雅易读
    ("georgia", True),        # Georgia 斜体：经典衬线
    ("applechancery", False), # 书法体
    ("corsiva", False),       # 花体，可读性比 Snell 好
    ("snellroundhand", False),
]

def make_poem_texts(lines, max_width):
    """选字体 + 字号从大到小自动缩到放得进画布；返回 (字体名, 斜体, 字号, 字体, 渲染好的行)
    freetype 的 italic 会用字体自带的真斜体字面，不会把正体拉斜（发糊的根源）"""
    for name, italic in ART_FONTS:
        if not pygame.font.match_font(name):
            continue
        for size in (52, 44, 38, 34, 30, 26):
            font = pygame.freetype.SysFont(name, size, italic=italic)
            longest = max(font.get_rect(ln).width for ln in lines)
            if longest <= max_width:
                return name, italic, size, font, [font.render(ln, (255, 225, 235))[0] for ln in lines]
    font = pygame.freetype.SysFont(None, 24)   # 兜底：系统默认字体
    return None, False, 24, font, [font.render(ln, (255, 225, 235))[0] for ln in lines]

poem_name, poem_italic, poem_size, poem_font, poem_texts = make_poem_texts(POEM_LINES, screen.get_width() - 140)

# 署名：七夕日期（字号为诗句的 60%，颜色更淡）
POEM_SIGN = "Qixi Festival · August 19, 2026"
sign_font = pygame.freetype.SysFont(poem_name, int(poem_size * 0.6), italic=poem_italic)
sign_text = sign_font.render(POEM_SIGN, (240, 205, 220))[0]


def start_drawing(sets):
    """切换到绘制新形状：清空粒子，从头描边"""
    global particles, drawn_count, current_sets, state_time
    particles = []
    drawn_count = 0
    current_sets = sets
    state_time = 0


# ── 主循环 ──
while True:
    dt = clock.tick(60) / 1000.0

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            sys.exit()

    # ── 状态机 ──
    state_time += dt

    if state in ("draw_heart", "draw_rose"):
        # 画笔随时间推进，逐点"点亮"粒子；多朵玫瑰共享同一进度，同步绘制
        target = int((state_time / DRAW_DURATION) * len(current_sets[0]))
        target = min(target, len(current_sets[0]))
        while drawn_count < target:
            for si, pts in enumerate(current_sets):
                x, y = pts[drawn_count]
                if state == "draw_rose":
                    # 每朵玫瑰用自己的色系，按花瓣渐变着色
                    palette = ROSE_PALETTES[si]
                    idx = int((drawn_count / len(pts)) * len(palette))
                    color = palette[idx % len(palette)]
                    center = ROSE_LAYOUT[si][:2]
                else:
                    color = None                   # 爱心随机粉色
                    center = (CX, CY)
                particles.append(Particle(x, y, color, bloom_center=center))
            drawn_count += 1
        if drawn_count >= len(current_sets[0]):   # 画完了，进入停留
            state = "hold_heart" if state == "draw_heart" else "hold_rose"
            state_time = 0

    elif state == "hold_heart":
        if state_time >= HOLD_HEART:
            state = "bloom_heart"
            for p in particles:
                p.bloom()

    elif state == "hold_rose":
        if state_time >= HOLD_ROSE:
            state = "bloom_rose"
            for p in particles:
                p.bloom()

    elif state == "bloom_heart":
        if not particles:                  # 爱心散尽 → 开始画玫瑰
            state = "draw_rose"
            start_drawing(rose_sets)

    elif state == "bloom_rose":
        if not particles:                  # 玫瑰散尽 → 烟花表演
            state = "firework"
            state_time = 0
            next_launch = 0.0

    elif state == "firework":
        # 全程持续发射，直到表演时长结束
        next_launch -= dt
        if state_time < FIREWORK_DURATION and next_launch <= 0:
            rockets.append(Rocket())
            next_launch = random.uniform(0.3, 0.6)
        # 火箭上升，到达顶点爆开成火花
        for rk in list(rockets):
            rk.update(dt)
            if rk.ready_to_explode:
                for _ in range(random.randint(80, 120)):
                    sparks.append(Spark(rk.x, rk.y, rk.color))
                rockets.remove(rk)
        # 火花更新与清理
        for sp in sparks:
            sp.update(dt)
        sparks = [sp for sp in sparks if not sp.dead]
        # 时长到且最后一个烟花消失 → 静默 1 秒后浮现诗句
        if state_time >= FIREWORK_DURATION and not rockets and not sparks:
            state = "poem_wait"
            state_time = 0

    elif state == "poem_wait":
        if state_time >= 1.0:              # 停顿 1 秒
            state = "poem"
            state_time = 0

    # ── 更新粒子 ──
    for p in particles:
        p.update(dt)
    if state in ("bloom_heart", "bloom_rose"):
        particles = [p for p in particles if not p.dead]

    # ── 绘制 ──
    screen.fill((12, 8, 18))
    for p in particles:
        p.draw(screen)

    # 烟花：火箭 + 火花画在透明层，用叠加发光贴到屏幕（重叠处变亮）
    if state == "firework":
        fx_surf.fill((0, 0, 0, 0))
        for rk in rockets:
            rk.draw(fx_surf)
        for sp in sparks:
            sp.draw(fx_surf)
        screen.blit(fx_surf, (0, 0), special_flags=ADD_BLEND)

    # 诗句：缓缓浮现（透明度随时间上升，POEM_FADE 秒内淡入完成）
    if state == "poem":
        fade = min(1.0, state_time / POEM_FADE)
        line_gap = poem_font.get_sized_height() + 12  # 行距跟随实际字号
        last_rect = None
        for i, text in enumerate(poem_texts):
            text.set_alpha(int(255 * fade))
            rect = text.get_rect(center=(screen.get_width() / 2,
                                         screen.get_height() / 2 + (i - 0.5) * line_gap))
            last_rect = rect
            screen.blit(text, rect)
        # 署名：第二行诗句的右下方，随诗句一起淡入
        sign_text.set_alpha(int(255 * fade))
        sign_rect = sign_text.get_rect()
        sign_rect.topright = (last_rect.right, last_rect.bottom + 18)
        screen.blit(sign_text, sign_rect)

    # 画笔光标：每个点集一支笔，同步推进
    if state in ("draw_heart", "draw_rose") and drawn_count > 0:
        brush = pygame.Surface((40, 40), pygame.SRCALPHA)
        pygame.draw.circle(brush, (255, 255, 255, 60), (20, 20), 18)
        pygame.draw.circle(brush, (255, 255, 255, 220), (20, 20), 6)
        for pts in current_sets:
            bx, by = pts[min(drawn_count, len(pts) - 1)]
            screen.blit(brush, (int(bx) - 20, int(by) - 20))

    # 提示文字
    font = pygame.font.SysFont(None, 30)
    tip = {"draw_heart": "画笔绘制爱心…",
           "hold_heart": "爱心成形，即将绽放…",
           "bloom_heart": "爱心绽放 ✿",
           "draw_rose": "画笔绘制6朵玫瑰…",
           "hold_rose": "玫瑰成形，即将绽放…",
           "bloom_rose": "玫瑰绽放 ✿",
           "firework": "烟花表演 ✨",
           "poem_wait": "",
           "poem": ""}[state]
    screen.blit(font.render(tip, True, (220, 200, 220)), (30, 30))

    pygame.display.flip()
