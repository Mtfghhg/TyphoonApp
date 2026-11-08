import os

app_root = os.environ.get("APP_ROOT")
if not app_root:
    print("找不到 APP_ROOT 环境变量")
    exit(1)

mobile_main_code = """
import os
os.environ['SDL_VIDEODRIVER'] = 'dummy'
os.environ['SDL_AUDIODRIVER'] = 'dummy'
import pygame, sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
pygame.init()
try:
    import py.constants as constants
    from py.ty_sim import TySim
    infoObject = pygame.display.Info()
    sw, sh = infoObject.current_w, infoObject.current_h
    if sw == 0: sw, sh = 1920, 1080
    constants.SW, constants.SH = sw, sh
    constants.MH = constants.SH - constants.CPH
    screen = pygame.display.set_mode((sw, sh))
    sim = TySim(screen)
    clock = pygame.time.Clock()
    running = True
    while running:
        dt = clock.tick(30) / 1000.0
        for event in pygame.event.get():
            if event.type == pygame.QUIT: running = False
            elif event.type == pygame.FINGERDOWN:
                mouse_event = pygame.event.Event(pygame.MOUSEBUTTONDOWN, {'pos': (event.x * sw, event.y * sh), 'button': 1})
                sim.handle_event(mouse_event)
            elif event.type == pygame.FINGERUP:
                mouse_event = pygame.event.Event(pygame.MOUSEBUTTONUP, {'pos': (event.x * sw, event.y * sh), 'button': 1})
                sim.handle_event(mouse_event)
            else:
                sim.handle_event(event)
        sim.update(dt)
        sim.draw(screen)
        pygame.display.flip()
    pygame.quit()
    os._exit(0)
except Exception as e:
    print(f"崩溃原因: {e}")
"""

target_file = os.path.join(app_root, "main.py")
with open(target_file, "w", encoding="utf-8") as f:
    f.write(mobile_main_code)
print(f"成功覆写文件: {target_file}")
