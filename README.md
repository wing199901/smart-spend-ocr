# 香港收據 OCR 訓練系統

一個完整的收據 OCR 端到端工作流程：**Web UI 上傳 → 自動 OCR → 人工驗證 → 一鍵生成數據集 → 訓練模型**

## 🎯 核心特點

- ✅ **Web UI 操作** - 簡單直觀，無需命令行
- ✅ **自動切割** - OCR 後自動切割文字區域
- ✅ **實時處理** - 上傳即處理，即時查看結果
- ✅ **人工驗證** - 可視化界面修正錯誤
- ✅ **一鍵生成** - 驗證完成後一鍵生成訓練數據集
- ✅ **標準格式** - 生成 deep-text-recognition-benchmark 標準 gt.txt 格式

## 🚀 快速開始

### 安裝

```bash
# 克隆項目並初始化 submodule
git clone https://github.com/your-repo/smart-spend-ocr.git
cd smart-spend-ocr
git submodule update --init --recursive

# 創建虛擬環境並安裝依賴
python -m venv .venv
source .venv/bin/activate
pip install easyocr opencv-python numpy flask lmdb pillow fire torch torchvision
```

### 使用流程（3 步完成）

```bash
# Step 1: 啟動驗證工具
cd verifier
python verifier.py

# Step 2: 打開瀏覽器 http://localhost:5001
#   - 上傳收據圖片
#   - 驗證和修正 OCR 結果
#   - 點擊「生成訓練數據集」

# Step 3: 轉換為 LMDB 並訓練
cd ..
python deep-text-recognition-benchmark/create_lmdb_dataset.py \
    --inputPath dataset/train \
    --gtFile dataset/train/gt.txt \
    --outputPath dataset_lmdb/train

python deep-text-recognition-benchmark/create_lmdb_dataset.py \
    --inputPath dataset/valid \
    --gtFile dataset/valid/gt.txt \
    --outputPath dataset_lmdb/valid

cd deep-text-recognition-benchmark
python train.py \
    --train_data ../dataset_lmdb/train \
    --valid_data ../dataset_lmdb/valid \
    --Transformation TPS \
    --FeatureExtraction ResNet \
    --SequenceModeling BiLSTM \
    --Prediction Attn
```

## 📁 目錄結構

```
smart-spend-ocr/
├── README.md
├── create_receipt_dataset.py         # 命令行工具（可選）
│
├── input/                            # ← 用戶上傳的原始收據
│   └── receipt001.jpg
│
├── processed/                        # ← OCR 處理結果
│   ├── annotations.json             # OCR 結果 + 驗證狀態
│   └── images/                      # 完整收據備份
│
├── crops/                           # ← 切割的文字區域
│   ├── receipt001_crop_000.jpg
│   ├── receipt001_crop_001.jpg
│   └── ...
│
├── dataset/                         # ← 驗證完成的訓練數據
│   ├── train/
│   │   ├── gt.txt                   # ← tab 分隔格式
│   │   └── *.jpg
│   ├── valid/
│   │   ├── gt.txt
│   │   └── *.jpg
│   └── test/
│       ├── gt.txt
│       └── *.jpg
│
├── dataset_lmdb/                    # ← LMDB 格式（訓練用）
│   ├── train/
│   └── valid/
│
├── verifier/                        # ← Web UI 驗證工具
│   └── verifier.py
│
└── deep-text-recognition-benchmark/ # ← 訓練框架 (submodule)
    ├── train.py
    ├── create_lmdb_dataset.py
    └── ...
```

## 🔄 工作流程圖

```
┌─────────────┐
│ 用戶上傳收據  │
│  (Web UI)   │
└──────┬──────┘
       │
       v
┌─────────────┐
│  自動 OCR    │  ← EasyOCR
│  切割區域    │
└──────┬──────┘
       │
       v
┌─────────────┐
│  人工驗證    │  ← Web UI
│  修正錯誤    │
└──────┬──────┘
       │
       v
┌─────────────┐
│ 生成數據集   │  ← 點擊按鈕
│  gt.txt     │
└──────┬──────┘
       │
       v
┌─────────────┐
│ 轉換 LMDB   │  ← 命令行
└──────┬──────┘
       │
       v
┌─────────────┐
│   訓練模型   │
└─────────────┘
```

## 💡 Web UI 使用說明

### 1. 啟動服務

```bash
cd verifier
python verifier.py
```

打開瀏覽器訪問 `http://localhost:5001`

### 2. 上傳收據

- 點擊「📤 上傳收據」按鈕
- 選擇收據圖片（支持 JPG/PNG）
- 系統自動：
  - OCR 識別文字
  - 切割文字區域
  - 過濾低信心度結果 (< 0.5)
  - 保存到 `crops/` 目錄

### 3. 驗證和修正

- 查看每個切割的文字區域
- 如果文字錯誤：點擊文字框修改
- 如果整個區域錯誤：點擊「🗑️ 刪除」
- 確認正確：勾選「✓ 驗證」

**批量操作：**
- ☑️ 全選 - 選擇所有可見項
- ✓ 批量驗證 - 驗證選中的項
- 🗑️ 批量刪除 - 刪除選中的項

### 4. 生成數據集

- 確保至少驗證了一張圖片
- 點擊「🎯 生成訓練數據集」
- 系統自動：
  - 分割訓練集/驗證集/測試集 (8:1:1)
  - 生成 `dataset/train/gt.txt`
  - 複製驗證過的圖片到對應目錄

## 📊 數據格式

### gt.txt 格式（Tab 分隔）

```
receipt001_crop_000.jpg	SUPERNORMAL
receipt001_crop_001.jpg	總計
receipt001_crop_002.jpg	$245.00
```

### annotations.json 格式

```json
{
  "receipt001.jpg": {
    "image_name": "receipt001.jpg",
    "ocr_results": [
      {
        "bbox": [[x1, y1], [x2, y2], [x3, y3], [x4, y4]],
        "text": "SUPERNORMAL",
        "confidence": 0.95,
        "crop_filename": "receipt001_crop_000.jpg"
      }
    ],
    "verified": true,
    "timestamp": "2025-11-19T10:30:00"
  }
}
```

## 🎓 訓練參數說明

### 推薦配置

**小數據集 (< 5K 樣本):**
```bash
python train.py \
    --train_data ../dataset_lmdb/train \
    --valid_data ../dataset_lmdb/valid \
    --Transformation None \
    --FeatureExtraction VGG \
    --SequenceModeling BiLSTM \
    --Prediction CTC \
    --batch_size 64 \
    --num_iter 50000
```

**中數據集 (5K-50K 樣本):**
```bash
python train.py \
    --train_data ../dataset_lmdb/train \
    --valid_data ../dataset_lmdb/valid \
    --Transformation TPS \
    --FeatureExtraction ResNet \
    --SequenceModeling BiLSTM \
    --Prediction Attn \
    --batch_size 32 \
    --num_iter 100000
```

**Fine-tuning 預訓練模型:**
```bash
python train.py \
    --train_data ../dataset_lmdb/train \
    --valid_data ../dataset_lmdb/valid \
    --Transformation TPS \
    --FeatureExtraction ResNet \
    --SequenceModeling BiLSTM \
    --Prediction Attn \
    --saved_model saved_models/chinese.pth \
    --FT \
    --batch_size 32
```

## 🔍 常見問題

### Q: 需要刪除舊的 dataset/ 目錄嗎？

**A:** 不需要！新的工作流程使用不同的目錄結構：
- `input/` - 原始上傳
- `processed/` - OCR 結果
- `crops/` - 切割區域
- `dataset/` - 最終數據集

如果你之前使用舊版本，可以保留舊的 `dataset/` 作為備份，或移到其他位置。

### Q: 上傳後沒有反應？

**A:** 檢查：
1. 圖片格式是否為 JPG/PNG
2. 瀏覽器控制台是否有錯誤
3. 終端是否顯示 OCR 處理信息

### Q: 驗證後找不到圖片？

**A:** 確保：
1. 已勾選「✓ 驗證」
2. 至少有一張圖片被驗證
3. 點擊「💾 保存所有變更」

### Q: gt.txt 格式錯誤？

**A:** 檢查：
```bash
# 確認是 UTF-8 編碼
file -I dataset/train/gt.txt

# 確認是 tab 分隔（不是空格）
cat dataset/train/gt.txt | head
```

### Q: 記憶體不足？

**A:** 
- 減少 `batch_size`
- 使用較小的模型（VGG 代替 ResNet）
- 分批上傳和處理圖片

## 📚 命令行工具（可選）

如果你更喜歡命令行，仍可使用：

```bash
# 批量處理 input/ 目錄中的所有圖片
python create_receipt_dataset.py --mode auto

# 生成數據集
python create_receipt_dataset.py --mode generate --auto-verify

# 一鍵完成
python create_receipt_dataset.py --mode all
```

## 🗑️ 清理未使用的文件

新的工作流程不需要以下文件，可以刪除：

```bash
# 舊的學習 notebook
rm workspace_step*.ipynb test.ipynb

# 如果不需要命令行訓練
rm -rf trainer/

# macOS 系統文件
find . -name ".DS_Store" -delete

# Python 緩存
find . -type d -name "__pycache__" -exec rm -rf {} +
```

詳細清單見 `FILES_TO_DELETE.md`

## 📖 相關資源

- [EasyOCR](https://github.com/JaidedAI/EasyOCR) - OCR 引擎
- [deep-text-recognition-benchmark](https://github.com/clovaai/deep-text-recognition-benchmark) - 訓練框架
- [EasyOCR Model Hub](https://jaided.ai/easyocr/modelhub/) - 預訓練模型

## 🤝 貢獻

歡迎提交 Issue 和 Pull Request！

## 📄 授權

MIT License

---

**💡 提示：建議至少準備 500-1000 張收據圖片才能訓練出好的模型。數據質量比數量更重要！**
