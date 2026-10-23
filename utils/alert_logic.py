class AlertManager:
    """Quan ly canh bao dua tren so frame co dien thoai lien tuc."""

    def __init__(self, warning_seconds=2):
        self.warning_seconds = warning_seconds
        self.phone_frame_count = 0

    def update(self, phone_detected, fps=30):
        threshold = max(int(fps * self.warning_seconds), 1)
        self.phone_frame_count = self.phone_frame_count + 1 if phone_detected else 0

        if self.phone_frame_count == 0:
            return "NORMAL", self.phone_frame_count
        if self.phone_frame_count < threshold:
            return "LOW", self.phone_frame_count
        return "HIGH", self.phone_frame_count

    def reset(self):
        self.phone_frame_count = 0
