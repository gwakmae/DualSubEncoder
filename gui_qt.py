# gui_qt.py
import os
import sys
import threading
from PyQt6.QtWidgets import (
    QApplication, QWidget, QPushButton, QListWidget, QCheckBox, QProgressBar,
    QLabel, QMessageBox, QGridLayout, QVBoxLayout, QDialog, QTextEdit, QLineEdit, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject

import tkinter as tk
import re
from tkinter import filedialog
from srt_overlap_error import fix_srt_overlaps_and_save, SevereOverlapError

# VideoProcessorManager import
from video_processor_manager import VideoProcessorManager

# subtitle_checker.py의 함수를 사용
from subtitle_checker import check_subtitle_files


# Helper class for thread signals
class WorkerSignals(QObject):
    progress = pyqtSignal(int)
    status = pyqtSignal(str)
    finished = pyqtSignal(list)
    error = pyqtSignal(str)  # Signal for general errors during processing


class VideoProcessingApp(QWidget):
    # --- Signals for thread communication ---
    # These signals are defined outside __init__ as class attributes
    progress_updated = pyqtSignal(int)
    status_updated = pyqtSignal(str)
    processing_finished = pyqtSignal(list)
    # -----------------------------------------

    def __init__(self):
        super().__init__()
        self.setWindowTitle("FFmpeg 다중 영상 처리 도구 (QuickSync/VCE 지원) - PyQt6")
        self.setGeometry(100, 100, 750, 600)

        self.video_subtitle_pairs = []
        self.results = []
        self.processor = None  # Initialize processor attribute
        self.processing_thread = None  # To keep track of the thread

        self.initUI()

        # Connect signals to slots (methods)
        self.progress_updated.connect(self.update_progress_bar)
        self.status_updated.connect(self.update_status_label)
        self.processing_finished.connect(self.show_final_results_qt)

    def rename_file_if_needed(self, file_path):
        """파일 경로를 받아와서 파일명에 허용되지 않는 문자가 있으면 수정하고, 파일명을 변경합니다."""
        if not file_path or not os.path.exists(file_path):
            return file_path

        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        name, ext = os.path.splitext(base_name)

        # 허용 문자: 한글, 영어, 숫자, 공백, 하이픈(-), 언더스코어(_), 마침표(.)
        # re.sub를 사용하여 허용되지 않는 모든 문자를 빈 문자열('')로 대체
        safe_name = re.sub(r'[^a-zA-Z0-9가-힣\s\._-]', '', name)
        safe_name = safe_name.strip()  # 앞뒤 공백 제거

        if not safe_name:  # 이름이 모두 제거된 경우
            safe_name = "renamed_file"

        if name != safe_name:
            new_base_name = safe_name + ext
            new_file_path = os.path.join(dir_name, new_base_name)

            if os.path.exists(new_file_path):
                # 이미 파일이 존재하면 이름 뒤에 숫자를 붙여 중복을 피합니다.
                i = 1
                while True:
                    temp_name = f"{safe_name}_{i}{ext}"
                    new_file_path = os.path.join(dir_name, temp_name)
                    if not os.path.exists(new_file_path):
                        break
                    i += 1

            try:
                os.rename(file_path, new_file_path)
                print(f"파일명 변경: '{base_name}' -> '{os.path.basename(new_file_path)}'")
                return new_file_path
            except OSError as e:
                QMessageBox.critical(self, "파일명 변경 오류", f"'{base_name}'의 파일명 변경에 실패했습니다:\n{e}")
                return file_path  # 실패 시 원본 경로 반환

        return file_path  # 변경이 필요 없는 경우 원본 경로 반환

    def initUI(self):
        layout = QGridLayout(self)

        # --- Row 0: File Selection ---
        self.select_files_button = QPushButton("비디오 및 자막 파일 선택")
        self.select_files_button.clicked.connect(self.select_files)
        layout.addWidget(self.select_files_button, 0, 0, 1, 3)  # Span 3 columns

        self.file_listbox = QListWidget()
        self.file_listbox.setMinimumHeight(150)
        layout.addWidget(self.file_listbox, 1, 0, 1, 3)  # Span 3 columns

        # --- Row 2: Padding Option ---
        self.padding_checkbox = QCheckBox("자막 패딩 추가 (상하단 검은색 여백)")
        self.padding_checkbox.setChecked(False)  # Default is False
        self.padding_checkbox.stateChanged.connect(self.on_padding_checkbox_changed)
        layout.addWidget(self.padding_checkbox, 2, 0, 1, 3)

        # --- Row 3: Padding Mode (NEW) ---
        self.padding_mode_label = QLabel("패딩 모드:")
        self.padding_mode_combo = QComboBox()
        self.padding_mode_combo.addItems([
            "상하단 패딩 (영어=위, 한글=아래)",
            "하단 이중 패딩 (영어패딩 → 한글패딩)"
        ])
        self.padding_mode_label.setEnabled(False)
        self.padding_mode_combo.setEnabled(False)
        layout.addWidget(self.padding_mode_label, 3, 0, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addWidget(self.padding_mode_combo, 3, 1, 1, 2)

        # --- Row 4: Subtitle Overlap Fix Option ---
        self.fix_overlap_checkbox = QCheckBox("자막 시간 겹침 자동 수정")
        self.fix_overlap_checkbox.setChecked(True)  # 기본값으로 활성화
        layout.addWidget(self.fix_overlap_checkbox, 4, 0, 1, 3)

        # --- Row 5: Upscaling Options ---
        self.upscale_checkbox = QCheckBox("자동 업스케일링 (권장, 낮은 해상도 영상에 효과적)")
        self.upscale_checkbox.setChecked(True)  # 기본적으로 업스케일링 활성화
        self.upscale_checkbox.stateChanged.connect(self.toggle_resolution_input)
        layout.addWidget(self.upscale_checkbox, 5, 0)

        self.target_resolution_label = QLabel("목표 해상도 (WxH):")
        layout.addWidget(self.target_resolution_label, 5, 1, alignment=Qt.AlignmentFlag.AlignRight)

        self.target_resolution_input = QLineEdit("1920x1080")  # 기본 목표 해상도
        self.target_resolution_input.setFixedWidth(100)  # 가로 길이 고정
        layout.addWidget(self.target_resolution_input, 5, 2, alignment=Qt.AlignmentFlag.AlignLeft)

        # --- Row 6: Start Button ---
        self.start_button = QPushButton("처리 시작")
        self.start_button.clicked.connect(self.start_processing)
        layout.addWidget(self.start_button, 6, 0, 1, 3)  # Span 3 columns

        # --- Row 7: Progress Bar ---
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        layout.addWidget(self.progress_bar, 7, 0, 1, 3)  # Span 3 columns

        # --- Row 8: Status Label ---
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label, 8, 0, 1, 3)  # Span 3 columns

        # Adjust column stretch factors for better resizing
        layout.setColumnStretch(0, 2)
        layout.setColumnStretch(1, 1)
        layout.setColumnStretch(2, 1)  # New column for resolution input

        self.setLayout(layout)
        self.toggle_resolution_input(self.upscale_checkbox.checkState().value)  # 초기 상태 설정
        self.on_padding_checkbox_changed(self.padding_checkbox.checkState().value)  # 초기 상태 설정

    def on_padding_checkbox_changed(self, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        self.padding_mode_label.setEnabled(is_checked)
        self.padding_mode_combo.setEnabled(is_checked)

    def toggle_resolution_input(self, state):
        is_checked = (state == Qt.CheckState.Checked.value)
        self.target_resolution_label.setEnabled(is_checked)
        self.target_resolution_input.setEnabled(is_checked)

    def select_files(self):
        root = tk.Tk()
        root.withdraw()

        video_files_tuple = filedialog.askopenfilenames(
            title="비디오 파일 선택",
            filetypes=(("비디오 파일", "*.mp4 *.mkv *.avi"), ("모든 파일", "*.*"))
        )

        if not video_files_tuple:
            return

        video_files = list(video_files_tuple)

        initial_dir = ""
        if video_files:
            initial_dir = os.path.dirname(video_files[0])

        for video_file in video_files:
            try:
                # 비디오 파일명 정리
                renamed_video_file = self.rename_file_if_needed(video_file)
                dialog_video_name = os.path.splitext(os.path.basename(renamed_video_file))[0]

                korean_sub = filedialog.askopenfilename(
                    title=f"{dialog_video_name}의 한글 자막 선택 (선택 사항)",
                    initialdir=os.path.dirname(renamed_video_file),
                    filetypes=(("SRT 파일", "*.srt"), ("모든 파일", "*.*"))
                )

                # 한글 자막 파일명 정리
                renamed_korean_sub = self.rename_file_if_needed(korean_sub)

                initial_dir = os.path.dirname(renamed_korean_sub) if renamed_korean_sub else initial_dir

                english_sub = filedialog.askopenfilename(
                    title=f"{dialog_video_name}의 영어 자막 선택 (선택 사항)",
                    initialdir=initial_dir,
                    filetypes=(("SRT 파일", "*.srt"), ("모든 파일", "*.*"))
                )

                # 영어 자막 파일명 정리
                renamed_english_sub = self.rename_file_if_needed(english_sub)

                self.video_subtitle_pairs.append((renamed_video_file, renamed_korean_sub or None, renamed_english_sub or None))

            except Exception as e:
                QMessageBox.critical(self, "파일 선택 오류", f"파일 처리 중 오류 발생:\n{video_file}\n{e}")

        self.update_file_listbox()

    def update_file_listbox(self):
        self.file_listbox.clear()
        for video, kor, eng in self.video_subtitle_pairs:
            v_name = os.path.basename(video)
            kor_name = os.path.basename(kor) if kor else "없음"
            eng_name = os.path.basename(eng) if eng else "없음"
            item_text = f"비디오: {v_name}\n  한글 자막: {kor_name}\n  영어 자막: {eng_name}\n---"
            self.file_listbox.addItem(item_text)

    def start_processing(self):
        if not self.video_subtitle_pairs:
            QMessageBox.warning(self, "경고", "처리할 비디오 파일을 선택해주세요.")
            return

        if self.processing_thread and self.processing_thread.is_alive():
            QMessageBox.warning(self, "처리 중", "이미 다른 작업이 처리 중입니다.")
            return

        # --- 자막 겹침 자동 수정 옵션 처리 ---
        if self.fix_overlap_checkbox.isChecked():
            try:
                fixed_any = False
                new_pairs = []
                for video, kor_sub, eng_sub in self.video_subtitle_pairs:
                    new_kor_path = kor_sub
                    new_eng_path = eng_sub

                    if kor_sub:
                        new_kor_path = fix_srt_overlaps_and_save(kor_sub)
                        if new_kor_path != kor_sub:
                            fixed_any = True

                    if eng_sub:
                        new_eng_path = fix_srt_overlaps_and_save(eng_sub)
                        if new_eng_path != eng_sub:
                            fixed_any = True

                    new_pairs.append((video, new_kor_path, new_eng_path))

                self.video_subtitle_pairs = new_pairs
                if fixed_any:
                    self.update_file_listbox()
                    QMessageBox.information(self, "알림", "자막 겹침이 자동으로 수정되었습니다.\n수정된 파일(*.fixed.srt)이 생성되었습니다.")

            except SevereOverlapError as e:
                QMessageBox.critical(self, "심각한 자막 오류", str(e))
                return  # 처리 중단
            except Exception as e:
                QMessageBox.critical(self, "자막 수정 오류", f"자막 파일 자동 수정 중 오류가 발생했습니다:\n{e}")
                return

        # 자막 파일 오류 최종 검사
        subtitle_check_result = check_subtitle_files(self.video_subtitle_pairs)
        if subtitle_check_result:
            error_file, errors = subtitle_check_result
            self.show_srt_errors_qt(error_file, errors)
            return

        # --- 업스케일링 옵션 값 가져오기 ---
        use_upscaling = self.upscale_checkbox.isChecked()
        target_width = 0
        target_height = 0
        if use_upscaling:
            try:
                res_text = self.target_resolution_input.text()
                if 'x' in res_text:
                    w_str, h_str = res_text.split('x')
                    w = int(w_str.strip())
                    h = int(h_str.strip())
                    if w > 0 and h > 0:
                        target_width = w
                        target_height = h
                    else:
                        QMessageBox.warning(self, "입력 오류", "유효한 목표 해상도(WxH)를 입력해주세요 (가로세로 > 0).")
                        return
                else:
                    QMessageBox.warning(self, "입력 오류", "목표 해상도 형식이 잘못되었습니다 (예: 1920x1080).")
                    return
            except ValueError:
                QMessageBox.warning(self, "입력 오류", "목표 해상도(WxH)는 숫자여야 합니다.")
                return
        else:
            target_width = 0
            target_height = 0

        self.progress_bar.setMaximum(len(self.video_subtitle_pairs))
        self.progress_bar.setValue(0)
        self.results.clear()
        self.status_label.setText("처리 준비 중...")
        self.start_button.setEnabled(False)
        self.select_files_button.setEnabled(False)

        # --- 패딩 모드 결정 (none / top_bottom / bottom_double) ---
        if self.padding_checkbox.isChecked():
            padding_mode = 'top_bottom' if self.padding_mode_combo.currentIndex() == 0 else 'bottom_double'
        else:
            padding_mode = 'none'

        # VideoProcessorManager 인스턴스 생성 (새로운 파라미터 전달)
        self.processor = VideoProcessorManager(
            padding_mode, use_upscaling, target_width, target_height
        )

        self.processing_thread = threading.Thread(target=self.process_videos, daemon=True)
        self.processing_thread.start()

    def process_videos(self):
        try:
            for i, (video, korean_sub, english_sub) in enumerate(self.video_subtitle_pairs):
                self.status_updated.emit(f"처리 중 ({i+1}/{len(self.video_subtitle_pairs)}): {os.path.basename(video)}")

                if not self.processor:
                    self.results.append(("Error", f"{os.path.basename(video)}: Processor not initialized."))
                    self.progress_updated.emit(i + 1)
                    continue

                result = self.processor.process_single_video(video, korean_sub, english_sub)
                self.results.append(result)
                self.progress_updated.emit(i + 1)

            self.status_updated.emit("모든 처리가 완료되었습니다.")
        except Exception as e:
            self.status_updated.emit(f"처리 중 심각한 오류 발생: {e}")
            self.results.append(("Fatal Error", f"처리 스레드 오류: {e}"))
        finally:
            self.processing_finished.emit(self.results)

    def update_progress_bar(self, value):
        self.progress_bar.setValue(value)

    def update_status_label(self, text):
        self.status_label.setText(text)

    def show_final_results_qt(self, results_data):
        dialog = QDialog(self)
        dialog.setWindowTitle("작업 결과")
        dialog.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout(dialog)
        text_edit = QTextEdit()
        text_edit.setReadOnly(True)

        for status, message in results_data:
            icon = ""
            if status == 'Success':
                icon = "✅"
            elif status == 'Warning':
                icon = "⚠️"
            elif status == 'Info':
                icon = "ℹ️"
            elif status == 'Error' or status == 'Fatal Error':
                icon = "❌"
            else:
                icon = "❓"
            text_edit.append(f"{icon} {message}\n")

        layout.addWidget(text_edit)

        close_button = QPushButton("닫기")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)

        self.start_button.setEnabled(True)
        self.select_files_button.setEnabled(True)

        dialog.exec()

    def show_srt_errors_qt(self, srt_file, errors):
        """SRT 파일 오류를 PyQt6 Dialog로 표시합니다."""
        dialog = QDialog(self)
        dialog.setWindowTitle(f"'{os.path.basename(srt_file)}' 자막 오류")
        dialog.setGeometry(200, 200, 600, 400)

        layout = QVBoxLayout(dialog)

        info_label = QLabel(f"파일 '{os.path.basename(srt_file)}'에서 다음 오류가 발견되었습니다:")
        layout.addWidget(info_label)

        text_edit = QTextEdit()
        text_edit.setReadOnly(True)
        text_edit.setText("\n".join(errors))
        layout.addWidget(text_edit)

        close_button = QPushButton("확인")
        close_button.clicked.connect(dialog.accept)
        layout.addWidget(close_button)

        dialog.setLayout(layout)
        dialog.exec()

        QMessageBox.critical(self, "자막 오류",
                             f"'{os.path.basename(srt_file)}'에 오류가 발견되어 처리를 중단합니다.\n오류 내용을 확인하세요.")

    def closeEvent(self, event):
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    ex = VideoProcessingApp()
    ex.show()
    sys.exit(app.exec())
