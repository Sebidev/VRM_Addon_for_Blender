import contextlib
import os
import subprocess
import sys
import tempfile
from typing import Optional
from unittest import TestCase


class BaseBlenderTestCase(TestCase):
    def __init__(self, *args: str, **kwargs: str) -> None:
        # https://stackoverflow.com/a/19102520
        super().__init__(*args, **kwargs)

        if sys.platform == "win32":
            self.exeext = ".exe"
        else:
            self.exeext = ""

        self.repository_root_dir = os.path.dirname(
            os.path.dirname(os.path.realpath(__file__))
        )
        repository_addon_dir = os.path.join(self.repository_root_dir, "io_scene_vrm")
        self.user_scripts_dir = tempfile.mkdtemp(prefix="blender_vrm_")
        os.mkdir(os.path.join(self.user_scripts_dir, "addons"))
        self.addons_pythonpath = os.path.join(self.user_scripts_dir, "addons")
        addon_dir = os.path.join(self.addons_pythonpath, "io_scene_vrm")
        if sys.platform == "win32":
            import _winapi

            _winapi.CreateJunction(repository_addon_dir, addon_dir)
        else:
            os.symlink(repository_addon_dir, addon_dir)

        command = [self.find_blender_command(), "--version"]
        completed_process = subprocess.run(
            command,
            check=False,
            capture_output=True,
        )
        stdout_str = self.process_output_to_str(completed_process.stdout)
        stderr_str = self.process_output_to_str(completed_process.stderr)
        output = (
            "\n  ".join(command)
            + "\n===== stdout =====\n"
            + stdout_str
            + "===== stderr =====\n"
            + stderr_str
            + "=================="
        )
        if completed_process.returncode != 0:
            raise RuntimeError("Failed to execute command:\n" + output)

        for line in stdout_str.splitlines():
            if not line.startswith("Blender"):
                continue
            self.major_minor = ".".join(line.split(" ")[1].split(".")[:2])
            return

        raise RuntimeError(f"Failed to detect Blender Version:\n---\n{stdout_str}\n---")

    @staticmethod
    def process_output_to_str(process_output: Optional[bytes]) -> str:
        if process_output is None:
            return ""
        output = ""
        for line_bytes in process_output.splitlines():
            line = None
            if sys.platform == "win32":
                with contextlib.suppress(UnicodeDecodeError):
                    line = line_bytes.decode("ansi")
            if line is None:
                line = line_bytes.decode()
            output += str.rstrip(line) + "\n"
        return output

    def find_blender_command(self) -> str:
        try:
            import bpy

            bpy_binary_path = str(bpy.app.binary_path)
            if bpy_binary_path and os.path.exists(bpy_binary_path):
                return bpy_binary_path
        except ImportError:
            pass
        env = os.environ.get("BLENDER_VRM_TEST_BLENDER_PATH")
        if env:
            return env
        if sys.platform == "win32":
            completed_process = subprocess.run(
                "where blender", shell=True, capture_output=True, check=False
            )
            if completed_process.returncode == 0:
                return self.process_output_to_str(
                    completed_process.stdout
                ).splitlines()[0]
        if os.name == "posix":
            completed_process = subprocess.run(
                "which blender", shell=True, capture_output=True, check=False
            )
            if completed_process.returncode == 0:
                return self.process_output_to_str(
                    completed_process.stdout
                ).splitlines()[0]
        if sys.platform == "darwin":
            default_path = "/Applications/Blender.app/Contents/MacOS/Blender"
            if os.path.exists(default_path):
                return default_path
        raise RuntimeError(
            "Failed to discover blender executable. "
            + "Please set blender executable location to "
            + 'environment variable "BLENDER_VRM_TEST_BLENDER_PATH"'
        )

    def run_script(self, script: str, *args: str) -> None:
        env = os.environ.copy()
        env["BLENDER_USER_SCRIPTS"] = self.user_scripts_dir
        env["BLENDER_VRM_AUTOMATIC_LICENSE_CONFIRMATION"] = "true"
        env["BLENDER_VRM_BLENDER_MAJOR_MINOR_VERSION"] = self.major_minor
        pythonpath = env.get("PYTHONPATH", "")
        if pythonpath:
            pythonpath += os.pathsep
        pythonpath += self.addons_pythonpath
        env["PYTHONPATH"] = pythonpath

        error_exit_code = 1
        command = [
            self.find_blender_command(),
            "-noaudio",
            "--factory-startup",
            "--addons",
            "io_scene_vrm",
            "--python-exit-code",
            str(error_exit_code),
            "--background",
            "--python-expr",
            "import bpy; bpy.ops.preferences.addon_enable(module='io_scene_vrm')",
            "--python",
            os.path.join(self.repository_root_dir, "tests", script),
            "--",
            *args,
        ]

        if self.major_minor == "2.83" and sys.platform == "darwin":
            retry = 3
        else:
            retry = 1

        for _ in range(retry):
            completed_process = subprocess.run(
                command,
                check=False,
                capture_output=True,
                cwd=self.repository_root_dir,
                env=env,
            )
            if completed_process.returncode not in [0, error_exit_code]:
                continue

            stdout_str = self.process_output_to_str(completed_process.stdout)
            stderr_str = self.process_output_to_str(completed_process.stderr)
            output = (
                "\n  ".join(command)
                + "\n===== stdout =====\n"
                + stdout_str
                + "===== stderr =====\n"
                + stderr_str
                + "=================="
            )
            self.assertEqual(
                completed_process.returncode,
                0,
                "Failed to execute command:\n" + output,
            )
