using System;
using System.Collections;
using System.IO;
using System.Text;
using UnityEngine;
using UnityEngine.Networking;

/// <summary>
/// SkyboxClient — Handles all HTTP communication with the new Phase 2 Blockade Labs API Bridge.
/// 
/// Responsibilities:
///   - POST /generate  → Uploads image directly and triggers Skybox Remix
///   - GET  /status    → Polls job progress 
///   - Downloads the final .jpg (or .zip) containing the generated Skybox
/// </summary>
public class SkyboxClient : MonoBehaviour
{
    [Header("Backend Configuration")]
    [Tooltip("Base URL of the FastAPI backend (e.g. http://localhost:8000)")]
    public string serverUrl = "http://localhost:8000";

    [Tooltip("Polling interval in seconds for /status endpoint")]
    public float pollInterval = 2f;

    // ============================
    // Public Events
    // ============================
    public Action<string> OnJobCreated;          // Fired with jobId after /generate
    public Action<string, int> OnProgressUpdate; // Fired with (message, progress%) during polling
    public Action<string> OnDownloadComplete;    // Fired with path to downloaded Skybox image
    public Action<string> OnError;               // Fired with error description

    private string _currentJobId;
    private Coroutine _pollingCoroutine;

    // ============================
    // Public API
    // ============================

    public void UploadImage(byte[] imageData, string filename = "capture.png")
    {
        StartCoroutine(CO_UploadAndGenerate(imageData, filename));
    }

    public void UploadImageFromPath(string imagePath)
    {
        if (!File.Exists(imagePath))
        {
            OnError?.Invoke($"Image not found: {imagePath}");
            return;
        }
        UploadImage(File.ReadAllBytes(imagePath), Path.GetFileName(imagePath));
    }

    public void Cancel()
    {
        if (_pollingCoroutine != null)
        {
            StopCoroutine(_pollingCoroutine);
            _pollingCoroutine = null;
        }
        _currentJobId = null;
    }

    // ============================
    // Internal Coroutines
    // ============================

    private IEnumerator CO_UploadAndGenerate(byte[] imageData, string filename)
    {
        // POST /generate (multipart form upload)
        WWWForm form = new WWWForm();
        form.AddBinaryData("image", imageData, filename, "image/png");

        using (UnityWebRequest req = UnityWebRequest.Post($"{serverUrl}/generate", form))
        {
            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                OnError?.Invoke($"Upload failed: {req.error}\n{req.downloadHandler?.text}");
                yield break;
            }

            GenerateResponse response = JsonUtility.FromJson<GenerateResponse>(req.downloadHandler.text);
            _currentJobId = response.jobId;
            Debug.Log($"[SkyboxClient] Generation triggered → JobId: {_currentJobId}");
            OnJobCreated?.Invoke(_currentJobId);
        }

        // Poll /status until done or failed
        _pollingCoroutine = StartCoroutine(CO_PollStatus(_currentJobId));
    }

    private IEnumerator CO_PollStatus(string jobId)
    {
        while (true)
        {
            using (UnityWebRequest req = UnityWebRequest.Get($"{serverUrl}/status/{jobId}"))
            {
                yield return req.SendWebRequest();

                if (req.result != UnityWebRequest.Result.Success)
                {
                    OnError?.Invoke($"Status poll error: {req.error}");
                    yield break;
                }

                StatusResponse status = JsonUtility.FromJson<StatusResponse>(req.downloadHandler.text);
                OnProgressUpdate?.Invoke(status.message, status.progress);

                if (status.state == "done")
                {
                    Debug.Log($"[SkyboxClient] Job {jobId} → DONE. Downloading: {status.download_url}");
                    yield return CO_DownloadResult(jobId, status.download_url);
                    yield break;
                }

                if (status.state == "failed")
                {
                    OnError?.Invoke($"Pipeline failed: {status.message}");
                    yield break;
                }
            }

            yield return new WaitForSeconds(pollInterval);
        }
    }

    private IEnumerator CO_DownloadResult(string jobId, string downloadUrl)
    {
        if (string.IsNullOrEmpty(downloadUrl))
        {
             OnError?.Invoke("Download URL is empty.");
             yield break;
        }

        // Handle the Mock Mode specific URL so it doesn't crash Unity
        if (downloadUrl == "https://example.com/mock_skybox.jpg")
        {
            Debug.Log("[SkyboxClient] Mock URL detected. Bypassing actual download.");
            string dummyPath = Path.Combine(Application.persistentDataPath, $"skybox_{jobId}.jpg");
            File.WriteAllBytes(dummyPath, new byte[] { 0x00 }); // Create an empty file
            OnDownloadComplete?.Invoke(dummyPath);
            yield break;
        }

        using (UnityWebRequest req = UnityWebRequest.Get(downloadUrl))
        {
            req.downloadHandler = new DownloadHandlerBuffer();
            yield return req.SendWebRequest();

            if (req.result != UnityWebRequest.Result.Success)
            {
                OnError?.Invoke($"Download failed: {req.error}");
                yield break;
            }

            string ext = ".jpg"; // Skybox outputs JPGs
            if (downloadUrl.Contains(".zip")) ext = ".zip";

            string filePath = Path.Combine(Application.persistentDataPath, $"skybox_{jobId}{ext}");
            File.WriteAllBytes(filePath, req.downloadHandler.data);
            
            Debug.Log($"[SkyboxClient] Download complete: {filePath}");
            OnDownloadComplete?.Invoke(filePath);
        }
    }

    // ============================
    // JSON Models
    // ============================

    [Serializable] private class GenerateResponse { public string jobId; public string blockadeId; }
    [Serializable] private class StatusResponse { public string jobId; public string state; public int progress; public string message; public string download_url; }
}
