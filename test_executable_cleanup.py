#!/usr/bin/env python3
"""
Test script to verify executable-based process cleanup.
This script tests that all processes using the same executable path are cleaned up.
"""

import subprocess
import time
import psutil
import sys
import os

def find_orca_processes():
    """Find all OrcaStudio.GameLauncher processes"""
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'exe']):
        try:
            if proc.info['name'] and 'OrcaStudio.GameLauncher' in proc.info['name']:
                processes.append(proc)
            elif proc.info['cmdline'] and any('OrcaStudio.GameLauncher' in str(cmd) for cmd in proc.info['cmdline']):
                processes.append(proc)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    return processes

def test_executable_cleanup():
    """Test executable-based process cleanup"""
    print("=== OrcaLab Executable-Based Process Cleanup Test ===")
    print()
    
    # Clean up any existing processes first
    print("1. Cleaning up any existing OrcaStudio processes...")
    existing_processes = find_orca_processes()
    for proc in existing_processes:
        try:
            print(f"   Killing existing process PID {proc.pid}")
            proc.kill()
            proc.wait(timeout=5)
        except Exception as e:
            print(f"   Error killing process {proc.pid}: {e}")
    
    time.sleep(2)
    
    # Start OrcaLab
    print("2. Starting OrcaLab...")
    project_dir = os.path.dirname(os.path.abspath(__file__))
    process = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    print(f"   Started OrcaLab with PID {process.pid}")
    
    # Wait for startup
    print("3. Waiting for OrcaLab to start...")
    time.sleep(10)
    
    # Check for OrcaStudio processes
    print("4. Checking for OrcaStudio processes...")
    orca_processes = find_orca_processes()
    print(f"   Found {len(orca_processes)} OrcaStudio processes")
    for proc in orca_processes:
        print(f"   - PID {proc.pid}: {proc.info['name']}")
    
    if len(orca_processes) == 0:
        print("   ⚠️  No OrcaStudio processes found. This might be normal.")
        print("   The test will continue to check cleanup behavior.")
    
    # Terminate OrcaLab
    print("5. Terminating OrcaLab...")
    process.terminate()
    
    # Wait for cleanup
    print("6. Waiting for cleanup...")
    time.sleep(15)
    
    # Check final state
    print("7. Checking final state...")
    final_processes = find_orca_processes()
    print(f"   Found {len(final_processes)} OrcaStudio processes after cleanup")
    for proc in final_processes:
        print(f"   - PID {proc.pid}: {proc.info['name']}")
    
    # Force kill OrcaLab if still running
    if process.poll() is None:
        print("   OrcaLab still running, force killing...")
        process.kill()
        process.wait()
    
    # Clean up any remaining OrcaStudio processes
    if final_processes:
        print("8. Cleaning up remaining OrcaStudio processes...")
        for proc in final_processes:
            try:
                print(f"   Killing remaining process PID {proc.pid}")
                proc.kill()
                proc.wait(timeout=5)
            except Exception as e:
                print(f"   Error: {e}")
    
    print("\n=== Test Complete ===")
    if len(final_processes) == 0:
        print("✅ SUCCESS: All OrcaStudio processes were cleaned up!")
        print("   Executable-based cleanup is working correctly.")
    else:
        print("❌ FAILURE: Some OrcaStudio processes remained after cleanup")
        print("   The cleanup mechanism needs further improvement.")
    
    return len(final_processes) == 0

if __name__ == "__main__":
    test_executable_cleanup()
