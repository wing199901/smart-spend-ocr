# 香港收據 OCR 訓練系統

一個完整的收據 OCR 端到端工作流程：**Web UI 上傳 → 自動 OCR → 人工驗證 → 一鍵生成數據集 → 一鍵轉換 LMDB → 訓練模型**

## 🎯 核心特點

- ✅ **Web UI 操作** - 簡單直觀，無需命令行
- ✅ **自動處理** - 放入圖片即自動 OCR,切割文字區域
- ✅ **實時更新** - 刷新頁面自動處理新圖片
- ✅ **智能驗證** - 可視化界面修正錯誤,Enter 鍵快速導航
- ✅ **一鍵生成** - 驗證完成後一鍵生成訓練數據集
- ✅ **一鍵轉換** - Web UI 直接轉換 LMDB,無需命令行
- ✅ **標準格式** - 生成 deep-text-recognition-benchmark 標準 gt.txt 格式
- ✅ **智能分割** - 按文字區域 (crop) 分割數據集,比例 7:1.5:1.5

## 🚀 快速開始

### 安裝

```bash
# 克隆項目並初始化 submodule
git clone https://github.com/your-repo/smart-spend-ocr.git
cd smart-spend-ocr
git submodule update --init --recursive

# 創建虛擬環境並安裝依賴
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install easyocr opencv-python numpy flask lmdb pillow fire torch torchvision
```

### 使用流程（完全 Web UI,無需命令行！）

```bash
# Step 1: 啟動驗證工具
python verifier.py

# Step 2: 打開瀏覽器 http://localhost:5001
#   ✅ 上傳收據圖片 (或放入 input/ 目錄後刷新頁面)
#   ✅ 驗證和修正 OCR 結果
#   ✅ 點擊「🎯 生成訓練數據集」
#   ✅ 點擊「📦 轉換 LMDB 格式」← 新功能!

# Step 3: 開始訓練
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
├── create_receipt_dataset.py         # 核心處理邏輯
├── verifier.py                       # Web UI 主程序
├── validate_lmdb.py                  # LMDB 驗證工具
│
├── templates/                        # Web UI 模板
│   └── index.html
│
├── static/                          # Web UI 靜態文件
│   └── app.js
│
├── input/                           # ← 放入原始收據圖片
│   └── receipt001.jpg
│
├── processed/                       # ← OCR 處理結果
│   ├── annotations.json            # OCR 結果 + 驗證狀態
│   ├── original_images/            # 原始圖片備份
│   ├── crops/                      # 切割的文字區域
│   │   ├── receipt001_crop_000.jpg
│   │   ├── receipt001_crop_001.jpg
│   │   └── ...
│   └── deleted/                    # 已刪除的圖片和 crops
│
├── dataset_gt/                      # ← 驗證完成的訓練數據 (gt.txt 格式)
│   ├── train/
│   │   ├── gt.txt                  # ← tab 分隔格式
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
│   ├── valid/
│   └── test/
│
└── deep-text-recognition-benchmark/ # ← 訓練框架 (submodule)
    ├── train.py
    ├── create_lmdb_dataset.py
    └── ...
```

## 🔄 工作流程圖

```
┌─────────────────┐
│ 放入圖片到 input/ │
│ 或 Web UI 上傳  │
└────────┬────────┘
         │
         v
┌─────────────────┐
│   自動 OCR      │  ← EasyOCR (刷新頁面觸發)
│   切割文字區域   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│   人工驗證      │  ← Web UI
│ • 修正錯誤文字   │
│ • 刪除無效區域   │
│ • Enter 快速導航 │
│ • 實時統計更新   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  生成數據集      │  ← 點擊「🎯 生成訓練數據集」
│ • 7:1.5:1.5 分割 │
│ • 按 crop 分割   │
│ • 生成 gt.txt    │
└────────┬────────┘
         │
         v
┌─────────────────┐
│  轉換 LMDB      │  ← 點擊「📦 轉換 LMDB 格式」
│ • train/valid/test│
│ • 自動轉換全部   │
└────────┬────────┘
         │
         v
┌─────────────────┐
│   訓練模型       │  ← 命令行
└─────────────────┘
```

## 💡 Web UI 使用說明

### 1. 啟動服務

```bash
python verifier.py
```

打開瀏覽器訪問 `http://localhost:5001`

### 2. 添加收據圖片（兩種方式）

**方式 A: Web UI 上傳**
- 點擊「📤 上傳收據」按鈕
- 選擇收據圖片（支持 JPG/PNG）

**方式 B: 放入 input/ 目錄** ← 推薦!
- 將收據圖片複製到 `input/` 目錄
- 刷新瀏覽器頁面
- 系統自動處理新圖片

系統自動完成:
- ✅ OCR 識別文字
- ✅ 切割文字區域到 `processed/crops/`
- ✅ 過濾低信心度結果 (< 0.5)
- ✅ 保存原圖到 `processed/original_images/`

### 3. 驗證和修正

**單個操作:**
- 📝 修正文字: 點擊文字框直接編輯
- ✅ 驗證: 勾選「已驗證」或點擊「💾 保存」
- 🗑️ 刪除: 點擊「🗑️ 刪除」移除無效區域
- ⌨️ Enter 鍵: 保存並跳到下一個輸入框

**篩選和排序:**
- 🔍 篩選: 全部/未驗證/已驗證/低信心度
- 📊 排序: 信心度(低→高)/信心度(高→低)/未驗證優先/已驗證優先

**批量操作:**
- ☑️ 全選 - 選擇所有可見項
- 批量操作下拉選單:
  - ✓ 批量驗證 - 驗證選中的項
  - 🗑️ 批量刪除 - 刪除選中的項
  - 💾 保存全部 - 保存選中的修改

**快捷鍵:**
- `Ctrl+S` - 保存所有變更
- `Delete` - 刪除選中的項

### 4. 生成訓練數據集

- 確保至少驗證了一些文字區域
- 點擊「🎯 生成訓練數據集」
- 系統自動:
  - 按文字區域 (crop) 分割數據集
  - 比例 7:1.5:1.5 (train:valid:test)
  - 生成 `dataset_gt/train/gt.txt`
  - 複製圖片到對應目錄
- 實時顯示進度和結果

### 5. 轉換 LMDB 格式 ← 新功能!

- 點擊「📦 轉換 LMDB 格式」
- 系統自動:
  - 轉換 train/valid/test 全部三個數據集
  - 生成到 `dataset_lmdb/` 目錄
  - 顯示每個數據集的轉換結果
- 無需任何命令行操作!

### 6. 驗證 LMDB（可選）

```bash
# 驗證生成的 LMDB
python validate_lmdb.py ./dataset_lmdb/train
python validate_lmdb.py ./dataset_lmdb/valid
python validate_lmdb.py ./dataset_lmdb/test
```

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

**A:** 新版本使用 `dataset_gt/` 目錄。如果你有舊的 `dataset/` 可以:
- 保留作為備份
- 刪除: `rm -rf dataset/`
- 重命名: `mv dataset dataset_old`

### Q: 放入圖片到 input/ 後沒反應？

**A:** 刷新瀏覽器頁面! 系統會在每次訪問首頁時自動處理新圖片。

### Q: crops/ 目錄在哪裡？

**A:** 新版本將 crops 移到 `processed/crops/`,所有 OCR 相關文件都在 `processed/` 目錄下。

### Q: 刪除區域後 crop 圖片還在？

**A:** 已修復! 刪除的 crop 會移動到 `processed/deleted/` 目錄,不會留在 crops/ 中。

### Q: 驗證後統計數據沒更新？

**A:** 已修復! 現在點擊驗證框或保存按鈕會立即更新頂部的統計和進度條。

### Q: 數據集比例是多少？

**A:** 當前使用 **7:1.5:1.5** (train:valid:test)，適合中小數據集。
- 對於 202 個 crops: Train=141, Valid=30, Test=31

### Q: 為什麼按 crop 分割而不是按圖片？

**A:** 按 crop 分割更合理:
- ✅ 每個 crop 是獨立的訓練樣本
- ✅ 分佈更均勻
- ✅ Valid/Test 數據量足夠評估

### Q: LMDB 轉換失敗？

**A:** 檢查:
1. 是否已生成 `dataset_gt/train/gt.txt`
2. 查看瀏覽器控制台錯誤信息
3. 使用 `python validate_lmdb.py ./dataset_lmdb/train` 驗證

### Q: gt.txt 格式錯誤？

**A:** 確認:
```bash
# 確認是 UTF-8 編碼
file -I dataset_gt/train/gt.txt

# 確認是 tab 分隔（不是空格）
cat dataset_gt/train/gt.txt | head
```

### Q: 記憶體不足？

**A:** 
- 減少 `batch_size`
- 使用較小的模型（VGG 代替 ResNet）
- 分批處理圖片（每次處理 10-20 張）

## 📚 命令行工具（可選）

如果你更喜歡命令行，仍可使用 `create_receipt_dataset.py`:

```bash
# 批量處理 input/ 目錄中的所有圖片
python create_receipt_dataset.py --mode auto

# 生成數據集
python create_receipt_dataset.py --mode generate --auto-verify

# 一鍵完成（處理 + 生成）
python create_receipt_dataset.py --mode all
```

**推薦使用 Web UI,更直觀且功能更完整!**

## 🧪 驗證工具

### 驗證 LMDB 數據集

```bash
# 驗證單個數據集
python validate_lmdb.py ./dataset_lmdb/train

# 驗證所有數據集
for split in train valid test; do
    echo "=== 驗證 $split ==="
    python validate_lmdb.py ./dataset_lmdb/$split
done
```

輸出示例:
```
======================================================================
📦 LMDB 驗證: train
======================================================================
📊 總樣本數: 141

📝 前 10 個樣本:
----------------------------------------------------------------------
  [  1] SUPERNORMAL                                        (12,345 bytes)
  [  2] 總計                                               (8,901 bytes)
  ... 還有 131 個樣本

🔍 檢查數據完整性...
✅ 所有數據完整!
======================================================================
```

## 🗑️ 清理未使用的文件

新版本不需要以下文件，可以刪除:

```bash
# 舊的學習 notebook
rm -f workspace_step*.ipynb test.ipynb

# 如果不需要命令行訓練
rm -rf trainer/

# 舊的目錄結構（如果存在）
rm -rf verifier/  # verifier.py 現在在根目錄

# macOS 系統文件
find . -name ".DS_Store" -delete

# Python 緩存
find . -type d -name "__pycache__" -exec rm -rf {} +
```

## 🎓 進階技巧

### 批量處理大量圖片

```bash
# 1. 將圖片分批放入 input/ 目錄（每次 10-20 張）
# 2. 刷新瀏覽器 → 自動處理
# 3. 驗證完成後,再放入下一批
```

### 自定義數據集分割比例

編輯 `create_receipt_dataset.py`:
```python
def generate_training_dataset(self, 
                             train_ratio: float = 0.7,   # 修改這裡
                             valid_ratio: float = 0.15,  # 修改這裡
                             ...)
```

### 使用預訓練模型 Fine-tuning

```bash
cd deep-text-recognition-benchmark
python train.py \
    --train_data ../dataset_lmdb/train \
    --valid_data ../dataset_lmdb/valid \
    --saved_model pretrained_model.pth \
    --FT \
    --Transformation TPS \
    --FeatureExtraction ResNet \
    --SequenceModeling BiLSTM \
    --Prediction Attn
```

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
