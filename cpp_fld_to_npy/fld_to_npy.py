import os
import subprocess

def process_fld_with_cpp(input_fld, output_npy):
    script_directory = os.path.dirname(os.path.realpath(__file__))

    # Path to C++ executable in the same directory
    executable_path = os.path.join(script_directory, 'fld_to_npy.exe')

    result = subprocess.run([executable_path, input_fld, output_npy], capture_output=True, text=True)

    if result.returncode != 0:
        print("Error:", result.stderr)
        return None

    print(result.stdout)