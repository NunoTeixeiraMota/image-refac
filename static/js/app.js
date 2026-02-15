(function () {
    'use strict';

    // DOM refs
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const settings = document.getElementById('settings');
    const actions = document.getElementById('actions');
    const btnConvert = document.getElementById('btn-convert');
    const btnZip = document.getElementById('btn-download-zip');
    const fileList = document.getElementById('file-list');
    const statusMsg = document.getElementById('status-msg');
    const uploadProgress = document.getElementById('upload-progress');
    const uploadFill = document.getElementById('upload-fill');
    const convertProgress = document.getElementById('convert-progress');
    const convertFill = document.getElementById('convert-fill');
    const qualitySlider = document.getElementById('quality');
    const qualityValue = document.getElementById('quality-value');
    const resizeToggle = document.getElementById('resize-toggle');
    const resizeFields = document.getElementById('resize-fields');
    const methodSelect = document.getElementById('method');
    const formatSelect = document.getElementById('output-format');
    const statsEl = document.getElementById('stats');

    let sessionId = null;
    let uploadedFiles = [];
    let convertedResults = [];
    // Map of filename -> object URL for client-side previews
    const localPreviews = {};

    // --- Settings interactivity ---
    qualitySlider.addEventListener('input', () => {
        qualityValue.textContent = qualitySlider.value;
    });

    resizeToggle.addEventListener('change', () => {
        resizeFields.style.display = resizeToggle.checked ? 'flex' : 'none';
    });

    formatSelect.addEventListener('change', () => {
        const isWebp = formatSelect.value === 'webp';
        methodSelect.disabled = !isWebp;
        if (!isWebp) methodSelect.value = 'lossy';
    });

    // --- Drag & Drop ---
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drag-over');
    });

    dropZone.addEventListener('dragleave', () => {
        dropZone.classList.remove('drag-over');
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drag-over');
        const files = e.dataTransfer.files;
        if (files.length) handleFiles(files);
    });

    fileInput.addEventListener('change', () => {
        if (fileInput.files.length) handleFiles(fileInput.files);
    });

    // --- File handling ---
    function handleFiles(files) {
        // Store local previews
        Array.from(files).forEach(f => {
            localPreviews[f.name] = URL.createObjectURL(f);
        });
        uploadFiles(files);
    }

    async function uploadFiles(files) {
        const formData = new FormData();
        Array.from(files).forEach(f => formData.append('files', f));

        setStatus('Uploading...');
        showProgress(uploadProgress, uploadFill, 10);

        try {
            const resp = await fetch('/api/upload', { method: 'POST', body: formData });
            const data = await resp.json();
            if (!resp.ok) {
                setStatus(data.error || 'Upload failed');
                hideProgress(uploadProgress);
                return;
            }

            sessionId = data.session_id;
            uploadedFiles = data.files;

            showProgress(uploadProgress, uploadFill, 100);
            setTimeout(() => hideProgress(uploadProgress), 500);

            settings.style.display = 'grid';
            actions.style.display = 'flex';
            btnZip.disabled = true;
            convertedResults = [];

            renderUploadedFiles();
            setStatus(`${uploadedFiles.length} file(s) ready to convert`);
        } catch (err) {
            setStatus('Upload error: ' + err.message);
            hideProgress(uploadProgress);
        }
    }

    function renderUploadedFiles() {
        fileList.innerHTML = '';
        statsEl.style.display = 'none';

        uploadedFiles.forEach(f => {
            const card = document.createElement('div');
            card.className = 'file-card';
            card.dataset.name = f.name;

            const previewSrc = localPreviews[f.name] || `/api/preview/${sessionId}/${encodeURIComponent(f.name)}`;

            card.innerHTML = `
                <div class="preview-col">
                    <img src="${previewSrc}" alt="${f.name}">
                    <span class="label">Original</span>
                </div>
                <div class="preview-col converted-preview" style="display:none;">
                    <img src="" alt="">
                    <span class="label">Converted</span>
                </div>
                <div class="info-col">
                    <div class="filename">${f.name}</div>
                    <div class="detail">Size: ${f.size_kb} KB</div>
                </div>
            `;
            fileList.appendChild(card);
        });
    }

    // --- Conversion ---
    btnConvert.addEventListener('click', doConvert);

    async function doConvert() {
        if (!sessionId) return;

        btnConvert.disabled = true;
        setStatus('Converting...');
        showProgress(convertProgress, convertFill, 30);

        const payload = {
            session_id: sessionId,
            format: formatSelect.value,
            method: methodSelect.value,
            quality: parseInt(qualitySlider.value, 10),
            resize: resizeToggle.checked,
            width: parseInt(document.getElementById('resize-width').value, 10) || 512,
            height: parseInt(document.getElementById('resize-height').value, 10) || 512,
            threads: parseInt(document.getElementById('threads').value, 10) || 4,
        };

        try {
            const resp = await fetch('/api/convert', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload),
            });
            const data = await resp.json();

            showProgress(convertProgress, convertFill, 100);
            setTimeout(() => hideProgress(convertProgress), 500);

            if (!resp.ok) {
                setStatus(data.error || 'Conversion failed');
                btnConvert.disabled = false;
                return;
            }

            convertedResults = data.results;
            btnZip.disabled = false;
            btnConvert.disabled = false;

            renderConvertedFiles(data);
            setStatus(`Converted ${data.results.length} file(s)`);
        } catch (err) {
            setStatus('Conversion error: ' + err.message);
            btnConvert.disabled = false;
            hideProgress(convertProgress);
        }
    }

    function renderConvertedFiles(data) {
        fileList.innerHTML = '';

        // Stats
        statsEl.style.display = 'flex';
        document.getElementById('stat-files').textContent = data.results.length;
        document.getElementById('stat-original').textContent = formatKB(data.total_original_kb);
        document.getElementById('stat-converted').textContent = formatKB(data.total_converted_kb);
        document.getElementById('stat-saved').textContent = data.total_reduction_pct + '%';

        data.results.forEach(r => {
            const card = document.createElement('div');
            card.className = 'file-card';

            const origSrc = localPreviews[r.name] || `/api/preview/${sessionId}/${encodeURIComponent(r.name)}`;
            const convSrc = `/api/preview/${sessionId}/${encodeURIComponent(r.output_name)}`;

            const errorHtml = r.error
                ? `<div class="detail" style="color:var(--accent)">Error: ${r.error}</div>`
                : '';

            card.innerHTML = `
                <div class="preview-col">
                    <img src="${origSrc}" alt="original">
                    <span class="label">Original</span>
                </div>
                <div class="info-col">
                    <div class="filename">${r.name} &rarr; ${r.output_name}</div>
                    <div class="detail">Original: ${r.original_size_kb} KB (${r.original_dimensions[0]}x${r.original_dimensions[1]})</div>
                    <div class="detail">Converted: ${r.converted_size_kb} KB (${r.final_dimensions[0]}x${r.final_dimensions[1]})</div>
                    ${r.success ? `<div class="reduction">${r.reduction_pct}% smaller &middot; ${r.method_used}</div>` : ''}
                    ${errorHtml}
                </div>
                <div class="actions-col">
                    ${r.success ? `
                        <a class="btn btn-secondary" href="/api/download/${sessionId}/${encodeURIComponent(r.output_name)}">Download</a>
                    ` : ''}
                </div>
            `;

            // Add converted preview image if successful
            if (r.success) {
                const convPreview = document.createElement('div');
                convPreview.className = 'preview-col';
                convPreview.innerHTML = `
                    <img src="${convSrc}" alt="converted">
                    <span class="label">Converted</span>
                `;
                card.insertBefore(convPreview, card.children[1]);
                card.style.gridTemplateColumns = '1fr 1fr auto auto';
            }

            fileList.appendChild(card);
        });
    }

    // --- ZIP download ---
    btnZip.addEventListener('click', () => {
        if (sessionId) {
            window.location.href = `/api/download-zip/${sessionId}`;
        }
    });

    // --- Helpers ---
    function setStatus(msg) {
        statusMsg.textContent = msg;
    }

    function showProgress(bar, fill, pct) {
        bar.classList.add('active');
        fill.style.width = pct + '%';
    }

    function hideProgress(bar) {
        bar.classList.remove('active');
    }

    function formatKB(kb) {
        if (kb >= 1024) return (kb / 1024).toFixed(1) + ' MB';
        return kb.toFixed(1) + ' KB';
    }
})();
