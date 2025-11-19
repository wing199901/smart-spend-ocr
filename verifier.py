#!/usr/bin/env python3
"""
香港收據 OCR 數據集快速驗證工具
輕量級網頁界面,快速驗證 EasyOCR 的識別結果
"""


import json
import base64
import shutil
import logging
from pathlib import Path
from flask import Flask, render_template, request, jsonify, abort
import cv2
from typing import List, Dict, Optional, Tuple

# 配置日誌
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class QuickVerifier:
    """輕量級驗證工具"""

    def __init__(self, processed_dir: str = "./processed", input_dir: str = "./input"):
        """
        初始化驗證器

        Args:
            processed_dir: 處理結果目錄路徑
            input_dir: 輸入圖片目錄路徑

        Raises:
            FileNotFoundError: 標註文件不存在
            json.JSONDecodeError: 標註文件格式錯誤
        """
        self.processed_dir = Path(processed_dir).resolve()
        self.input_dir = Path(input_dir).resolve()
        self.crops_dir = self.processed_dir / "crops"
        self.annotations_file = self.processed_dir / "annotations.json"
        self.deleted_dir = self.processed_dir / "deleted"

        # 創建所有必要的目錄
        self.processed_dir.mkdir(parents=True, exist_ok=True)
        self.deleted_dir.mkdir(parents=True, exist_ok=True)
        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.crops_dir.mkdir(parents=True, exist_ok=True)

        # 驗證文件存在
        if not self.annotations_file.exists():
            logger.warning(f"標註文件不存在，將創建新文件: {self.annotations_file}")
            self.annotations = {}
            self.save_annotations()
        else:
            # 載入標註
            try:
                with open(self.annotations_file, 'r', encoding='utf-8') as f:
                    self.annotations = json.load(f)
                logger.info(f"成功載入 {len(self.annotations)} 個標註")
            except json.JSONDecodeError as e:
                logger.error(f"標註文件格式錯誤: {e}")
                raise
            except Exception as e:
                logger.error(f"載入標註失敗: {e}")
                raise

        # 統計
        self.total_regions = sum(
            len(anno.get('ocr_results', []))
            for anno in self.annotations.values()
        )

        self.verified_regions = 0
        self.corrected_regions = 0

        # 自動檢測並處理 input 目錄中的新圖片
        self.process_input_folder()

    def process_input_folder(self):
        """自動處理 input 目錄中的新圖片"""
        try:
            # 檢查 input 目錄中的圖片
            image_files = list(self.input_dir.glob('*.jpg')) + \
                list(self.input_dir.glob('*.jpeg')) + \
                list(self.input_dir.glob('*.png'))

            if not image_files:
                logger.info("input 目錄中沒有新圖片")
                return

            # 過濾出未處理的圖片
            new_images = [
                img for img in image_files if img.name not in self.annotations]

            if not new_images:
                logger.info(f"input 目錄中的 {len(image_files)} 張圖片都已處理")
                return

            logger.info(f"發現 {len(new_images)} 張新圖片，開始自動處理...")

            # 導入並使用 ReceiptDatasetCreator 處理新圖片
            import sys
            sys.path.insert(0, str(Path(__file__).parent))
            from create_receipt_dataset import ReceiptDatasetCreator

            creator = ReceiptDatasetCreator()

            for img_path in new_images:
                try:
                    logger.info(f"處理: {img_path.name}")
                    annotation = creator.ocr_image(img_path)
                    creator.annotations[img_path.name] = annotation
                    self.annotations[img_path.name] = annotation
                    logger.info(
                        f"✓ {img_path.name}: 發現 {len(annotation.get('ocr_results', []))} 個文字區域")
                except Exception as e:
                    logger.error(f"處理 {img_path.name} 失敗: {e}")

            # 保存更新的標註
            creator.save_annotations()
            self.save_annotations()

            # 更新統計
            self.total_regions = sum(
                len(anno.get('ocr_results', []))
                for anno in self.annotations.values()
            )

            logger.info(f"✅ 成功處理 {len(new_images)} 張新圖片")

        except Exception as e:
            logger.error(f"自動處理 input 目錄失敗: {e}")

    def save_annotations(self):
        """保存標註到文件"""
        try:
            self.processed_dir.mkdir(parents=True, exist_ok=True)
            with open(self.annotations_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, ensure_ascii=False, indent=2)
            logger.info(f"保存標註: {self.annotations_file}")
        except Exception as e:
            logger.error(f"保存標註失敗: {e}")

    def get_verification_data(self) -> List[Dict]:
        """
        準備驗證數據

        返回格式:
        [
            {
                'image_name': 'receipt001.jpg',
                'region_idx': 0,
                'cropped_image': 'base64...',
                'text': 'SUPERNORMAL',
                'confidence': 0.95,
                'verified': False
            },
            ...
        ]

        Returns:
            驗證項目列表
        """
        verification_items = []

        for image_name, anno in self.annotations.items():
            for idx, ocr_result in enumerate(anno.get('ocr_results', [])):
                try:
                    text = ocr_result['text']
                    confidence = ocr_result['confidence']

                    # 使用已保存的裁切圖片
                    crop_filename = ocr_result.get('crop_filename')
                    if not crop_filename:
                        logger.warning(f"缺少 crop_filename: {image_name}_{idx}")
                        continue

                    crop_path = self.crops_dir / crop_filename
                    if not crop_path.exists():
                        logger.warning(f"裁切圖片不存在: {crop_path}")
                        continue

                    # 讀取裁切圖片
                    cropped = cv2.imread(str(crop_path))
                    if cropped is None:
                        logger.error(f"無法讀取裁切圖片: {crop_path}")
                        continue

                    if cropped.size == 0:
                        logger.warning(f"空白裁剪區域: {image_name}_{idx}")
                        continue

                    # 轉為 base64
                    _, buffer = cv2.imencode('.jpg', cropped)
                    img_base64 = base64.b64encode(buffer).decode('utf-8')

                    verification_items.append({
                        'id': f"{image_name}_{idx}",
                        'image_name': image_name,
                        'region_idx': idx,
                        'cropped_image': img_base64,
                        'text': text,
                        'confidence': confidence,
                        'verified': ocr_result.get('verified', False),
                        'corrected_text': ocr_result.get('corrected_text', None)
                    })
                except Exception as e:
                    logger.error(f"處理區域失敗 {image_name}_{idx}: {e}")
                    continue

        logger.info(f"準備了 {len(verification_items)} 個驗證項目")
        return verification_items

    def save_verification(self, updates: List[Dict]) -> bool:
        """
        保存驗證結果

        Args:
            updates: 更新列表，每項包含 image_name, region_idx, verified, corrected_text

        Returns:
            是否成功保存
        """
        try:
            for update in updates:
                # 驗證輸入
                if not isinstance(update, dict):
                    logger.error(f"無效的更新格式: {update}")
                    continue

                image_name = update.get('image_name')
                region_idx = update.get('region_idx')

                if not image_name or region_idx is None:
                    logger.error(f"缺少必要欄位: {update}")
                    continue

                if image_name in self.annotations:
                    ocr_results = self.annotations[image_name]['ocr_results']
                    if region_idx < len(ocr_results):
                        ocr_results[region_idx]['verified'] = update.get(
                            'verified', False)

                        corrected_text = update.get('corrected_text')
                        if corrected_text:
                            # 清理文字，防止 CSV 注入
                            corrected_text = corrected_text.strip()
                            corrected_text = corrected_text.replace(
                                '\n', ' ').replace('\r', '')

                            ocr_results[region_idx]['corrected_text'] = corrected_text
                            ocr_results[region_idx]['text'] = corrected_text
                            logger.info(f"修正文字: {image_name}_{region_idx}")

            # 備份原文件
            backup_file = self.annotations_file.with_suffix('.json.bak')
            shutil.copy2(self.annotations_file, backup_file)
            logger.info(f"備份標註文件: {backup_file}")

            # 保存
            with open(self.annotations_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, ensure_ascii=False, indent=2)

            logger.info(f"成功保存 {len(updates)} 個更新")
            return True

        except Exception as e:
            logger.error(f"保存驗證失敗: {e}")
            # 恢復備份
            backup_file = self.annotations_file.with_suffix('.json.bak')
            if backup_file.exists():
                shutil.copy2(backup_file, self.annotations_file)
                logger.info("已從備份恢復")
            return False

    def delete_regions(self, delete_items: List[Dict]) -> Tuple[bool, int]:
        """
        刪除指定的文字區域

        Args:
            delete_items: 要刪除的項目列表，每項包含 image_name, region_idx

        Returns:
            (是否成功, 刪除數量)
        """
        try:
            deleted_count = 0

            # 按圖片分組刪除項目
            delete_by_image = {}
            for item in delete_items:
                if not isinstance(item, dict):
                    logger.error(f"無效的刪除項目: {item}")
                    continue

                image_name = item.get('image_name')
                region_idx = item.get('region_idx')

                if not image_name or region_idx is None:
                    logger.error(f"缺少必要欄位: {item}")
                    continue

                if image_name not in delete_by_image:
                    delete_by_image[image_name] = []
                delete_by_image[image_name].append(region_idx)

            # 備份原文件
            backup_file = self.annotations_file.with_suffix('.json.bak')
            shutil.copy2(self.annotations_file, backup_file)
            logger.info(f"備份標註文件: {backup_file}")

            # 執行刪除
            for image_name, indices in delete_by_image.items():
                if image_name not in self.annotations:
                    logger.warning(f"圖片不存在於標註中: {image_name}")
                    continue

                ocr_results = self.annotations[image_name]['ocr_results']

                # 按降序排序，避免索引混亂
                indices_sorted = sorted(set(indices), reverse=True)

                for idx in indices_sorted:
                    if 0 <= idx < len(ocr_results):
                        deleted_region = ocr_results.pop(idx)
                        deleted_count += 1
                        logger.info(
                            f"刪除區域: {image_name}_{idx} - {deleted_region.get('text', '')}")
                    else:
                        logger.warning(f"無效的索引: {image_name}_{idx}")

                # 如果圖片沒有任何 OCR 結果了，移動圖片到 deleted 資料夾
                if len(ocr_results) == 0:
                    self._move_image_to_deleted(image_name)
                    del self.annotations[image_name]
                    logger.info(f"刪除整個圖片標註: {image_name}")

            # 保存更新後的標註
            with open(self.annotations_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, ensure_ascii=False, indent=2)

            # 更新統計
            self.total_regions -= deleted_count

            logger.info(f"成功刪除 {deleted_count} 個區域")
            return True, deleted_count

        except Exception as e:
            logger.error(f"刪除區域失敗: {e}")
            # 恢復備份
            backup_file = self.annotations_file.with_suffix('.json.bak')
            if backup_file.exists():
                shutil.copy2(backup_file, self.annotations_file)
                logger.info("已從備份恢復")
            return False, 0

    def _move_image_to_deleted(self, image_name: str) -> None:
        """
        將圖片移動到 deleted 資料夾

        Args:
            image_name: 圖片名稱
        """
        try:
            if image_name not in self.annotations:
                return

            anno = self.annotations[image_name]

            # 移動處理後的圖片
            processed_path = Path(anno.get('processed_image_path', ''))
            if processed_path.exists():
                dest = self.deleted_dir / processed_path.name
                shutil.move(str(processed_path), str(dest))
                logger.info(f"移動圖片到 deleted: {processed_path.name}")

            # 移動原始圖片
            original_path = Path(anno.get('original_image_path', ''))
            if original_path.exists():
                dest = self.deleted_dir / original_path.name
                shutil.move(str(original_path), str(dest))
                logger.info(f"移動原始圖片到 deleted: {original_path.name}")

        except Exception as e:
            logger.error(f"移動圖片失敗 {image_name}: {e}")

    def delete_image(self, image_name: str) -> bool:
        """
        刪除整個圖片及其所有標註

        Args:
            image_name: 圖片名稱

        Returns:
            是否成功刪除
        """
        try:
            if image_name not in self.annotations:
                logger.warning(f"圖片不存在: {image_name}")
                return False

            # 備份
            backup_file = self.annotations_file.with_suffix('.json.bak')
            shutil.copy2(self.annotations_file, backup_file)

            # 移動圖片
            self._move_image_to_deleted(image_name)

            # 刪除標註
            region_count = len(
                self.annotations[image_name].get('ocr_results', []))
            del self.annotations[image_name]

            # 保存
            with open(self.annotations_file, 'w', encoding='utf-8') as f:
                json.dump(self.annotations, f, ensure_ascii=False, indent=2)

            # 更新統計
            self.total_regions -= region_count

            logger.info(f"成功刪除圖片: {image_name} ({region_count} 個區域)")
            return True

        except Exception as e:
            logger.error(f"刪除圖片失敗 {image_name}: {e}")
            # 恢復備份
            backup_file = self.annotations_file.with_suffix('.json.bak')
            if backup_file.exists():
                shutil.copy2(backup_file, self.annotations_file)
                logger.info("已從備份恢復")
            return False


# Flask 應用
app = Flask(__name__)
verifier: Optional[QuickVerifier] = None


@app.route('/')
def index():
    """主頁面"""
    if verifier is None:
        abort(500, "Verifier not initialized")

    items = verifier.get_verification_data()

    # 按信心度排序 (低信心度優先)
    items_sorted = sorted(items, key=lambda x: x['confidence'])

    # 檢查 dataset_gt 和 dataset_lmdb 是否存在
    dataset_exists = (Path('./dataset_gt/train/gt.txt').exists())
    lmdb_exists = (Path('./dataset_lmdb/train').exists())

    stats = {
        'total': len(items),
        'verified': sum(1 for item in items if item['verified']),
        'low_confidence': sum(1 for item in items if item['confidence'] < 0.8),
        'dataset_exists': dataset_exists,
        'lmdb_exists': lmdb_exists,
    }

    return render_template('index.html', items=items_sorted, stats=stats)


@app.route('/api/verify', methods=['POST'])
def verify():
    """保存驗證結果"""
    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    data = request.json or {}
    if not isinstance(data, dict):
        return jsonify({'success': False, 'error': '無效的請求格式'}), 400

    updates = data.get('updates', [])

    success = verifier.save_verification(updates)

    return jsonify({'success': success})


@app.route('/api/batch_verify', methods=['POST'])
def batch_verify():
    """批量驗證 (標記為正確)"""
    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': '無效的請求數據'}), 400

        items = data.get('items', [])
        if not items:
            return jsonify({'success': False, 'error': '沒有要驗證的項目'}), 400

        updates = []
        for item in items:
            if not isinstance(item, dict):
                continue
            updates.append({
                'image_name': item.get('image_name'),
                'region_idx': item.get('region_idx'),
                'verified': True
            })

        success = verifier.save_verification(updates)

        return jsonify({'success': success, 'count': len(updates)})
    except Exception as e:
        logger.error(f"批量驗證失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/delete_regions', methods=['POST'])
def delete_regions():
    """刪除選中的文字區域"""
    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': '無效的請求數據'}), 400

        items = data.get('items', [])
        if not items:
            return jsonify({'success': False, 'error': '沒有要刪除的項目'}), 400

        # 驗證輸入
        delete_items = []
        for item in items:
            if not isinstance(item, dict):
                continue
            image_name = item.get('image_name')
            region_idx = item.get('region_idx')
            if image_name and region_idx is not None:
                delete_items.append({
                    'image_name': image_name,
                    'region_idx': region_idx
                })

        if not delete_items:
            return jsonify({'success': False, 'error': '沒有有效的刪除項目'}), 400

        success, count = verifier.delete_regions(delete_items)

        return jsonify({
            'success': success,
            'count': count,
            'message': f'成功刪除 {count} 個區域'
        })
    except Exception as e:
        logger.error(f"刪除區域失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/delete_image', methods=['POST'])
def delete_image():
    """刪除整個圖片"""
    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': '無效的請求數據'}), 400

        image_name = data.get('image_name')
        if not image_name:
            return jsonify({'success': False, 'error': '缺少圖片名稱'}), 400

        success = verifier.delete_image(image_name)

        return jsonify({
            'success': success,
            'message': f'成功刪除圖片: {image_name}' if success else '刪除失敗'
        })
    except Exception as e:
        logger.error(f"刪除圖片失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/upload', methods=['POST'])
def upload_image():
    """上傳收據圖片到 input/ 目錄並自動處理"""
    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '沒有上傳文件'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '文件名為空'}), 400

        # 檢查文件類型
        allowed_extensions = {'.jpg', '.jpeg', '.png'}
        file_ext = Path(file.filename).suffix.lower()
        if file_ext not in allowed_extensions:
            return jsonify({'success': False, 'error': f'不支持的文件類型: {file_ext}'}), 400

        # 保存到 input/ 目錄
        file_path = verifier.input_dir / file.filename
        file.save(str(file_path))
        logger.info(f"已上傳文件: {file.filename}")

        # 自動處理
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from create_receipt_dataset import ReceiptDatasetCreator

        creator = ReceiptDatasetCreator()
        annotation = creator.ocr_image(file_path)
        creator.annotations[file.filename] = annotation
        creator.save_annotations()

        # 重新載入 verifier 的標註
        verifier.annotations = creator.annotations

        return jsonify({
            'success': True,
            'message': f'成功上傳並處理: {file.filename}',
            'regions_found': len(annotation.get('ocr_results', []))
        })

    except Exception as e:
        logger.error(f"上傳處理失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/generate_dataset', methods=['POST'])
def generate_dataset():
    """生成訓練數據集（gt.txt 格式）"""
    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    try:
        # 檢查是否有已驗證的數據（檢查每個 OCR 結果）
        verified_count = 0
        for anno in verifier.annotations.values():
            for ocr_result in anno.get('ocr_results', []):
                if ocr_result.get('verified', False):
                    verified_count += 1

        if verified_count == 0:
            return jsonify({
                'success': False,
                'error': '沒有已驗證的數據！請先驗證至少一個文字區域。'
            }), 400

        # 調用數據集生成器
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from create_receipt_dataset import ReceiptDatasetCreator

        creator = ReceiptDatasetCreator()
        creator.annotations = verifier.annotations
        creator.generate_training_dataset()

        return jsonify({
            'success': True,
            'message': f'成功生成訓練數據集！已驗證 {verified_count} 個文字區域。',
            'verified_count': verified_count
        })

    except Exception as e:
        logger.error(f"生成數據集失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/convert_to_lmdb', methods=['POST'])
def convert_to_lmdb():
    """轉換 dataset 為 LMDB 格式"""
    import subprocess
    import sys

    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    try:
        dataset_dir = Path('./dataset_gt')
        lmdb_output_dir = Path('./dataset_lmdb')

        # 檢查 dataset_gt 目錄是否存在
        if not dataset_dir.exists():
            return jsonify({
                'success': False,
                'error': 'dataset_gt 目錄不存在！請先生成訓練數據集。'
            }), 400

        # 檢查 gt.txt 檔案
        train_gt = dataset_dir / 'train' / 'gt.txt'
        valid_gt = dataset_dir / 'valid' / 'gt.txt'
        test_gt = dataset_dir / 'test' / 'gt.txt'

        if not train_gt.exists():
            return jsonify({
                'success': False,
                'error': 'train/gt.txt 不存在！請先生成訓練數據集。'
            }), 400

        # 創建 LMDB 輸出目錄
        lmdb_output_dir.mkdir(parents=True, exist_ok=True)

        # 檢查 create_lmdb_dataset.py 腳本
        script_path = Path(
            './deep-text-recognition-benchmark/create_lmdb_dataset.py')
        if not script_path.exists():
            return jsonify({
                'success': False,
                'error': 'create_lmdb_dataset.py 不存在！'
            }), 400

        # 轉換所有資料集 (train, valid, test)
        splits_to_convert = []

        if train_gt.exists():
            splits_to_convert.append(('train', train_gt))
        if valid_gt.exists():
            splits_to_convert.append(('valid', valid_gt))
        if test_gt.exists():
            splits_to_convert.append(('test', test_gt))

        if not splits_to_convert:
            return jsonify({
                'success': False,
                'error': '沒有找到任何 gt.txt 檔案！'
            }), 400

        all_outputs = []

        for split_name, gt_file in splits_to_convert:
            # 執行轉換命令
            cmd = [
                sys.executable,
                str(script_path),
                str(dataset_dir / split_name),  # inputPath
                str(gt_file),                    # gtFile
                str(lmdb_output_dir / split_name)  # outputPath
            ]

            logger.info(f"執行 LMDB 轉換 ({split_name}): {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300  # 5分鐘超時
            )

            if result.returncode != 0:
                logger.error(f"LMDB 轉換失敗 ({split_name}): {result.stderr}")
                return jsonify({
                    'success': False,
                    'error': f'LMDB 轉換失敗 ({split_name}): {result.stderr}'
                }), 500

            logger.info(f"LMDB 轉換輸出 ({split_name}): {result.stdout}")
            all_outputs.append(f"✅ {split_name}: {result.stdout.strip()}")

        return jsonify({
            'success': True,
            'message': f'成功轉換 {len(splits_to_convert)} 個資料集為 LMDB 格式！',
            'output': '\n'.join(all_outputs)
        })

    except subprocess.TimeoutExpired:
        logger.error("LMDB 轉換超時")
        return jsonify({'success': False, 'error': '轉換超時！請檢查數據集大小。'}), 500
    except Exception as e:
        logger.error(f"LMDB 轉換失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reprocess_images', methods=['POST'])
def reprocess_images():
    """重新處理 input 目錄中的所有圖片（強制重新 OCR）"""
    if verifier is None:
        return jsonify({'success': False, 'error': 'Verifier not initialized'}), 500

    try:
        # 檢查 input 目錄
        image_files = list(verifier.input_dir.glob('*.jpg')) + \
            list(verifier.input_dir.glob('*.jpeg')) + \
            list(verifier.input_dir.glob('*.png'))

        if not image_files:
            return jsonify({
                'success': False,
                'error': 'input 目錄中沒有圖片！'
            }), 400

        logger.info(f"開始重新處理 {len(image_files)} 張圖片...")

        # 導入 ReceiptDatasetCreator
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from create_receipt_dataset import ReceiptDatasetCreator

        creator = ReceiptDatasetCreator()
        processed_count = 0
        failed_count = 0

        for img_path in image_files:
            try:
                logger.info(f"重新處理: {img_path.name}")
                annotation = creator.ocr_image(img_path)
                creator.annotations[img_path.name] = annotation
                verifier.annotations[img_path.name] = annotation
                processed_count += 1
                logger.info(
                    f"✓ {img_path.name}: 發現 {len(annotation.get('ocr_results', []))} 個文字區域")
            except Exception as e:
                logger.error(f"處理 {img_path.name} 失敗: {e}")
                failed_count += 1

        # 保存更新的標註
        creator.save_annotations()
        verifier.save_annotations()

        # 更新統計
        verifier.total_regions = sum(
            len(anno.get('ocr_results', []))
            for anno in verifier.annotations.values()
        )

        return jsonify({
            'success': True,
            'message': f'重新處理完成！\n成功: {processed_count}\n失敗: {failed_count}',
            'processed': processed_count,
            'failed': failed_count
        })

    except Exception as e:
        logger.error(f"重新處理失敗: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


def main():
    import argparse

    parser = argparse.ArgumentParser(description='快速驗證工具')
    parser.add_argument('--processed', default='./processed', help='處理結果目錄')
    parser.add_argument('--input', default='./input', help='輸入圖片目錄')
    parser.add_argument('--port', type=int, default=5001, help='伺服器端口')

    args = parser.parse_args()

    global verifier
    verifier = QuickVerifier(args.processed, args.input)

    print("\n" + "="*70)
    print("🚀 香港收據 OCR 驗證工具啟動!")
    print("="*70)
    print(f"\n📊 統計:")
    print(f"   總文字區域: {verifier.total_regions}")
    print(f"   輸入目錄: {verifier.input_dir}")
    print(f"   處理目錄: {verifier.processed_dir}")
    print(f"\n🌐 打開瀏覽器訪問:")
    print(f"   http://localhost:{args.port}")
    print(f"\n💡 工作流程:")
    print(f"   1. 上傳收據圖片 → 自動 OCR")
    print(f"   2. 人工驗證和修正")
    print(f"   3. 生成訓練數據集")
    print(f"\n⌨️  快捷鍵:")
    print(f"   Ctrl+S: 保存所有變更")
    print(f"   Delete: 刪除選中項")
    print("\n" + "="*70 + "\n")

    app.run(host='0.0.0.0', port=args.port, debug=True)


if __name__ == '__main__':
    main()
