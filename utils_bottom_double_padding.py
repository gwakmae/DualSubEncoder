# utils_bottom_double_padding.py
# 하단 이중 패딩(영상 아래 영어 패딩, 그 아래 한글 패딩) 전용 유틸
# ASS 스타일 Alignment=8(Top-Center) 기준으로 pos(x, y)의 y는 "문자 상단"입니다.

import re

def escape_path(path: str) -> str:
    """
    FFmpeg 필터에서 경로가 정상 인식되도록
    백슬래시, 콜론, 작은따옴표 등을 이스케이프 처리
    """
    return path.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")

def adjust_font_size_and_position(text: str, width: int, height: int,
                                  eng_pad: int = 180, kor_pad: int = 180,
                                  max_font_size: int = 72,
                                  min_font_size: int = 48,
                                  max_chars: int = 80,
                                  is_english: bool = True):
    """
    하단 이중 패딩 모드에서 자막 폰트 크기 및 위치 계산
    - 최종 캔버스 높이 = height + eng_pad + kor_pad
    - 스타일 Alignment=8(Top-Center) 가정: pos(x, y)의 y는 '문자 상단'
    - 영어: 영상 바로 아래 첫 번째 하단 패딩의 윗쪽에 가깝게 배치
    - 한글: 그 아래 두 번째 하단 패딩의 윗쪽에 가깝게 배치
    """

    # 1) 텍스트 전처리 및 폰트 크기 산정 (기존 로직과 유사하되 min 보장)
    text_processed = re.sub(r"{.*?}", "", text).replace('\n', ' ')
    char_count = len(text_processed)

    if char_count <= 20:
        font_size = max_font_size
    elif char_count <= 40:
        font_size = int(max_font_size * 0.9)
    elif char_count <= 60:
        font_size = int(max_font_size * 0.8)
    elif char_count <= max_chars:
        font_size = int(max_font_size * 0.7)
    else:
        font_size = min_font_size

    font_size = max(font_size, min_font_size)

    # 2) 위치 계산
    # Alignment=8 기준 pos(x,y)에서 x는 중앙, y는 '문자 상단' 좌표
    position_x = width // 2

    # 패딩 밴드 상단으로부터 약간 내려서 시작시키면
    # (a) 영상/밴드 경계에 너무 붙지 않고
    # (b) 글자가 밴드 밖으로 나가지 않음
    #
    # 경험적 권장값:
    # - 밴드 상단에서 약 20% 지점에 "문자 상단"을 놓음.
    #   pad * 0.2 ≈ 36px (pad=180 기준)
    # - 최소 24px 안전 여백 보장
    top_margin_ratio = 0.20
    min_top_margin_px = 24

    if is_english:
        band_top = height                   # 영어 밴드 시작 (영상 바로 아래)
        pad = eng_pad
    else:
        band_top = height + eng_pad         # 한글 밴드 시작 (영어 밴드 아래)
        pad = kor_pad

    top_offset = max(min_top_margin_px, int(pad * top_margin_ratio))
    position_y = band_top + top_offset

    return font_size, position_x, position_y
