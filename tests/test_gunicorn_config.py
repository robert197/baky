import importlib.util


def _load_gunicorn_config():
    spec = importlib.util.spec_from_file_location("gunicorn_conf", "gunicorn.conf.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_gunicorn_config_is_importable():
    """gunicorn.conf.py must be valid Python with required attributes."""
    mod = _load_gunicorn_config()
    assert hasattr(mod, "bind")
    assert hasattr(mod, "workers")
    assert hasattr(mod, "max_requests")


def test_gunicorn_worker_tmp_dir():
    mod = _load_gunicorn_config()
    assert mod.worker_tmp_dir == "/dev/shm"


def test_gunicorn_max_requests_set():
    mod = _load_gunicorn_config()
    assert mod.max_requests > 0
    assert mod.max_requests_jitter > 0


def test_gunicorn_binds_to_port_8000():
    mod = _load_gunicorn_config()
    assert "8000" in mod.bind


def test_gunicorn_logs_to_stdout():
    mod = _load_gunicorn_config()
    assert mod.accesslog == "-"
    assert mod.errorlog == "-"
