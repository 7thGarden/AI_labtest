import subprocess


def run_command(command: list[str]) -> dict:
    try:
        process = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=30,
        )

        return {
            "success": process.returncode == 0,
            "returncode": process.returncode,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
        }

    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
        }