#!/bin/bash

# Create test videos for video editor validation
# Creates various short test clips with different properties

set -e

# Output directory for test videos
OUTPUT_DIR="outputs/video-editor/test_videos"
mkdir -p "$OUTPUT_DIR"

echo "Creating test videos for video editor validation..."

# Function to create a test video with specific properties
create_test_video() {
    local name=$1
    local duration=$2
    local text=$3
    local bg_color=$4
    local text_color=${5:-white}
    local audio_tone=${6:-440}  # Audio frequency in Hz

    echo "Creating $name.mp4 (${duration}s) - $text"

    # Create video with text overlay and audio tone
    # Note: Using text without font file - ffmpeg will use built-in font
    ffmpeg -y -f lavfi -i "color=c=${bg_color}:s=640x360:d=${duration}" \
           -f lavfi -i "sine=frequency=${audio_tone}:duration=${duration}" \
           -vf "drawtext=text='${text}':fontcolor=${text_color}:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2" \
           -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
           -c:a aac -b:a 128k \
           "${OUTPUT_DIR}/${name}.mp4" 2>/dev/null
}

# Create Camera 1 - Presenter/Speaker video (10 seconds)
create_test_video "camera1_presenter" 10 "Presenter View\nThis is an important presentation\nAbout video editing" "darkblue" "white" 440

# Create Camera 2 - Audience/Reaction video (10 seconds)
create_test_video "camera2_audience" 10 "Audience View\nGreat presentation!\nVery informative" "darkgreen" "white" 880

# Create short clip for testing (5 seconds)
create_test_video "short_clip" 5 "Short Test Clip\nFor quick validation" "darkred" "yellow" 660

# Create clip with "silence" (low volume) section (15 seconds)
echo "Creating video with silence section..."
# First part with audio (5s)
ffmpeg -y -f lavfi -i "color=c=black:s=640x360:d=5" \
       -f lavfi -i "sine=frequency=440:duration=5" \
       -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Speaking Section':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2" \
       -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
       -c:a aac -b:a 128k \
       "${OUTPUT_DIR}/part1_audio.mp4" 2>/dev/null

# Silent part (5s)
ffmpeg -y -f lavfi -i "color=c=gray:s=640x360:d=5" \
       -f lavfi -i "anullsrc=duration=5" \
       -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Silent Section':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2" \
       -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
       -c:a aac -b:a 128k \
       "${OUTPUT_DIR}/part2_silence.mp4" 2>/dev/null

# Last part with audio (5s)
ffmpeg -y -f lavfi -i "color=c=black:s=640x360:d=5" \
       -f lavfi -i "sine=frequency=880:duration=5" \
       -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='Speaking Again':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2" \
       -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
       -c:a aac -b:a 128k \
       "${OUTPUT_DIR}/part3_audio.mp4" 2>/dev/null

# Concatenate parts
echo "file 'part1_audio.mp4'" > "${OUTPUT_DIR}/concat_list.txt"
echo "file 'part2_silence.mp4'" >> "${OUTPUT_DIR}/concat_list.txt"
echo "file 'part3_audio.mp4'" >> "${OUTPUT_DIR}/concat_list.txt"

ffmpeg -y -f concat -safe 0 -i "${OUTPUT_DIR}/concat_list.txt" -c copy "${OUTPUT_DIR}/video_with_silence.mp4" 2>/dev/null

# Clean up temp files
rm -f "${OUTPUT_DIR}/part1_audio.mp4" "${OUTPUT_DIR}/part2_silence.mp4" "${OUTPUT_DIR}/part3_audio.mp4" "${OUTPUT_DIR}/concat_list.txt"

# Create a video with scene changes (20 seconds total)
echo "Creating video with scene changes..."
scenes=("Scene 1\nIntroduction" "Scene 2\nMain Content" "Scene 3\nKey Points" "Scene 4\nConclusion")
colors=("navy" "darkgreen" "maroon" "purple")

for i in {0..3}; do
    ffmpeg -y -f lavfi -i "color=c=${colors[$i]}:s=640x360:d=5" \
           -f lavfi -i "sine=frequency=$((440 + i*220)):duration=5" \
           -vf "drawtext=fontfile=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf:text='${scenes[$i]}':fontcolor=white:fontsize=24:x=(w-text_w)/2:y=(h-text_h)/2" \
           -c:v libx264 -preset ultrafast -pix_fmt yuv420p \
           -c:a aac -b:a 128k \
           "${OUTPUT_DIR}/scene_${i}.mp4" 2>/dev/null
done

# Concatenate scenes
: > "${OUTPUT_DIR}/scene_list.txt"
for i in {0..3}; do
    echo "file 'scene_${i}.mp4'" >> "${OUTPUT_DIR}/scene_list.txt"
done

ffmpeg -y -f concat -safe 0 -i "${OUTPUT_DIR}/scene_list.txt" -c copy "${OUTPUT_DIR}/video_with_scenes.mp4" 2>/dev/null

# Clean up temp files
rm -f "${OUTPUT_DIR}"/scene_*.mp4 "${OUTPUT_DIR}/scene_list.txt"

echo ""
echo "Test videos created successfully in ${OUTPUT_DIR}/"
echo "Available test videos:"
find "${OUTPUT_DIR}" -name "*.mp4" -exec ls -lh {} \; | awk '{print "  - " $9 " (" $5 ")"}'
echo ""
echo "Videos created with different properties for testing:"
echo "  1. camera1_presenter.mp4 - Simulated presenter view (10s)"
echo "  2. camera2_audience.mp4 - Simulated audience view (10s)"
echo "  3. short_clip.mp4 - Short test clip (5s)"
echo "  4. video_with_silence.mp4 - Video with silent section (15s)"
echo "  5. video_with_scenes.mp4 - Video with scene changes (20s)"
