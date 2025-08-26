from video_processor import VideoProcessor
from video_processor_with_padding import VideoProcessor as VideoProcessorWithPadding

class VideoProcessorManager:
    def __init__(self, padding_option, use_upscaling, target_width, target_height):
        self.padding_option = padding_option
        self.use_upscaling = use_upscaling
        self.target_width = target_width
        self.target_height = target_height

        if self.padding_option:
            self.processor = VideoProcessorWithPadding(
                self.use_upscaling, self.target_width, self.target_height
            )
        else:
            self.processor = VideoProcessor(
                self.use_upscaling, self.target_width, self.target_height
            )

    def process_single_video(self, input_path, korean_srt_path, english_srt_path):
        return self.processor.process_single_video(input_path, korean_srt_path, english_srt_path)