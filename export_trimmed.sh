#!/bin/bash
# Export all trimmed files from source directory to destination, preserving folder structure
# Usage: ./export_trimmed.sh <source_dir> <dest_dir>

# Check arguments
if [ $# -lt 2 ]; then
    echo "Usage: $0 <source_dir> <dest_dir>"
    echo ""
    echo "This script finds all 'trimmed' folders under source_dir and"
    echo "copies their contents to dest_dir, preserving the folder structure."
    echo ""
    echo "Example:"
    echo "  $0 '/Users/wgong/Downloads/合集·海底小纵队' '/Users/wgong/Movies/海底小纵队_trimmed'"
    exit 1
fi

SOURCE_DIR="$1"
DEST_DIR="$2"

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Source directory '$SOURCE_DIR' does not exist"
    exit 1
fi

# Create destination directory if it doesn't exist
mkdir -p "$DEST_DIR"

echo "Source: $SOURCE_DIR"
echo "Destination: $DEST_DIR"
echo ""

# Initialize counters
total_files=0
total_copied=0
total_skipped=0

# Find all 'trimmed' directories and copy their contents
while IFS= read -r -d '' trimmed_dir; do
    # Get the relative path from source to the parent of trimmed folder
    parent_dir=$(dirname "$trimmed_dir")
    relative_path="${parent_dir#$SOURCE_DIR}"
    relative_path="${relative_path#/}"  # Remove leading slash if present
    
    # Create corresponding directory in destination
    if [ -n "$relative_path" ]; then
        dest_subdir="$DEST_DIR/$relative_path"
    else
        dest_subdir="$DEST_DIR"
    fi
    
    # Count files
    file_count=$(find "$trimmed_dir" -maxdepth 1 -type f -name "*.mkv" | wc -l | tr -d ' ')
    
    if [ "$file_count" -gt 0 ]; then
        mkdir -p "$dest_subdir"
        echo "📁 $relative_path/ ($file_count files)"
        
        # Copy each mkv file, skip if exists
        while IFS= read -r -d '' src_file; do
            filename=$(basename "$src_file")
            dest_file="$dest_subdir/$filename"
            total_files=$((total_files + 1))
            
            if [ -f "$dest_file" ]; then
                # Check if sizes match
                src_size=$(stat -f%z "$src_file" 2>/dev/null || stat -c%s "$src_file" 2>/dev/null)
                dest_size=$(stat -f%z "$dest_file" 2>/dev/null || stat -c%s "$dest_file" 2>/dev/null)
                if [ "$src_size" = "$dest_size" ]; then
                    echo "  [SKIP] $filename (already exists)"
                    total_skipped=$((total_skipped + 1))
                    continue
                fi
            fi
            
            echo "  [COPY] $filename"
            cp "$src_file" "$dest_subdir/"
            total_copied=$((total_copied + 1))
        done < <(find "$trimmed_dir" -maxdepth 1 -type f -name "*.mkv" -print0)
        echo ""
    fi
done < <(find "$SOURCE_DIR" -type d -name "trimmed" -print0)

echo "✅ Export complete!"
echo "Total files: $total_files"
echo "Copied: $total_copied"
echo "Skipped (already exist): $total_skipped"
echo "Files exported to: $DEST_DIR"
