"""Windows-only subprocess entry point: enroll in a job before creating child processes."""

import subprocess
import sys

from windows_job import WindowsJob


def main():
    job = WindowsJob()
    result = subprocess.run(sys.argv[1:], check=False)
    # Retain ownership through normal exit; the OS closes the job on both exit and termination.
    assert job.handle
    raise SystemExit(result.returncode)


if __name__ == "__main__":
    main()
