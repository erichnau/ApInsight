"""Project-scoped ApPPD cache. No permanent writes until save_project_with_ap_ppd()."""
import json
import os
from pathlib import Path
import re
import tempfile
import uuid
import numpy as np

VERSION = 1
KEY = 'ap_ppd_section_cache'
_REGISTRY = {}

def project_key(path):
    return os.path.normcase(os.path.abspath(path)) if path else None

def section_vertices(info):
    vertices = info.get('vertices') if info.get('type') == 'polyline' else [info.get('start'), info.get('end')]
    a = np.asarray(vertices, dtype=float)
    if a.ndim != 2 or a.shape[0] < 2 or a.shape[1] != 2 or not np.isfinite(a).all():
        raise ValueError('A section needs at least two finite XY vertices.')
    if np.sum(np.linalg.norm(np.diff(a, axis=0), axis=1)) <= 0:
        raise ValueError('Section length must be positive.')
    return a.tolist()

def source_signature(folder):
    if not folder or not Path(folder).is_dir():
        return None
    paths = sorted(p for p in Path(folder).iterdir() if p.suffix.lower() in ('.ap_ppd', '.apppd') or p.name == 'ap_ppd_trace_index.npy')
    return [[p.name, p.stat().st_size, p.stat().st_mtime_ns] for p in paths]

def viewer_arrays(result):
    arrays = {k: np.array(result[k], copy=True) for k in ('final_section', 'distance', 'sample_interval_ns')}
    for k in ('surface_elevation', 'surface_elevation_spread'):
        if k in result and result[k] is not None:
            arrays[k] = np.array(result[k], copy=True)
    a, x = arrays['final_section'], arrays['distance']
    dt = float(arrays['sample_interval_ns'])
    if any(v.dtype.hasobject for v in arrays.values()) or a.ndim != 2 or x.ndim != 1 or a.shape[1] != len(x) or len(x) < 2 or not np.isfinite(x).all() or not np.all(np.diff(x) > 0) or not np.isfinite(dt) or dt <= 0:
        raise ValueError('Invalid cached section dimensions, distances, or sample interval.')
    for k in ('surface_elevation', 'surface_elevation_spread'):
        if k in arrays and arrays[k].shape != x.shape:
            raise ValueError('Cached heights must match section distances.')
    return arrays

class SectionCache:
    def __init__(self):
        self.project = None
        self.entries = {}
        self.pending = {}

    def bind(self, project):
        key = project_key(project)
        if key == self.project:
            return
        self.project = key
        self.entries, self.pending = {}, {}
        if key:
            if Path(key).is_file():
                with open(key, encoding='utf-8') as f:
                    self.entries = json.load(f).get(KEY, {})
            _REGISTRY[key] = self

    def put(self, name, vertices, result, folder, recipe):
        self.pending[name] = (viewer_arrays(result), dict(version=VERSION, vertices=vertices,
            source_folder=os.path.abspath(folder), source_signature=source_signature(folder), recipe=recipe))

    def get(self, name, vertices, recipe):
        item = self.pending.get(name)
        meta = item[1] if item else self.entries.get(name)
        if not meta or meta.get('version') != VERSION or meta.get('vertices') != vertices or meta.get('recipe') != recipe:
            return None
        current = source_signature(meta.get('source_folder'))
        # Offline source folders are allowed: the saved data are self-contained.
        if current is not None and current != meta.get('source_signature'):
            return None
        if item:
            return viewer_arrays(item[0])
        path = (Path(self.project).parent / meta['file']).resolve()
        with np.load(path, allow_pickle=False) as f:
            return viewer_arrays(f)

    def prepare(self, target, sections):
        """Write immutable cache generations; project JSON is committed last."""
        target = Path(target).resolve()
        entries = {}
        folder = target.parent / (target.stem + '_ap_ppd_sections')
        for name, info in sections.items():
            try:
                vertices = section_vertices(info)
            except (TypeError, ValueError):
                continue
            item = self.pending.get(name)
            meta = item[1] if item else self.entries.get(name)
            if not meta or meta.get('vertices') != vertices:
                continue
            # Preserve an existing saved snapshot even if its sources are offline/changed.
            if item:
                arrays = item[0]
            else:
                with np.load(Path(self.project).parent / meta['file'], allow_pickle=False) as f:
                    arrays = viewer_arrays(f)
            folder.mkdir(parents=True, exist_ok=True)
            safe = re.sub(r'[^\w.-]+', '_', name).strip('._')[:80] or 'section'
            filename = safe + '_' + uuid.uuid4().hex + '.npz'
            path = folder / filename
            with open(path, 'xb') as f:
                np.savez_compressed(f, **arrays)
            entries[name] = dict(meta, file=os.path.relpath(path, target.parent))
        return entries


def save_project_with_ap_ppd(path, data, *, cache=None, source_project=None, persist=True):
    """Replace json.dump at project-save sites. Call AFTER Save As is accepted.

    data is the normal serializable project dictionary (including saved sections).
    Pass cache=right_frame.ap_ppd_cache from the main menu save handler.
    persist=False preserves existing manifests for unrelated project-editor writes.
    """
    target = Path(path).resolve()
    source = project_key(source_project or path)
    cache = cache or _REGISTRY.get(source)
    output = dict(data)
    if cache is None:
        cache = SectionCache()
        cache.bind(source)
    if persist:
        output[KEY] = cache.prepare(target, output.get('sections', {}))
    else:
        output[KEY] = dict(cache.entries)
    fd, temporary = tempfile.mkstemp(prefix=target.name + '.', suffix='.tmp', dir=target.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=4)
            f.flush()
            os.fsync(f.fileno())
        os.replace(temporary, target)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    if persist:
        old = cache.project
        if old and _REGISTRY.get(old) is cache:
            del _REGISTRY[old]
        cache.project = project_key(target)
        cache.entries = output[KEY]
        cache.pending = {}
        _REGISTRY[cache.project] = cache
    return str(target)
