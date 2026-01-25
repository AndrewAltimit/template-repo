using System.IO.Pipes;
using Reloaded.Mod.Interfaces;

namespace NmsCockpitOverlay.Ipc;

/// <summary>
/// Named pipe client for sending screen rect data to the video overlay daemon.
///
/// Wire format (ITK Protocol):
/// - 4 bytes: Magic "ITKP"
/// - 4 bytes: Version (1)
/// - 4 bytes: Message type (10 = ScreenRect)
/// - 4 bytes: Payload length
/// - 4 bytes: CRC32 of payload
/// - N bytes: Payload (bincode-encoded ScreenRect)
/// </summary>
public class PipeClient : IDisposable
{
    private const string MagicBytes = "ITKP";
    private const uint ProtocolVersion = 1;
    private const uint MessageTypeScreenRect = 10;

    private readonly string _pipeName;
    private readonly ILogger? _logger;
    private NamedPipeClientStream? _pipe;
    private bool _isConnected;
    private readonly object _lock = new();

    public PipeClient(string pipeName, ILogger? logger)
    {
        _pipeName = pipeName;
        _logger = logger;
    }

    /// <summary>
    /// Try to connect to the daemon's named pipe.
    /// </summary>
    public bool TryConnect()
    {
        lock (_lock)
        {
            if (_isConnected && _pipe?.IsConnected == true)
            {
                return true;
            }

            try
            {
                _pipe?.Dispose();
                _pipe = new NamedPipeClientStream(
                    ".",
                    _pipeName,
                    PipeDirection.Out,
                    PipeOptions.Asynchronous);

                // Non-blocking connect attempt
                _pipe.Connect(100);
                _isConnected = true;
                _logger?.WriteLine($"[PipeClient] Connected to {_pipeName}");
                return true;
            }
            catch (TimeoutException)
            {
                // Daemon not available yet
                return false;
            }
            catch (Exception ex)
            {
                _logger?.WriteLine($"[PipeClient] Connection error: {ex.Message}");
                return false;
            }
        }
    }

    /// <summary>
    /// Disconnect from the pipe.
    /// </summary>
    public void Disconnect()
    {
        lock (_lock)
        {
            _pipe?.Dispose();
            _pipe = null;
            _isConnected = false;
        }
    }

    /// <summary>
    /// Send a screen rect update to the daemon.
    /// </summary>
    public async Task SendScreenRectAsync(CockpitTracker.ScreenProjection.ScreenRect rect)
    {
        if (!_isConnected)
        {
            TryConnect();
            if (!_isConnected) return;
        }

        try
        {
            var message = EncodeScreenRect(rect);
            await _pipe!.WriteAsync(message, 0, message.Length);
            await _pipe.FlushAsync();
        }
        catch (IOException)
        {
            // Pipe broken, try to reconnect next time
            _isConnected = false;
        }
        catch (Exception ex)
        {
            _logger?.WriteLine($"[PipeClient] Send error: {ex.Message}");
            _isConnected = false;
        }
    }

    /// <summary>
    /// Encode a ScreenRect to ITK protocol wire format.
    /// </summary>
    private static byte[] EncodeScreenRect(CockpitTracker.ScreenProjection.ScreenRect rect)
    {
        // Payload: x, y, width, height, rotation, visible (f32, f32, f32, f32, f32, bool)
        // Using manual binary encoding to match Rust bincode format
        using var payloadStream = new MemoryStream();
        using var payloadWriter = new BinaryWriter(payloadStream);

        // Write floats as little-endian
        payloadWriter.Write(rect.X);
        payloadWriter.Write(rect.Y);
        payloadWriter.Write(rect.Width);
        payloadWriter.Write(rect.Height);
        payloadWriter.Write(rect.Rotation);
        payloadWriter.Write(rect.Visible ? (byte)1 : (byte)0);

        var payload = payloadStream.ToArray();

        // Calculate CRC32
        var crc = CalculateCrc32(payload);

        // Build full message
        using var messageStream = new MemoryStream();
        using var messageWriter = new BinaryWriter(messageStream);

        // Header
        messageWriter.Write(System.Text.Encoding.ASCII.GetBytes(MagicBytes)); // 4 bytes
        messageWriter.Write(ProtocolVersion);                                   // 4 bytes (little-endian)
        messageWriter.Write(MessageTypeScreenRect);                             // 4 bytes
        messageWriter.Write((uint)payload.Length);                              // 4 bytes
        messageWriter.Write(crc);                                               // 4 bytes

        // Payload
        messageWriter.Write(payload);

        return messageStream.ToArray();
    }

    /// <summary>
    /// Calculate CRC32 of data (matches crc32fast crate).
    /// </summary>
    private static uint CalculateCrc32(byte[] data)
    {
        // CRC32 with IEEE polynomial (same as crc32fast)
        const uint polynomial = 0xEDB88320;
        var table = new uint[256];

        for (uint i = 0; i < 256; i++)
        {
            var crc = i;
            for (int j = 0; j < 8; j++)
            {
                crc = (crc & 1) == 1 ? (crc >> 1) ^ polynomial : crc >> 1;
            }
            table[i] = crc;
        }

        uint result = 0xFFFFFFFF;
        foreach (var b in data)
        {
            result = table[(result ^ b) & 0xFF] ^ (result >> 8);
        }

        return result ^ 0xFFFFFFFF;
    }

    public void Dispose()
    {
        Disconnect();
        GC.SuppressFinalize(this);
    }
}
