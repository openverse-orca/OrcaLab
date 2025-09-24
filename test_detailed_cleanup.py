#!/usr/bin/env python3
"""
Detailed test to see what's happening during cleanup.
"""

import subprocess
import time
import psutil
import sys
import os
import signal

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

def test_detailed_cleanup():
    """Detailed test with output capture"""
    print("=== Detailed OrcaLab Cleanup Test ===")
    print()
    
    # Clean up any existing processes
    print("1. Cleaning up existing processes...")
    existing_processes = find_orca_processes()
    for proc in existing_processes:
        try:
            print(f"   Killing existing process PID {proc.pid}")
            proc.kill()
            proc.wait(timeout=5)
        except Exception as e:
            print(f"   Error: {e}")
    
    time.sleep(2)
    
    # Start OrcaLab with output capture
    print("2. Starting OrcaLab with output capture...")
    project_dir = os.path.dirname(os.path.abspath(__file__))
    
    process = subprocess.Popen(
        [sys.executable, "run.py"],
        cwd=project_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    print(f"   Started OrcaLab with PID {process.pid}")
    
    # Wait for startup
    print("3. Waiting for startup...")
    time.sleep(10)
    
    # Check for OrcaStudio processes
    orca_processes = find_orca_processes()
    print(f"   Found {len(orca_processes)} OrcaStudio processes")
    for proc in orca_processes:
        print(f"   - PID {proc.pid}: {proc.info['name']}")
    
    # Send SIGTERM to OrcaLab
    print("4. Sending SIGTERM to OrcaLab...")
    process.terminate()
    
    # Read output while waiting
    print("5. Reading output during shutdown...")
    try:
        output_lines = []
        start_time = time.time()
        while time.time() - start_time < 15:  # 15 second timeout
            try:
                line = process.stdout.readline()
                if line:
                    output_lines.append(line.strip())
                    # Look for cleanup-related messages
                    if any(keyword in line.lower() for keyword in ['cleanup', 'terminate', 'kill', 'orca']):
                        print(f"   CLEANUP OUTPUT: {line.strip()}")
                elif process.poll() is not None:
                    break
                else:
                    time.sleep(0.1)
            except:
                break
        
        # Read any remaining output
        remaining_output = process.stdout.read()
        if remaining_output:
            for line in remaining_output.split('\n'):
                if line.strip():
                    if any(keyword in line.lower() for keyword in ['cleanup', 'terminate', 'kill', 'orca']):
                        print(f"   CLEANUP OUTPUT: {line.strip()}")
                    output_lines.append(line.strip())
    
    except Exception as e:
        print(f"   Error reading output: {e}")
    
    # Wait for process to finish
    try:
        process.wait(timeout=5)
        print("   OrcaLab terminated")
    except subprocess.TimeoutExpired:
        print("   OrcaLab did not terminate, force killing...")
        process.kill()
        process.wait()
    
    # Check final state
    print("6. Checking final state...")
    final_processes = find_orca_processes()
    print(f"   Found {len(final_processes)} OrcaStudio processes after cleanup")
    for proc in final_processes:
        print(f"   - PID {proc.pid}: {proc.info['name']}")
    
    # Clean up any remaining processes
    if final_processes:
        print("7. Cleaning up remaining processes...")
        for proc in final_processes:
            try:
                print(f"   Killing remaining process PID {proc.pid}")
                proc.kill()
                proc.wait(timeout=5)
            except Exception as e:
                print(f"   Error: {e}")
    
    print("\n=== Test Complete ===")
    return True

if __name__ == "__main__":
    test_detailed_cleanup()
