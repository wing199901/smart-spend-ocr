// 在頁面載入時恢復過濾器狀態
document.addEventListener('DOMContentLoaded', function () {
    loadFilterState();
});

function focusNextInput(currentInput) {
    // 獲取所有可見的輸入框
    const allInputs = Array.from(document.querySelectorAll('.item-input'))
        .filter(input => {
            const card = input.closest('.item-card');
            return card && card.style.display !== 'none';
        });

    // 找到當前輸入框的索引
    const currentIndex = allInputs.indexOf(currentInput);

    // 跳到下一個輸入框
    if (currentIndex >= 0 && currentIndex < allInputs.length - 1) {
        setTimeout(() => {
            allInputs[currentIndex + 1].focus();
            allInputs[currentIndex + 1].select();
        }, 100);  // 短暫延遲確保保存完成
    }
}

function saveFilterState() {
    const filterSelect = document.getElementById('filterSelect');
    if (filterSelect) {
        localStorage.setItem('verifierFilterState', filterSelect.value);
    }
}

function loadFilterState() {
    const saved = localStorage.getItem('verifierFilterState');
    const filterSelect = document.getElementById('filterSelect');

    if (saved && filterSelect) {
        filterSelect.value = saved;
        filterItems();
    }
}

function executeBatchAction() {
    const select = document.getElementById('batchActionSelect');
    const action = select.value;

    if (!action) return;

    switch (action) {
        case 'verify':
            batchVerifySelected();
            break;
        case 'delete':
            batchDeleteSelected();
            break;
        case 'save-all':
            saveAll();
            break;
    }

    // 重置下拉選單
    select.value = '';
}

function selectAll() {
    const visibleCards = Array.from(document.querySelectorAll('.item-card'))
        .filter(card => card.style.display !== 'none');

    const allSelected = visibleCards.every(card =>
        card.querySelector('.select-checkbox').checked
    );

    // 切換選擇狀態
    visibleCards.forEach(card => {
        card.querySelector('.select-checkbox').checked = !allSelected;
    });

    // 更新按鈕文字
    updateSelectAllButton();
}

function updateSelectAllButton() {
    const visibleCards = Array.from(document.querySelectorAll('.item-card'))
        .filter(card => card.style.display !== 'none');

    const allSelected = visibleCards.every(card =>
        card.querySelector('.select-checkbox').checked
    );

    const btn = document.querySelector('button[onclick="selectAll()"]');
    if (btn) {
        btn.textContent = allSelected ? '◻️ 取消全選' : '☑️ 全選';
    }
}

// 監聽 checkbox 變化以更新按鈕狀態
document.addEventListener('change', function (e) {
    if (e.target.classList.contains('select-checkbox')) {
        updateSelectAllButton();
    }
});

function filterItems() {
    const filterSelect = document.getElementById('filterSelect');
    if (!filterSelect) return;

    const filterValue = filterSelect.value;

    document.querySelectorAll('.item-card').forEach(card => {
        const isVerified = card.dataset.verified === 'true';
        const isLowConf = parseFloat(card.dataset.confidence) < 0.8;

        let show = false;

        switch (filterValue) {
            case 'all':
                show = true;
                break;
            case 'verified':
                show = isVerified;
                break;
            case 'unverified':
                show = !isVerified;
                break;
            case 'low-confidence':
                show = isLowConf;
                break;
        }

        card.style.display = show ? 'block' : 'none';
    });

    // 更新全選按鈕狀態
    updateSelectAllButton();
}

function batchVerifySelected() {
    const selected = [];
    document.querySelectorAll('.select-checkbox:checked').forEach(cb => {
        const card = cb.closest('.item-card');
        const id = card.dataset.id;
        const parts = id.split('_');
        const regionIdx = parts.pop();
        const imageName = parts.join('_');

        selected.push({
            image_name: imageName,
            region_idx: parseInt(regionIdx)
        });
        card.querySelector('.verify-checkbox').checked = true;
        cb.checked = false;
    });

    if (selected.length === 0) {
        alert('請先選擇要驗證的項目!');
        return;
    }

    fetch('/api/batch_verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: selected })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert('✓ 已驗證 ' + data.count + ' 個項目!');
                location.reload();
            } else {
                alert('❌ 驗證失敗: ' + (data.error || '未知錯誤'));
            }
        })
        .catch(error => {
            alert('❌ 批量驗證失敗: ' + error);
        });
}

function batchDeleteSelected() {
    const selected = [];
    document.querySelectorAll('.select-checkbox:checked').forEach(cb => {
        const card = cb.closest('.item-card');
        const id = card.dataset.id;
        const parts = id.split('_');
        const regionIdx = parts.pop();
        const imageName = parts.join('_');

        selected.push({
            image_name: imageName,
            region_idx: parseInt(regionIdx)
        });
    });

    if (selected.length === 0) {
        alert('請先選擇要刪除的項目!');
        return;
    }

    if (!confirm('確定要刪除 ' + selected.length + ' 個項目嗎?\n此操作無法撤銷!')) {
        return;
    }

    fetch('/api/delete_regions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ items: selected })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert('✓ 已刪除 ' + data.count + ' 個項目!');
                location.reload();
            } else {
                alert('❌ 刪除失敗: ' + (data.error || '未知錯誤'));
            }
        })
        .catch(error => {
            alert('❌ 批量刪除失敗: ' + error);
        });
}

function deleteItem(button, imageName, regionIdx) {
    if (!confirm('確定要刪除此項目嗎?\n圖片: ' + imageName + '\n區域: ' + regionIdx + '\n\n此操作無法撤銷!')) {
        return;
    }

    // 禁用按鈕防止重複點擊
    button.disabled = true;
    button.textContent = '刪除中...';

    fetch('/api/delete_regions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            items: [{
                image_name: imageName,
                region_idx: regionIdx
            }]
        })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                // 移除卡片元素，不需要重新載入整個頁面
                const card = button.closest('.item-card');
                card.style.opacity = '0';
                card.style.transform = 'scale(0.8)';
                setTimeout(() => {
                    card.remove();
                }, 300);
            } else {
                alert('❌ 刪除失敗: ' + (data.error || '未知錯誤'));
                button.disabled = false;
                button.innerHTML = '🗑️ 刪除';
            }
        })
        .catch(error => {
            alert('❌ 刪除失敗: ' + error);
            button.disabled = false;
            button.innerHTML = '🗑️ 刪除';
        });
}

function saveItem(button, imageName, regionIdx) {
    // 禁用按鈕防止重複點擊
    button.disabled = true;
    button.textContent = '⏳ 保存中...';

    const card = button.closest('.item-card');
    const input = card.querySelector('.item-input');
    const verifyCheckbox = card.querySelector('.verify-checkbox');
    const originalText = input.dataset.original;
    const currentText = input.value;

    // 保存時自動標記為已驗證
    verifyCheckbox.checked = true;

    const update = {
        image_name: imageName,
        region_idx: regionIdx,
        verified: true,  // 保存時自動驗證
        corrected_text: currentText !== originalText ? currentText : null
    };

    fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: [update] })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                // 更新視覺反饋
                button.textContent = '✓ 已保存';
                button.classList.remove('btn-primary');
                button.classList.add('btn-success');

                // 2秒後恢復按鈕
                setTimeout(() => {
                    button.disabled = false;
                    button.textContent = '💾 保存';
                    button.classList.remove('btn-success');
                    button.classList.add('btn-primary');
                }, 2000);

                // 更新卡片狀態為已驗證
                card.classList.add('verified');
                card.dataset.verified = 'true';
            } else {
                alert('❌ 保存失敗: ' + (data.error || '未知錯誤'));
                button.disabled = false;
                button.textContent = '💾 保存';
            }
        })
        .catch(error => {
            alert('❌ 保存失敗: ' + error);
            button.disabled = false;
            button.textContent = '💾 保存';
        });
}

function saveAll() {
    const updates = [];

    document.querySelectorAll('.item-card').forEach(card => {
        const id = card.dataset.id;
        const parts = id.split('_');
        const regionIdx = parts.pop();
        const imageName = parts.join('_');

        const input = card.querySelector('.item-input');
        const verified = card.querySelector('.verify-checkbox').checked;
        const originalText = input.dataset.original;
        const currentText = input.value;

        updates.push({
            image_name: imageName,
            region_idx: parseInt(regionIdx),
            verified: verified,
            corrected_text: currentText !== originalText ? currentText : null
        });
    });

    fetch('/api/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updates: updates })
    })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                alert('✓ 保存成功!');
                location.reload();
            } else {
                alert('❌ 保存失敗: ' + (data.error || '未知錯誤'));
            }
        })
        .catch(error => {
            alert('❌ 保存失敗: ' + error);
        });
}

// 鍵盤快捷鍵
document.addEventListener('keydown', e => {
    if (e.ctrlKey && e.key === 's') {
        e.preventDefault();
        saveAll();
    }
    // Delete 鍵刪除選中項
    if (e.key === 'Delete') {
        const selected = document.querySelectorAll('.select-checkbox:checked');
        if (selected.length > 0) {
            batchDeleteSelected();
        }
    }
});

// 上傳圖片功能
async function uploadImage(input) {
    const file = input.files[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            body: formData
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ ' + result.message + '\n發現 ' + result.regions_found + ' 個文字區域');
            location.reload();
        } else {
            alert('❌ 上傳失敗: ' + result.error);
        }
    } catch (error) {
        alert('❌ 上傳失敗: ' + error.message);
    }

    // 清空 input
    input.value = '';
}

// 生成訓練數據集
async function generateDataset() {
    if (!confirm('確定要生成訓練數據集嗎？\n這會將所有已驗證的數據轉換為 gt.txt 格式。')) {
        return;
    }

    const btn = document.getElementById('generateBtn');
    btn.disabled = true;
    btn.textContent = '⏳ 生成中...';

    try {
        const response = await fetch('/api/generate_dataset', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ ' + result.message + '\n\n下一步：\n轉換為 LMDB 格式');
            // 啟用 LMDB 轉換按鈕
            const lmdbBtn = document.getElementById('lmdbBtn');
            if (lmdbBtn) {
                lmdbBtn.disabled = false;
                lmdbBtn.removeAttribute('title');
            }
        } else {
            alert('❌ 生成失敗: ' + result.error);
        }
    } catch (error) {
        alert('❌ 生成失敗: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '🎯 生成訓練數據集';
    }
}

// 轉換為 LMDB 格式
async function convertToLmdb() {
    if (!confirm('確定要轉換為 LMDB 格式嗎？\n這會執行 deep-text-recognition-benchmark/create_lmdb_dataset.py')) {
        return;
    }

    const btn = document.getElementById('lmdbBtn');
    btn.disabled = true;
    btn.textContent = '⏳ 轉換中...';

    try {
        const response = await fetch('/api/convert_to_lmdb', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        if (result.success) {
            alert('✅ ' + result.message + '\n\n輸出目錄: dataset_lmdb/train/\n\n下一步：\n使用 deep-text-recognition-benchmark/train.py 開始訓練');
        } else {
            alert('❌ 轉換失敗: ' + result.error);
        }
    } catch (error) {
        alert('❌ 轉換失敗: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = '📦 轉換 LMDB 格式';
    }
}

// 重新處理圖片
window.reprocessImages = function () {
    console.log('reprocessImages called');

    if (!confirm('⚠️ 警告：重新處理圖片\n\n此操作會：\n1. 重新執行 OCR 處理 input 目錄中的所有圖片\n2. 重新生成所有裁切圖片（會覆蓋舊的）\n3. 更新 annotations.json（會覆蓋現有標註）\n\n已驗證的數據可能會丟失！\n\n確定要繼續嗎？')) {
        console.log('User cancelled');
        return;
    }

    const btn = document.getElementById('reprocessBtn');
    if (!btn) {
        console.error('Button not found!');
        return;
    }

    btn.disabled = true;
    btn.textContent = '⏳ 處理中...';

    fetch('/api/reprocess_images', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    })
        .then(response => {
            console.log('Response received:', response.status);
            return response.json();
        })
        .then(result => {
            console.log('Result:', result);
            if (result.success) {
                alert('✅ ' + result.message + '\n\n請重新載入頁面查看新結果');
                location.reload();
            } else {
                alert('❌ 處理失敗: ' + result.error);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            alert('❌ 處理失敗: ' + error.message);
        })
        .finally(() => {
            btn.disabled = false;
            btn.textContent = '🔄 重新處理圖片';
        });
};
