import logging
from dataclasses import dataclass
from typing import Optional, Dict, Any

# from paddleocr import PaddleOCR
from pathlib import Path
from PIL import Image

from src.services.base_service import BaseService
from src.utils.params_helper import ParamsHelper

# 减少 paddleocr 日志输出
logging.getLogger("ppocr").setLevel(logging.WARNING)
logging.getLogger("ppocr.utils").setLevel(logging.WARNING)
logging.getLogger("paddleocr").setLevel(logging.WARNING)
logging.getLogger("PIL").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)


def preprocess_image(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext == ".webp":
        new_path = str(Path(path).with_suffix(".png"))
        Image.open(path).convert("RGB").save(new_path, "PNG")
        return new_path
    return path

class PaddleOCRService(BaseService):
    @dataclass
    class Params:
        lang: str
        image_path_abs_path: str
        include_text: bool = True
        need_merge_lines: bool = True
        include_boxes: bool = False
        include_confidence: bool = True
        include_layout: bool = False
        include_table: bool = False
        include_raw_image: bool = True

    # def __init__(self):
    #     super().__init__()
    #
    #     self.ocr: Optional[PaddleOCR] = None
    #     self.params: Optional[PaddleOCRService.Params] = None
    #
    # def invoke(self, extra_params: Dict[str, Any]) -> Dict:
    #     if self.ocr is None:
    #         # 初始化OCR（只初始化一次）
    #         self.ocr = PaddleOCR(
    #             use_angle_cls=True,
    #             lang=extra_params['lang']
    #         )
    #
    #     self.params = ParamsHelper.build_params(self.Params, extra_params)
    #     image_path = preprocess_image(self.params.image_path_abs_path)
    #     ocr_result = self.ocr.ocr(image_path)
    #
    #     result = ocr_result[0].json.get("res")
    #
    #     output = {}
    #     line_num = len(result.get("rec_texts"))
    #
    #     # 提取纯文本
    #     if self.params.include_text:
    #         text_lines = result.get("rec_texts")
    #         if self.params.need_merge_lines:
    #             output["text"] = "\n".join(text_lines)
    #         else:
    #             output["text"] = text_lines
    #
    #     # 坐标 + 置信度
    #     if self.params.include_boxes:
    #         output["boxes"] = [
    #             {
    #                 "text": result.get("rec_texts")[i],
    #                 "box": result.get("polys")[i],
    #                 "confidence": result.get("rec_scores")[i]
    #             }
    #             for i in range(line_num)
    #         ]
    #
    #     if self.params.include_confidence:
    #         avg_conf = sum(result.get("rec_scores")) / line_num
    #         output["confidence"] = { "avg_confidence": avg_conf }
    #
    #     # 版面分析 / 表格识别（这里先留接口，需要 PP-Structure）
    #     if self.params.include_layout:
    #         output["layout"] = "[Layout analysis not implemented in demo]"
    #
    #     if self.params.include_table:
    #         output["table"] = "[Table recognition not implemented in demo]"
    #
    #     # 原图（仅在多模态大模型场景使用）
    #     if self.params.include_raw_image:
    #         output["raw_image_path"] = self.params.image_path_abs_path
    #
    #     return output

paddle_ocr_service = PaddleOCRService()
