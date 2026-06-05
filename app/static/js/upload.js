document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById('file-input');
    const btnSelect = document.getElementById('btn-select');
    const btnUpload = document.getElementById('btn-upload');
    const previewList = document.getElementById('preview-list');
    const progressContainer = document.getElementById('progress-container');
    const progressFill = document.getElementById('progress-fill');
    const progressText = document.getElementById('progress-text');
    
    let selectedFiles = [];

    if(btnSelect) {
        btnSelect.addEventListener('click', () => {
            fileInput.click();
        });
    }

    if(fileInput) {
        fileInput.addEventListener('change', (e) => {
            const files = Array.from(e.target.files);
            selectedFiles = [...selectedFiles, ...files];
            updatePreview();
        });
    }

    function updatePreview() {
        previewList.innerHTML = '';
        selectedFiles.forEach((file, index) => {
            const el = document.createElement('div');
            el.className = 'preview-item';
            el.textContent = file.name;
            // Can add remove button here
            previewList.appendChild(el);
        });

        if (selectedFiles.length > 0) {
            btnUpload.classList.remove('hidden');
        } else {
            btnUpload.classList.add('hidden');
        }
    }

    if(btnUpload) {
        btnUpload.addEventListener('click', async () => {
            if (selectedFiles.length === 0) return;

            btnUpload.classList.add('hidden');
            btnSelect.classList.add('hidden');
            progressContainer.classList.remove('hidden');

            let successCount = 0;
            const total = selectedFiles.length;

            for (let i = 0; i < total; i++) {
                const file = selectedFiles[i];
                progressText.textContent = `Subiendo ${i + 1} de ${total}...`;
                
                const formData = new FormData();
                formData.append('file', file);

                try {
                    const response = await fetch(`/api/upload/${token}`, {
                        method: 'POST',
                        body: formData
                    });

                    if (response.ok) {
                        successCount++;
                    } else {
                        const data = await response.json();
                        alert(`Error con ${file.name}: ${data.error}`);
                    }
                } catch (error) {
                    console.error('Upload error', error);
                    alert(`Error de conexión al subir ${file.name}`);
                }

                progressFill.style.width = `${((i + 1) / total) * 100}%`;
            }

            if (successCount === total) {
                window.location.href = `/upload/${token}?success=1`;
                // Wait, redirecting manually since the endpoint returns html or we can just render the success page.
                // The PRD mentions a success page. Let's just alter the UI or redirect.
                document.body.innerHTML = `<div class="container"><div class="card" style="text-align: center;"><h2>¡Archivos enviados con éxito!</h2><p>Gracias por compartir tus fotos y videos.</p><a href="/upload/${token}" class="btn-primary" style="display: inline-block; margin-top: 20px;">Subir más</a></div></div>`;
            } else {
                progressText.textContent = "Hubo algunos errores.";
                btnSelect.classList.remove('hidden');
                selectedFiles = [];
                updatePreview();
            }
        });
    }
});
