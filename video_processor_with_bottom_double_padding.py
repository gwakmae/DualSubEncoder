import os
import re
import subprocess
import platform
import pysrt

from utils_bottom_double_padding import escape_path, adjust_font_size_and_position

class VideoProcessor:
    def __init__(self, use_upscaling, target_width, target_height):
        self.use_upscaling = use_upscaling
        self.target_width = target_width
        self.target_height = target_height

    def process_single_video(self, input_path, korean_srt_path, english_srt_path):
        video_name = os.path.basename(input_path)
        video_name_no_ext = os.path.splitext(video_name)[0]
        temp_upscaled_path = ""
        temp_ass_path = ""

        try:
            output_path = self.get_output_path(input_path)

            if not korean_srt_path and not english_srt_path:
                warning_msg = f"{video_name}: 최소 하나의 SRT 자막 파일이 선택되지 않았습니다. 스킵합니다."
                return ("Warning", warning_msg)

            original_width, original_height = self.get_video_resolution(input_path)
            if not original_width or not original_height:
                error_msg = f"{video_name}: 원본 비디오 해상도 가져오기 실패"
                return ("Error", error_msg)

            current_video_path_for_processing = input_path
            final_video_width = original_width
            final_video_height = original_height

            # 업스케일링
            if self.use_upscaling and (original_width != self.target_width or original_height != self.target_height):
                temp_upscaled_path = os.path.join(os.path.dirname(input_path), video_name_no_ext + "_upscaled_temp.mp4")
                print(f"원본 해상도 ({original_width}x{original_height})가 목표 해상도 ({self.target_width}x{self.target_height})와 다릅니다. 업스케일링을 시작합니다.")

                upscale_result, upscale_error = self.run_upscaling(input_path, temp_upscaled_path, self.target_width, self.target_height)
                if not upscale_result:
                    error_msg = f"{video_name}: 비디오 업스케일링 실패.\n{upscale_error}"
                    return ("Error", error_msg)

                current_video_path_for_processing = temp_upscaled_path
                final_video_width = self.target_width
                final_video_height = self.target_height
                print(f"업스케일링 완료: {current_video_path_for_processing}")
            else:
                print("업스케일링 옵션 비활성화 또는 원본 해상도가 목표 해상도와 일치. 업스케일링 건너뜀.")

            # 임시 ASS 파일
            temp_ass_path = os.path.join(os.path.dirname(input_path), video_name_no_ext + "_merged_temp.ass")

            # 하단 이중 패딩 값
            eng_pad = 180
            kor_pad = 180
            pad_top = 0
            pad_bottom_total = eng_pad + kor_pad

            if not self.generate_merged_ass(
                english_srt_path, korean_srt_path, temp_ass_path,
                final_video_width, final_video_height,
                eng_pad, kor_pad
            ):
                error_msg = f"{video_name}: ASS 파일 병합 실패."
                return ("Error", error_msg)

            # FFmpeg 필터: 원본 + 하단(영어+한글) 패딩 후 ASS 적용
            escaped_ass = escape_path(temp_ass_path)
            final_display_height = final_video_height + pad_bottom_total
            vf_filter = f"pad=iw:{final_display_height}:0:{pad_top}:black,ass='{escaped_ass}'"

            # 인코더
            encoder = self.get_encoder()
            print(f"선택된 인코더: {encoder}")

            ffmpeg_result, ffmpeg_error = self.run_ffmpeg(current_video_path_for_processing, output_path, vf_filter)

            # 임시 파일 정리
            if current_video_path_for_processing != input_path and os.path.exists(current_video_path_for_processing):
                try:
                    os.remove(current_video_path_for_processing)
                    print(f"임시 업스케일링 파일 삭제: {current_video_path_for_processing}")
                except Exception as e:
                    print(f"임시 파일 삭제 실패 {current_video_path_for_processing}: {e}")
            if os.path.exists(temp_ass_path):
                try:
                    os.remove(temp_ass_path)
                    print(f"임시 ASS 파일 삭제: {temp_ass_path}")
                except Exception as e:
                    print(f"임시 ASS 파일 삭제 실패 {temp_ass_path}: {e}")

            if ffmpeg_result and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                success_msg = f"{video_name}: 성공적으로 처리되었습니다. 인코더: {encoder} 최종 해상도: {final_video_width}:{final_display_height}"
                return ("Success", success_msg)
            else:
                error_msg = f"{video_name}: FFmpeg 처리 실패 (인코더: {encoder}).\n{ffmpeg_error}"
                return ("Error", error_msg)

        except Exception as e:
            error_msg = f"{video_name}: 예기치 않은 오류 발생 - {e}"
            return ("Error", error_msg)

    def get_output_path(self, input_path):
        base, ext = os.path.splitext(input_path)
        return f"{base}_with_bottompadding{ext}"

    def get_video_resolution(self, input_path):
        try:
            ffprobe_command = [
                "ffprobe", "-v", "error", "-select_streams", "v:0",
                "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", input_path
            ]
            result = subprocess.run(ffprobe_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            if result.returncode != 0:
                raise Exception(result.stderr)
            width, height = map(int, result.stdout.strip().split('x'))
            return width, height
        except Exception as e:
            print(f"Error getting video resolution for {input_path}: {e}")
            return None, None

    def run_upscaling(self, input_path, output_path, target_width, target_height):
        try:
            if os.path.exists(output_path):
                os.remove(output_path)

            threads = os.cpu_count() or 4
            encoder = self.get_encoder()
            scale_filter = (
                f"scale='min({target_width},iw*min({target_height}/ih,{target_width}/iw)):"
                f"min({target_height},ih*min({target_height}/ih,{target_width}/iw))',"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black"
            )

            ffmpeg_command = [
                'ffmpeg', '-i', input_path, '-vf', scale_filter,
                '-c:v', encoder, '-crf', '0', '-preset', 'fast',
                '-c:a', 'copy', '-threads', str(threads), '-y', output_path
            ]
            print(f"실행할 FFmpeg 업스케일링 명령어: {' '.join(ffmpeg_command)}")

            process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
            upscale_output = []
            for line in process.stdout:
                upscale_output.append(line)
                print(line.strip())
            process.wait()

            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True, ""
            else:
                return False, ''.join(upscale_output)

        except FileNotFoundError:
            return False, "FFmpeg가 설치되어 있지 않거나, 환경 변수로 등록되지 않았습니다."
        except Exception as e:
            return False, f"비디오 업스케일링 중 오류: {e}"

    def generate_merged_ass(self, english_srt, korean_srt, merged_ass, width, height, eng_pad=180, kor_pad=180):
        try:
            total_height = height + eng_pad + kor_pad

            with open(merged_ass, 'w', encoding='utf-8') as f:
                # [Script Info]
                f.write("[Script Info]\n")
                f.write("ScriptType: v4.00+\n")
                f.write(f"PlayResX: {width}\n")
                f.write(f"PlayResY: {total_height}\n")
                f.write("ScaledBorderAndShadow: yes\n\n")

                # [V4+ Styles]
                f.write("[V4+ Styles]\n")
                f.write("Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
                        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, "
                        "Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n")
                # Alignment 8: Top Center
                f.write("Style: Korean,NanumGothic,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,8,10,10,10,1\n")
                f.write("Style: English,Arial,72,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,3,0,8,10,10,10,1\n")
                f.write("\n")

                # [Events]
                f.write("[Events]\n")
                f.write("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")

                if english_srt:
                    eng_subs = pysrt.open(english_srt, encoding='utf-8-sig')
                    for sub in eng_subs:
                        start = sub.start.to_time().strftime("%H:%M:%S.%f")[:-4]
                        end = sub.end.to_time().strftime("%H:%M:%S.%f")[:-4]
                        text = sub.text.replace('\n', ' ')
                        font_size, pos_x, pos_y = adjust_font_size_and_position(
                            text, width, height, eng_pad, kor_pad, is_english=True
                        )
                        f.write(f"Dialogue: 0,{start},{end},English,,0,0,0,,{{\\fs{font_size}}}{{\\pos({pos_x},{pos_y})}}{text}\n")

                if korean_srt:
                    kor_subs = pysrt.open(korean_srt, encoding='utf-8-sig')
                    for sub in kor_subs:
                        start = sub.start.to_time().strftime("%H:%M:%S.%f")[:-4]
                        end = sub.end.to_time().strftime("%H:%M:%S.%f")[:-4]
                        text = sub.text.replace('\n', ' ')
                        font_size, pos_x, pos_y = adjust_font_size_and_position(
                            text, width, height, eng_pad, kor_pad, is_english=False
                        )
                        f.write(f"Dialogue: 0,{start},{end},Korean,,0,0,0,,{{\\fs{font_size}}}{{\\pos({pos_x},{pos_y})}}{text}\n")

            return True

        except Exception as e:
            print(f"Error in generate_merged_ass: {e}")
            return False

    def run_ffmpeg(self, input_path, output_path, vf_filter):
        try:
            if os.path.exists(output_path):
                print(f"기존 출력 파일 삭제: {output_path}")
                os.remove(output_path)

            encoder = self.get_encoder()
            threads = os.cpu_count() or 4

            ffmpeg_command = ['ffmpeg', '-i', input_path, '-vf', vf_filter,
                              '-c:v', encoder, '-crf', '0', '-preset', 'fast',
                              '-c:a', 'copy', '-threads', str(threads), '-y', output_path]

            print(f"실행할 FFmpeg 명령어: {' '.join(ffmpeg_command)}")

            process = subprocess.Popen(ffmpeg_command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding='utf-8')

            ffmpeg_output = []
            for line in process.stdout:
                ffmpeg_output.append(line)
                print(line.strip())

            process.wait()

            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                if os.path.getsize(output_path) < 10240:
                    return False, "출력 파일이 너무 작습니다. 인코딩이 제대로 되지 않았을 수 있습니다."
                return True, ""
            else:
                return False, ''.join(ffmpeg_output)

        except FileNotFoundError:
            error_msg = "FFmpeg가 설치되어 있지 않거나, 환경 변수로 등록되지 않았습니다."
            return False, error_msg
        except Exception as e:
            error_msg = f"FFmpeg 처리 중 오류: {e}"
            return False, error_msg

    def detect_nvidia_gpu(self):
        try:
            result = subprocess.run(['ffmpeg', '-encoders'], capture_output=True, text=True, check=False, encoding='utf-8')
            if 'h264_nvenc' in result.stdout:
                print("NVIDIA NVENC 인코더 감지됨")
                return True

            if platform.system() == 'Windows':
                result = subprocess.run(['wmic', 'path', 'win32_VideoController', 'get', 'name'],
                                        capture_output=True, text=True, check=False, encoding='cp949')
                if 'NVIDIA' in result.stdout:
                    print("NVIDIA GPU 감지됨 (Windows)")
                    return True
            elif platform.system() == 'Linux':
                result = subprocess.run(['lspci'], capture_output=True, text=True, check=False, encoding='utf-8')
                if 'NVIDIA' in result.stdout:
                    print("NVIDIA GPU 감지됨 (Linux)")
                    return True
            print("NVIDIA GPU 감지되지 않음")
            return False
        except Exception as e:
            print(f"GPU 감지 중 오류 발생: {e}")
            return False

    def detect_cpu_vendor(self):
        processor_info = platform.processor()
        if processor_info:
            if 'Intel' in processor_info or 'GenuineIntel' in processor_info:
                return 'Intel'
            elif 'AMD' in processor_info or 'AuthenticAMD' in processor_info:
                return 'AMD'

        if platform.system() == 'Windows':
            try:
                result = subprocess.run(['wmic', 'cpu', 'get', 'Name'],
                                        capture_output=True, text=True, check=False, encoding='cp949')
                if result.returncode == 0:
                    output = result.stdout.strip()
                    if 'Intel' in output: return 'Intel'
                    if 'AMD' in output: return 'AMD'
            except Exception as e:
                print(f"Windows CPU WMIC 감지 오류: {e}")
        if platform.system() == 'Linux':
            try:
                with open('/proc/cpuinfo', 'r') as f:
                    cpuinfo = f.read()
                    if 'GenuineIntel' in cpuinfo:
                        return 'Intel'
                    elif 'AuthenticAMD' in cpuinfo:
                        return 'AMD'
            except:
                pass
        return 'Unknown'

    def get_encoder(self):
        if self.detect_nvidia_gpu():
            return 'h264_nvenc'
        cpu_vendor = self.detect_cpu_vendor()
        os_system = platform.system()
        if cpu_vendor == 'Intel':
            if os_system == 'Windows':
                return 'h264_qsv'
            elif os_system == 'Linux':
                return 'h264_vaapi'
            else:
                return 'libx264'
        elif cpu_vendor == 'AMD':
            if os_system == 'Windows':
                return 'h264_amf'
            elif os_system == 'Linux':
                return 'h264_vaapi'
            else:
                return 'libx264'
        else:
            return 'libx264'
