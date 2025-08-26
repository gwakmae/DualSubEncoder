import re
import os

# 사용자 정의 예외 클래스 추가
class SevereOverlapError(Exception):
    """심각한 자막 겹침 오류를 위한 사용자 정의 예외"""
    pass

# --- 새로운 자막 수정 함수 (pysrt 라이브러리를 사용하지 않음) ---

def time_str_to_ms(time_str):
    """'HH:MM:SS,ms' 형식의 시간 문자열을 밀리초(ms)로 변환합니다."""
    try:
        h, m, s_ms = time_str.split(':')
        s, ms = s_ms.split(',')
        return int(h) * 3600000 + int(m) * 60000 + int(s) * 1000 + int(ms)
    except ValueError:
        return 0

def ms_to_time_str(ms):
    """밀리초(ms)를 'HH:MM:SS,ms' 형식의 시간 문자열로 변환합니다."""
    if ms < 0: ms = 0
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

def fix_srt_overlaps_and_save(srt_path):
    """
    pysrt 라이브러리를 사용하지 않고 SRT 파일의 시간 겹침을 수정하고,
    인코딩 문제를 해결하여 새 파일로 저장합니다.
    """
    try:
        with open(srt_path, 'r', encoding='utf-8-sig') as f:
            content = f.read()
    except Exception as e:
        raise IOError(f"'{os.path.basename(srt_path)}' 파일을 읽는 중 오류 발생: {e}")

    blocks = content.strip().split('\n\n')
    parsed_subs = []
    time_pattern = re.compile(r'(\d{1,2}:\d{2}:\d{2},\d{1,3})\s*-->\s*(\d{1,2}:\d{2}:\d{2},\d{1,3})')

    for block_num, block in enumerate(blocks):
        lines = block.split('\n')
        if len(lines) < 2: continue
        
        index_line = lines[0]
        time_line = ""
        text_lines_start_index = -1

        for i, line in enumerate(lines):
            if '-->' in line:
                time_line = line
                text_lines_start_index = i + 1
                break
        
        if not time_line or text_lines_start_index == -1: continue
        
        text_lines = lines[text_lines_start_index:]
        match = time_pattern.match(time_line)
        if not match: continue
            
        start_str, end_str = match.groups()
        parsed_subs.append({
            'original_index': index_line.strip(),
            'start_ms': time_str_to_ms(start_str),
            'end_ms': time_str_to_ms(end_str),
            'text': '\n'.join(text_lines)
        })

    # 1. 바로 다음 자막과의 겹침 우선 수정 (기존 로직)
    fixed_count = 0
    for i in range(len(parsed_subs) - 1):
        current_sub = parsed_subs[i]
        next_sub = parsed_subs[i+1]
        
        if current_sub['end_ms'] > next_sub['start_ms']:
            current_sub['end_ms'] = next_sub['start_ms']
            fixed_count += 1
            
    # 2. 심각한 겹침 오류 검사 (새로운 로직)
    #    수정된 데이터를 기반으로, 현재 자막의 종료시간이 다음 자막의 종료시간보다도 늦는지 확인
    for i in range(len(parsed_subs) - 1):
        current_sub = parsed_subs[i]
        next_sub = parsed_subs[i+1]
        
        if current_sub['end_ms'] > next_sub['end_ms']:
            # 오류 발생 시, 프로그램을 멈추고 상세 정보를 담은 예외를 발생시킴
            error_msg = (
                f"심각한 자막 겹침 오류가 '{os.path.basename(srt_path)}' 파일에서 발견되어 작업을 중단합니다.\n\n"
                f"▶ 문제 자막: {current_sub['original_index']}번\n"
                f"   시간: {ms_to_time_str(current_sub['start_ms'])} --> {ms_to_time_str(current_sub['end_ms'])}\n\n"
                f"이 자막의 종료 시간이 다음 자막({next_sub['original_index']}번)의 종료 시간보다 늦습니다.\n"
                f"SRT 파일을 직접 열어 해당 자막의 종료 시간을 수정해주세요."
            )
            raise SevereOverlapError(error_msg)

    # 모든 검사를 통과한 경우에만 파일 저장
    base, ext = os.path.splitext(srt_path)
    output_path = f"{base}.fixed{ext}"
    
    try:
        with open(output_path, 'w', encoding='utf-8-sig') as f:
            for i, sub in enumerate(parsed_subs):
                start_str = ms_to_time_str(sub['start_ms'])
                end_str = ms_to_time_str(sub['end_ms'])
                
                f.write(f"{sub['original_index']}\n") # 원본 인덱스 유지
                f.write(f"{start_str} --> {end_str}\n")
                f.write(f"{sub['text']}\n\n")
        
        if fixed_count > 0:
            print(f"INFO: '{os.path.basename(srt_path)}'의 겹침/인코딩 문제를 수정하여 '{os.path.basename(output_path)}'로 저장했습니다.")
        else:
            print(f"INFO: '{os.path.basename(srt_path)}'의 인코딩 문제를 처리하여 '{os.path.basename(output_path)}'로 저장했습니다.")
        return output_path
    except Exception as e:
        raise IOError(f"수정된 자막 파일 저장 중 오류 발생: {e}")


def check_srt_overlap(srt_file):
    # 이 함수는 변경할 필요 없습니다.
    # ... (기존 코드와 동일) ...
    try:
        with open(srt_file, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
    except FileNotFoundError:
        return [f"오류: '{srt_file}' 파일을 찾을 수 없습니다."]
    except Exception as e:
        return [f"오류: 파일을 읽는 중 오류가 발생했습니다: {e}"]

    entries = []
    current_entry = {}
    errors = []
    line_num = 0

    for line in lines:
        line_num += 1
        line = line.strip()
        if not line:
            if current_entry:
                entries.append(current_entry)
            current_entry = {}
            continue

        if '-->' in line:
            current_entry['time'] = line
            match = re.match(r'(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)', line)
            if match:
                current_entry['start'] = match.group(1)
                current_entry['end'] = match.group(2)
            else:
                errors.append(f"경고: {line_num}번 줄의 시간 형식이 잘못되었습니다: {line}")
                continue

        elif line.isdigit() and 'index' not in current_entry:
            if 'index' in current_entry:
                entries.append(current_entry)
                current_entry = {}
            current_entry['index'] = int(line)

        else:
            if 'text' in current_entry:
                current_entry['text'] += '\n' + line
            else:
                current_entry['text'] = line

    if current_entry:
        entries.append(current_entry)

    def time_to_milliseconds(time_str):
        hours, minutes, seconds_ms = time_str.split(':')
        seconds, milliseconds = seconds_ms.split(',')
        total_milliseconds = (int(hours) * 3600 + int(minutes) * 60 + int(seconds)) * 1000 + int(milliseconds)
        return total_milliseconds

    for i in range(len(entries) - 1):
        try:
            if 'end' not in entries[i] or 'start' not in entries[i+1]:
                errors.append(f"경고: 자막 {entries[i].get('index', i)}의 시간 정보가 불완전합니다.")
                continue

            current_end_time = time_to_milliseconds(entries[i]['end'])
            next_start_time = time_to_milliseconds(entries[i + 1]['start'])

            if current_end_time > next_start_time:
                errors.append(
                    f"경고: 자막 {entries[i].get('index', i)} ({entries[i].get('time', '시간 정보 없음')})이(가) "
                    f"다음 자막 {entries[i + 1].get('index', i+1)} ({entries[i + 1].get('time', '시간 정보 없음')})과(와) 겹칩니다.\n"
                    f"     {entries[i].get('index', i)} 종료: {entries[i].get('end', '종료 시간 없음')},  {entries[i + 1].get('index', i+1)} 시작: {entries[i + 1].get('start', '시작 시간 없음')}"
                )
        except (ValueError, KeyError) as e:
            errors.append(f"경고: 자막 {entries[i].get('index', i)} 시간 처리 중 오류 발생: {e}")
            continue

    return errors