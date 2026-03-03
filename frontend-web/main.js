// Script principal de l'application WebVR
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
        // Enlève le texte de chargement et affiche la scène 360 directement dans la page
        viewport.innerHTML = `
            <div style="width: 100%; height: 100%; position: relative; overflow: hidden; background: #000; border-radius: 20px; touch-action: none;">
                
                <!-- A-Frame 360 Viewer (Embedded on Desktop, Fullscreen ready on Mobile) -->
                <a-scene embedded style="width: 100%; height: 100%;" vr-mode-ui="enabled: false">
                    <a-sky src="${imageUrl}" rotation="0 -90 0"></a-sky>
                    <!-- Permet le glissement horizontal via look-controls de base (le vertical sera géré manuellement ci-dessous) -->
                    <a-entity id="vr-camera" camera look-controls="reverseMouseDrag: true, touchEnabled: true, magicWindowTrackingEnabled: false" position="0 0 0"></a-entity>
                </a-scene>

                <!-- UI Overlay: Instructions pour l'utilisateur -->
                <div id="instruction-overlay" style="position: absolute; top: 20px; left: 50%; transform: translateX(-50%); background: rgba(0,0,0,0.6); padding: 10px 20px; border-radius: 30px; backdrop-filter: blur(5px); z-index: 999; color: white; display: flex; align-items: center; gap: 10px; font-weight: bold; pointer-events: none; border: 1px solid rgba(255,126,95,0.4); transition: opacity 0.5s ease;">
                    <span>👆 Glissez dans toutes les directions pour explorer le monde 360°</span>
                </div>

                <!-- Bouton optionnel Télécharger en bas -->
                <div style="position: absolute; bottom: 20px; right: 20px; z-index: 999;">
                    <a href="${imageUrl}" target="_blank" style="background: rgba(0,0,0,0.8); color: #fff; padding: 10px 15px; border-radius: 8px; text-decoration: none; font-size: 0.9rem; border: 1px solid rgba(255,255,255,0.2);">⬇️ Télécharger l'image</a>
                </div>
            </div>
        `;

        // Code manuel pour assurer le Look Control 100% total sur Mobile (Haut/Bas/Gauche/Droite)
        // et pour faire disparaître l'instruction au premier touché
        setTimeout(() => {
            const workspaceObj = document.querySelector('.workspace');
            if (workspaceObj) {
                workspaceObj.scrollIntoView({ behavior: 'smooth', block: 'end' });
            }

            const instructionOverlay = document.getElementById('instruction-overlay');
            const sceneEl = document.querySelector('a-scene');
            const cameraEl = document.getElementById('vr-camera');

            if (sceneEl && cameraEl) {
                let isDragging = false;
                let previousTouchY = 0;
                let currentPitch = 0;

                sceneEl.addEventListener('touchstart', (e) => {
                    // Cacher l'instruction dès le premier touché
                    if (instructionOverlay) {
                        instructionOverlay.style.opacity = '0';
                        setTimeout(() => instructionOverlay.style.display = 'none', 500);
                    }

                    if (e.touches.length === 1) {
                        isDragging = true;
                        previousTouchY = e.touches[0].pageY;
                    }
                }, { passive: true });

                sceneEl.addEventListener('touchend', () => {
                    isDragging = false;
                }, { passive: true });

                sceneEl.addEventListener('touchmove', (e) => {
                    if (!isDragging || e.touches.length > 1) return;

                    const touchY = e.touches[0].pageY;
                    const deltaY = touchY - previousTouchY;
                    previousTouchY = touchY;

                    // A-Frame's look-controls gère déjà parfaitement le delta X (droite/gauche)
                    // Nous gérons manuellement le delta Y (Haut/Bas) qui est souvent bloqué
                    const sensitivity = 0.005; // Sensibilité en radians

                    const lookControls = cameraEl.components['look-controls'];
                    if (lookControls && lookControls.pitchObject) {
                        let pitch = lookControls.pitchObject.rotation.x;
                        pitch += (deltaY * sensitivity);

                        // Limiter pour ne pas faire de looping complet (regarder ses pieds/ciel max, soit environ -PI/2 à PI/2)
                        const PI_2 = Math.PI / 2;
                        pitch = Math.max(-PI_2, Math.min(PI_2, pitch));

                        // Mettre à jour l'objet interne de A-Frame directement
                        lookControls.pitchObject.rotation.x = pitch;
                    }
                }, { passive: true });
            }
        }, 500);
    }
});
