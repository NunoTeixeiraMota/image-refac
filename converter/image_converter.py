from PIL import Image
import os
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from threading import Lock


# Formats Pillow can read
INPUT_FORMATS = {
    'PNG', 'JPEG', 'JPG', 'BMP', 'TIFF', 'TIF', 'GIF', 'WEBP', 'ICO', 'PPM', 'TGA',
}

# Formats Pillow can write, mapped to Pillow save format string
OUTPUT_FORMATS = {
    'webp': 'WEBP',
    'png': 'PNG',
    'jpeg': 'JPEG',
    'jpg': 'JPEG',
    'bmp': 'BMP',
    'tiff': 'TIFF',
    'gif': 'GIF',
    'ico': 'ICO',
}


def calculate_aspect_ratio_resize(original_size, target_size):
    """Calculate new dimensions that fit within target_size while maintaining aspect ratio."""
    orig_width, orig_height = original_size
    target_width, target_height = target_size

    orig_aspect = orig_width / orig_height
    target_aspect = target_width / target_height

    if orig_aspect > target_aspect:
        new_width = target_width
        new_height = int(target_width / orig_aspect)
    else:
        new_height = target_height
        new_width = int(target_height * orig_aspect)

    return (new_width, new_height)


class ImageConverter:
    """Reusable image converter supporting any Pillow-compatible format."""

    def __init__(self, output_format='webp', method='auto', quality=90,
                 resize=False, target_size=(512, 512), max_workers=None):
        self.output_format = output_format.lower()
        self.method = method
        self.quality = quality
        self.resize = resize
        self.target_size = target_size
        self.max_workers = max_workers
        self._lock = Lock()

    @staticmethod
    def supported_input_extensions():
        """Return set of supported input file extensions (lowercase, with dot)."""
        exts = set()
        for fmt in INPUT_FORMATS:
            exts.add(f'.{fmt.lower()}')
        # Add aliases
        exts.add('.jpg')
        exts.add('.tif')
        return exts

    @staticmethod
    def supported_output_formats():
        """Return list of supported output format names."""
        return sorted(set(OUTPUT_FORMATS.keys()) - {'jpg', 'tif'})

    def _get_pillow_format(self):
        return OUTPUT_FORMATS.get(self.output_format)

    def _get_save_kwargs(self, method_override=None):
        """Build save kwargs based on output format and settings."""
        fmt = self.output_format
        method = method_override or self.method

        if fmt in ('webp',):
            if method == 'lossless':
                return {'lossless': True, 'quality': 100, 'method': 6}
            elif method == 'lossy':
                return {'lossless': False, 'quality': self.quality, 'method': 6}
            else:
                return {}  # auto will try both
        elif fmt in ('jpeg', 'jpg'):
            return {'quality': self.quality, 'optimize': True}
        elif fmt == 'png':
            return {'optimize': True}
        else:
            return {}

    def convert_single(self, input_path, output_path):
        """
        Convert a single image file.

        Returns a dict with conversion results:
            {
                'input_path': str,
                'output_path': str,
                'original_size_kb': float,
                'converted_size_kb': float,
                'reduction_pct': float,
                'original_dimensions': (w, h),
                'final_dimensions': (w, h),
                'method_used': str,
                'success': bool,
                'error': str or None,
            }
        """
        input_path = Path(input_path)
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        result = {
            'input_path': str(input_path),
            'output_path': str(output_path),
            'original_size_kb': 0,
            'converted_size_kb': 0,
            'reduction_pct': 0,
            'original_dimensions': (0, 0),
            'final_dimensions': (0, 0),
            'method_used': '',
            'success': False,
            'error': None,
        }

        try:
            original_size = os.path.getsize(input_path) / 1024
            result['original_size_kb'] = round(original_size, 2)

            with Image.open(input_path) as img:
                result['original_dimensions'] = img.size

                # Convert to RGB if saving as JPEG (no alpha support)
                if self.output_format in ('jpeg', 'jpg') and img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                elif img.mode == 'P' and self.output_format == 'webp':
                    img = img.convert('RGBA')

                if self.resize:
                    new_dims = calculate_aspect_ratio_resize(img.size, self.target_size)
                    processed = img.resize(new_dims, Image.Resampling.LANCZOS)
                    result['final_dimensions'] = new_dims
                else:
                    processed = img.copy()
                    result['final_dimensions'] = img.size

                pillow_fmt = self._get_pillow_format()

                if self.output_format == 'webp' and self.method == 'auto':
                    method_used = self._try_both_webp(processed, output_path)
                    result['method_used'] = method_used
                else:
                    kwargs = self._get_save_kwargs()
                    processed.save(output_path, pillow_fmt, **kwargs)
                    result['method_used'] = self.method

            converted_size = os.path.getsize(output_path) / 1024
            result['converted_size_kb'] = round(converted_size, 2)
            if original_size > 0:
                result['reduction_pct'] = round(
                    (original_size - converted_size) / original_size * 100, 2
                )
            result['success'] = True

        except Exception as e:
            result['error'] = str(e)

        return result

    def _try_both_webp(self, img, output_path):
        """Try lossy and lossless WebP, keep the smaller one."""
        methods = {
            'lossless': {'lossless': True, 'quality': 100, 'method': 6},
            'lossy': {
                'lossless': False, 'quality': self.quality, 'method': 6,
            },
        }

        best_size = float('inf')
        best_method = 'lossy'
        temp_path = output_path.parent / f'_temp_{output_path.name}'

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
            except Exception:
                if temp_path.exists():
                    temp_path.unlink()

        return best_method

    def convert_batch(self, file_pairs):
        """
        Convert multiple files using a thread pool.

        Args:
            file_pairs: list of (input_path, output_path) tuples

        Returns:
            list of result dicts from convert_single
        """
        results = []

        def _convert(pair):
            r = self.convert_single(pair[0], pair[1])
            with self._lock:
                results.append(r)
            return r

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = [executor.submit(_convert, pair) for pair in file_pairs]
            for f in futures:
                f.result()

        return results
