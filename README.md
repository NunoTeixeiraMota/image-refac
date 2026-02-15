# PNG to WebP Converter

## Features

- Convert single PNG files or entire directories
- Automatic selection of best compression method (lossy vs lossless)
- Multi-threaded processing for faster conversion
- Preserves directory structure in output
- Detailed conversion statistics for each file
- Support for manual selection of compression method

## Prerequisites

- Python 3.6 or higher
- Pillow (PIL) library

## Installation

1. Clone this repository or download the script
2. Install required dependencies:
```bash
pip install Pillow
```

## Usage

### Basic Command

```bash
python converter.py path/to/image_or_directory
```

### Command Line Arguments

```bash
python converter.py [-h] [--method {auto,lossy,lossless}] [--threads THREADS] path
```

- `path`: Path to a PNG file or directory containing PNG files
- `--method`: Compression method (default: auto)
  - `auto`: Tries both lossy and lossless, keeps the smaller file
  - `lossy`: Uses lossy compression (better for photographs)
  - `lossless`: Uses lossless compression (better for screenshots/graphics)
- `--threads`: Number of worker threads (default: CPU count)

### Examples

1. Convert a single PNG file:
```bash
python converter.py image.png
```

2. Convert all PNG files in a directory:
```bash
python converter.py path/to/directory
```

3. Use specific compression method:
```bash
python converter.py --method lossy image.png
```

4. Specify number of worker threads:
```bash
python converter.py --threads 4 path/to/directory
```

## Output

- Converted files are saved in a `converted` directory at the same level as the input
- The original directory structure is preserved
- For each converted file, the following information is displayed:
  - Path to the converted file
  - Compression method used
  - Original file size
  - Converted file size
  - Percentage of size reduction

### Example Output
```
Converted: example.png
Method used: lossy
Original size: 1024.55 KB
WebP size: 285.32 KB
Size reduction: 72.15%
```

## Compression Settings

### Lossless Mode
- Quality: 100
- Method: 6 (highest compression)

### Lossy Mode
- Quality: 90
- Method: 6 (highest compression)
- Preprocessing: 4
- Filter: 2

## Notes

- The script automatically creates output directories if they don't exist
- Existing WebP files in the output directory will be overwritten
- Non-PNG files are skipped with a notification
- Error messages are displayed if any conversion fails

## Error Handling

The script includes comprehensive error handling for:
- Invalid input paths
- Corrupted image files
- File permission issues
- Disk space limitations
"# image-refac" 
