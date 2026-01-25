using Reloaded.Mod.Interfaces;
using NmsCockpitOverlay.CockpitTracker;
using NmsCockpitOverlay.Ipc;

namespace NmsCockpitOverlay;

/// <summary>
/// Main entry point for the NMS Cockpit Overlay mod.
/// Extracts camera matrices and cockpit screen coordinates from No Man's Sky
/// and sends them to the video overlay daemon via named pipe.
/// </summary>
public class Mod : IMod
{
    /// <summary>
    /// Used for logging to the Reloaded-II console.
    /// </summary>
    private ILogger? _logger;

    /// <summary>
    /// Mod configuration (user-adjustable settings).
    /// </summary>
    private IModConfig? _config;

    /// <summary>
    /// Signature scanner for finding camera matrices.
    /// </summary>
    private MatrixReader? _matrixReader;

    /// <summary>
    /// Computes screen-space projection of cockpit screen.
    /// </summary>
    private ScreenProjection? _screenProjection;

    /// <summary>
    /// Named pipe client for sending data to daemon.
    /// </summary>
    private PipeClient? _pipeClient;

    /// <summary>
    /// Whether the mod is currently active.
    /// </summary>
    private bool _isActive;

    /// <summary>
    /// Token for cancelling the update loop.
    /// </summary>
    private CancellationTokenSource? _cts;

    /// <summary>
    /// Background task for the update loop.
    /// </summary>
    private Task? _updateTask;

    /// <summary>
    /// Called when the mod is first loaded.
    /// </summary>
    public void Start(IModLoaderV1 loader)
    {
        _config = loader.GetModConfig();
        _logger = loader.GetLogger();

        _logger.WriteLine("[NMS Cockpit Overlay] Starting...");

        try
        {
            // Initialize components
            _pipeClient = new PipeClient("nms_cockpit_injector", _logger);
            _matrixReader = new MatrixReader(_logger);
            _screenProjection = new ScreenProjection();

            // Try to find signatures
            if (_matrixReader.Initialize())
            {
                _logger.WriteLine("[NMS Cockpit Overlay] Signature scan successful");
                StartUpdateLoop();
            }
            else
            {
                _logger.WriteLine("[NMS Cockpit Overlay] WARNING: Signature scan failed - mod disabled");
                _logger.WriteLine("[NMS Cockpit Overlay] This game version may not be supported");
            }
        }
        catch (Exception ex)
        {
            _logger.WriteLine($"[NMS Cockpit Overlay] ERROR: {ex.Message}");
        }
    }

    /// <summary>
    /// Start the background update loop.
    /// </summary>
    private void StartUpdateLoop()
    {
        _isActive = true;
        _cts = new CancellationTokenSource();
        _updateTask = Task.Run(UpdateLoopAsync, _cts.Token);
        _logger?.WriteLine("[NMS Cockpit Overlay] Update loop started");
    }

    /// <summary>
    /// Background loop that reads camera matrices and sends updates.
    /// </summary>
    private async Task UpdateLoopAsync()
    {
        const int targetFps = 60;
        const int frameTimeMs = 1000 / targetFps;

        while (!_cts!.Token.IsCancellationRequested && _isActive)
        {
            try
            {
                var startTime = Environment.TickCount64;

                // Read camera matrices
                if (_matrixReader!.TryReadMatrices(out var view, out var proj))
                {
                    // Compute screen rect
                    var rect = _screenProjection!.ComputeCockpitRect(view, proj);

                    // Send to daemon
                    if (rect.HasValue)
                    {
                        await _pipeClient!.SendScreenRectAsync(rect.Value);
                    }
                }

                // Sleep to maintain target FPS
                var elapsed = Environment.TickCount64 - startTime;
                var sleepTime = (int)(frameTimeMs - elapsed);
                if (sleepTime > 0)
                {
                    await Task.Delay(sleepTime, _cts.Token);
                }
            }
            catch (OperationCanceledException)
            {
                break;
            }
            catch (Exception ex)
            {
                _logger?.WriteLine($"[NMS Cockpit Overlay] Update error: {ex.Message}");
                await Task.Delay(1000, _cts.Token); // Back off on error
            }
        }
    }

    /// <summary>
    /// Called when the mod can be unloaded.
    /// </summary>
    public void Suspend()
    {
        _isActive = false;
        _cts?.Cancel();
        _updateTask?.Wait(1000);
        _pipeClient?.Disconnect();
        _logger?.WriteLine("[NMS Cockpit Overlay] Suspended");
    }

    /// <summary>
    /// Called when the mod is being reloaded.
    /// </summary>
    public void Resume()
    {
        if (_matrixReader?.IsInitialized == true)
        {
            _pipeClient?.TryConnect();
            StartUpdateLoop();
            _logger?.WriteLine("[NMS Cockpit Overlay] Resumed");
        }
    }

    /// <summary>
    /// Called when the mod is being unloaded permanently.
    /// </summary>
    public void Unload()
    {
        Suspend();
        _pipeClient?.Dispose();
        _logger?.WriteLine("[NMS Cockpit Overlay] Unloaded");
    }

    /// <summary>
    /// Whether this mod can be unloaded.
    /// </summary>
    public bool CanUnload() => true;

    /// <summary>
    /// Whether this mod can be suspended.
    /// </summary>
    public bool CanSuspend() => true;

    /// <summary>
    /// Mod action (unused).
    /// </summary>
    public Action? Disposing { get; }
}
