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

    // 載入排序狀態
    const savedSort = localStorage.getItem('verifierSortState');
    const sortSelect = document.getElementById('sortSelect');

    if (savedSort && sortSelect) {
        sortSelect.value = savedSort;
        sortItems();
    }
}

function saveSortState() {
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        localStorage.setItem('verifierSortState', sortSelect.value);
    }
}

function sortItems() {
    const container = document.getElementById('itemsContainer');
    const cards = Array.from(container.querySelectorAll('.item-card'));
    const sortSelect = document.getElementById('sortSelect');
    const sortType = sortSelect ? sortSelect.value : 'confidence-asc';

    cards.sort((a, b) => {
        const aConfidence = parseFloat(a.dataset.confidence);
        const bConfidence = parseFloat(b.dataset.confidence);
        const aVerified = a.dataset.verified === 'true';
        const bVerified = b.dataset.verified === 'true';

        switch (sortType) {
            case 'confidence-asc':
                return aConfidence - bConfidence;
            case 'confidence-desc':
                return bConfidence - aConfidence;
            case 'verified-first':
                if (aVerified === bVerified) {
                    return aConfidence - bConfidence;
                }
                return aVerified ? 1 : -1;
            case 'verified-last':
                if (aVerified === bVerified) {
                    return aConfidence - bConfidence;
                }
                return aVerified ? -1 : 1;
            default:
                return aConfidence - bConfidence;
        }
    });

    // 重新排列 DOM
    cards.forEach(card => container.appendChild(card));
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
        image_name: imageName,  // 裁切圖片檔名
        region_idx: regionIdx,
        verified: true,
        label: currentText !== originalText ? currentText : null
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

                // 更新統計數據
                updateStats();

                // 重新排序 (如果選擇了驗證相關排序)
                const sortSelect = document.getElementById('sortSelect');
                if (sortSelect && (sortSelect.value === 'verified-first' || sortSelect.value === 'verified-last')) {
                    sortItems();
                }
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
            label: currentText !== originalText ? currentText : null
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

    const modal = document.getElementById('processingModal');
    const text = document.getElementById('processingText');
    const subtext = document.getElementById('processingSubtext');

    text.textContent = '🎯 生成訓練數據集中...';
    subtext.textContent = '正在分割數據集,請稍候';
    modal.classList.add('active');

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
            document.querySelector('#processingModal .processing-spinner').style.display = 'none';
            text.textContent = '✅ 數據集生成成功!';
            subtext.innerHTML = result.message + '<br><br>下一步: 轉換為 LMDB 格式<br><br><button class="btn btn-primary" onclick="closeProcessingModal()">確認</button>';
        } else {
            document.querySelector('#processingModal .processing-spinner').style.display = 'none';
            text.textContent = '❌ 生成失敗';
            subtext.innerHTML = result.error + '<br><br><button class="btn btn-danger" onclick="closeProcessingModal()">關閉</button>';
        }
    } catch (error) {
        document.querySelector('#processingModal .processing-spinner').style.display = 'none';
        text.textContent = '❌ 生成失敗';
        subtext.innerHTML = error.message + '<br><br><button class="btn btn-danger" onclick="closeProcessingModal()">關閉</button>';
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

    const modal = document.getElementById('processingModal');
    const text = document.getElementById('processingText');
    const subtext = document.getElementById('processingSubtext');

    text.textContent = '📦 轉換 LMDB 格式中...';
    subtext.textContent = '正在創建 LMDB 數據庫,請稍候';
    modal.classList.add('active');

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
            document.querySelector('#processingModal .processing-spinner').style.display = 'none';
            text.textContent = '✅ LMDB 轉換成功!';
            subtext.innerHTML = result.message + '<br><br>輸出目錄: dataset_lmdb/train/<br><br>下一步: 使用 deep-text-recognition-benchmark/train.py 開始訓練<br><br><button class="btn btn-primary" onclick="closeProcessingModal()">確認</button>';
        } else {
            document.querySelector('#processingModal .processing-spinner').style.display = 'none';
            text.textContent = '❌ 轉換失敗';
            subtext.innerHTML = result.error + '<br><br><button class="btn btn-danger" onclick="closeProcessingModal()">關閉</button>';
        }
    } catch (error) {
        document.querySelector('#processingModal .processing-spinner').style.display = 'none';
        text.textContent = '❌ 轉換失敗';
        subtext.innerHTML = error.message + '<br><br><button class="btn btn-danger" onclick="closeProcessingModal()">關閉</button>';
    } finally {
        btn.disabled = false;
        btn.textContent = '📦 轉換 LMDB 格式';
    }
}

// 重新處理圖片
window.reprocessImages = async function () {
    console.log('reprocessImages called');

    if (!confirm('⚠️ 警告：完全重置並重新處理\n\n此操作會：\n1. 清空所有標註數據 (annotations.json)\n2. 清空所有裁切圖片 (crops/)\n3. 清空 MD5 記錄\n4. 重新 OCR input 目錄中的所有圖片\n\n所有驗證進度和修正都會丟失！\n\n確定要繼續嗎？')) {
        console.log('User cancelled');
        return;
    }

    // 顯示 modal
    const modal = document.getElementById('resetModal');
    const progressFill = document.getElementById('resetProgressFill');
    const progressText = document.getElementById('resetProgressText');
    const resetMessage = document.getElementById('resetMessage');
    const resetStatus = document.getElementById('resetStatus');
    const resetSpinner = document.getElementById('resetSpinner');
    const confirmBtn = document.getElementById('resetConfirmBtn');

    modal.classList.add('active');
    confirmBtn.classList.remove('show');
    resetSpinner.style.display = 'inline-block';

    // 模擬進度更新
    let progress = 0;
    const progressInterval = setInterval(() => {
        if (progress < 90) {
            progress += Math.random() * 10;
            if (progress > 90) progress = 90;
            progressFill.style.width = progress + '%';
            progressText.textContent = Math.floor(progress) + '%';
        }
    }, 300);

    try {
        resetMessage.textContent = '步驟 1/4: 清空數據...';
        resetStatus.textContent = '正在清空 annotations.json';

        await new Promise(resolve => setTimeout(resolve, 300));

        resetMessage.textContent = '步驟 2/4: 清空裁切圖片...';
        resetStatus.textContent = '正在清空 crops 目錄';

        await new Promise(resolve => setTimeout(resolve, 300));

        resetMessage.textContent = '步驟 3/4: 清空已刪除文件...';
        resetStatus.textContent = '正在清空 deleted 目錄';

        await new Promise(resolve => setTimeout(resolve, 300));

        resetMessage.textContent = '步驟 4/4: 重新處理...';
        resetStatus.textContent = '正在執行 OCR 並生成裁切圖片';

        const response = await fetch('/api/reprocess_images', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });

        const result = await response.json();

        clearInterval(progressInterval);
        progress = 100;
        progressFill.style.width = '100%';
        progressText.textContent = '100%';
        resetSpinner.style.display = 'none';

        if (result.success) {
            resetMessage.textContent = '✅ 重置完成！';
            resetStatus.textContent = result.message.replace(/\n/g, ' | ');
            confirmBtn.classList.add('show');
        } else {
            resetMessage.textContent = '❌ 處理失敗';
            resetStatus.textContent = result.error;
            confirmBtn.classList.add('show');
        }
    } catch (error) {
        clearInterval(progressInterval);
        console.error('Error:', error);
        resetMessage.textContent = '❌ 處理失敗';
        resetStatus.textContent = error.message;
        resetSpinner.style.display = 'none';
        confirmBtn.classList.add('show');
    }
};

function closeResetModal() {
    const modal = document.getElementById('resetModal');
    modal.classList.remove('active');
    location.reload();
}

// ========== 返回頂部按鈕 ==========
function scrollToTop() {
    window.scrollTo({
        top: 0,
        behavior: 'smooth'
    });
}

function closeProcessingModal() {
    const modal = document.getElementById('processingModal');
    const spinner = modal.querySelector('.processing-spinner');
    spinner.style.display = 'inline-block';
    modal.classList.remove('active');
    // 不再重新載入頁面，改用 AJAX 更新統計數據
    updateStats();
}

// 使用 AJAX 更新頁面統計數據
async function updateStats() {
    try {
        const response = await fetch('/api/stats');
        const stats = await response.json();

        if (stats.success) {
            // 更新統計數字
            document.querySelector('.stat-item:nth-child(1) strong').textContent = stats.data.total;
            document.querySelector('.stat-item:nth-child(2) strong').textContent = stats.data.verified;
            document.querySelector('.stat-item:nth-child(3) strong').textContent = stats.data.low_confidence;

            // 更新按鈕狀態
            const lmdbBtn = document.getElementById('lmdbBtn');
            if (stats.data.dataset_exists) {
                lmdbBtn.disabled = false;
                lmdbBtn.removeAttribute('title');
            } else {
                lmdbBtn.disabled = true;
                lmdbBtn.setAttribute('title', '請先生成訓練數據集');
            }
        }
    } catch (error) {
        console.error('更新統計失敗:', error);
    }
}