#!/usr/bin/env python3
"""
香港收據 OCR 數據集創建工具
使用 EasyOCR 自動生成標註
生成符合 deep-text-recognition-benchmark 的 gt.txt 格式(切割文字區域用於 Recognition 訓練)
支援彎曲收據的自動校正功能
"""

import json
import cv2
import easyocr
import numpy as np
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, Tuple
import argparse


class ReceiptDatasetCreator:
    """收據數據集創建器"""

    # 類別常數 - 配置參數
    CONFIDENCE_THRESHOLD = 0.5
    MAX_DEVIATION_THRESHOLD = 50
    TILT_ANGLE_THRESHOLD = 2
    MIN_LINES_FOR_CURVE_DETECTION = 5
    CLAHE_CLIP_LIMIT = 2.0
    CLAHE_GRID_SIZE = (8, 8)
    DENOISE_H = 7
    SHARPEN_STRENGTH = 0.5

    # 模型快取 (單例模式)
    _reader_cache = {}
    _doctr_cache = None

    @classmethod
    def get_reader(cls, langs=('ch_tra', 'en'), gpu=True):
        """獲取快取的 EasyOCR Reader (單例模式)"""
        cache_key = (tuple(langs), gpu)
        if cache_key not in cls._reader_cache:
            print(f"🔄 Loading EasyOCR model ({', '.join(langs)})...")
            cls._reader_cache[cache_key] = easyocr.Reader(list(langs), gpu=gpu)
            print("✅ EasyOCR model loaded!")
        return cls._reader_cache[cache_key]

    @classmethod
    def get_doctr_model(cls):
        """獲取快取的 doctr 模型 (單例模式)"""
        if cls._doctr_cache is None and DOCTR_AVAILABLE:
            try:
                print("🔄 Loading doctr model for document correction...")
                cls._doctr_cache = ocr_predictor(pretrained=True)
                print("✅ doctr model loaded!")
            except Exception as e:
                print(f"⚠️  Failed to load doctr: {e}")
        return cls._doctr_cache

    def __init__(self, input_dir: str = "./input", processed_dir: str = "./processed",
                 crops_dir: str = "./processed/crops", dataset_dir: str = "./dataset_gt",
                 enable_correction: bool = False):
        # 輸入驗證
        if not input_dir or not isinstance(input_dir, str):
            raise ValueError(f"Invalid input_dir: {input_dir}")

        self.input_dir = Path(input_dir).resolve()
        self.processed_dir = Path(processed_dir).resolve()
        self.crops_dir = Path(crops_dir).resolve()
        self.dataset_dir = Path(dataset_dir).resolve()
        self.enable_correction = False  # 強制停用圖像處理

        # 創建目錄結構
        self.annotations_file = self.processed_dir / "annotations.json"
        self.processed_images_dir = self.processed_dir / "images"
        self.train_dir = self.dataset_dir / "train"
        self.valid_dir = self.dataset_dir / "valid"
        self.test_dir = self.dataset_dir / "test"

        for dir_path in [self.input_dir, self.processed_dir, self.processed_images_dir,
                         self.crops_dir, self.train_dir, self.valid_dir, self.test_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

        # 延遲載入 EasyOCR 模型 (只在需要 OCR 時才載入)
        self.reader = None

        # 標註數據
        self.annotations = {}
        self.load_annotations()

    def load_annotations(self):
        """載入已有的標註"""
        if self.annotations_file.exists():
            try:
                with open(self.annotations_file, 'r', encoding='utf-8') as f:
                    self.annotations = json.load(f)
                print(f"📂 Loaded {len(self.annotations)} existing annotations")
            except (json.JSONDecodeError, IOError) as e:
                print(f"⚠️  Failed to load annotations: {e}")
                self.annotations = {}
            except Exception as e:
                print(
                    f"❌ Unexpected error loading annotations: {type(e).__name__}: {e}")
                self.annotations = {}

    def save_annotations(self):
        """保存標註"""
        try:
            with open(self.annotations_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, ensure_ascii=False, indent=2)
            print(f"💾 Saved annotations to {self.annotations_file}")
        except (IOError, OSError) as e:
            print(f"❌ Failed to save annotations: {e}")
        except Exception as e:
            print(
                f"❌ Unexpected error saving annotations: {type(e).__name__}: {e}")

    def correct_document_distortion(self, image: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        溫和的文檔校正 - 只修正明顯的透視傾斜,保留圖片細節
        Returns: (校正後的圖像, 是否進行了校正)
        """
        # 輸入驗證
        if image is None or not isinstance(image, np.ndarray):
            raise ValueError("Invalid image: expected numpy array")
        if image.size == 0:
            raise ValueError("Invalid image: empty array")

        try:
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY) if len(
                image.shape) == 3 else image

            # 1. 檢測邊緣
            edges = cv2.Canny(gray, 50, 150, apertureSize=3)

            # 2. 使用 Hough 變換檢測直線
            lines = cv2.HoughLinesP(edges, 1, np.pi / 180, threshold=100,
                                    minLineLength=100, maxLineGap=10)

            if lines is None or len(lines) < 10:
                return image, False

            # 3. 計算主要角度(檢測是否傾斜)
            angles = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                angle = np.arctan2(y2 - y1, x2 - x1) * 180 / np.pi
                angles.append(angle)

            # 找到主要角度
            median_angle = np.median(angles)

            # 如果傾斜角度很小(<2度),不需要校正
            if abs(median_angle) < self.TILT_ANGLE_THRESHOLD:
                return image, False

            # 如果傾斜明顯,進行旋轉校正
            if abs(median_angle) > self.TILT_ANGLE_THRESHOLD and abs(median_angle) < 45:
                h, w = image.shape[:2]
                center = (w // 2, h // 2)

                # 計算旋轉矩陣
                rotation_matrix = cv2.getRotationMatrix2D(
                    center, float(median_angle), 1.0)

                # 計算新的邊界大小
                cos_val = abs(rotation_matrix[0, 0])
                sin_val = abs(rotation_matrix[0, 1])
                new_w = int((h * sin_val) + (w * cos_val))
                new_h = int((h * cos_val) + (w * sin_val))

                # 調整旋轉矩陣
                rotation_matrix[0, 2] += (new_w / 2) - center[0]
                rotation_matrix[1, 2] += (new_h / 2) - center[1]

                # 應用旋轉
                corrected = cv2.warpAffine(image, rotation_matrix, (new_w, new_h),
                                           flags=cv2.INTER_LINEAR,
                                           borderMode=cv2.BORDER_CONSTANT,
                                           borderValue=(255, 255, 255))

                print(f"   ✅ 校正傾斜 {median_angle:.1f}°")
                return corrected, True

            return image, False

        except cv2.error as e:
            print(f"   ⚠️  OpenCV 錯誤: {e}")
            return image, False
        except (ValueError, TypeError) as e:
            print(f"   ⚠️  數據錯誤: {e}")
            return image, False
        except Exception as e:
            print(f"   ❌  未預期的錯誤: {type(e).__name__}: {e}")
            return image, False

    def dewarp_curved_document(self, img: np.ndarray) -> Tuple[np.ndarray, bool]:
        """
        檢測並校正彎曲的文檔 (溫和處理,保留細節)

        返回:
            (校正後的圖片, 是否檢測到彎曲)
        """
        # 輸入驗證
        if img is None or not isinstance(img, np.ndarray):
            raise ValueError("Invalid image: expected numpy array")
        if img.size == 0:
            raise ValueError("Invalid image: empty array")

        try:
            # 1. 先增強對比度
            enhanced = self.enhance_image_quality(img)

            # 2. 轉為灰度圖進行邊緣檢測
            # 檢查是否已經是灰度圖
            if len(enhanced.shape) == 2:
                gray = enhanced
            else:
                gray = cv2.cvtColor(enhanced, cv2.COLOR_BGR2GRAY)

            # 3. 檢測水平線條
            edges = cv2.Canny(gray, 50, 150)
            lines = cv2.HoughLinesP(edges, 1, np.pi/180, threshold=100,
                                    minLineLength=100, maxLineGap=10)

            if lines is None or len(lines) < self.MIN_LINES_FOR_CURVE_DETECTION:
                return img, False

            # 4. 檢查線條是否有明顯彎曲
            deviations = []
            for line in lines:
                x1, y1, x2, y2 = line[0]
                # 計算線條中點到理想直線的偏差
                mid_x = (x1 + x2) / 2
                mid_y = (y1 + y2) / 2
                ideal_y = y1 + (y2 - y1) * (mid_x - x1) / \
                    (x2 - x1) if x2 != x1 else y1
                deviation = abs(mid_y - ideal_y)
                deviations.append(deviation)

            max_deviation = max(deviations) if deviations else 0

            # 5. 如果偏差超過閾值,標記為彎曲(但不做激進校正)
            is_curved = max_deviation > self.MAX_DEVIATION_THRESHOLD

            if is_curved:
                print(f"   ⚠️  檢測到彎曲 (最大偏差: {max_deviation:.1f}px)")
                print(f"   💡 建議: 使用平整的表面重新拍攝,或手動使用 Photoshop/GIMP 校正")

            # 返回原圖 - 我們不做激進的去彎曲,只提醒用戶
            return img, is_curved

        except cv2.error as e:
            print(f"   ⚠️  OpenCV 錯誤: {e}")
            return img, False
        except (ValueError, TypeError) as e:
            print(f"   ⚠️  數據錯誤: {e}")
            return img, False
        except Exception as e:
            print(f"   ❌  未預期的錯誤: {type(e).__name__}: {e}")
            return img, False

    def enhance_image_quality(self, image: np.ndarray) -> np.ndarray:
        """
        溫和地增強圖像質量 - 保留細節,適合 OCR

        Args:
            image: 輸入圖片 (BGR 彩色)

        Returns:
            增強後的圖片 (灰度圖)
        """
        # 輸入驗證
        if image is None or not isinstance(image, np.ndarray):
            raise ValueError("Invalid image: expected numpy array")
        if image.size == 0:
            raise ValueError("Invalid image: empty array")

        try:
            # 1. 轉灰階
            if len(image.shape) == 3:
                gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            else:
                gray = image.copy()

            # 2. 輕微去噪 (保留文字邊緣)
            denoised = cv2.fastNlMeansDenoising(gray, h=self.DENOISE_H)

            # 3. 自適應直方圖均衡化 (CLAHE) - 增強對比度
            clahe = cv2.createCLAHE(clipLimit=self.CLAHE_CLIP_LIMIT,
                                    tileGridSize=self.CLAHE_GRID_SIZE)
            enhanced = clahe.apply(denoised)

            # 4. 輕微銳化 (增強文字邊緣)
            kernel = np.array([[-1, -1, -1],
                              [-1, 9, -1],
                              [-1, -1, -1]])
            sharpened = cv2.filter2D(
                enhanced, -1, kernel * self.SHARPEN_STRENGTH)
            sharpened = np.clip(sharpened, 0, 255).astype(np.uint8)

            return sharpened

        except cv2.error as e:
            print(f"   ⚠️  OpenCV 錯誤: {e}")
            return image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        except (ValueError, TypeError) as e:
            print(f"   ⚠️  數據錯誤: {e}")
            return image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        except Exception as e:
            print(f"   ❌  未預期的錯誤: {type(e).__name__}: {e}")
            return image if len(image.shape) == 2 else cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    def preprocess_image(self, image_path: Path) -> np.ndarray:
        """
        簡單讀取圖片 - 不做任何處理

        Returns:
            原始圖片
        """
        # 輸入驗證
        if not isinstance(image_path, Path):
            image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        img = cv2.imread(str(image_path))
        if img is None:
            raise ValueError(f"Cannot read image: {image_path}")

        return img

    def ocr_image(self, image_path: Path) -> Dict:
        """使用 EasyOCR 識別圖片並切割文字區域"""
        print(f"\n🔍 Processing: {image_path.name}")

        # 確保模型已載入 (延遲載入)
        if self.reader is None:
            self.reader = self.get_reader()

        # 讀取原圖
        img = self.preprocess_image(image_path)

        # 直接使用原圖進行 OCR
        result = self.reader.readtext(img)

        # 整理結果 - 只保留高信心度的結果，並切割文字區域
        ocr_results = []
        full_text_lines = []
        filtered_count = 0
        base_name = Path(image_path).stem

        for idx, (bbox, text, confidence) in enumerate(result):
            # 過濾低信心度結果
            if confidence < self.CONFIDENCE_THRESHOLD:
                filtered_count += 1
                continue

            # 將 numpy 數組轉換為 Python list
            bbox_list = [[float(x), float(y)] for x, y in bbox]

            # 切割文字區域並保存到 crops/ 目錄
            try:
                cropped_img = self.crop_text_regions(image_path, bbox_list)
                if cropped_img is not None and cropped_img.size > 0:
                    crop_filename = f"{base_name}_crop_{idx:03d}.jpg"
                    crop_path = self.crops_dir / crop_filename
                    cv2.imwrite(str(crop_path), cropped_img)

                    ocr_results.append({
                        'bbox': bbox_list,
                        'text': text,
                        'confidence': float(confidence),
                        'crop_filename': crop_filename
                    })
                    full_text_lines.append(text)
            except Exception as e:
                print(f"   ⚠️  切割區域 {idx} 失敗: {e}")
                continue

        if filtered_count > 0:
            print(
                f"   🔍 過濾掉 {filtered_count} 個低信心度結果 (< {self.CONFIDENCE_THRESHOLD})")

        # 保存原圖到 processed/images 目錄
        processed_img_path = self.processed_images_dir / image_path.name
        shutil.copy(str(image_path), str(processed_img_path))

        return {
            'image_name': image_path.name,
            'original_image_path': str(image_path),
            'processed_image_path': str(processed_img_path),
            'ocr_results': ocr_results,
            'full_text': '\n'.join(full_text_lines),
            'timestamp': datetime.now().isoformat(),
            'verified': False  # 標記是否已人工驗證
        }

    def auto_generate_annotations(self, overwrite: bool = False):
        """自動為 input/ 目錄中的所有圖片生成標註"""
        import gc  # 垃圾回收

        image_files = list(self.input_dir.glob('*.jpg')) + \
            list(self.input_dir.glob('*.jpeg')) + \
            list(self.input_dir.glob('*.png'))

        print(f"\n📸 Found {len(image_files)} images in {self.input_dir}")

        for idx, img_path in enumerate(image_files, 1):
            print(f"\n[{idx}/{len(image_files)}] Processing {img_path.name}")

            # 跳過已處理的圖片
            if img_path.name in self.annotations and not overwrite:
                print(f"⏭️  Skipping (already processed)")
                continue

            try:
                annotation = self.ocr_image(img_path)
                self.annotations[img_path.name] = annotation

                # 顯示識別結果
                print(
                    f"✅ Detected {len(annotation['ocr_results'])} text regions")
                print(f"📝 Preview:")
                print("-" * 60)
                print(annotation['full_text'][:500])  # 顯示前 500 字符
                if len(annotation['full_text']) > 500:
                    print("...")
                print("-" * 60)

            except Exception as e:
                print(f"❌ Error processing {img_path.name}: {e}")

            finally:
                # 記憶體管理: 每處理 10 張圖片後執行垃圾回收
                if idx % 10 == 0:
                    gc.collect()
                    print(
                        f"   🧹 Memory cleanup (processed {idx}/{len(image_files)})")

        # 保存標註
        self.save_annotations()
        print(
            f"\n✅ Auto-annotation complete! Processed {len(image_files)} images")

        # 最終記憶體清理
        gc.collect()

    def crop_text_regions(self, image_path: Path, bbox, padding: int = 5):
        """
        根據 bbox 切割文字區域

        Args:
            image_path: 圖片路徑
            bbox: 文字框坐標 [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
            padding: 邊界填充像素

        Returns:
            切割後的圖片 (numpy array)
        """
        # 輸入驗證
        if not isinstance(image_path, Path):
            image_path = Path(image_path)
        if not image_path.exists():
            raise FileNotFoundError(f"Image file not found: {image_path}")

        if not isinstance(bbox, (list, np.ndarray)) or len(bbox) != 4:
            raise ValueError(
                f"Invalid bbox format: expected 4 points, got {len(bbox) if bbox else 'None'}")

        if padding < 0:
            raise ValueError(f"Padding must be non-negative, got {padding}")

        img = cv2.imread(str(image_path))
        if img is None:
            raise FileNotFoundError(f"Cannot read image: {image_path}")

        try:
            # 獲取 bbox 的最小外接矩形
            points = np.array(bbox, dtype=np.float32)
            x_min = max(0, int(np.min(points[:, 0])) - padding)
            y_min = max(0, int(np.min(points[:, 1])) - padding)
            x_max = min(img.shape[1], int(np.max(points[:, 0])) + padding)
            y_max = min(img.shape[0], int(np.max(points[:, 1])) + padding)

            # 驗證裁切區域
            if x_max <= x_min or y_max <= y_min:
                raise ValueError(
                    f"Invalid crop region: x({x_min},{x_max}), y({y_min},{y_max})")

            # 切割圖片
            cropped = img[y_min:y_max, x_min:x_max]

            return cropped

        except (ValueError, TypeError) as e:
            print(f"   ⚠️  裁切失敗: {e}")
            return None
        except Exception as e:
            print(f"   ❌  未預期的錯誤: {type(e).__name__}: {e}")
            return None

    def generate_training_dataset(self, train_ratio: float = 0.8, valid_ratio: float = 0.1,
                                  crop_text_regions: bool = True):
        """
        生成訓練數據集 - gt.txt 格式 (用於 deep-text-recognition-benchmark)

        Args:
            train_ratio: 訓練集比例
            valid_ratio: 驗證集比例
            crop_text_regions: 是否切割文字區域 (True=訓練Recognition, False=訓練完整OCR)

        目錄結構 (crop_text_regions=True):
        dataset_gt/
        ├── train/
        │   ├── receipt001_crop_000.jpg  # 第一個文字區域
        │   ├── receipt001_crop_001.jpg  # 第二個文字區域
        │   └── gt.txt

        gt.txt 格式 (tab 分隔):
        receipt001_crop_000.jpg	SUPERNORMAL
        receipt001_crop_001.jpg	總計
        """
        # 輸入驗證
        if not (0 < train_ratio < 1):
            raise ValueError(
                f"Invalid train_ratio: {train_ratio}, must be between 0 and 1")
        if not (0 <= valid_ratio < 1):
            raise ValueError(
                f"Invalid valid_ratio: {valid_ratio}, must be between 0 and 1")
        if train_ratio + valid_ratio > 1:
            raise ValueError(
                f"train_ratio + valid_ratio must be <= 1, got {train_ratio + valid_ratio}")

        # 檢查是否有已驗證的 OCR 結果 (檢查 ocr_results 層級而不是圖片層級)
        verified_count = 0
        annotations_with_verified = {}

        for image_name, anno in self.annotations.items():
            verified_regions = [
                ocr for ocr in anno.get('ocr_results', [])
                if ocr.get('verified', False)
            ]
            if verified_regions:
                annotations_with_verified[image_name] = anno
                verified_count += len(verified_regions)

        if verified_count == 0:
            print(
                "❌ No verified annotations found! Please run manual verification first.")
            print("💡 Or run with --auto-verify to skip manual verification")
            return

        print(
            f"✅ Found {verified_count} verified text regions across {len(annotations_with_verified)} images")

        print(
            f"\n📊 Generating training dataset from {verified_count} verified text regions")
        print(
            f"📐 Mode: {'Crop text regions (Recognition training)' if crop_text_regions else 'Full image (Complete OCR training)'}")
        print(f"📄 Format: gt.txt (tab-separated, for deep-text-recognition-benchmark)")

        # 使用有驗證結果的標註
        verified = annotations_with_verified

        if crop_text_regions:
            # 模式 1: 按 crop (文字區域) 分割數據集
            # 收集所有已驗證的 crop
            all_crops = []
            for image_name, anno in verified.items():
                for ocr_result in anno.get('ocr_results', []):
                    if ocr_result.get('verified', False):
                        all_crops.append({
                            'image_name': image_name,
                            'anno': anno,
                            'ocr_result': ocr_result
                        })

            # 打亂並分割
            np.random.seed(42)
            np.random.shuffle(all_crops)

            n_total = len(all_crops)
            n_train = int(n_total * train_ratio)
            n_valid = int(n_total * valid_ratio)

            train_crops = all_crops[:n_train]
            valid_crops = all_crops[n_train:n_train + n_valid]
            test_crops = all_crops[n_train + n_valid:]

            print(
                f"📈 Split by crops: Train={len(train_crops)}, Valid={len(valid_crops)}, Test={len(test_crops)}")

            # 轉換為舊格式 (為了相容後續代碼)
            def crops_to_items(crops):
                # 將 crop 列表轉換為 {image_name: anno} 格式，但標記哪些 ocr_result 屬於這個 split
                items_dict = {}
                for crop in crops:
                    img_name = crop['image_name']
                    if img_name not in items_dict:
                        items_dict[img_name] = {
                            'anno': crop['anno'],
                            'crop_indices': []
                        }
                    # 找到這個 ocr_result 在原始列表中的索引
                    ocr_idx = crop['anno']['ocr_results'].index(
                        crop['ocr_result'])
                    items_dict[img_name]['crop_indices'].append(ocr_idx)

                return [(k, v['anno'], v['crop_indices']) for k, v in items_dict.items()]

            train_items = crops_to_items(train_crops)
            valid_items = crops_to_items(valid_crops)
            test_items = crops_to_items(test_crops)

        else:
            # 模式 2: 按圖片分割數據集 (完整 OCR 訓練)
            items = list(verified.items())
            np.random.seed(42)
            np.random.shuffle(items)

            n_total = len(items)
            n_train = int(n_total * train_ratio)
            n_valid = int(n_total * valid_ratio)

            # 確保 valid 至少有 1 張圖片 (如果總數 >= 3)
            if n_total >= 3 and n_valid == 0:
                n_valid = 1
                n_train = n_total - n_valid - \
                    max(1, int(n_total * (1 - train_ratio - valid_ratio)))

            train_items = [(k, v, None) for k, v in items[:n_train]]
            valid_items = [(k, v, None)
                           for k, v in items[n_train:n_train + n_valid]]
            test_items = [(k, v, None) for k, v in items[n_train + n_valid:]]

            print(
                f"📈 Split by images: Train={len(train_items)}, Valid={len(valid_items)}, Test={len(test_items)}")

        # 生成數據集文件 (gt.txt 格式)
        for split_name, split_items in [
            ('train', train_items),
            ('valid', valid_items),
            ('test', test_items)
        ]:
            if not split_items:
                continue

            split_dir = self.dataset_dir / split_name
            split_dir.mkdir(exist_ok=True)

            # 創建 gt.txt (tab 分隔格式)
            gt_file = split_dir / 'gt.txt'

            print(f"\n📝 Creating {split_name} dataset...")

            total_samples = 0

            try:
                with open(gt_file, 'w', encoding='utf-8') as f:

                    for item in split_items:
                        # 解包新格式: (image_name, anno, crop_indices)
                        if len(item) == 3:
                            image_name, anno, crop_indices = item
                        else:
                            # 向後兼容舊格式
                            image_name, anno = item
                            crop_indices = None

                        src_img = Path(anno['processed_image_path'])

                        if not src_img.exists():
                            print(f"  ⚠️  Image not found: {src_img}")
                            continue

                        if crop_text_regions:
                            # 模式 1: 使用已切割的文字區域 (從 crops/ 目錄)
                            # 如果有 crop_indices，只處理這些索引的 OCR 結果
                            ocr_results = anno['ocr_results']

                            if crop_indices is not None:
                                # 只處理指定的 crop
                                ocr_results_to_process = [
                                    ocr_results[i] for i in crop_indices if i < len(ocr_results)]
                            else:
                                # 處理所有已驗證的 crop
                                ocr_results_to_process = [
                                    ocr for ocr in ocr_results if ocr.get('verified', False)]

                            for ocr_result in ocr_results_to_process:
                                text = ocr_result['text'].strip()
                                crop_filename = ocr_result.get('crop_filename')
                                confidence = ocr_result['confidence']

                                if not text or not crop_filename:
                                    continue

                                # 清理文字 (移除換行符和 tab)
                                text = text.replace('\n', ' ').replace(
                                    '\r', '').replace('\t', ' ')
                                text = ' '.join(text.split())

                                if not text:
                                    continue

                                # 從 crops/ 目錄複製到對應的 split 目錄
                                try:
                                    src_crop = self.crops_dir / crop_filename
                                    if not src_crop.exists():
                                        print(
                                            f"  ⚠️  Crop not found: {crop_filename}")
                                        continue

                                    dst_crop = split_dir / crop_filename
                                    shutil.copy(src_crop, dst_crop)

                                    # 寫入 gt.txt (tab 分隔: filename\ttext)
                                    f.write(f"{crop_filename}\t{text}\n")
                                    total_samples += 1
                                    print(
                                        f"  ✓ {crop_filename}: {text} (信心度: {confidence:.2f})")

                                except Exception as e:
                                    print(
                                        f"  ⚠️  處理 {crop_filename} 失敗: {e}")
                                    continue

                        else:
                            # 模式 2: 完整圖片 (訓練完整 OCR)
                            try:
                                dst_img = split_dir / image_name
                                shutil.copy(src_img, dst_img)

                                # 準備標註文字 (單行,移除換行符和 tab)
                                label_text = anno.get(
                                    'corrected_text') or anno['full_text']

                                # 清理文字
                                label_text = label_text.replace(
                                    '\n', ' ').replace('\r', '').replace('\t', ' ')
                                label_text = ' '.join(label_text.split())

                                if not label_text:
                                    print(f"  ⚠️  跳過空標籤: {image_name}")
                                    continue

                                # 寫入 gt.txt (tab 分隔: filename\ttext)
                                f.write(f"{image_name}\t{label_text}\n")
                                total_samples += 1

                                print(f"  ✓ {image_name}")

                            except Exception as e:
                                print(f"  ⚠️  處理 {image_name} 失敗: {e}")
                                continue

                print(f"✅ Created {split_name} set: {total_samples} samples")
                print(f"   📄 gt.txt: {gt_file}")
                print(f"   📂 Images: {split_dir}")

            except (IOError, OSError) as e:
                print(f"❌ 無法創建 gt.txt 文件 {gt_file}: {e}")
                continue
            except Exception as e:
                print(f"❌ 未預期的錯誤: {type(e).__name__}: {e}")
                continue

        print(f"\n{'='*70}")
        print(f"✅ Training dataset generated in {self.dataset_dir}")
        print(f"📄 Format: gt.txt (tab-separated)")
        print(f"{'='*70}")
        print(f"\n📖 Next steps:")
        print(f"\n1. Convert gt.txt to LMDB format:")
        print(f"   python deep-text-recognition-benchmark/create_lmdb_dataset.py \\")
        print(f"       --inputPath {self.dataset_dir}/train \\")
        print(f"       --gtFile {self.dataset_dir}/train/gt.txt \\")
        print(f"       --outputPath dataset_lmdb/train")
        print(f"   ")
        print(f"   python deep-text-recognition-benchmark/create_lmdb_dataset.py \\")
        print(f"       --inputPath {self.dataset_dir}/valid \\")
        print(f"       --gtFile {self.dataset_dir}/valid/gt.txt \\")
        print(f"       --outputPath dataset_lmdb/valid")
        print(f"\n2. Start training:")
        print(f"   cd deep-text-recognition-benchmark")
        print(f"   python train.py \\")
        print(f"       --train_data ../dataset_lmdb/train \\")
        print(f"       --valid_data ../dataset_lmdb/valid \\")
        print(f"       --Transformation TPS \\")
        print(f"       --FeatureExtraction ResNet \\")
        print(f"       --SequenceModeling BiLSTM \\")
        print(f"       --Prediction Attn")
        print()

    def show_statistics(self):
        """顯示統計資訊"""
        total = len(self.annotations)
        verified = sum(1 for v in self.annotations.values()
                       if v.get('verified', False))
        manual_corrected = sum(
            1 for v in self.annotations.values() if v.get('manual_corrected', False))

        print(f"\n{'='*70}")
        print(f"📊 Dataset Statistics")
        print(f"{'='*70}")
        print(f"Total images: {total}")
        print(
            f"Verified: {verified} ({verified/total*100:.1f}%)" if total > 0 else "Verified: 0")
        print(f"Manual corrected: {manual_corrected}")
        print(f"Pending verification: {total - verified}")
        print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description='香港收據 OCR 數據集創建工具')
    parser.add_argument('--input', default='input', help='原始收據圖片資料夾')
    parser.add_argument('--processed', default='processed', help='處理結果資料夾')
    parser.add_argument('--crops', default='crops', help='切割區域資料夾')
    parser.add_argument('--dataset', default='dataset_gt',
                        help='最終數據集資料夾(gt.txt格式)')
    parser.add_argument('--mode', choices=['auto', 'generate', 'stats', 'all'],
                        default='auto', help='運行模式')
    parser.add_argument('--overwrite', action='store_true', help='覆蓋已有的標註')
    parser.add_argument('--auto-verify', action='store_true',
                        help='自動驗證所有標註(跳過手動檢查)')

    args = parser.parse_args()

    # 創建數據集創建器
    creator = ReceiptDatasetCreator(
        args.input, args.processed, args.crops, args.dataset, enable_correction=False)

    print("✨ 模式: 使用原圖直接進行 OCR")
    print("   - 不做任何圖像預處理")
    print("   - 只保留高信心度結果 (>= 0.5)")
    print("   - 切割文字區域用於訓練\n")

    if args.mode == 'auto':
        print("\n🤖 Mode: Auto-generate annotations")
        creator.auto_generate_annotations(overwrite=args.overwrite)
        creator.show_statistics()
        print("\n💡 Next step:")
        print("  Run with --mode generate --auto-verify to create training dataset")

    elif args.mode == 'generate':
        print("\n📦 Mode: Generate training dataset")

        # 如果啟用自動驗證,標記所有為已驗證
        if args.auto_verify:
            print("⚡ Auto-verify enabled: marking all annotations as verified")
            for anno in creator.annotations.values():
                anno['verified'] = True
            creator.save_annotations()

        creator.show_statistics()
        creator.generate_training_dataset()

    elif args.mode == 'all':
        print("\n🚀 Mode: Complete pipeline (auto + generate)")

        # Step 1: 自動標註
        print("\n" + "="*70)
        print("Step 1/2: Auto-generate annotations")
        print("="*70)
        creator.auto_generate_annotations(overwrite=args.overwrite)

        # Step 2: 自動驗證並生成數據集
        print("\n⚡ Auto-verify: marking all annotations as verified")
        for anno in creator.annotations.values():
            anno['verified'] = True
        creator.save_annotations()

        # Step 3: 生成數據集
        print("\n" + "="*70)
        print("Step 2/2: Generate training dataset")
        print("="*70)
        creator.generate_training_dataset()

        print("\n" + "="*70)
        print("✅ Complete pipeline finished!")
        print("="*70)

    elif args.mode == 'stats':
        creator.show_statistics()


if __name__ == '__main__':
    main()
