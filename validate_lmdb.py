#!/usr/bin/env python3
"""
驗證 LMDB 數據集
檢查 LMDB 是否正確生成,並顯示統計資訊
"""

import lmdb
import sys
from pathlib import Path


def validate_lmdb(lmdb_path: str):
    """
    驗證 LMDB 數據集

    Args:
        lmdb_path: LMDB 目錄路徑
    """
    lmdb_path = Path(lmdb_path)

    if not lmdb_path.exists():
        print(f"❌ LMDB 路徑不存在: {lmdb_path}")
        return False

    try:
        # 打開 LMDB 環境
        env = lmdb.open(str(lmdb_path), max_readers=32, readonly=True, lock=False,
                        readahead=False, meminit=False)

        with env.begin(write=False) as txn:
            # 獲取數據集大小
            n_samples = int(txn.get('num-samples'.encode()).decode('utf-8'))

            print(f"\n{'='*70}")
            print(f"📦 LMDB 驗證: {lmdb_path.name}")
            print(f"{'='*70}")
            print(f"📊 總樣本數: {n_samples}")

            # 顯示前 10 個樣本
            print(f"\n📝 前 10 個樣本:")
            print(f"{'-'*70}")

            for i in range(min(10, n_samples)):
                img_key = f'image-{i+1:09d}'.encode()
                label_key = f'label-{i+1:09d}'.encode()

                img_data = txn.get(img_key)
                label_data = txn.get(label_key)

                if img_data and label_data:
                    label = label_data.decode('utf-8')
                    img_size = len(img_data)
                    print(f"  [{i+1:3d}] {label[:50]:<50} ({img_size:,} bytes)")
                else:
                    print(f"  [{i+1:3d}] ❌ 數據缺失")

            if n_samples > 10:
                print(f"  ... 還有 {n_samples - 10} 個樣本")

            # 檢查數據完整性
            print(f"\n🔍 檢查數據完整性...")
            missing_count = 0
            empty_label_count = 0

            for i in range(n_samples):
                img_key = f'image-{i+1:09d}'.encode()
                label_key = f'label-{i+1:09d}'.encode()

                img_data = txn.get(img_key)
                label_data = txn.get(label_key)

                if not img_data or not label_data:
                    missing_count += 1
                elif not label_data.decode('utf-8').strip():
                    empty_label_count += 1

            if missing_count == 0 and empty_label_count == 0:
                print(f"✅ 所有數據完整!")
            else:
                if missing_count > 0:
                    print(f"⚠️  缺失數據: {missing_count} 個樣本")
                if empty_label_count > 0:
                    print(f"⚠️  空白標籤: {empty_label_count} 個樣本")

            print(f"\n{'='*70}")
            print(f"✅ LMDB 驗證完成!")
            print(f"{'='*70}\n")

            return True

    except Exception as e:
        print(f"❌ 驗證失敗: {e}")
        return False
    finally:
        env.close()


def main():
    """主函數"""
    if len(sys.argv) < 2:
        print("使用方法:")
        print("  python validate_lmdb.py <lmdb_path>")
        print("\n範例:")
        print("  python validate_lmdb.py ./dataset_lmdb/train")
        print("  python validate_lmdb.py ./dataset_lmdb/valid")
        print("  python validate_lmdb.py ./dataset_lmdb/test")
        sys.exit(1)

    lmdb_path = sys.argv[1]
    success = validate_lmdb(lmdb_path)

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
