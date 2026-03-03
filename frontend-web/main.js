document.addEventListener('DOMContentLoaded', () => {
    const generateBtn = document.getElementById('generate-btn');
    const btnText = document.querySelector('.btn-text');
    const btnLoader = document.getElementById('btn-loader');
    const statusText = document.getElementById('status-text');
    const viewport = document.getElementById('viewport');

    // New Image Controls
    const btnUpload = document.getElementById('btn-upload');
    const btnCamera = document.getElementById('btn-camera');
    const fileInput = document.getElementById('file-input');
    const cameraContainer = document.getElementById('camera-container');
    const cameraVideo = document.getElementById('camera-video');
    const btnCapture = document.getElementById('btn-capture');
    const previewContainer = document.getElementById('preview-container');
    const imagePreview = document.getElementById('image-preview');
    const btnClear = document.getElementById('btn-clear');
    const cameraCanvas = document.getElementById('camera-canvas');

    let currentImageBlob = null;
    let cameraStream = null;

    let isGenerating = false;

    // --- Image Source Handlers ---

    // 1. Upload via File Explorer
    btnUpload.addEventListener('click', () => {
        fileInput.click();
    });

    fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            currentImageBlob = file;
            showPreview(URL.createObjectURL(file));
            stopCamera();
        }
    });

    // 2. Camera Capture
    btnCamera.addEventListener('click', async () => {
        try {
            cameraStream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } });
            cameraVideo.srcObject = cameraStream;
            cameraContainer.style.display = 'block';
            previewContainer.style.display = 'none';
        } catch (err) {
            alert('Impossible d accéder à la caméra: ' + err.message);
        }
    });

    btnCapture.addEventListener('click', () => {
        if (!cameraStream) return;
        cameraCanvas.width = cameraVideo.videoWidth;
        cameraCanvas.height = cameraVideo.videoHeight;
        const ctx = cameraCanvas.getContext('2d');
        ctx.drawImage(cameraVideo, 0, 0, cameraCanvas.width, cameraCanvas.height);

        cameraCanvas.toBlob((blob) => {
            currentImageBlob = blob;
            showPreview(URL.createObjectURL(blob));
            stopCamera();
        }, 'image/jpeg', 0.9);
    });

    // 3. Clear selected image
    btnClear.addEventListener('click', () => {
        currentImageBlob = null;
        previewContainer.style.display = 'none';
        fileInput.value = '';
        statusText.textContent = 'Prêt pour la génération.';
        statusText.style.color = 'var(--text-muted)';
    });

    function showPreview(url) {
        imagePreview.src = url;
        previewContainer.style.display = 'block';
        cameraContainer.style.display = 'none';
        statusText.style.color = '#20c997';
        statusText.textContent = 'Image chargée et prête !';
    }

    function stopCamera() {
        if (cameraStream) {
            cameraStream.getTracks().forEach(track => track.stop());
            cameraStream = null;
            cameraContainer.style.display = 'none';
        }
    }

    // --- Generation Handler ---
    generateBtn.addEventListener('click', async () => {
        if (isGenerating) return;

        if (!currentImageBlob) {
            statusText.style.color = '#ff6b6b';
            statusText.textContent = "Veuillez uploader une image ou prendre une photo.";
            return;
        }

        // Start Loading State
        isGenerating = true;
        btnText.style.display = 'none';
        btnLoader.style.display = 'block';
        statusText.style.color = '#ff7e5f';
        statusText.textContent = "Connexion au backend (AIWorldProject)...";

        // Actual Backend Call
        try {
            statusText.textContent = "Envoi de l'image (Upload)...";

            const formData = new FormData();
            formData.append('image', currentImageBlob, 'capture.jpg');
            formData.append('prompt', 'A photorealistic environment based precisely on the provided image sketch.');

            // Note: The backend currently hardcodes style and negative text, but we could pass them here
            // if we modify the backend later. For now we just send the required fields.

            statusText.textContent = "Envoi de la requête à l'IA...";

            const hostname = window.location.hostname || '127.0.0.1';
            const response = await fetch(`http://${hostname}:8000/generate`, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                const errData = await response.json();
                throw new Error(errData.detail || "Erreur serveur");
            }

            const data = await response.json();
            const jobId = data.jobId;

            statusText.textContent = "Génération du monde en cours (Patientez environ 30s)...";

            // Poll for status
            await pollStatus(jobId);

        } catch (error) {
            console.error(error);
            statusText.style.color = '#ff6b6b';
            statusText.textContent = "Erreur: " + error.message;
        } finally {
            // Reset UI State
            isGenerating = false;
            btnText.style.display = 'block';
            btnLoader.style.display = 'none';
        }
    });

    // Helper to poll the backend status
    async function pollStatus(jobId) {
        return new Promise((resolve, reject) => {
            const interval = setInterval(async () => {
                try {
                    const hostname = window.location.hostname || '127.0.0.1';
                    const res = await fetch(`http://${hostname}:8000/status/${jobId}`);
                    if (!res.ok) throw new Error("Erreur lors de la vérification du statut");

                    const statusData = await res.json();

                    if (statusData.state === 'done') {
                        clearInterval(interval);
                        statusText.style.color = '#20c997';
                        statusText.textContent = "Environnement généré avec succès !";
                        showResultInViewport(statusData.download_url);
                        resolve();
                    } else if (statusData.state === 'failed') {
                        clearInterval(interval);
                        throw new Error(statusData.message || "La génération a échoué.");
                    } else {
                        // Update progress
                        statusText.textContent = `${statusData.message} (${statusData.progress}%)`;
                    }
                } catch (err) {
                    clearInterval(interval);
                    reject(err);
                }
            }, 3000); // Poll every 3 seconds
        });
    }

    // Show the actual generated result
    function showResultInViewport(imageUrl) {
        // Obtenir l'URL de base pour pouvoir ouvrir la nouvelle fenêtre correctement
        const baseUrl = window.location.origin + window.location.pathname.replace('index.html', '');
        const viewerUrl = `${baseUrl}viewer.html?image=${encodeURIComponent(imageUrl)}`;

        // Ouvrir automatiquement la nouvelle fenêtre (peut être bloqué par les pop-ups safari/chrome, d'où le bouton)
        window.open(viewerUrl, '_blank');

        viewport.innerHTML = `
            <div style="width: 100%; height: 100%; border-radius: 20px; animation: fadeIn 1s ease-out forwards; position: relative; overflow: hidden; background: #1a1a2e; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; padding: 20px;">
                
                <h2 style="color: #20c997; margin-bottom: 20px;">Le monde a été généré avec succès !</h2>
                <p style="color: #a0a0b0; max-width: 80%; margin-bottom: 30px;">
                    Une nouvelle fenêtre devrait s'être ouverte avec votre vue 360. Si votre navigateur l'a bloquée, cliquez sur le bouton ci-dessous.
                </p>

                <img src="${imageUrl}" alt="Aperçu miniature" style="width: 80%; max-height: 200px; object-fit: cover; border-radius: 12px; margin-bottom: 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5);" />

                <button onclick="window.open('${viewerUrl}', '_blank')" style="background: linear-gradient(135deg, #ff7e5f, #feb47b); color: #fff; border: none; padding: 15px 30px; border-radius: 12px; font-weight: bold; cursor: pointer; font-family: 'Outfit', sans-serif; font-size: 1.2rem; box-shadow: 0 4px 15px rgba(255,126,95,0.4); display: flex; align-items: center; gap: 8px; transition: transform 0.2s;">
                    <span>🌍 Ouvrir le visualiseur 360° en plein écran</span>
                </button>
                
                <div style="margin-top: 20px;">
                    <a href="${imageUrl}" target="_blank" style="color: rgba(255,255,255,0.5); text-decoration: underline; font-size: 0.9rem;">Télécharger l'image brute</a>
                </div>
            </div>
        `;
    }
});
