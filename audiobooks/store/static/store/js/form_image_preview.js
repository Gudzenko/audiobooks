document.addEventListener('DOMContentLoaded', function () {
    const imageFields = JSON.parse(document.getElementById('image-fields-data').textContent);
    imageFields.forEach((fieldName) => {
        const dropZone = document.getElementById(`drop-zone-${fieldName}`);
        const fileInput = document.getElementById(`id_${fieldName}`);
        const preview = document.getElementById(`preview-${fieldName}`);
        const clearButton = document.getElementById(`clear-${fieldName}`);

        if (dropZone && fileInput && preview && clearButton) {
            if (preview.querySelector('img')) {
                clearButton.classList.remove('d-none');
            }

            dropZone.addEventListener('click', () => fileInput.click());

            fileInput.addEventListener('change', () => {
                handleFile(fileInput, preview);
                clearButton.classList.remove('d-none');
            });

            clearButton.addEventListener('click', (e) => {
                e.stopPropagation();
                e.preventDefault();
                fileInput.value = '';
                preview.innerHTML = '<span class="text-muted">Перетащите фото сюда или нажмите для выбора</span>';
                clearButton.classList.add('d-none');
                document.getElementById(`clear-input-${fieldName}`).value = 'true';
            });

            dropZone.addEventListener('dragover', (e) => {
                e.preventDefault();
                dropZone.classList.add('border-primary');
            });

            dropZone.addEventListener('dragleave', () => {
                dropZone.classList.remove('border-primary');
            });

            dropZone.addEventListener('drop', (e) => {
                e.preventDefault();
                dropZone.classList.remove('border-primary');
                const files = e.dataTransfer.files;
                if (files.length) {
                    fileInput.files = files;
                    handleFile(fileInput, preview);
                }
            });

            function handleFile(input, preview) {
                const file = input.files[0];
                if (file && file.type.startsWith('image/')) {
                    const reader = new FileReader();
                    reader.onload = (e) => {
                        preview.innerHTML = `<img src="${e.target.result}" alt="Preview" style="height: 100%;">`;
                    };
                    reader.readAsDataURL(file);
                    document.getElementById(`clear-input-${fieldName}`).value = 'true';
                } else {
                    preview.innerHTML = '<span class="text-muted">Неверный формат файла</span>';
                }
            }
        }
    });
});
