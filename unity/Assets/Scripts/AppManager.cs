using UnityEngine;
using UnityEngine.UI;
using TMPro;

/// <summary>
/// AppManager — AUTO-WIRING VERSION
/// Finds all UI references automatically by GameObject name.
/// No need to drag anything in the Inspector.
/// 
/// Expected Hierarchy names:
///   Panels:  PanelIdle, PanelUploading, PanelProcessing, PanelViewing
///   Buttons: BtnUpload, BtnReset
///   Slider:  ProgressBar
///   Text:    TxtProgress, TxtStatus
/// </summary>
public class AppManager : MonoBehaviour
{
    public enum State { Idle, Uploading, Processing, Viewing }

    [Header("Core References (auto-found if empty)")]
    public SkyboxClient backendClient;
    public WorldImporter worldImporter;

    [Header("UI Panels (auto-found by name)")]
    public GameObject panelIdle;
    public GameObject panelUploading;
    public GameObject panelProcessing;
    public GameObject panelViewing;

    [Header("UI Elements (auto-found by name)")]
    public Button btnUpload;
    public Button btnReset;
    public Slider sliderProgress;
    public TextMeshProUGUI txtProgress;
    public TextMeshProUGUI txtStatus;

    [Header("Debug")]
    [SerializeField] private State _currentState = State.Idle;

    private void Awake()
    {
        // === AUTO-FIND all references by name ===
        if (backendClient == null)
            backendClient = FindAnyObjectByType<SkyboxClient>();
        if (worldImporter == null)
            worldImporter = FindAnyObjectByType<WorldImporter>();

        if (panelIdle == null) panelIdle = FindByName("PanelIdle");
        if (panelUploading == null) panelUploading = FindByName("PanelUploading");
        if (panelProcessing == null) panelProcessing = FindByName("PanelProcessing");
        if (panelViewing == null) panelViewing = FindByName("PanelViewing");

        if (btnUpload == null)
        {
            var obj = FindByName("BtnUpload");
            if (obj != null)
            {
                btnUpload = obj.GetComponent<Button>() ?? obj.GetComponentInChildren<Button>();
                if (btnUpload == null) btnUpload = obj.AddComponent<Button>();
            }
        }
        if (btnReset == null)
        {
            var obj = FindByName("BtnReset");
            if (obj != null)
            {
                btnReset = obj.GetComponent<Button>() ?? obj.GetComponentInChildren<Button>();
                if (btnReset == null) btnReset = obj.AddComponent<Button>();
            }
        }
        if (sliderProgress == null)
        {
            var obj = FindByName("ProgressBar");
            if (obj != null) sliderProgress = obj.GetComponent<Slider>();
        }
        if (txtProgress == null)
        {
            var obj = FindByName("TxtProgress");
            if (obj != null) txtProgress = obj.GetComponent<TextMeshProUGUI>();
        }
        if (txtStatus == null)
        {
            var obj = FindByName("TxtStatus");
            if (obj != null) txtStatus = obj.GetComponent<TextMeshProUGUI>();
        }

        Debug.Log($"[AppManager] Auto-wiring: BackendClient={backendClient != null}, WorldImporter={worldImporter != null}, " +
                  $"Panels={panelIdle != null}/{panelUploading != null}/{panelProcessing != null}/{panelViewing != null}, " +
                  $"BtnUpload={btnUpload != null}, BtnReset={btnReset != null}, Slider={sliderProgress != null}");
    }

    private void Start()
    {
        if (btnUpload != null) btnUpload.onClick.AddListener(HandleUploadClick);
        if (btnReset != null) btnReset.onClick.AddListener(HandleResetClick);

        if (backendClient != null)
        {
            backendClient.OnJobCreated += HandleJobCreated;
            backendClient.OnProgressUpdate += HandleProgressUpdate;
            backendClient.OnDownloadComplete += HandleDownloadComplete;
            backendClient.OnError += HandleError;
        }

        TransitionTo(State.Idle);
    }

    private void OnDestroy()
    {
        if (backendClient != null)
        {
            backendClient.OnJobCreated -= HandleJobCreated;
            backendClient.OnProgressUpdate -= HandleProgressUpdate;
            backendClient.OnDownloadComplete -= HandleDownloadComplete;
            backendClient.OnError -= HandleError;
        }
    }

    public void TransitionTo(State newState)
    {
        _currentState = newState;
        Debug.Log($"[AppManager] State -> {newState}");

        SetActive(panelIdle, false);
        SetActive(panelUploading, false);
        SetActive(panelProcessing, false);
        SetActive(panelViewing, false);

        switch (newState)
        {
            case State.Idle:
                SetActive(panelIdle, true);
                SetStatus("Ready. Click Upload to generate a 3D world.");
                break;
            case State.Uploading:
                SetActive(panelUploading, true);
                SetStatus("Uploading image to server...");
                break;
            case State.Processing:
                SetActive(panelProcessing, true);
                if (sliderProgress != null) sliderProgress.value = 0f;
                SetProgress(0, "Waiting for server...");
                break;
            case State.Viewing:
                SetActive(panelViewing, true);
                SetStatus("World loaded. Explore!");
                break;
        }
    }

    private void HandleUploadClick()
    {
        string testImage = System.IO.Path.Combine(Application.streamingAssetsPath, "test_input.png");
        if (System.IO.File.Exists(testImage))
        {
            TransitionTo(State.Uploading);
            backendClient.UploadImageFromPath(testImage);
        }
        else
        {
            SetStatus("Place 'test_input.png' in Assets/StreamingAssets/");
            Debug.LogWarning("[AppManager] No test image found.");
        }
    }

    private void HandleResetClick()
    {
        backendClient.Cancel();
        worldImporter.DestroyCurrentWorld();
        TransitionTo(State.Idle);
    }

    private void HandleJobCreated(string jobId)
    {
        TransitionTo(State.Processing);
        SetStatus($"Job {jobId.Substring(0, 8)}... queued.");
    }

    private void HandleProgressUpdate(string message, int progress)
    {
        SetProgress(progress, message);
    }

    private void HandleDownloadComplete(string filePath)
    {
        SetStatus("Loading 3D world...");
        Debug.Log($"[AppManager] Ignoring glb load for now, file saved to: {filePath}");
        StartCoroutine(LoadSkyboxTexture(filePath));
    }

    private System.Collections.IEnumerator LoadSkyboxTexture(string filePath)
    {
        Texture2D texture = null;
        
        // 1. Check if it's the 1-byte mock file (Mock Mode)
        var fileInfo = new System.IO.FileInfo(filePath);
        if (fileInfo.Exists && fileInfo.Length < 100)
        {
            Debug.Log("[AppManager] Detected mock 1-byte file. Generating a procedural gradient skybox for testing...");
            texture = new Texture2D(1024, 512, TextureFormat.RGBA32, false);
            for (int y = 0; y < texture.height; y++)
            {
                Color c = Color.Lerp(new Color(0.1f, 0.2f, 0.5f), new Color(0.8f, 0.4f, 0.2f), (float)y / texture.height);
                for (int x = 0; x < texture.width; x++) texture.SetPixel(x, y, c);
            }
            texture.Apply();
        }
        else
        {
            // 2. Load the actual downloaded JPG
            string url = "file:///" + filePath.Replace("\\", "/");
            using (UnityEngine.Networking.UnityWebRequest uwr = UnityEngine.Networking.UnityWebRequestTexture.GetTexture(url))
            {
                yield return uwr.SendWebRequest();

                if (uwr.result != UnityEngine.Networking.UnityWebRequest.Result.Success)
                {
                    Debug.LogError($"[AppManager] Failed to load skybox texture: {uwr.error}");
                    SetStatus($"Error loading texture.");
                    yield break;
                }
                texture = UnityEngine.Networking.DownloadHandlerTexture.GetContent(uwr);
            }
        }
        
        // 3. Apply the texture to the Unity Skybox
        if (texture != null)
        {
            Material skyboxMat = new Material(Shader.Find("Skybox/Panoramic"));
            skyboxMat.mainTexture = texture;
            RenderSettings.skybox = skyboxMat;
            DynamicGI.UpdateEnvironment(); // Update lighting to match the new sky
            Debug.Log($"[AppManager] Skybox applied successfully.");
        }
        
        TransitionTo(State.Viewing);
    }

    private void HandleError(string error)
    {
        Debug.LogError($"[AppManager] {error}");
        SetStatus($"Error: {error}");
        Invoke(nameof(ReturnToIdle), 4f);
    }

    private void SetActive(GameObject panel, bool active)
    {
        if (panel != null) panel.SetActive(active);
    }

    private void SetStatus(string text)
    {
        if (txtStatus != null) txtStatus.text = text;
    }

    private void SetProgress(int percent, string message)
    {
        if (sliderProgress != null) sliderProgress.value = percent / 100f;
        if (txtProgress != null) txtProgress.text = $"{percent}%";
        if (txtStatus != null) txtStatus.text = message;
    }

    private void ReturnToIdle() { TransitionTo(State.Idle); }

    private GameObject FindByName(string objectName)
    {
        foreach (var root in UnityEngine.SceneManagement.SceneManager.GetActiveScene().GetRootGameObjects())
        {
            var found = SearchChildren(root.transform, objectName);
            if (found != null) return found.gameObject;
        }
        Debug.LogWarning($"[AppManager] Could not find: '{objectName}'");
        return null;
    }

    private Transform SearchChildren(Transform parent, string name)
    {
        if (parent.name == name) return parent;
        for (int i = 0; i < parent.childCount; i++)
        {
            var result = SearchChildren(parent.GetChild(i), name);
            if (result != null) return result;
        }
        return null;
    }
}
