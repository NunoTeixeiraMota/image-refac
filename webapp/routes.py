import uuid
from pathlib import Path

from flask import Blueprint, request, jsonify, send_file, send_from_directory

from converter.image_converter import ImageConverter, OUTPUT_FORMATS
from .utils import (
    session_upload_dir, session_conversion_dir, create_zip_in_memory,
)

api = Blueprint('api', __name__)


def _allowed_input(filename):
    ext = Path(filename).suffix.lower()
    return ext in ImageConverter.supported_input_extensions()


@api.route('/api/formats')
def formats():
    return jsonify({
        'input': sorted(ImageConverter.supported_input_extensions()),
        'output': ImageConverter.supported_output_formats(),
    })


@api.route('/api/upload', methods=['POST'])
def upload():
    files = request.files.getlist('files')
    if not files:
        return jsonify({'error': 'No files provided'}), 400

    session_id = uuid.uuid4().hex
    upload_dir = session_upload_dir(session_id)

    saved = []
    for f in files:
        if not f.filename:
            continue
        # Sanitize filename
        safe_name = Path(f.filename).name
        if not _allowed_input(safe_name):
            continue
        dest = upload_dir / safe_name
        f.save(str(dest))
        saved.append({
            'name': safe_name,
            'size_kb': round(dest.stat().st_size / 1024, 2),
        })

    if not saved:
        return jsonify({'error': 'No valid image files uploaded'}), 400

    return jsonify({'session_id': session_id, 'files': saved})


@api.route('/api/convert', methods=['POST'])
def convert():
    data = request.get_json(silent=True) or {}
    session_id = data.get('session_id')
    if not session_id:
        return jsonify({'error': 'session_id required'}), 400

    upload_dir = session_upload_dir(session_id)
    conv_dir = session_conversion_dir(session_id)

    output_format = data.get('format', 'webp')
    method = data.get('method', 'auto')
    quality = int(data.get('quality', 90))
    resize = bool(data.get('resize', False))
    width = int(data.get('width', 512))
    height = int(data.get('height', 512))
    max_workers = data.get('threads')
    if max_workers is not None:
        max_workers = int(max_workers)

    converter = ImageConverter(
        output_format=output_format,
        method=method,
        quality=quality,
        resize=resize,
        target_size=(width, height),
        max_workers=max_workers,
    )

    file_pairs = []
    for fpath in sorted(upload_dir.iterdir()):
        if not fpath.is_file():
            continue
        out_name = fpath.stem + '.' + output_format
        file_pairs.append((fpath, conv_dir / out_name))

    if not file_pairs:
        return jsonify({'error': 'No files to convert'}), 400

    results = converter.convert_batch(file_pairs)

    # Build response with filenames relative to session
    response_results = []
    total_original = 0
    total_converted = 0
    for r in results:
        total_original += r['original_size_kb']
        total_converted += r['converted_size_kb']
        response_results.append({
            'name': Path(r['input_path']).name,
            'output_name': Path(r['output_path']).name,
            'original_size_kb': r['original_size_kb'],
            'converted_size_kb': r['converted_size_kb'],
            'reduction_pct': r['reduction_pct'],
            'original_dimensions': r['original_dimensions'],
            'final_dimensions': r['final_dimensions'],
            'method_used': r['method_used'],
            'success': r['success'],
            'error': r['error'],
        })

    return jsonify({
        'session_id': session_id,
        'results': response_results,
        'total_original_kb': round(total_original, 2),
        'total_converted_kb': round(total_converted, 2),
        'total_reduction_pct': round(
            (total_original - total_converted) / total_original * 100, 2
        ) if total_original > 0 else 0,
    })


@api.route('/api/preview/<session_id>/<filename>')
def preview(session_id, filename):
    """Serve an original uploaded file."""
    upload_dir = session_upload_dir(session_id)
    fpath = upload_dir / filename
    if not fpath.is_file():
        # Try conversions dir
        conv_dir = session_conversion_dir(session_id)
        fpath = conv_dir / filename
        if not fpath.is_file():
            return jsonify({'error': 'File not found'}), 404
    return send_file(str(fpath))


@api.route('/api/download/<session_id>/<filename>')
def download(session_id, filename):
    conv_dir = session_conversion_dir(session_id)
    fpath = conv_dir / filename
    if not fpath.is_file():
        return jsonify({'error': 'File not found'}), 404
    return send_file(str(fpath), as_attachment=True, download_name=filename)


@api.route('/api/download-zip/<session_id>')
def download_zip(session_id):
    conv_dir = session_conversion_dir(session_id)
    if not conv_dir.exists() or not any(conv_dir.iterdir()):
        return jsonify({'error': 'No converted files'}), 404

    buf = create_zip_in_memory(conv_dir)
    return send_file(buf, mimetype='application/zip', as_attachment=True,
                     download_name=f'converted_{session_id[:8]}.zip')
