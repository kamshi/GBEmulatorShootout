import os
import time
import json
import argparse
import traceback
import queue
import concurrent.futures
import multiprocessing
from importlib import import_module

import testroms.blargg
import testroms.mooneye
import testroms.acid
import testroms.samesuite
import testroms.ax6
import testroms.daid
import testroms.ashiepaws
import testroms.cpp
import testroms.mealybug
from test import *
from emulators.kami_gb_rest import KamiGBRest

# Gather all tests
all_tests = testroms.acid.all + testroms.blargg.all + testroms.daid.all + testroms.ax6.all + testroms.mooneye.all + testroms.samesuite.all + testroms.ashiepaws.all + testroms.cpp.all + testroms.mealybug.all

def checkFilter(input_val, filter_data):
    if filter_data is None:
        return True
    input_str = str(input_val)

    out_filter = False
    for f in filter_data:
        if f.startswith("!"):
            out_filter = True
            if f[1:] in input_str:
                return False
    if out_filter:
        return True

    for f in filter_data:
        if not f.startswith("!"):
            if f in input_str:
                return True
    return False

def run_single_test(test, port_queue):
    port = port_queue.get()
    try:
        emu = KamiGBRest(port=port)
        emu.setup()
        result = emu.run(test)
        return test, result
    except Exception as e:
        print(f"Error running {test} on port {port}: {e}")
        traceback.print_exc()
        return test, None
    finally:
        port_queue.put(port)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--test', action='append', help="Filter for tests with keywords")
    parser.add_argument('--model', action='append', help="Filter for tests of given model")
    parser.add_argument('--workers', type=int, default=multiprocessing.cpu_count(), help="Number of parallel workers (defaults to CPU count)")
    parser.add_argument('--base-port', type=int, default=8080, help="Starting port for API")
    parser.add_argument('--output', default='kami-gb-rest.json', help="Output JSON file")
    args = parser.parse_args()

    for model in args.model or []:
        if model not in ["DMG", "CGB", "SGB"]:
            print(f"Model {model} is invalid. Only DMG, CGB and SGB are valid models")
            exit(1)

    filtered_tests = [
        test
        for test in all_tests
        if checkFilter(test, args.test) and checkFilter(test.model, args.model)
    ]

    print(f"Running {len(filtered_tests)} tests with {args.workers} workers...")

    port_queue = queue.Queue()
    for i in range(args.workers):
        port_queue.put(args.base_port + i)

    results = {}
    
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as executor:
        future_to_test = {executor.submit(run_single_test, test, port_queue): test for test in filtered_tests}
        for future in concurrent.futures.as_completed(future_to_test):
            test, result = future.result()
            if result:
                results[str(test)] = {
                    'result': result.result,
                    'startuptime': result.startuptime,
                    'runtime': result.runtime,
                    'screenshot': result.screenshot
                }

    # Save results in the shootout format
    data = {
        'emulator': "kami-gb-rest",
        'date': time.time(),
        'tests': results,
    }
    
    with open(args.output, "wt") as f:
        json.dump(data, f, indent="  ")
    
    passed = len([r for r in results.values() if r['result'] != 'FAIL'])
    print(f"Finished. Results saved to {args.output}")
    print(f"Passed: {passed}/{len(results)}")

if __name__ == "__main__":
    main()
