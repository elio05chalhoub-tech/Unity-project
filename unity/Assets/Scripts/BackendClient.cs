using UnityEngine;

/// <summary>
/// LEGACY BackendClient — Replaced by SkyboxClient in Phase 3.
/// Keeping the class name intact so Unity scene references don't break, 
/// but the AppManager now uses SkyboxClient directly.
/// </summary>
public class BackendClient : MonoBehaviour
{
    private void Start()
    {
        Debug.LogWarning("[BackendClient] This component is deprecated! Please use SkyboxClient instead.");
    }
}
