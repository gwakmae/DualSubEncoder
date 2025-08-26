# subtitle_checker.py
import os
from srt_overlap_error import check_srt_overlap

def check_subtitle_files(video_subtitle_pairs):
    """
    선택된 자막 파일들의 오류를 검사합니다.

    Args:
        video_subtitle_pairs:  [(video_file, korean_sub, english_sub), ...] 형태의 리스트

    Returns:
        tuple | None: 오류가 있으면 (오류 파일 경로, 오류 메시지 리스트) 튜플 반환, 없으면 None
    """
    for video, kor, eng in video_subtitle_pairs:
        if kor:
            errors = check_srt_overlap(kor)
            if errors:
                return kor, errors
        if eng:
            errors = check_srt_overlap(eng)
            if errors:
                return eng, errors
    return None