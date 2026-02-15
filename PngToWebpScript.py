from PIL import Image
import os
from pathlib import Path
import argparse
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import queue
import shutil

class OutputManager:
    def __init__(self):
        self.lock = Lock()
        
    def print_result(self, message):
        with self.lock:
            print(message)

def calculate_aspect_ratio_resize(original_size, target_size):
    """
    Calculate new dimensions that fit within target_size while maintaining aspect ratio.
    
    Args:
        original_size (tuple): Original (width, height)
        target_size (tuple): Target (width, height)
        
    Returns:
        tuple: New (width, height) that fits within target while preserving aspect ratio
    """
    orig_width, orig_height = original_size
    target_width, target_height = target_size
    
    # Calculate aspect ratios
    orig_aspect = orig_width / orig_height
    target_aspect = target_width / target_height
    
    # Determine which dimension is the limiting factor
    if orig_aspect > target_aspect:
        # Image is wider than target aspect ratio - width is limiting
        new_width = target_width
        new_height = int(target_width / orig_aspect)
    else:
        # Image is taller than target aspect ratio - height is limiting
        new_height = target_height
        new_width = int(target_height * orig_aspect)
    
    return (new_width, new_height)

def convert_png_to_webp(input_path, method='auto', max_workers=None, resize=True, target_size=(512, 512)):
    """
    Convert PNG images to WebP format with optimized compression settings using multiple threads.
    Non-PNG files will be copied to the destination folder.
    
    Args:
        input_path (str): Path to PNG file or directory containing PNG files
        method (str): Compression method - 'auto' (tries both), 'lossy', or 'lossless'
        max_workers (int): Maximum number of worker threads (None for default)
        resize (bool): Whether to resize images to target_size
        target_size (tuple): Target size as (width, height) if resize is True
    """
    input_path = Path(input_path).resolve()
    output_manager = OutputManager()
    
    # Determine output location based on input type
    if input_path.is_file():
        # For single file: create output file at same level with .webp extension
        # or in converted folder if it's not a PNG
        if input_path.suffix.lower() == '.png':
            converted_base = None  # Will be handled differently for single files
        else:
            converted_base = input_path.parent / 'converted'
            converted_base.mkdir(parents=True, exist_ok=True)
    else:
        # For directory: create 'converted' folder structure
        converted_base = input_path.parent / 'converted' / input_path.name
        converted_base.mkdir(parents=True, exist_ok=True)
    
    def try_compression_methods(img, output_path):
        """Try different compression methods and return the smallest file."""
        methods = {
            'lossless': {
                'lossless': True,
                'quality': 100,
                'method': 6,
            },
            'lossy': {
                'lossless': False,
                'quality': 90,
                'method': 6,
                'preprocessing': 4,
                'filter': 2,
            }
        }
        
        best_size = float('inf')
        best_method = None
        temp_path = output_path.parent / f"temp_{output_path.name}"
        
        for method_name, settings in methods.items():
            try:
                img.save(temp_path, 'WEBP', **settings)
                size = os.path.getsize(temp_path)
                
                if size < best_size:
                    best_size = size
                    best_method = method_name
                    if output_path.exists():
                        output_path.unlink()
                    temp_path.rename(output_path)
                else:
                    temp_path.unlink()
            except Exception as e:
                output_manager.print_result(f"Error trying {method_name} compression: {str(e)}")
                if temp_path.exists():
                    temp_path.unlink()
        
        return best_method
    
    def process_file(file_path):
        """Process a single file and return the results."""
        try:
            # Handle single file input differently
            if input_path.is_file():
                if file_path.suffix.lower() == '.png':
                    # For single PNG file: output directly with .webp extension
                    output_path = file_path.with_suffix('.webp')
                    relative_path = file_path.name
                else:
                    # For single non-PNG file: copy to converted folder
                    output_path = converted_base / file_path.name
                    relative_path = file_path.name
            else:
                # For directory input: maintain structure in converted folder
                relative_path = file_path.relative_to(input_path)
                output_path = converted_base / relative_path
                output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # If not a PNG file, just copy it
            if file_path.suffix.lower() != '.png':
                if not input_path.is_file() or converted_base:
                    shutil.copy2(file_path, output_path)
                    output_manager.print_result(f"Copied non-PNG file: {relative_path}")
                else:
                    output_manager.print_result(f"Skipped non-PNG file: {relative_path}")
                return
                
            # For PNG files, convert to WebP
            if not file_path.suffix.lower() == '.png':
                webp_output_path = output_path.with_suffix('.webp')
            else:
                webp_output_path = output_path if output_path.suffix == '.webp' else output_path.with_suffix('.webp')
                
            with Image.open(file_path) as img:
                original_size = os.path.getsize(file_path) / 1024  # KB
                original_dimensions = img.size
                
                # Use the image as is or resize
                if resize:
                # Calculate dimensions that maintain aspect ratio
                    new_dimensions = calculate_aspect_ratio_resize(img.size, target_size)
                    processed_img = img.resize(new_dimensions, Image.Resampling.LANCZOS)
                    final_dimensions = new_dimensions
                else:
                    processed_img = img.copy()
                    final_dimensions = original_dimensions
                
                if method == 'auto':
                    best_method = try_compression_methods(processed_img, webp_output_path)
                else:
                    settings = {
                        'lossless': {
                            'lossless': True,
                            'quality': 100,
                            'method': 6,
                        },
                        'lossy': {
                            'lossless': False,
                            'quality': 90,
                            'method': 6,
                            'preprocessing': 4,
                            'filter': 2,
                        }
                    }[method]
                    
                    processed_img.save(webp_output_path, 'WEBP', **settings)
                    best_method = method
                
                converted_size = os.path.getsize(webp_output_path) / 1024  # KB
                reduction = ((original_size - converted_size) / original_size * 100)
                
                result = (
                    f"Converted: {relative_path}\n"
                    f"Dimensions: {final_dimensions[0]}x{final_dimensions[1]}\n"
                    f"Method used: {best_method}\n"
                    f"Original size: {original_size:.2f} KB\n"
                    f"WebP size: {converted_size:.2f} KB\n"
                    f"Size reduction: {reduction:.2f}%\n"
                )
                output_manager.print_result(result)
                
        except Exception as e:
            output_manager.print_result(f"Error processing {file_path}: {str(e)}")
    
    def process_files():
        # Collect all files to process
        if input_path.is_file():
            files = [input_path]
        else:
            files = [f for f in input_path.rglob('*') if f.is_file()]
        
        # Process files using thread pool
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all files for processing
            futures = [executor.submit(process_file, file) for file in files]
            
            # Wait for all tasks to complete
            for future in futures:
                future.result()
    
    # Start processing
    process_files()
    
    # Print completion message
    if input_path.is_file() and input_path.suffix.lower() == '.png':
        output_manager.print_result(f"\nProcessing completed. Output file: {input_path.with_suffix('.webp')}")
    elif converted_base:
        output_manager.print_result(f"\nAll processing completed. Output saved in: {converted_base}")
    else:
        output_manager.print_result("\nProcessing completed.")

def main():
    parser = argparse.ArgumentParser(
        description='Convert PNG images to WebP format and copy other files to destination folder.'
    )
    parser.add_argument(
        'path',
        help='Path to file or directory containing files'
    )
    parser.add_argument(
        '--method',
        choices=['auto', 'lossy', 'lossless'],
        default='auto',
        help='Compression method (default: auto)'
    )
    parser.add_argument(
        '--threads',
        type=int,
        default=None,
        help='Number of worker threads (default: CPU count)'
    )
    parser.add_argument(
        '--resize',
        action='store_true',
        help='Resize images to specified dimensions (default: maintain original size)'
    )
    parser.add_argument(
        '--width',
        type=int,
        default=302,
        help='Target width in pixels for resize (default: 302)'
    )
    parser.add_argument(
        '--height',
        type=int,
        default=170,
        help='Target height in pixels for resize (default: 170)'
    )
    
    args = parser.parse_args()
    target_size = (args.width, args.height)
    convert_png_to_webp(args.path, args.method, args.threads, True, (512,512))

if __name__ == "__main__":
    main()