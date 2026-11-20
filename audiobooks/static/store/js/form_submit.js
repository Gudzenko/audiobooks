const i18nData = JSON.parse(document.getElementById('i18n-js').textContent);

function showGlobalLoader() {
    document.getElementById('global-loader').classList.remove('d-none');
    updateProgress(0, i18nData.preparing);
}

function hideGlobalLoader() {
    document.getElementById('global-loader').classList.add('d-none');
}

function updateProgress(percent, statusText) {
    const progressBar = document.getElementById('upload-progress-bar');
    const statusElement = document.getElementById('upload-status');
    progressBar.style.width = `${percent}%`;
    progressBar.setAttribute('aria-valuenow', percent);
    progressBar.textContent = `${Math.round(percent)}%`;
    if (statusText) statusElement.textContent = statusText;
}

function replacePageWithResponse(xhr) {
    document.open();
    document.write(xhr.responseText);
    document.close();
}

function submitRegularForm(form) {
    const xhr = new XMLHttpRequest();
    xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
            updateProgress((event.loaded / event.total) * 100, i18nData.uploading);
        }
    });
    xhr.addEventListener('load', () => {
        if (xhr.status === 200 || xhr.status === 302) {
            updateProgress(100, i18nData.processing);
            const redirectUrl = xhr.responseURL;
            if (redirectUrl && redirectUrl !== window.location.href) {
                window.location.href = redirectUrl;
            } else {
                replacePageWithResponse(xhr);
            }
        } else {
            replacePageWithResponse(xhr);
        }
    });
    xhr.addEventListener('error', () => {
        alert(i18nData.uploadError);
        hideGlobalLoader();
    });
    xhr.addEventListener('abort', () => {
        alert(i18nData.uploadAborted);
        hideGlobalLoader();
    });
    xhr.open(form.method, form.action || window.location.href);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.send(new FormData(form));
}

function uploadAudioFiles(files, metadata, csrfToken, index = 0) {
    if (index >= files.length) {
        updateProgress(100, i18nData.processing);
        window.location.href = metadata.redirect_url;
        return;
    }

    const file = files[index];
    const formData = new FormData();
    formData.append('audio_file', file, file.name);
    formData.append('csrfmiddlewaretoken', csrfToken);
    const xhr = new XMLHttpRequest();

    xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
            const completed = index / files.length;
            const current = (event.loaded / event.total) / files.length;
            const status = `${i18nData.uploading} ${index + 1}/${files.length}: ${file.name}`;
            updateProgress((completed + current) * 100, status);
        }
    });

    const retryOrRecover = () => {
        const retry = window.confirm(
            `${i18nData.uploadError}\n${file.name}\n${i18nData.retryUpload}`
        );
        if (retry) {
            uploadAudioFiles(files, metadata, csrfToken, index);
        } else {
            window.location.href = metadata.recovery_url;
        }
    };

    xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
            uploadAudioFiles(files, metadata, csrfToken, index + 1);
        } else {
            retryOrRecover();
        }
    });
    xhr.addEventListener('error', retryOrRecover);
    xhr.addEventListener('abort', retryOrRecover);
    xhr.open('POST', metadata.upload_url);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.send(formData);
}

function submitBookWithSequentialAudio(form, audioInput) {
    const files = Array.from(audioInput.files);
    const formData = new FormData(form);
    formData.delete(audioInput.name);
    formData.append('sequential_audio_upload', '1');
    const xhr = new XMLHttpRequest();

    xhr.addEventListener('load', () => {
        const contentType = xhr.getResponseHeader('content-type') || '';
        if (xhr.status >= 200 && xhr.status < 300 && contentType.includes('application/json')) {
            const metadata = JSON.parse(xhr.responseText);
            const csrfToken = form.querySelector('[name="csrfmiddlewaretoken"]').value;
            uploadAudioFiles(files, metadata, csrfToken);
        } else {
            replacePageWithResponse(xhr);
        }
    });
    xhr.addEventListener('error', () => {
        alert(i18nData.uploadError);
        hideGlobalLoader();
    });
    xhr.addEventListener('abort', () => {
        alert(i18nData.uploadAborted);
        hideGlobalLoader();
    });
    xhr.open(form.method, form.action || window.location.href);
    xhr.setRequestHeader('X-Requested-With', 'XMLHttpRequest');
    xhr.send(formData);
}

document.getElementById('main-form').addEventListener('submit', function (event) {
    event.preventDefault();
    showGlobalLoader();
    const audioInput = this.querySelector('input[name="audio_files"]');
    if (audioInput && audioInput.files.length > 0) {
        submitBookWithSequentialAudio(this, audioInput);
    } else {
        submitRegularForm(this);
    }
});
