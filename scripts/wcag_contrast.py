import math

def hex_to_rgb(h):
    h = h.lstrip('#')
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))

def srgb_to_linear(c):
    s = c / 255.0
    return s / 12.92 if s <= 0.04045 else math.pow((s + 0.055) / 1.055, 2.4)

def relative_luminance(hex_color):
    r, g, b = hex_to_rgb(hex_color)
    return 0.2126 * srgb_to_linear(r) + 0.7152 * srgb_to_linear(g) + 0.0722 * srgb_to_linear(b)

def cr(hex1, hex2):
    L1 = relative_luminance(hex1)
    L2 = relative_luminance(hex2)
    return (max(L1, L2) + 0.05) / (min(L1, L2) + 0.05)

pairs = [
    ('Sage on Cream', '#7B9E8B', '#FAFAF5'),
    ('Fern on Cream', '#4A6B5A', '#FAFAF5'),
    ('Clay on Cream', '#B87355', '#FAFAF5'),
    ('White on Fern', '#FFFFFF', '#4A6B5A'),
    ('White on Clay', '#FFFFFF', '#B87355'),
    ('Sand on Cream', '#C4A87A', '#FAFAF5'),
    ('WarmGray on Cream', '#7A7168', '#FAFAF5'),
    ('TextPrimary on Cream', '#3D3730', '#FAFAF5'),
    ('TextStrong on Cream', '#1E1A16', '#FAFAF5'),
    ('Sage on DarkBG', '#7B9E8B', '#1A1714'),
    ('Sand on DarkBG', '#C4A87A', '#1A1714'),
    ('Clay on DarkBG', '#B87355', '#1A1714'),
    ('Moss on Cream', '#9BAB82', '#FAFAF5'),
    ('Moss on DarkBG', '#9BAB82', '#1A1714'),
    ('RoseDusk on Cream', '#C49AAE', '#FAFAF5'),
    ('Amber on Cream', '#D4935A', '#FAFAF5'),
    ('TextPrimary DarkMode', '#D4C8B8', '#1A1714'),
    ('TextStrong DarkMode', '#F2EDE4', '#1A1714'),
    ('TextSecondary DarkMode', '#9A8E84', '#1A1714'),
    ('Sage on ThrivingBG Dark', '#7B9E8B', '#1E2D27'),
    ('Sand on WatchBG Dark', '#C4A87A', '#2A2418'),
    ('Clay on ConcernBG Dark', '#B87355', '#2A1F18'),
    ('Sage on ThrivingBG Light', '#7B9E8B', '#EDF4F0'),
    ('Sand on WatchBG Light', '#C4A87A', '#F7F2EA'),
    ('Clay on ConcernBG Light', '#B87355', '#F5EDEA'),
    ('WarmGray on Parchment', '#7A7168', '#F2EDE4'),
    ('Fern on White', '#4A6B5A', '#FFFFFF'),
]
for label, fg, bg in pairs:
    r = cr(fg, bg)
    an = 'PASS' if r >= 4.5 else 'FAIL'
    al = 'PASS' if r >= 3.0 else 'FAIL'
    aaa = 'PASS' if r >= 7.0 else 'FAIL'
    print(f'{label:<32} {r:>6.2f}:1  AA-norm:{an}  AA-lg:{al}  AAA:{aaa}')
print()
print(f'Moss vs Sage distinguishability: {cr("#9BAB82", "#7B9E8B"):.2f}:1')
print(f'Sand vs SandMid: {cr("#C4A87A", "#C4B8AA"):.2f}:1')
