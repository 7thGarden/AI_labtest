import subprocess


def run(command):

    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    return {
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }