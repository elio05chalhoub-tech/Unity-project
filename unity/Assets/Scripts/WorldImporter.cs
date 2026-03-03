using System.Threading.Tasks;
using UnityEngine;

/// <summary>
/// WorldImporter — Loads .glb files at runtime using glTFast and places them in the scene.
/// 
/// Dependencies:
///   - glTFast package (com.unity.cloud.gltfast) — install via Unity Package Manager.
///
/// Features:
///   - Async GLB loading from local file path
///   - Auto-center: moves the mesh so its bounding box center sits at world origin
///   - Auto-scale: normalizes the mesh to a configurable world-unit size
///   - Cleanup: destroys the previous world before loading a new one
/// </summary>
public class WorldImporter : MonoBehaviour
{
    [Header("Import Settings")]
    [Tooltip("Parent transform for imported models. Defaults to this transform if null.")]
    public Transform worldParent;

    [Tooltip("Auto-center and scale after import")]
    public bool autoCenterAndScale = true;

    [Tooltip("Target bounding size in world units")]
    public float targetWorldSize = 10f;

    [Header("State")]
    [SerializeField, Tooltip("Currently loaded world (read-only)")]
    private GameObject _currentWorld;

    /// <summary>
    /// Returns the currently loaded world GameObject, or null.
    /// </summary>
    public GameObject CurrentWorld => _currentWorld;

    /// <summary>
    /// Load a .glb file from disk and instantiate it in the scene.
    /// Destroys any previously loaded world first.
    /// </summary>
    public async void LoadGLB(string glbFilePath)
    {
        Debug.Log($"[WorldImporter] Loading: {glbFilePath}");

        // Clean up previous world
        DestroyCurrentWorld();

        try
        {
            // Create container
            _currentWorld = new GameObject("GeneratedWorld");
            Transform parent = worldParent != null ? worldParent : transform;
            _currentWorld.transform.SetParent(parent, false);

            // Load via glTFast
            var gltfImport = new GLTFast.GltfImport();
            bool success = await gltfImport.Load($"file://{glbFilePath}");

            if (!success)
            {
                Debug.LogError("[WorldImporter] glTFast failed to load the GLB file.");
                DestroyCurrentWorld();
                return;
            }

            // Instantiate the main scene into our container
            await gltfImport.InstantiateMainSceneAsync(_currentWorld.transform);
            Debug.Log("[WorldImporter] GLB instantiated successfully.");

            // Post-process: center and scale
            if (autoCenterAndScale)
            {
                CenterAndScaleToOrigin(_currentWorld);
            }
        }
        catch (System.Exception e)
        {
            Debug.LogError($"[WorldImporter] Exception: {e.Message}\n{e.StackTrace}");
            DestroyCurrentWorld();
        }
    }

    /// <summary>
    /// Centers the world mesh at the origin and scales it to targetWorldSize.
    /// </summary>
    private void CenterAndScaleToOrigin(GameObject worldObj)
    {
        Renderer[] renderers = worldObj.GetComponentsInChildren<Renderer>();
        if (renderers.Length == 0)
        {
            Debug.LogWarning("[WorldImporter] No renderers found — skipping center/scale.");
            return;
        }

        // Compute combined AABB
        Bounds combinedBounds = renderers[0].bounds;
        for (int i = 1; i < renderers.Length; i++)
        {
            combinedBounds.Encapsulate(renderers[i].bounds);
        }

        // Translate to origin
        worldObj.transform.position -= combinedBounds.center;

        // Uniform scale to target size
        float maxExtent = Mathf.Max(
            combinedBounds.extents.x,
            combinedBounds.extents.y,
            combinedBounds.extents.z
        );

        if (maxExtent > 0.001f)
        {
            float scale = targetWorldSize / (maxExtent * 2f);
            worldObj.transform.localScale = Vector3.one * scale;
        }

        Debug.Log($"[WorldImporter] Centered at origin, scaled to {targetWorldSize}u (bounds: {combinedBounds.size})");
    }

    /// <summary>
    /// Destroy the currently loaded world and free memory.
    /// </summary>
    public void DestroyCurrentWorld()
    {
        if (_currentWorld != null)
        {
            Destroy(_currentWorld);
            _currentWorld = null;
        }
    }
}
