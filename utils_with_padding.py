# my_video_app/utils_with_padding.py

import re

def escape_path(path: str) -> str:
    """
    FFmpeg 필터에서 경로가 정상 인식되도록
    백슬래시, 콜론 등을 이스케이프 처리
    """
    return path.replace('\\', '\\\\').replace(':', '\\:').replace("'", "\\'")

def adjust_font_size_and_position(text: str, width: int, height: int,
                                  pad_top=180, pad_bottom=180, 
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
        
    font_size = max(font_size, min_font_size)

    total_height = height + pad_top + pad_bottom # height는 이제 1080
    position_x = width // 2 # width는 이제 1920

    # Y 위치 (Alignment 8: Top Center에 맞춰 조정)
    if is_english:
        # 상단 패딩 영역의 상단에 위치
        position_y = pad_top // 2 
    else:
        # 하단 패딩 영역의 상단에 위치
        position_y = height + pad_top + (pad_bottom // 2) - 60
    
    return font_size, position_x, position_y