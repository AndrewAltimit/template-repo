using System.Diagnostics;
using System.Numerics;
using System.Runtime.InteropServices;
using Reloaded.Memory.SigScan;
using Reloaded.Memory.SigScan.Definitions.Structs;
using Reloaded.Mod.Interfaces;

namespace NmsCockpitOverlay.CockpitTracker;

/// <summary>
/// Reads view and projection matrices from No Man's Sky memory using signature scanning.
///
/// IMPORTANT: These signatures are specific to particular NMS versions.
/// After game updates, the signatures may need to be updated.
///
/// Finding new signatures:
/// 1. Use x64dbg or IDA to find the camera update function
/// 2. Look for matrix multiplication sequences near player tick
/// 3. The view matrix is typically near the camera/player controller
/// 4. The projection matrix is updated when FOV changes
///
/// Pattern format: "XX XX XX ?? ?? XX" where ?? is wildcard
/// </summary>
public class MatrixReader
{
    private readonly ILogger? _logger;
    private IntPtr _viewMatrixPtr;
    private IntPtr _projMatrixPtr;
    private bool _isInitialized;

    // Known signatures for different NMS versions
    // Format: (exeHash, viewPattern, viewOffset, projPattern, projOffset)
    private static readonly Dictionary<string, SignatureSet> KnownSignatures = new()
    {
        // NMS 4.x - Update these patterns after finding them in a specific version
        // The patterns here are PLACEHOLDERS - real patterns must be discovered
        // by reverse engineering each NMS version
        ["placeholder"] = new SignatureSet
        {
            ViewPattern = "48 8B ?? ?? ?? ?? ?? 48 85 C0 74 ?? F3 0F 10",
            ViewOffset = 3,
            ProjPattern = "F3 0F 10 ?? ?? ?? ?? ?? F3 0F 10 ?? ?? ?? ?? ?? 0F 28",
            ProjOffset = 4,
        }
    };

    /// <summary>
    /// Signature patterns and offsets for a specific NMS version.
    /// </summary>
    private record SignatureSet
    {
        public required string ViewPattern { get; init; }
        public required int ViewOffset { get; init; }
        public required string ProjPattern { get; init; }
        public required int ProjOffset { get; init; }
    }

    public MatrixReader(ILogger? logger)
    {
        _logger = logger;
    }

    /// <summary>
    /// Whether initialization was successful.
    /// </summary>
    public bool IsInitialized => _isInitialized;

    /// <summary>
    /// Initialize the matrix reader by scanning for signatures.
    /// </summary>
    public bool Initialize()
    {
        try
        {
            var process = Process.GetCurrentProcess();
            var mainModule = process.MainModule;
            if (mainModule == null)
            {
                _logger?.WriteLine("[MatrixReader] Could not get main module");
                return false;
            }

            var baseAddress = mainModule.BaseAddress;
            var moduleSize = mainModule.ModuleMemorySize;

            _logger?.WriteLine($"[MatrixReader] Scanning module: {mainModule.ModuleName}");
            _logger?.WriteLine($"[MatrixReader] Base: 0x{baseAddress.ToInt64():X}, Size: {moduleSize}");

            // Calculate EXE hash for version detection
            var exeHash = CalculateExeHash(mainModule.FileName);
            _logger?.WriteLine($"[MatrixReader] EXE hash: {exeHash}");

            // Try to find matching signatures
            if (!TryFindSignatures(baseAddress, moduleSize))
            {
                _logger?.WriteLine("[MatrixReader] No matching signatures found");
                _logger?.WriteLine("[MatrixReader] This game version may require new signatures");
                return false;
            }

            _isInitialized = true;
            return true;
        }
        catch (Exception ex)
        {
            _logger?.WriteLine($"[MatrixReader] Initialization failed: {ex.Message}");
            return false;
        }
    }

    /// <summary>
    /// Try to find camera matrix signatures in memory.
    /// </summary>
    private bool TryFindSignatures(IntPtr baseAddress, int moduleSize)
    {
        // For now, return false since we don't have real signatures
        // Real implementation would:
        // 1. Create a Scanner with the module memory region
        // 2. Search for the view matrix pattern
        // 3. Search for the projection matrix pattern
        // 4. Resolve relative addresses to absolute pointers

        _logger?.WriteLine("[MatrixReader] WARNING: Using placeholder signatures");
        _logger?.WriteLine("[MatrixReader] Real signatures must be discovered for each NMS version");

        // Placeholder: In a real implementation, you would:
        //
        // using var scanner = new Scanner(process, baseAddress, moduleSize);
        //
        // var viewResult = scanner.FindPattern(signatureSet.ViewPattern);
        // if (!viewResult.Found) return false;
        //
        // var viewInstructionAddr = baseAddress + viewResult.Offset;
        // var viewRelativeOffset = Marshal.ReadInt32(viewInstructionAddr + signatureSet.ViewOffset);
        // _viewMatrixPtr = viewInstructionAddr + signatureSet.ViewOffset + 4 + viewRelativeOffset;
        //
        // Similar for projection matrix...

        return false;
    }

    /// <summary>
    /// Try to read the current view and projection matrices.
    /// </summary>
    public bool TryReadMatrices(out Matrix4x4 view, out Matrix4x4 proj)
    {
        view = Matrix4x4.Identity;
        proj = Matrix4x4.Identity;

        if (!_isInitialized || _viewMatrixPtr == IntPtr.Zero || _projMatrixPtr == IntPtr.Zero)
        {
            return false;
        }

        try
        {
            // Read raw matrix data from memory
            unsafe
            {
                var viewPtr = (float*)_viewMatrixPtr.ToPointer();
                var projPtr = (float*)_projMatrixPtr.ToPointer();

                view = new Matrix4x4(
                    viewPtr[0], viewPtr[1], viewPtr[2], viewPtr[3],
                    viewPtr[4], viewPtr[5], viewPtr[6], viewPtr[7],
                    viewPtr[8], viewPtr[9], viewPtr[10], viewPtr[11],
                    viewPtr[12], viewPtr[13], viewPtr[14], viewPtr[15]
                );

                proj = new Matrix4x4(
                    projPtr[0], projPtr[1], projPtr[2], projPtr[3],
                    projPtr[4], projPtr[5], projPtr[6], projPtr[7],
                    projPtr[8], projPtr[9], projPtr[10], projPtr[11],
                    projPtr[12], projPtr[13], projPtr[14], projPtr[15]
                );
            }

            // Validate matrices (basic sanity check)
            if (!IsValidMatrix(view) || !IsValidMatrix(proj))
            {
                return false;
            }

            return true;
        }
        catch
        {
            return false;
        }
    }

    /// <summary>
    /// Basic validation that a matrix contains finite values.
    /// </summary>
    private static bool IsValidMatrix(Matrix4x4 m)
    {
        return float.IsFinite(m.M11) && float.IsFinite(m.M22) && float.IsFinite(m.M33) &&
               float.IsFinite(m.M44) && Math.Abs(m.M44) > 0.0001f;
    }

    /// <summary>
    /// Calculate a hash of the EXE for version detection.
    /// </summary>
    private static string CalculateExeHash(string? path)
    {
        if (string.IsNullOrEmpty(path) || !File.Exists(path))
        {
            return "unknown";
        }

        try
        {
            // Use file size + timestamp as a quick hash
            var info = new FileInfo(path);
            return $"{info.Length:X}_{info.LastWriteTimeUtc.Ticks:X}";
        }
        catch
        {
            return "error";
        }
    }
}
