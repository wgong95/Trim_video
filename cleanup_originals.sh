#!/bin/bash
# Delete original mkv files after trimmed versions exist
# Usage: ./cleanup_originals.sh <directory> [--dry-run]

# Check arguments
if [ $# -lt 1 ]; then
    echo "Usage: $0 <directory> [--dry-run]"
    echo ""
    echo "This script deletes original .mkv files in directories that have"
    echo "a 'trimmed' subfolder with corresponding files."
    echo ""
    echo "Options:"
    echo "  --dry-run    Preview what would be deleted without actually deleting"
    echo ""
    echo "Example:"
    echo "  $0 '/Users/wgong/Downloads/合集·海底小纵队' --dry-run   # Preview"
    echo "  $0 '/Users/wgong/Downloads/合集·海底小纵队'             # Delete"
    exit 1
fi

SOURCE_DIR="$1"
DRY_RUN=false

if [ "$2" = "--dry-run" ]; then
    DRY_RUN=true
    echo "🔍 DRY RUN MODE - No files will be deleted"
    echo ""
fi

# Check if source directory exists
if [ ! -d "$SOURCE_DIR" ]; then
    echo "Error: Directory '$SOURCE_DIR' does not exist"
    exit 1
fi

echo "Directory: $SOURCE_DIR"
echo ""

total_count=0
total_size=0

# Find all 'trimmed' directories
while IFS= read -r -d '' trimmed_dir; do
    parent_dir=$(dirname "$trimmed_dir")
    
    # Find .mkv files in parent directory (not in trimmed)
    for mkv_file in "$parent_dir"/*.mkv; do
        # Check if file exists (glob might not match anything)
        [ -f "$mkv_file" ] || continue
        
        filename=$(basename "$mkv_file")
        trimmed_file="$trimmed_dir/$filename"
        
        # Only delete if trimmed version exists
        if [ -f "$trimmed_file" ]; then
            file_size=$(stat -f%z "$mkv_file" 2>/dev/null || stat -c%s "$mkv_file" 2>/dev/null)
            file_size_mb=$((file_size / 1024 / 1024))
            
            if [ "$DRY_RUN" = true ]; then
                echo "Would delete: $mkv_file (${file_size_mb}MB)"
            else
                echo "Deleting: $mkv_file (${file_size_mb}MB)"
                rm "$mkv_file"
            fi
            
            total_count=$((total_count + 1))
            total_size=$((total_size + file_size_mb))
        fi
    done
done < <(find "$SOURCE_DIR" -type d -name "trimmed" -print0)

echo ""
echo "=================================="
if [ "$DRY_RUN" = true ]; then
    echo "Would delete $total_count file(s)"
    echo "Would free approximately ${total_size}MB"
    echo ""
    echo "Run without --dry-run to actually delete files."
else
    echo "✅ Deleted $total_count file(s)"
    echo "Freed approximately ${total_size}MB"
fi
