# my_video_app/utils.py

import re

def escape_path(path: str) -> str:
    """
    FFmpeg 필터에서 경로가 정상 인식되도록
    백슬래시, 콜론, 작은따옴표 등을 이스케이프 처리
    """
    return path.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")

def adjust_font_size_and_position(text: str, width: int, height: int,
                                  pad_top=0, pad_bottom=0,
                                  # 사용자님이 처음에 잘 작동했다고 하셨던 값으로 복구 (Full HD 기준)
                                  max_font_size=72,
                                  min_font_size=48,
                                  max_chars=80,
                                  is_english=True):
    """
    자막 문자열 길이에 따라 폰트 크기 및 화면 위치를 계산 (줄바꿈 제거 후 한 줄로 처리 시도)
    모든 영상이 목표 해상도(예: Full HD)로 업스케일링된 후 적용됩니다.
    """
    text_processed = re.sub(r"{.*?}", "", text).replace('\n', ' ')
    char_count = len(text_processed)

    # 폰트 크기 계산 로직 (초기 로직 유지)
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

    # 폰트 크기가 min_font_size보다 작아지지 않도록 보장
    font_size = max(font_size, min_font_size)

    position_x = width // 2

    # Y 위치 (Alignment 8: Top Center에 맞춰 조정, Full HD 기준)
    if is_english:
        # 영어 자막 위치 (상단에서 적당히 내려옴)
        position_y = int(height * 0.07) # Full HD 상단 10% 위치
    else:
        # 한글 자막 위치 (하단에서 충분히 위로 올림)
        position_y = int(height * 0.87) # Full HD 하단 20% 지점에 상단이 오도록

    return font_size, position_x, position_y