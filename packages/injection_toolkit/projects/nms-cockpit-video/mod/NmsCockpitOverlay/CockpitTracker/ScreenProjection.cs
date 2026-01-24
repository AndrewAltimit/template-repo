using System.Numerics;

namespace NmsCockpitOverlay.CockpitTracker;

/// <summary>
/// Computes the screen-space bounding rectangle for the cockpit display screen.
///
/// The cockpit screen is defined as a quad in 3D space relative to the player's
/// cockpit. This class projects those world-space corners through the view and
/// projection matrices to get 2D screen coordinates.
/// </summary>
public class ScreenProjection
{
    // Cockpit screen corners in local cockpit space (meters)
    // These values define where the "screen" is located relative to the pilot's view
    // Adjust these based on the specific cockpit geometry in NMS
    private static readonly Vector3[] CockpitScreenCorners =
    [
        new Vector3(-0.25f, 0.15f, 0.5f),  // Top-left
        new Vector3(0.25f, 0.15f, 0.5f),   // Top-right
        new Vector3(-0.25f, -0.05f, 0.5f), // Bottom-left
        new Vector3(0.25f, -0.05f, 0.5f),  // Bottom-right
    ];

    // Minimum screen size threshold (pixels)
    private const float MinScreenSize = 50f;

    // Maximum screen size as fraction of viewport
    private const float MaxScreenFraction = 0.8f;

    /// <summary>
    /// Result of projecting the cockpit screen to 2D.
    /// </summary>
    public readonly struct ScreenRect
    {
        public float X { get; init; }
        public float Y { get; init; }
        public float Width { get; init; }
        public float Height { get; init; }
        public float Rotation { get; init; }
        public bool Visible { get; init; }
    }

    /// <summary>
    /// Compute the screen-space rectangle for the cockpit display.
    /// </summary>
    /// <param name="view">View matrix from the game camera.</param>
    /// <param name="proj">Projection matrix from the game camera.</param>
    /// <param name="viewportWidth">Viewport width in pixels (default 1920).</param>
    /// <param name="viewportHeight">Viewport height in pixels (default 1080).</param>
    /// <returns>Screen rect if visible, null if not visible.</returns>
    public ScreenRect? ComputeCockpitRect(
        Matrix4x4 view,
        Matrix4x4 proj,
        float viewportWidth = 1920f,
        float viewportHeight = 1080f)
    {
        // Compute view-projection matrix
        var viewProj = view * proj;

        // Project each corner to screen space
        var screenPoints = new Vector2[4];
        var allVisible = true;

        for (int i = 0; i < 4; i++)
        {
            var worldPos = CockpitScreenCorners[i];
            var projected = ProjectToScreen(worldPos, viewProj, viewportWidth, viewportHeight, out var visible);

            if (!visible)
            {
                allVisible = false;
                break;
            }

            screenPoints[i] = projected;
        }

        if (!allVisible)
        {
            return null;
        }

        // Compute axis-aligned bounding box
        var minX = float.MaxValue;
        var minY = float.MaxValue;
        var maxX = float.MinValue;
        var maxY = float.MinValue;

        foreach (var point in screenPoints)
        {
            minX = Math.Min(minX, point.X);
            minY = Math.Min(minY, point.Y);
            maxX = Math.Max(maxX, point.X);
            maxY = Math.Max(maxY, point.Y);
        }

        var width = maxX - minX;
        var height = maxY - minY;

        // Validate size
        if (width < MinScreenSize || height < MinScreenSize)
        {
            return null;
        }

        // Clamp to viewport bounds
        minX = Math.Max(0, minX);
        minY = Math.Max(0, minY);
        maxX = Math.Min(viewportWidth, maxX);
        maxY = Math.Min(viewportHeight, maxY);

        width = maxX - minX;
        height = maxY - minY;

        // Check if too large (likely incorrect projection)
        if (width > viewportWidth * MaxScreenFraction || height > viewportHeight * MaxScreenFraction)
        {
            return null;
        }

        // Compute rotation from top edge (for perspective correction)
        var topLeft = screenPoints[0];
        var topRight = screenPoints[1];
        var rotation = MathF.Atan2(topRight.Y - topLeft.Y, topRight.X - topLeft.X);

        return new ScreenRect
        {
            X = minX,
            Y = minY,
            Width = width,
            Height = height,
            Rotation = rotation,
            Visible = true
        };
    }

    /// <summary>
    /// Project a 3D point to 2D screen coordinates.
    /// </summary>
    private static Vector2 ProjectToScreen(
        Vector3 worldPos,
        Matrix4x4 viewProj,
        float viewportWidth,
        float viewportHeight,
        out bool visible)
    {
        // Transform to clip space
        var clipPos = Vector4.Transform(new Vector4(worldPos, 1.0f), viewProj);

        // Check if behind camera
        if (clipPos.W <= 0.0001f)
        {
            visible = false;
            return Vector2.Zero;
        }

        // Perspective divide to NDC (-1 to 1)
        var ndcX = clipPos.X / clipPos.W;
        var ndcY = clipPos.Y / clipPos.W;
        var ndcZ = clipPos.Z / clipPos.W;

        // Check if outside view frustum
        if (ndcX < -1 || ndcX > 1 || ndcY < -1 || ndcY > 1 || ndcZ < 0 || ndcZ > 1)
        {
            visible = false;
            return Vector2.Zero;
        }

        // Convert to screen coordinates
        // Note: Y is inverted (NDC y=1 is top, screen y=0 is top)
        var screenX = (ndcX + 1) * 0.5f * viewportWidth;
        var screenY = (1 - ndcY) * 0.5f * viewportHeight;

        visible = true;
        return new Vector2(screenX, screenY);
    }
}
