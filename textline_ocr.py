"""SynthScan PP-OCRv4 line recognition with a fixed-shape model.

Preprocessing/CTC adapted from SC-Ravaxx/Bedrock src/TextLineReader.cpp,
Copyright (C) 2026 Ravaxx, GPL-3.0-or-later. See third_party/bedrock/LICENSE.
Model and alphabet: PaddleOCR / Guten OCR, separate Apache-2.0 / MIT notices
in third_party/bedrock/textline/NOTICE-textline.txt.
"""
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


class TextLineRecognizer:
    def __init__(self):
        directory = Path(__file__).parent / 'third_party/bedrock/textline'
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        self.session = ort.InferenceSession(str(directory / 'textline.onnx'), options, providers=['CPUExecutionProvider'])
        self.input_name = self.session.get_inputs()[0].name
        self.keys = [''] + (directory / 'textline_keys.txt').read_text(encoding='utf-8').splitlines() + [' ']

    def read(self, bgr):
        if bgr is None or bgr.size == 0:
            return '', 0.0
        if bgr.ndim == 2:
            bgr = cv2.cvtColor(bgr, cv2.COLOR_GRAY2BGR)
        width = max(1, min(320, round(bgr.shape[1] * 48 / bgr.shape[0])))
        resized = cv2.resize(bgr, (width, 48), interpolation=cv2.INTER_CUBIC)
        canvas = np.full((48, 320, 3), 127.5, dtype=np.float32)
        canvas[:, :width] = resized
        tensor = ((canvas / 127.5) - 1).transpose(2, 0, 1)[None].astype(np.float32)
        prediction = self.session.run(None, {self.input_name: tensor})[0][0]
        best = np.argmax(prediction, axis=1)
        previous, text, scores = -1, [], []
        for timestep, index in enumerate(best):
            if index and index != previous and index < len(self.keys):
                text.append(self.keys[index])
                scores.append(float(prediction[timestep, index]))
            previous = index
        return ''.join(text).strip(), sum(scores)/len(scores) if scores else 0.0
