"""Batch Processing with RAXE

Process large volumes of prompts efficiently with parallel scanning.

Run:
    python batch_scan.py input.csv output.csv
"""
import csv
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict
from dataclasses import dataclass
from tqdm import tqdm
from raxe import Raxe

@dataclass
class ScanTask:
    """Scan task for batch processing."""
    id: str
    text: str
    metadata: Dict = None

@dataclass
class ScanResult:
    """Batch scan result."""
    id: str
    text: str
    has_threats: bool
    severity: str
    detections_count: int
    scan_time_ms: float
    metadata: Dict = None

def batch_scan(tasks: List[ScanTask], max_workers: int = 10) -> List[ScanResult]:
    """Scan multiple texts in parallel.

    Args:
        tasks: List of scan tasks
        max_workers: Number of parallel workers

    Returns:
        List of scan results
    """
    raxe = Raxe(telemetry=True)
    results = []

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_task = {
            executor.submit(raxe.scan, task.text): task
            for task in tasks
        }

        # Collect results with progress bar
        with tqdm(total=len(tasks), desc="Scanning") as pbar:
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    scan_result = future.result()
                    results.append(ScanResult(
                        id=task.id,
                        text=task.text,
                        has_threats=scan_result.has_threats,
                        severity=scan_result.severity if scan_result.has_threats else "NONE",
                        detections_count=len(scan_result.scan_result.l1_result.detections),
                        scan_time_ms=scan_result.duration_ms,
                        metadata=task.metadata
                    ))
                except Exception as e:
                    print(f"Error scanning {task.id}: {e}")

                pbar.update(1)

    return results

def process_csv(input_path: Path, output_path: Path, text_column: str = "text"):
    """Process CSV file with batch scanning.

    Args:
        input_path: Input CSV file
        output_path: Output CSV file with results
        text_column: Column name containing text to scan
    """
    # Read input CSV
    tasks = []
    with open(input_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for i, row in enumerate(reader):
            if text_column not in row:
                print(f"Warning: Column '{text_column}' not found in row {i}")
                continue

            tasks.append(ScanTask(
                id=row.get('id', str(i)),
                text=row[text_column],
                metadata=row
            ))

    print(f"Loaded {len(tasks)} tasks from {input_path}")

    # Scan in batches
    results = batch_scan(tasks, max_workers=10)

    # Write results
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        fieldnames = ['id', 'text', 'has_threats', 'severity', 'detections_count', 'scan_time_ms']

        # Add original metadata columns
        if results and results[0].metadata:
            fieldnames.extend([k for k in results[0].metadata.keys() if k not in fieldnames])

        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for result in results:
            row = {
                'id': result.id,
                'text': result.text,
                'has_threats': result.has_threats,
                'severity': result.severity,
                'detections_count': result.detections_count,
                'scan_time_ms': round(result.scan_time_ms, 2)
            }

            # Add metadata
            if result.metadata:
                row.update(result.metadata)

            writer.writerow(row)

    print(f"Results written to {output_path}")

    # Summary statistics
    total = len(results)
    threats = sum(1 for r in results if r.has_threats)
    avg_time = sum(r.scan_time_ms for r in results) / total if total > 0 else 0

    print("\n=== Summary ===")
    print(f"Total scanned: {total}")
    print(f"Threats detected: {threats} ({threats/total*100:.1f}%)")
    print(f"Average scan time: {avg_time:.2f}ms")

    # Severity breakdown
    severity_counts = {}
    for r in results:
        if r.has_threats:
            severity_counts[r.severity] = severity_counts.get(r.severity, 0) + 1

    if severity_counts:
        print("\nSeverity breakdown:")
        for severity, count in sorted(severity_counts.items()):
            print(f"  {severity}: {count}")

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python batch_scan.py <input.csv> <output.csv> [text_column]")
        print("\nExample:")
        print("  python batch_scan.py prompts.csv results.csv")
        print("  python batch_scan.py data.csv output.csv message")
        sys.exit(1)

    input_file = Path(sys.argv[1])
    output_file = Path(sys.argv[2])
    text_col = sys.argv[3] if len(sys.argv) > 3 else "text"

    if not input_file.exists():
        print(f"Error: Input file '{input_file}' not found")
        sys.exit(1)

    process_csv(input_file, output_file, text_col)
