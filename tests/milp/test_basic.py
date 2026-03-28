import subprocess
import os


def test_symphony():
    # Check if file exists and is executable
    symphony_path = '/usr/local/bin/symphony'
    assert os.path.exists(symphony_path), \
        f"{symphony_path} does not exist"
    assert os.access(symphony_path, os.X_OK), \
        f"{symphony_path} is not executable"
    res = subprocess.run([symphony_path, '-h'], capture_output=True,
                            text=True)
    assert res.returncode == 0, f"symphony -h failed {res.returncode}"
    assert len(res.stdout) > 0, "symphony -h produced no output"